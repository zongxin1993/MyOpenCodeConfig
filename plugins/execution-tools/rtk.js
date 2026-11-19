import { spawn } from 'node:child_process';
import { mkdir,writeFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import path from 'node:path';
export function safeFilter(command,rgBinary){
 if(typeof command!=='string'||/[\n\r;&|<>`$(){}\\]/.test(command))return null;
 // No edit/build/test/source-body/diff commands. Never rewrite command or argv.
 if((/^rg\s/.test(command)||rgBinary&&command.startsWith(rgBinary+' '))&&!/(?:--pre|--search-zip|--files-without-match)/.test(command))return 'grep';
 if(/^git\s+log\s+--oneline(?:\s+(?:-[1-9]\d{0,3}|(?:-n|--max-count)\s+[1-9]\d{0,3}|--max-count=[1-9]\d{0,3}))?\s*$/.test(command))return 'git-log';
 return null;
}
async function pipe(bin,filter,text){
 return new Promise((resolve,reject)=>{
  const p=spawn(bin,['pipe','--filter',filter],{stdio:['pipe','pipe','pipe']});let out='',err='';
  const timer=setTimeout(()=>{p.kill('SIGKILL');reject(Error('RTK timeout'));},1500);
  p.on('error',e=>{clearTimeout(timer);reject(e);});
  p.stdout.on('data',b=>{out+=b;if(out.length>256000)p.kill('SIGKILL');});
  p.stderr.on('data',b=>{err+=b;});p.stdin.on('error',()=>{});
  p.on('close',code=>{clearTimeout(timer);code===0?resolve(out):reject(Error(err.slice(0,200)));});p.stdin.end(text);
 });
}
export async function filterOutput(bin,filter,result,evidence){
 const blocks=result.content;
 if(!Array.isArray(blocks)||blocks.some(b=>b.type!=='text'))return;
 const raw=blocks.map(b=>b.text).join('\n');
 if(filter==='grep'&&!/^[^:\n]+:\d+:/m.test(raw))return;
 if(raw.length<800||raw.length>120000||result.metadata?.truncated)return;
 try{
  const filtered=await pipe(bin,filter,raw);
  if(!filtered.trim()||filtered.length>=raw.length*.9)return;
  await mkdir(evidence,{recursive:true,mode:0o700});
  const file=path.join(evidence,randomUUID()+'.log');await writeFile(file,raw,{mode:0o600,flag:'wx'});
  result.content=[{type:'text',text:filtered+'\n[RTK display only; original output: '+file+']'}];
  result.metadata={...result.metadata,rtkOriginal:file};
 }catch{/* Filtering is optional; retain native result exactly, never rerun command. */}
}
