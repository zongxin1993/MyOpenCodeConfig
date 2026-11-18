import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm,readFile,realpath} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import plugin,{inspectWorktree} from '../plugins/worktree-policy/index.js';
const git=(cwd,...args)=>execFileSync('git',['-C',cwd,...args],{encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim();
async function fixture(){
 const base=await realpath(await mkdtemp(path.join(tmpdir(),'workflow-wt-')));const main=path.join(base,'source');await mkdir(main);
 git(main,'init');git(main,'config','user.email','fixture@example.invalid');git(main,'config','user.name','Fixture');
 await writeFile(path.join(main,'README.md'),'source');await mkdir(path.join(main,'app'));await writeFile(path.join(main,'app','README.md'),'nested');git(main,'add','.');git(main,'commit','-m','fixture');
 const linked=path.join(base,'linked');git(main,'worktree','add','-b','fixture/task',linked);
 return {base,main,linked};
}
function sdk(f){
 const hooks={};const tools={};const sessions=new Map([['root',{id:'root',projectID:'p',agent:'cloud-workflow',location:{directory:f.main}}],['old',{id:'old',parentID:'root',agent:'local-worker',location:{directory:f.main}}]]);
 let creates=0;const ctx={session:{get:async({sessionID})=>sessions.get(sessionID),move:async({sessionID,directory})=>{sessions.get(sessionID).location.directory=directory;},hook:async(n,fn)=>hooks[n]=fn},
 tool:{transform:async fn=>fn({add:t=>tools[t.name]=t}),hook:async(n,fn)=>hooks[n]=fn},
 worktree:{create:async()=>{creates++;return {directory:f.linked,branch:'fixture/task'};}}};
 return {ctx,hooks,tools,sessions,creates:()=>creates};
}
test('real Git primary checkout is refused; linked worktree is recognised',async()=>{
 const f=await fixture();try{assert.equal((await inspectWorktree(f.main)).isolated,false);assert.equal((await inspectWorktree(f.linked)).isolated,true);assert.equal(git(f.main,'status','--porcelain'),'');}finally{await rm(f.base,{recursive:true,force:true});}
});
test('tool creates and moves once, then reuses isolation without touching source',async()=>{
 const f=await fixture();try{const s=sdk(f);await plugin.setup(s.ctx);const result=await s.tools.workflow_worktree.execute({name:'small-task'},{sessionID:'root'});
 assert.equal(s.creates(),1);assert.equal(s.sessions.get('root').location.directory,f.linked);assert.match(JSON.stringify(result),/WORKTREE_READY/);
 await s.tools.workflow_worktree.execute({name:'small-task'},{sessionID:'root'});assert.equal(s.creates(),1);assert.equal(await readFile(path.join(f.main,'README.md'),'utf8'),'source');
 }finally{await rm(f.base,{recursive:true,force:true});}
});
test('local dispatch from source and resuming an old source worker both fail closed',async()=>{
 const f=await fixture();try{const s=sdk(f);await plugin.setup(s.ctx);
 await assert.rejects(s.hooks['execute.before']({tool:'subagent',sessionID:'root',input:{agent:'local-worker'}}),/worktree/i);
 s.sessions.get('root').location.directory=f.linked;
 await assert.rejects(s.hooks['execute.before']({tool:'subagent',sessionID:'root',input:{agent:'local-worker',sessionID:'old'}}),/worktree/i);
 await s.hooks['execute.before']({tool:'subagent',sessionID:'root',input:{agent:'local-worker'}});
 }finally{await rm(f.base,{recursive:true,force:true});}
});
test('a non-Git or fake .git directory cannot be implementation isolation',async()=>{
 const f=await fixture();try{const fake=path.join(f.base,'fake');await mkdir(fake);await writeFile(path.join(fake,'.git'),'gitdir: missing');await assert.rejects(inspectWorktree(fake));
 }finally{await rm(f.base,{recursive:true,force:true});}
});

test('copied genuine git marker is rejected and nested project location is preserved',async()=>{
 const f=await fixture();try{
  const fake=path.join(f.base,'fake');await mkdir(fake);await writeFile(path.join(fake,'.git'),await readFile(path.join(f.linked,'.git')));
  await assert.rejects(inspectWorktree(fake),/registered|backlink/i);
  const s=sdk(f);s.sessions.get('root').location.directory=path.join(f.main,'app');await plugin.setup(s.ctx);
  await s.tools.workflow_worktree.execute({name:'nested-task'},{sessionID:'root'});
  assert.equal(s.sessions.get('root').location.directory,path.join(f.linked,'app'));
 }finally{await rm(f.base,{recursive:true,force:true});}
});
