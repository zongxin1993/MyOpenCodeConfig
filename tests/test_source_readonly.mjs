import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm,realpath,symlink} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {sourceReadPolicy} from '../plugins/worktree-policy/source-policy.js';
const git=(p,...a)=>execFileSync('git',['-C',p,...a],{encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim();
async function fixture(){
 const base=await realpath(await mkdtemp(path.join(tmpdir(),'source-ro-')));const main=path.join(base,'main');await mkdir(main);
 git(main,'init');git(main,'config','user.email','fixture@example.invalid');git(main,'config','user.name','Fixture');
 await mkdir(path.join(main,'app'));await writeFile(path.join(main,'app','code.py'),'value = 1\n');git(main,'add','.');git(main,'commit','-m','fixture');
 const linked=path.join(base,'linked');git(main,'worktree','add','-b','fixture/task',linked);return{base,main,linked};
}
function effect(rules,action,resource){
 const match=(v,p)=>new RegExp('^'+p.replace(/[.+?^${}()|[\]\\]/g,'\\$&').replaceAll('*','.*')+'$').test(v);
 return rules.findLast(r=>match(action,r.action)&&match(resource,r.resource))?.effect??'ask';
}
test('worktree automatically reads only its genuine source while source edits remain denied',async()=>{
 const f=await fixture();try{
  const p=await sourceReadPolicy(path.join(f.linked,'app'));assert.equal(p.source,f.main);
  const rules=[{action:'*',resource:'*',effect:'deny'},{action:'read',resource:'*',effect:'allow'},{action:'edit',resource:'*/docs/superpowers/specs/*.md',effect:'allow'},...p.rules];
  assert.equal(effect(rules,'external_directory',f.main+'/*'),'allow');
  assert.equal(effect(rules,'external_directory',f.base+'/unrelated/*'),'deny');
  assert.equal(effect(rules,'read',path.join(f.main,'app/code.py')),'allow');
  assert.equal(effect(rules,'edit',path.join(f.main,'docs/superpowers/specs/probe.md')),'deny');
  assert.equal(effect(rules,'edit',path.join(f.linked,'docs/superpowers/specs/probe.md')),'allow');
  assert.equal(effect(rules,'read',path.join(f.main,'.env')),'deny');
  assert.equal(effect(rules,'read',path.join(f.main,'.git/config')),'deny');
  assert.equal(await readFile(path.join(f.main,'app/code.py'),'utf8'),'value = 1\n');
 }finally{await rm(f.base,{recursive:true,force:true});}
});
test('policy also protects primary checkout and never grants sibling worktree or path prefix collisions',async()=>{
 const f=await fixture();try{
  const p=await sourceReadPolicy(f.main);assert.equal(p.source,f.main);
  assert.equal(effect(p.rules,'edit',f.main+'/x'),'deny');
  assert.equal(effect(p.rules,'external_directory',f.main+'-other/*'),'ask');
  assert.equal(effect(p.rules,'external_directory',f.linked+'/*'),'ask');
  assert.equal(await sourceReadPolicy(f.base),null);
 }finally{await rm(f.base,{recursive:true,force:true});}
});
test('fake copied Git marker cannot obtain a source grant',async()=>{
 const f=await fixture();try{const fake=path.join(f.base,'fake');await mkdir(fake);await writeFile(path.join(fake,'.git'),await readFile(path.join(f.linked,'.git')));
 await assert.rejects(sourceReadPolicy(fake),/backlink|registered/);
 }finally{await rm(f.base,{recursive:true,force:true});}
});

test('runtime transforms preserve role restrictions; only direct source reads cross the boundary',async()=>{
 const {installSourcePolicy}=await import('../plugins/worktree-policy/source-policy.js');
 const f=await fixture();try{
  const hooks=new Map();const register=(key,fn)=>hooks.set(key,[...(hooks.get(key)??[]),fn]);
  const agents=[{id:'cloud-workflow',model:{id:'unchanged'},permissions:[{action:'*',resource:'*',effect:'deny'},{action:'read',resource:'*',effect:'allow'}]},
    {id:'cloud-review',permissions:[{action:'external_directory',resource:'*',effect:'deny'}]},
    {id:'unrelated',permissions:[]}];
  const ctx={location:{directory:f.linked},agent:{transform:async fn=>fn({list:()=>agents,update:(id,fn)=>fn(agents.find(a=>a.id===id))})},
   shell:{hook:async(name,fn)=>register('shell.'+name,fn)},tool:{hook:async(name,fn)=>register('tool.'+name,fn)},permission:{hook:async(name,fn)=>register('permission.'+name,fn)},
   session:{get:async()=>({agent:'cloud-workflow'}),hook:async(name,fn)=>register('session.'+name,fn)}};
  await installSourcePolicy(ctx);
  const fire=async(name,event)=>{for(const fn of hooks.get(name)??[])await fn(event);};
  await fire('session.context',{agent:'cloud-workflow',system:[]});
  assert.equal(agents[0].model.id,'unchanged');assert.equal(agents[2].permissions.length,0);
  assert.equal(effect(agents[1].permissions,'external_directory',f.main+'/*'),'deny');
  for(const tool of ['read','glob','grep','shell','edit','execute']){
   await fire('tool.execute.before',{sessionID:'s',id:'call',tool,input:{path:f.linked}});
   const event={sessionID:'s',action:'external_directory',resources:[f.main+'/*'],source:{type:'tool',id:'call'},effect:'allow'};
   await fire('permission.evaluate',event);assert.equal(event.effect,tool==='read'?'allow':'deny');
   await fire('tool.execute.after',{sessionID:'s',id:'call'});
   const unknown={...event,effect:'allow'};await fire('permission.evaluate',unknown);assert.equal(unknown.effect,'deny');
  }
  for(const tool of ['grep','glob']) await assert.rejects(fire('tool.execute.before',{sessionID:'s',id:'blocked',tool,input:{path:f.main}}),/SOURCE_READ_ONLY/);
  await symlink(f.main,path.join(f.linked,'alias'));
  await symlink(f.base,path.join(f.main,'escape'));
  for (const event of [
   {action:'edit',resources:[path.join(f.linked,'alias/app/code.py')]},
   {action:'read',resources:[path.join(f.linked,'alias/.env')]},
   {action:'read',resources:[path.join(f.main,'escape/unrelated.txt')]},
  ]) { event.effect='allow'; await fire('permission.evaluate',event);assert.equal(event.effect,'deny'); }
  const unrelated={sessionID:'s',action:'external_directory',resources:[f.base+'/unrelated/*'],effect:'deny'};
  await fire('permission.evaluate',unrelated);assert.equal(unrelated.effect,'deny');
 }finally{await rm(f.base,{recursive:true,force:true});}
});


test('shell confinement blocks relative, indirect and symlink source writes but permits worktree files and commits',async t=>{
 if(process.platform!=='darwin')return t.skip('macOS sandbox-exec integration; unsupported systems refuse shell');
 const {protectShell}=await import('../plugins/worktree-policy/source-policy.js');
 const f=await fixture();try{
  const policy=await sourceReadPolicy(f.linked);
  await symlink(f.main,path.join(f.linked,'source-alias'));
  const run=async command=>{const e={shell:'/bin/sh',command};await protectShell(e,policy);assert.equal(e.command,command);assert.equal(path.basename(e.shell),'sh');return execFileSync(e.shell,['-c',e.command],{cwd:f.linked,env:{...process.env,...e.env},encoding:'utf8',stdio:['ignore','pipe','pipe']});};
  // This must run on a host that supports sandbox-exec; no fallback may execute an unprotected command.
  for(const command of ['printf bad > ../main/app/code.py', 'p=../main; printf bad > "$p/app/code.py"', 'printf bad > source-alias/app/code.py']) {
    await assert.rejects(run(command));
  }
  await writeFile(path.join(f.main,'.env'),'SYNTHETIC=fixture\n');
  await assert.rejects(run('cat ../main/.env'));
  await run('printf okay > app/allowed.txt');
  assert.equal(await readFile(path.join(f.linked,'app/allowed.txt'),'utf8'),'okay');
  await run('git add app/allowed.txt && git commit -m sandbox-fixture');
  assert.equal(await readFile(path.join(f.main,'app/code.py'),'utf8'),'value = 1\n');
  assert.equal(git(f.main,'status','--porcelain'),'?? .env');
 }finally{await rm(f.base,{recursive:true,force:true});}
});
