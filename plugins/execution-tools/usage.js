// Only counters and skill names: no source, query, prompt, model credentials or shell text.
const queues=new WeakMap();
const empty=()=>({tools:{},skills:{},shellSearchFallbacks:0,rtk:{eligible:0,filtered:0,bytesBefore:0,bytesAfter:0}});
export async function readUsage(ctx,id){return await ctx.storage.get('execution-usage:'+id)??empty();}
export async function recordUsage(ctx,id,entry){
 let queue=queues.get(ctx);if(!queue){queue=new Map();queues.set(ctx,queue);}
 const previous=queue.get(id)??Promise.resolve();
 const next=previous.catch(()=>{}).then(async()=>{
  const state=await readUsage(ctx,id);
  if(entry.tool)state.tools[entry.tool]=(state.tools[entry.tool]??0)+1;
  if(entry.skill)state.skills[entry.skill]=(state.skills[entry.skill]??0)+1;
  if(entry.fallback)state.shellSearchFallbacks++;
  if(entry.bytesBefore!==undefined){state.rtk.eligible++;state.rtk.bytesBefore+=entry.bytesBefore;state.rtk.bytesAfter+=entry.bytesAfter;state.rtk.filtered+=Number(!!entry.filtered);}
  await ctx.storage.set('execution-usage:'+id,state);
 });queue.set(id,next);try{await next;}finally{if(queue.get(id)===next)queue.delete(id);}
}
