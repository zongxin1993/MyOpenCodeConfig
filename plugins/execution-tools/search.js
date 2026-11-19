import path from 'node:path';
import {realpath,stat} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {protectedPath,readAuthorizedSources} from './access.js';
import {inspectWorktree} from '../worktree-policy/git-worktree.js';
const roles=new Set(['local-worker','local-build','local-inspect']);
const within=(p,r)=>p===r||p.startsWith(r+path.sep);
const excludes=['.git','.ssh','.aws','.config','.env*','*.pem','*.key','node_modules','.venv','target','dist'];
async function run(bin,args,cwd,input,signal){
 if(signal?.aborted)throw Error('Search cancelled');
 return new Promise((resolve,reject)=>{
  const child=spawn(bin,args,{cwd,stdio:['pipe','pipe','pipe'],env:{...process.env,RIPGREP_CONFIG_PATH:''}});let output=Buffer.alloc(0),error='',failure;
  const stop=reason=>{failure=Error(reason);child.kill('SIGKILL');};
  const timer=setTimeout(()=>stop('Search timeout'),10000);const cancel=()=>stop('Search cancelled');signal?.addEventListener('abort',cancel,{once:true});
  child.on('error',e=>{clearTimeout(timer);signal?.removeEventListener('abort',cancel);reject(e);});
  child.stdout.on('data',b=>{output=Buffer.concat([output,b]);if(output.length>512*1024)stop('Search output limit; narrow paths or query');});
  child.stderr.on('data',b=>{error=(error+b).slice(0,2000);});child.stdin.on('error',()=>{});
  child.on('close',code=>{clearTimeout(timer);signal?.removeEventListener('abort',cancel);if(failure)reject(failure);else if(code===0||code===1)resolve(output.toString('utf8'));else reject(Error('rg failed: '+error));});child.stdin.end(input??'');
 });
}
export async function search(ctx,call,input,bin){
 if(!roles.has(call.agent))throw Error('Execution tool role not allowed');
 const session=await ctx.session.get({sessionID:call.sessionID});const directory=await realpath(session.location.directory);
 if(session.agent!==call.agent||directory!==await realpath(ctx.location.directory))throw Error('Session role/location changed');
 const info=await inspectWorktree(directory);if(!info.isolated)throw Error('Linked worktree required');
 const mode=input.mode??'text',scopes=input.paths??['.'];
 if(!['text','files'].includes(mode)||!Array.isArray(scopes)||scopes.length<1||scopes.length>8)throw Error('Select 1..8 worktree paths');
 if(mode==='text'&&(typeof input.query!=='string'||!input.query||input.query.length>4000))throw Error('Select a text query of 1..4000 characters');
 if(mode==='files'&&input.query!==undefined&&(typeof input.query!=='string'||!input.query||input.query.length>4000||input.query.includes('\0')))throw Error('Invalid filename glob');
 if(input.regex!==undefined&&typeof input.regex!=='boolean')throw Error('regex must be boolean');
 const resources=[],paths=[];
 for(const scope of scopes){
  if(typeof scope!=='string'||!scope||scope.includes('\0'))throw Error('Invalid search path');
  const lexical=path.resolve(directory,scope),target=await realpath(lexical);
  if(!within(lexical,directory)||!within(target,directory))throw Error('Target outside current worktree');
  if(protectedPath(path.relative(directory,lexical))||protectedPath(path.relative(directory,target)))throw Error('Protected search path');
  // Avoid filesystem traversal through aliases, including directories.
  if(target!==lexical)throw Error('Search path aliases are not supported');
  const s=await stat(target);if(!s.isDirectory()&&!s.isFile())throw Error('Unsupported search path');
  resources.push(lexical,path.relative(directory,lexical)||'.');if(s.isDirectory())resources.push(lexical+'/**',(path.relative(directory,lexical)||'.')+'/**');
  paths.push(path.relative(directory,lexical)||'.');
 }
 await ctx.permission.assert({sessionID:call.sessionID,agent:call.agent,action:'read',resources:[...new Set(resources)],save:[],metadata:{purpose:'execution search discovery'},source:{type:'tool',id:call.id,messageID:call.messageID}});
 const current=await ctx.session.get({sessionID:call.sessionID});if(current.agent!==call.agent||await realpath(current.location.directory)!==directory)throw Error('Session changed during permission wait');
 for(let i=0;i<paths.length;i++)if(await realpath(path.resolve(directory,paths[i]))!==path.resolve(directory,paths[i]))throw Error('Search path changed during permission wait');
 const flags=['--no-config','--files','--null','--hidden',...excludes.flatMap(p=>['--glob','!'+p])];
 const listing=await run(bin,[...flags,'--',...paths],directory,null,call.signal);
 const names=text=>[...new Set(text.split('\0').filter(Boolean).map(p=>p.replace(/^\.\//,'')))];
 // Positive rg globs override ignore rules: intersect with the unfiltered, ignore-respecting listing.
 let candidates=names(listing);
 if(mode==='files'&&input.query){
  const selected=new Set(names(await run(bin,['--no-config','--files','--null','--hidden','--glob',input.query,...excludes.flatMap(p=>['--glob','!'+p]),'--',...paths],directory,null,call.signal)));
  candidates=candidates.filter(p=>selected.has(p));
 }
 const all=candidates.filter(p=>!protectedPath(p)).sort();
 const files=all.slice(0,256),limits={fileListing:256,textFiles:64,fileBytes:1048576,totalBytes:8388608,matches:200};
 if(mode==='files')return{files,incomplete:all.length>256,discoveredFiles:all.length,limits};
 let total=0,skipped=0;const selected=[];
 for(const file of all){
  if(selected.length>=64){skipped++;continue;}
  const s=await stat(path.resolve(directory,file));if(s.size>1048576||total+s.size>8388608){skipped++;continue;}
  total+=s.size;selected.push(file);
 }
 const sources=selected.length?await readAuthorizedSources(ctx,call,selected,{maxTotalBytes:8388608}):[];const offsets=[];let lines=0,text='';
 for(const source of sources){const part=source.text.endsWith('\n')?source.text:source.text+'\n';offsets.push({line:lines+1,file:path.relative(directory,source.file)});lines+=part.split('\n').length-1;text+=part;}
 const raw=sources.length?await run(bin,['--no-config','--json',...(input.regex?[]:['--fixed-strings']),'--',input.query],directory,text,call.signal):'';
 const matches=[];let count=0;
 for(const line of raw.split('\n').filter(Boolean)){
  const item=JSON.parse(line);if(item.type!=='match')continue;count++;
  if(matches.length>=200)continue;
  const d=item.data,owner=offsets.findLast(p=>p.line<=d.line_number);const full=d.lines.text??'';
  matches.push({file:owner.file,line:d.line_number-owner.line+1,text:full.replace(/\n$/,'')});
 }
 return{matches,incomplete:skipped>0||count>200,discoveredFiles:all.length,scannedFiles:sources.length,skippedFiles:skipped,totalMatches:count,limits};
}
