import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import plugin from '../plugins/cloud-session-router/index.js';

async function fixture() {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'worker-continuity-'));
  const sessions = new Map(); const stored = new Map();
  const root = {id:'root', projectID:'project', agent:'cloud-workflow', location:{directory}, model:{providerID:'cloud',id:'selected',variant:'low'}};
  sessions.set(root.id, root);
  function worker(id='worker', changes={}) { const s={id,parentID:'root',projectID:'project',agent:'local-worker',location:{directory},model:{providerID:'local',id:'fixed'},...changes};sessions.set(id,s);return s; }
  let pages;
  async function boot() {
    const hooks={};
    const ctx={ options:{cloudRoles:['cloud-workflow','cloud-review'],localBindings:{'local-worker':'local/fixed','local-build':'local/fixed'}},
      storage:{get:async key=>structuredClone(stored.get(key)),set:async(key,value)=>stored.set(key,structuredClone(value))},
      session:{ get:async({sessionID})=>{if(!sessions.has(sessionID))throw Error('not found');return sessions.get(sessionID);},
        list:async input=>pages ? pages(input) : {data:[...sessions.values()].filter(s=>s.parentID===input.parentID),cursor:{}},
        hook:async(name,fn)=>hooks[name]=fn},
      tool:{hook:async(name,fn)=>hooks[name]=fn}};
    await plugin.setup(ctx);return hooks;
  }
  const event=(input={})=>({tool:'subagent',sessionID:'root',agent:'cloud-workflow',id:'dispatch',messageID:'message',input:{agent:'local-worker',prompt:'Approved implementation',...input}});
  const completed=(e,id)=>({...e,status:'completed',result:{content:[{type:'text',text:'background'}],metadata:{sessionID:id,status:'running'}}});
  return {sessions,stored,worker,boot,event,completed,root,directory,setPages(fn){pages=fn;},cleanup:()=>rm(directory,{recursive:true,force:true})};
}

test('dispatch receipt survives plugin restart; an ID-free repair resumes original worker with fixed local model',async()=>{
 const f=await fixture();try {
  let hooks=await f.boot();const e=f.event();await hooks['execute.before'](e);assert.equal(e.input.sessionID,undefined);
  f.worker();await hooks['execute.after'](f.completed(e,'worker'));
  hooks=await f.boot();const repair=f.event({prompt:'Repair review finding',model:'cloud/selected#low'});
  await hooks['execute.before'](repair);assert.equal(repair.input.sessionID,'worker');assert.equal(repair.input.model,'local/fixed');
  const request={sessionID:'root',agent:'cloud-workflow',model:f.root.model,system:[]};await hooks.context(request);
  assert.match(request.system.map(p=>p.text).join('\n'),/worker/);
  const record=[...f.stored.values()][0];assert.equal(record.worker.sessionID,'worker');
  assert.equal(JSON.stringify(record).includes('Approved implementation'),false);
 } finally {await f.cleanup();}
});

test('legacy worker recovery exhausts pagination instead of picking first page or most recent child',async()=>{
 const f=await fixture();try{
  const old=f.worker();f.sessions.set('review',{id:'review',parentID:'root',agent:'cloud-review',location:{directory:f.directory}});
  f.setPages(input=>input.cursor?{data:[old],cursor:{}}:{data:[f.sessions.get('review')],cursor:{next:'page2'}});
  const h=await f.boot();const e=f.event();await h['execute.before'](e);assert.equal(e.input.sessionID,'worker');
  assert.equal([...f.stored.values()][0].worker.source,'host-session-recovery');
 }finally{await f.cleanup();}
});

test('multiple old workers block automatic dispatch, including when model supplies a guessed ID',async()=>{
 const f=await fixture();try{
  f.worker('a');f.worker('b');const h=await f.boot();
  await assert.rejects(h['execute.before'](f.event()),/WORKER_AMBIGUOUS/);
  await assert.rejects(h['execute.before'](f.event({sessionID:'b'})),/WORKER_AMBIGUOUS/);
 }finally{await f.cleanup();}
});

test('a missing registered worker blocks replacement; a temporarily restored same session can resume',async()=>{
 const f=await fixture();try{
  const h=await f.boot();const e=f.event();await h['execute.before'](e);const w=f.worker();await h['execute.after'](f.completed(e,w.id));
  f.sessions.delete('worker');await assert.rejects(h['execute.before'](f.event()),/WORKER_UNAVAILABLE/);
  f.sessions.set(w.id,w);const repair=f.event();await h['execute.before'](repair);assert.equal(repair.input.sessionID,w.id);
 }finally{await f.cleanup();}
});

