import test from 'node:test';import assert from 'node:assert/strict';
import {mkdtemp,writeFile,mkdir,symlink,readFile,rm,realpath} from 'node:fs/promises';import {tmpdir} from 'node:os';import path from 'node:path';import {execFileSync} from 'node:child_process';
import {safeFilter,filterOutput} from '../plugins/execution-tools/rtk.js';
import {authorizeFiles} from '../plugins/execution-tools/access.js';
const git=(p,...args)=>execFileSync('git',['-C',p,...args],{stdio:'pipe'});
async function fixture(){const base=await realpath(await mkdtemp(path.join(tmpdir(),'execution-test-')));const main=path.join(base,'main');await mkdir(main);git(main,'init');git(main,'config','user.email','fixture@example.invalid');git(main,'config','user.name','Fixture');await writeFile(path.join(main,'code.rs'),'fn sample() {}\n');git(main,'add','.');git(main,'commit','-m','fixture');const wt=path.join(base,'task');git(main,'worktree','add','-b','fixture/task',wt);return{base,main,wt};}
test('RTK selection never touches evidence commands, shell syntax or source bodies',()=>{
 assert.equal(safeFilter('rg --line-number sample src'),'grep');
 for(const c of ['cargo test','python scripts/dev_verification.py run -- pytest','git diff','cat src/code.rs','rg x . > output','rg x . | head','ls; rm -rf x','echo $(id)','rtk rg x .','git log --oneline --format=fuller -p','git log --oneline --pretty fuller','git log --oneline --stat','git log --oneline --format=%B'])assert.equal(safeFilter(c),null,c);
});
test('filter failure preserves full native result and exit metadata',async()=>{
 const result={content:[{type:'text',text:'src/file.rs:1: raw text\n'.repeat(100)}],metadata:{exitCode:1}};
 const copy=structuredClone(result);await filterOutput('/nonexistent/rtk','grep',result,'/nonexistent/evidence');assert.deepEqual(result,copy);
});
test('search permission uses actual role and canonical worktree, preserves deny/ask',async()=>{
 const f=await fixture();try{
  const requests=[];const ctx={location:{directory:f.wt},session:{get:async()=>({agent:'local-worker',location:{directory:f.wt}})},permission:{assert:async r=>{requests.push(r);if(r.resources.some(x=>x.includes('blocked')))throw Error('permission denied');}}};
  const call={sessionID:'s',agent:'local-worker',id:'c',messageID:'m'};
  const allowed=await authorizeFiles(ctx,call,['code.rs']);assert.equal(allowed[0],path.join(f.wt,'code.rs'));assert.equal(requests[0].action,'read');assert.equal(requests[0].source.messageID,'m');
  await writeFile(path.join(f.wt,'blocked.rs'),'x');await assert.rejects(authorizeFiles(ctx,call,['blocked.rs']),/permission denied/);
  await assert.rejects(authorizeFiles(ctx,{...call,agent:'cloud-workflow'},['code.rs']),/role/);
  await assert.rejects(authorizeFiles(ctx,call,[path.join(f.main,'code.rs')]),/worktree/);
  await writeFile(path.join(f.wt,'.env'),'fake');await assert.rejects(authorizeFiles(ctx,call,['.env']),/protected/);
  await symlink(path.join(f.main,'code.rs'),path.join(f.wt,'alias.rs'));await assert.rejects(authorizeFiles(ctx,call,['alias.rs']),/worktree/);
 }finally{await rm(f.base,{recursive:true,force:true});}
});

