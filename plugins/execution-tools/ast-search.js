import path from 'node:path';
import { spawn } from 'node:child_process';
import { readAuthorizedSources } from './access.js';
function run(bin,args,text,signal){return new Promise((resolve,reject)=>{
 const p=spawn(bin,args,{stdio:['pipe','pipe','pipe'],signal,cwd:path.dirname(bin)});let out='',err='';
 const timer=setTimeout(()=>p.kill('SIGKILL'),10000);
 p.on('error',e=>{clearTimeout(timer);reject(e)});p.stdin.on('error',()=>{});
 p.stdout.on('data',b=>{out+=b;if(out.length>512000)p.kill('SIGKILL')});p.stderr.on('data',b=>{err+=b});
 p.on('close',(code)=>{clearTimeout(timer);if(code===0||code===1&&!err)resolve(out);else reject(Error('ast-grep failed: '+err.slice(0,1500)))});p.stdin.end(text);
});}
export async function astSearch(ctx,call,input,bin){
 if(!['rust','python','typescript','tsx','javascript'].includes(input.language))throw Error('Unsupported structural language');
 if(typeof input.pattern!=='string'||!input.pattern||input.pattern.length>4000)throw Error('Invalid structural pattern');
 const sources=await readAuthorizedSources(ctx,call,input.files);
 // Piped source only: CLI cannot crawl directories, follow symlinks or load project config.
 const matches=[];let truncated=false;
 for(const {file,text} of sources){
  const out=await run(bin,['run','--pattern',input.pattern,'--lang',input.language,'--json=compact','--stdin'],text,call.signal);
  let rows;try{rows=JSON.parse(out||'[]');}catch{throw Error('Invalid ast-grep output');}
  for(const row of rows){
   if(matches.length>=100){truncated=true;break;}
   matches.push({file,line:row.range.start.line+1,column:row.range.start.column+1,text:row.text.slice(0,3000)});
  }
  if(truncated)break;
 }
 return {matches,truncated};
}
