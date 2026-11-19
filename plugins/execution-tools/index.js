import {realpath} from 'node:fs/promises';import path from 'node:path';import { homedir } from 'node:os';
import {assertSingleRtk} from './discovery.js';
import {safeFilter,filterOutput} from './rtk.js';import {astSearch} from './ast-search.js';
import {search} from './search.js';
import {recordUsage,readUsage} from './usage.js';
const roles=new Set(['local-worker','local-build','local-inspect']);
export default {id:'myopencodeconfig-execution-tools',async setup(ctx){
 const options=ctx.options;
 for(const name of ['rtk','ast_grep'])if(options[name]?.enabled&&!path.isAbsolute(options.tools?.[name]??''))throw Error('Run pinned execution setup before enabling '+name);
 if(options.search?.enabled&&!path.isAbsolute(options.tools?.rg??''))throw Error('Run execution setup with rg before enabling search');
 await ctx.tool.hook('execute.after',async event=>{
  if(!roles.has(event.agent)||event.status!=='completed')return;
  const entry={tool:event.tool};
  if(event.tool==='skill')entry.skill=event.result?.metadata?.name??event.input?.id;
  if(event.tool==='shell')entry.fallback=/(?:^|[\s;&|/])(grep|find|rg)(?:\s|$)/.test(event.input?.command??'');
  if(options.rtk?.enabled&&event.tool==='shell'){
   const filter=safeFilter(event.input?.command,options.tools?.rg);
   if(filter){const raw=event.result.content?.filter(b=>b.type==='text').map(b=>b.text).join('\n')??'';await filterOutput(options.tools.rtk,filter,event.result,path.join(homedir(),'.local/share/myopencodeconfig/execution-logs'));Object.assign(entry,{bytesBefore:Buffer.byteLength(raw),bytesAfter:Buffer.byteLength(event.result.content?.map(b=>b.text??'').join('\n')??''),filtered:!!event.result.metadata?.rtkOriginal});}
  }
  if(event.result?.metadata?.executionRtk)Object.assign(entry,event.result.metadata.executionRtk);
  try{await recordUsage(ctx,event.sessionID,entry);}catch{/* Optional telemetry must not change task results. */}
 });
 if(options.search?.enabled)await ctx.tool.transform(editor=>{
  editor.add({name:'execution_search',description:'Preferred read-only file discovery and literal text search in current task worktree. Fixed rg, no shell. Choose mode files to locate paths, then text with query and narrow paths. Explicit limits/incomplete flag. RTK display keeps original evidence.',
   input:{type:'object',properties:{mode:{type:'string',enum:['files','text']},query:{type:'string',description:'Text query in text mode; optional filename glob such as *.rs in files mode.',maxLength:4000},paths:{type:'array',items:{type:'string'},minItems:1,maxItems:8},regex:{type:'boolean'}},required:['mode'],additionalProperties:false},options:{codemode:false,permission:'execution_search'},
   async execute(input,call){
    const result=await search(ctx,call,input,options.tools.rg);
    if(input.mode==='files')return{content:JSON.stringify(result)};
    const {matches,...summary}=result;
    const raw=matches.map(m=>m.file+':'+m.line+':'+m.text).join('\n');
    const output={content:[{type:'text',text:raw}],metadata:{truncated:result.incomplete}};
    if(options.rtk?.enabled)await filterOutput(options.tools.rtk,'grep',output,path.join(homedir(),'.local/share/myopencodeconfig/execution-logs'));
    const bytesBefore=Buffer.byteLength(raw),bytesAfter=Buffer.byteLength(output.content[0].text);
    return{content:JSON.stringify(summary)+'\n'+output.content[0].text,metadata:{...output.metadata,executionRtk:{bytesBefore,bytesAfter,filtered:!!output.metadata.rtkOriginal}}};
   }});
  editor.add({name:'execution_status',description:'Actual successful tool/skill counts and RTK display bytes for THIS execution session. Availability is not usage. No source or query contents.',input:{type:'object',properties:{},additionalProperties:false},options:{codemode:false,permission:'execution_status'},
   async execute(_input,call){const session=await ctx.session.get({sessionID:call.sessionID});if(!roles.has(call.agent)||session.agent!==call.agent||await realpath(session.location.directory)!==await realpath(ctx.location.directory))throw Error('Execution role/location changed');return{content:JSON.stringify(await readUsage(ctx,call.sessionID))};}});
 });
 if(options.ast_grep?.enabled)await ctx.tool.transform(editor=>editor.add({
  name:'execution_ast_search',description:'Read-only syntax-pattern search in 1..64 explicit files of current linked worktree. Use rg for plain text. No edits. Zero matches do not prove absence.',
  input:{type:'object',properties:{pattern:{type:'string'},language:{type:'string',enum:['rust','python','typescript','tsx','javascript']},files:{type:'array',items:{type:'string'},minItems:1,maxItems:64}},required:['pattern','language','files'],additionalProperties:false},
  options:{codemode:false,permission:'execution_ast_search'},
  async execute(input,call){return {content:JSON.stringify(await astSearch(ctx,call,input,options.tools?.ast_grep??'ast-grep'))};}
 }));
 await ctx.session.hook('context',async event=>{
  if(options.rtk?.enabled)await assertSingleRtk(ctx.location.directory);
  if(!roles.has(event.agent)){delete event.tools.execution_ast_search;delete event.tools.execution_search;delete event.tools.execution_status;}
  else if(options.search?.enabled)event.system.push({type:'text',text:'EXECUTION ROUTING: Load local-execution skill at task entry. Prefer execution_search for code paths/text; execution_ast_search for syntax. Avoid compound grep/find pipelines. Use shell for builds/tests. On completion call execution_status and report actual tool and skill use. Limited search is incomplete; narrow paths before absence claims.'});
  if(roles.has(event.agent)&&options.tools?.rg)event.system.push({type:'text',text:'SHELL TOOL AVAILABILITY: if using shell rg, use the verified absolute executable '+JSON.stringify(options.tools.rg)+'. Desktop PATH may omit it. Native grep/read remain available; do not retry command-not-found or install packages.'});
 });
}};