test('real ast-grep matches Rust without reading or writing unchecked paths',async t=>{
 const bin=process.env.EXECUTION_AST_BINARY;if(!bin)return t.skip('Set EXECUTION_AST_BINARY for fixed CLI integration');
 const {astSearch}=await import('../plugins/execution-tools/ast-search.js');const f=await fixture();try{
  const ctx={location:{directory:f.wt},session:{get:async()=>({agent:'local-worker',location:{directory:f.wt}})},permission:{assert:async()=>{}}};const call={sessionID:'s',agent:'local-worker',id:'c'};
  const out=await astSearch(ctx,call,{language:'rust',pattern:'fn $NAME() {}',files:['code.rs']},bin);assert.equal(out.matches.length,1);assert.equal(out.matches[0].line,1);
  const no=await astSearch(ctx,call,{language:'rust',pattern:'struct $NAME {}',files:['code.rs']},bin);assert.equal(no.matches.length,0);
  assert.equal(await readFile(path.join(f.wt,'code.rs'),'utf8'),'fn sample() {}\n');
 }finally{await rm(f.base,{recursive:true,force:true});}
});


test('real RTK filters display once and keeps exact original evidence',async t=>{
 const bin=process.env.EXECUTION_RTK_BINARY;if(!bin)return t.skip('Set EXECUTION_RTK_BINARY for fixed CLI integration');
 const base=await realpath(await mkdtemp(path.join(tmpdir(),'rtk-output-')));try{
 const raw=Array.from({length:100},(_,i)=>'src/file.rs:'+(i+1)+':    fn repeated_function_name() { /* repeated informational detail */ }').join('\n');
 const result={content:[{type:'text',text:raw}],metadata:{exitCode:1}};await filterOutput(bin,'grep',result,base);
 assert.equal(result.metadata.exitCode,1);assert.ok(result.metadata.rtkOriginal);assert.equal(await readFile(result.metadata.rtkOriginal,'utf8'),raw);assert.ok(result.content[0].text.length<raw.length);
 }finally{await rm(base,{recursive:true,force:true});}
});

test('permission wait cannot substitute an outside symlink as search input',async()=>{
 const {readAuthorizedSources}=await import('../plugins/execution-tools/access.js');const {unlink}=await import('node:fs/promises');const f=await fixture();try{
  const outside=path.join(f.base,'outside.rs');await writeFile(outside,'fn secret_outside() {}');
  const ctx={location:{directory:f.wt},session:{get:async()=>({agent:'local-worker',location:{directory:f.wt}})},permission:{assert:async()=>{await unlink(path.join(f.wt,'code.rs'));await symlink(outside,path.join(f.wt,'code.rs'));}}};
  await assert.rejects(readAuthorizedSources(ctx,{sessionID:'s',agent:'local-worker',id:'c'},['code.rs']),/changed|worktree|symlink/);
 }finally{await rm(f.base,{recursive:true,force:true});}
});


test('RTK nonzero, timeout and evidence failure keep raw output without rerunning native command',async()=>{
 const base=await realpath(await mkdtemp(path.join(tmpdir(),'rtk-failures-')));try{
 const raw='src/file.rs:1: repeated original output\n'.repeat(100);
 for(const [name,body] of [['nonzero','exit 7'],['timeout','exec sleep 5'],['log-failure',"cat >/dev/null\nprintf 'compact result\\n'"]]){
  const bin=path.join(base,name);await writeFile(bin,'#!/bin/sh\nprintf attempted > "${0}.called"\n'+body+'\n',{mode:0o700});
  const result={content:[{type:'text',text:raw}],metadata:{exitCode:3}};const original=structuredClone(result);
  const evidence=path.join(base,'not-a-directory');await writeFile(evidence,'occupied');
  await filterOutput(bin,'grep',result,evidence);assert.equal(await readFile(bin+'.called','utf8'),'attempted');assert.deepEqual(result,original);
 }
 }finally{await rm(base,{recursive:true,force:true});}
});

test('RTK accepts only the setup-selected absolute rg executable',()=>{
 assert.equal(safeFilter('/verified/rg -H -n marker file','/verified/rg'),'grep');
 assert.equal(safeFilter('/other/rg -H marker file','/verified/rg'),null);
});