test('receipt child must match parent, project, directory, role and fixed model',async()=>{
 for(const changes of [{parentID:'other'},{projectID:'other'},{location:{directory:'/'}},{agent:'cloud-review'},{model:{providerID:'cloud',id:'selected'}},{time:{archived:1}}]){
  const f=await fixture();try{const h=await f.boot();const e=f.event();await h['execute.before'](e);f.worker('bad',changes);
   await assert.rejects(h['execute.after'](f.completed(e,'bad')),/WORKER_IDENTITY/);
   assert.equal([...f.stored.values()].some(r=>r.worker),false);
  }finally{await f.cleanup();}
 }
});

test('existing child in same task cannot be silently ignored because its model or location changed',async()=>{
 const f=await fixture();try{f.worker('old',{model:{providerID:'local',id:'wrong'}});const h=await f.boot();await assert.rejects(h['execute.before'](f.event()),/WORKER_IDENTITY/);}finally{await f.cleanup();}
});

test('pending first dispatch prevents a second session, even across restart; accepted child is recoverable',async()=>{
 const f=await fixture();try{
  let h=await f.boot();await h['execute.before'](f.event());h=await f.boot();
  await assert.rejects(h['execute.before'](f.event()),/WORKER_DISPATCH_UNCERTAIN/);
  f.worker();const e=f.event();await h['execute.before'](e);assert.equal(e.input.sessionID,'worker');
 }finally{await f.cleanup();}
});

test('simultaneous first dispatch calls admit only one creator',async()=>{
 const f=await fixture();try{const h=await f.boot();const results=await Promise.allSettled([h['execute.before'](f.event()),h['execute.before']({...f.event(),id:'second'})]);assert.equal(results.filter(r=>r.status==='fulfilled').length,1);}finally{await f.cleanup();}
});

test('reviewers return findings to parent and cannot acquire a local implementer',async()=>{
 const f=await fixture();try{
  f.sessions.set('review',{id:'review',parentID:'root',projectID:'project',agent:'cloud-review',location:{directory:f.directory}});
  const h=await f.boot();await assert.rejects(h['execute.before']({...f.event(),sessionID:'review',agent:'cloud-review'}),/WORKER_COORDINATOR_ONLY/);
  const request={sessionID:'review',agent:'cloud-review',model:f.root.model,system:[]};await h.context(request);
  assert.match(request.system.map(p=>p.text).join('\n'),/Return findings/);
 }finally{await f.cleanup();}
});

test('truncated session listing and corrupt registry never permit a new worker',async()=>{
 const f=await fixture();try{
  const h=await f.boot();f.setPages(()=>({data:[],cursor:{next:'repeated'}}));await assert.rejects(h['execute.before'](f.event()),/WORKER_HISTORY_INCOMPLETE/);
  f.setPages(undefined);await h['execute.before'](f.event());const key=[...f.stored.keys()][0];f.stored.set(key,{version:999});await assert.rejects(h['execute.before'](f.event()),/WORKER_REGISTRY_INVALID/);
 }finally{await f.cleanup();}
});

test('lost result never fabricates an ID from model-visible result text',async()=>{
 const f=await fixture();try{const h=await f.boot();const e=f.event();await h['execute.before'](e);
  await assert.rejects(h['execute.after']({...e,status:'completed',result:{content:'sessionID: guessed'}}),/WORKER_RECEIPT_MISSING/);
  await assert.rejects(h['execute.before'](f.event()),/WORKER_DISPATCH_UNCERTAIN/);
 }finally{await f.cleanup();}
});


test('legacy archived worker is not hidden to authorise a fresh replacement',async()=>{
 const f=await fixture();try{const old=f.worker('archived',{time:{archived:1}});f.setPages(input=>({data:input.archived?[old]:[],cursor:{}}));const h=await f.boot();await assert.rejects(h['execute.before'](f.event()),/WORKER_IDENTITY/);}finally{await f.cleanup();}
});

test('other task directories and unrelated parents are never resumed',async()=>{
 const f=await fixture();try{f.worker('other',{parentID:'other-root'});f.worker('previous',{location:{directory:'/'}});const h=await f.boot();const e=f.event();await h['execute.before'](e);assert.equal(e.input.sessionID,undefined);}finally{await f.cleanup();}
});

test('explicit wrong ID cannot override a receipt and error after dispatch stays conservative',async()=>{
 const f=await fixture();try{const h=await f.boot();const e=f.event();await h['execute.before'](e);await h['execute.after']({...e,status:'error',error:{message:'unknown native failure'}});await assert.rejects(h['execute.before'](f.event()),/WORKER_DISPATCH_UNCERTAIN/);f.worker();const repair=f.event({sessionID:'guessed'});await assert.rejects(h['execute.before'](repair),/WORKER_IDENTITY/);}finally{await f.cleanup();}
});
