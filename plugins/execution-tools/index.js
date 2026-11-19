import path from 'node:path';import { homedir } from 'node:os';
import {assertSingleRtk} from './discovery.js';
import {safeFilter,filterOutput} from './rtk.js';import {astSearch} from './ast-search.js';
const roles=new Set(['local-worker','local-build','local-inspect']);
export default {id:'myopencodeconfig-execution-tools',async setup(ctx){
 const options=ctx.options;
 for(const name of ['rtk','ast_grep'])if(options[name]?.enabled&&!path.isAbsolute(options.tools?.[name]??''))throw Error('Run pinned execution setup before enabling '+name);
 if(options.rtk?.enabled)await ctx.tool.hook('execute.after',async event=>{
  if(!roles.has(event.agent)||event.tool!=='shell'||event.status!=='completed')return;
  const filter=safeFilter(event.input?.command,options.tools?.rg);if(!filter)return;
  await filterOutput(options.tools?.rtk??'rtk',filter,event.result,path.join(homedir(),'.local/share/myopencodeconfig/execution-logs'));
 });
 if(options.ast_grep?.enabled)await ctx.tool.transform(editor=>editor.add({
  name:'execution_ast_search',description:'Read-only syntax-pattern search in 1..64 explicit files of current linked worktree. Use rg for plain text. No edits. Zero matches do not prove absence.',
  input:{type:'object',properties:{pattern:{type:'string'},language:{type:'string',enum:['rust','python','typescript','tsx','javascript']},files:{type:'array',items:{type:'string'},minItems:1,maxItems:64}},required:['pattern','language','files'],additionalProperties:false},
  options:{codemode:false,permission:'execution_ast_search'},
  async execute(input,call){return {content:JSON.stringify(await astSearch(ctx,call,input,options.tools?.ast_grep??'ast-grep'))};}
 }));
 await ctx.session.hook('context',async event=>{
  if(options.rtk?.enabled)await assertSingleRtk(ctx.location.directory);
  if(!roles.has(event.agent))delete event.tools.execution_ast_search;
  else if(options.tools?.rg)event.system.push({type:'text',text:'SHELL TOOL AVAILABILITY: if using shell rg, use the verified absolute executable '+JSON.stringify(options.tools.rg)+'. Desktop PATH may omit it. Native grep/read remain available; do not retry command-not-found or install packages.'});
 });
}};
