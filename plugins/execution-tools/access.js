import path from 'node:path';
import { realpath,stat,open } from 'node:fs/promises';
import { constants } from 'node:fs';
import { inspectWorktree } from '../worktree-policy/git-worktree.js';
const roles=new Set(['local-worker','local-build','local-inspect']);
const within=(p,r)=>p===r||p.startsWith(r+path.sep);
export function protectedPath(p){return p.split(path.sep).some(x=>['.git','.ssh','.aws','.config','node_modules','.venv'].includes(x)||x.startsWith('.env')||/\.(pem|key)$/i.test(x));}
export async function authorizeFiles(ctx,call,files){
 if(!roles.has(call.agent))throw Error('Execution tool role not allowed');
 const session=await ctx.session.get({sessionID:call.sessionID});
 if(session.agent!==call.agent)throw Error('Execution role differs from session');
 const directory=await realpath(session.location.directory);
 if(directory!==await realpath(ctx.location.directory))throw Error('Session moved; rebuild tools in current worktree');
 const info=await inspectWorktree(directory);
 if(!info.isolated)throw Error('Linked worktree required');
 if(!Array.isArray(files)||!files.length||files.length>64)throw Error('Select 1..64 explicit source files');
 const targets=[],resources=[];
 for(const input of files){
  if(typeof input!=='string'||!input)throw Error('Invalid source file');
  const lexical=path.resolve(directory,input),target=await realpath(lexical);
  if(!within(lexical,info.directory)||!within(target,info.directory))throw Error('Target outside current worktree');
  if(protectedPath(path.relative(info.directory,lexical))||protectedPath(path.relative(info.directory,target)))throw Error('protected source target');
  const s=await stat(target);if(!s.isFile()||s.size>1024*1024)throw Error('Select text source files below 1MiB');
  targets.push(target);resources.push(path.relative(directory,lexical),path.relative(directory,target),lexical,target);
 }
 await ctx.permission.assert({sessionID:call.sessionID,agent:call.agent,action:'read',resources:[...new Set(resources)],save:[],metadata:{purpose:'execution structural search'},source:{type:'tool',id:call.id,messageID:call.messageID}});
 return [...new Set(targets)];
}


export async function readAuthorizedSources(ctx,call,files){
 if(!Array.isArray(files)||!files.length||files.length>64)throw Error('Select 1..64 explicit source files');
 if(!roles.has(call.agent))throw Error('Execution tool role not allowed');
 const session=await ctx.session.get({sessionID:call.sessionID});
 const directory=await realpath(session.location.directory);
 if(session.agent!==call.agent||directory!==await realpath(ctx.location.directory))throw Error('Session role/location changed');
 const info=await inspectWorktree(directory);if(!info.isolated)throw Error('Linked worktree required');
 const handles=[],seen=new Set();
 try{
  // Fix file identity before an approval can yield to other filesystem writers.
  for(const input of files){
   const lexical=path.resolve(directory,input),target=await realpath(lexical);
   if(!within(lexical,info.directory)||!within(target,info.directory))throw Error('Target outside current worktree');
   if(protectedPath(path.relative(info.directory,lexical))||protectedPath(path.relative(info.directory,target)))throw Error('protected source target');
   if(seen.has(target))throw Error('Duplicate source target');seen.add(target);
   const before=await stat(target);if(!before.isFile()||before.size>1024*1024||before.nlink>1)throw Error('Unsupported source file identity');
   const handle=await open(target,constants.O_RDONLY|constants.O_NOFOLLOW);handles.push({handle,target});
   const st=await handle.stat();if(!st.isFile()||st.dev!==before.dev||st.ino!==before.ino||st.size>1024*1024||st.nlink>1)throw Error('Unsupported source file identity');
  }
  const targets=await authorizeFiles(ctx,call,files),out=[];
  const currentSession=await ctx.session.get({sessionID:call.sessionID});
  if(currentSession.agent!==call.agent||await realpath(currentSession.location.directory)!==directory)throw Error('Session changed during permission wait');
  for(let i=0;i<targets.length;i++){
   const item=handles[i],current=await realpath(path.resolve(ctx.location.directory,files[i]));
   if(current!==item.target)throw Error('Source changed during permission wait');
   const actual=await stat(current),opened=await item.handle.stat();
   if(actual.dev!==opened.dev||actual.ino!==opened.ino)throw Error('Source identity changed during permission wait');
   const text=await item.handle.readFile('utf8');if(text.includes('\0')||Buffer.byteLength(text)>1024*1024)throw Error('Invalid text source');
   out.push({file:item.target,text});
  }
  return out;
 }finally{for(const {handle} of handles)await handle.close();}
}
