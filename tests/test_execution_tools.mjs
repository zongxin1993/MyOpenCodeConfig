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


test('structured search discovers files, searches literal text and honours read denial',async()=>{
 const {search}=await import('../plugins/execution-tools/search.js');const f=await fixture();try{
  const rg=process.env.EXECUTION_RG_BINARY||'rg';const requests=[];
  const ctx={location:{directory:f.wt},session:{get:async()=>({agent:'local-worker',location:{directory:f.wt}})},permission:{assert:async r=>requests.push(r)}};
  const call={sessionID:'search-test',agent:'local-worker',id:'c',messageID:'m'};
  await writeFile(path.join(f.wt,'.env'),'sample secret');
  const files=await search(ctx,call,{mode:'files',paths:['.']},rg);
  assert.ok(files.files.includes('code.rs'));assert.ok(!files.files.includes('.env'));
  const result=await search(ctx,call,{mode:'text',query:'sample()',paths:['.']},rg);
  assert.equal(result.matches.length,1);assert.equal(result.matches[0].file,'code.rs');assert.equal(result.matches[0].line,1);
  assert.ok(requests.length>=3);assert.equal(result.incomplete,false);
  await assert.rejects(search(ctx,{...call,agent:'cloud-workflow'},{mode:'files'},rg),/role/);
  await assert.rejects(search(ctx,call,{mode:'text',query:'x',paths:[f.main]},rg),/worktree/);
  ctx.permission.assert=async()=>{throw Error('read denied')};await assert.rejects(search(ctx,call,{mode:'text',query:'sample'},rg),/read denied/);
 }finally{await rm(f.base,{recursive:true,force:true});}
});
test('structured search reports candidate limits and never interprets query as arguments',async()=>{
 const {search}=await import('../plugins/execution-tools/search.js');const f=await fixture();try{
 const ctx={location:{directory:f.wt},session:{get:async()=>({agent:'local-worker',location:{directory:f.wt}})},permission:{assert:async()=>{}}};const call={sessionID:'s',agent:'local-worker',id:'c'};const rg=process.env.EXECUTION_RG_BINARY||'rg';
 for(let i=0;i<70;i++)await writeFile(path.join(f.wt,`f${i}.rs`),'token\n');
 const limited=await search(ctx,call,{mode:'text',query:'token'},rg);assert.equal(limited.incomplete,true);assert.equal(limited.scannedFiles,64);
 const flags=await search(ctx,call,{mode:'text',query:'--files',paths:['code.rs']},rg);assert.equal(flags.matches.length,0);
 await symlink(path.join(f.main,'code.rs'),path.join(f.wt,'outside.rs'));await assert.rejects(search(ctx,call,{mode:'text',query:'sample',paths:['outside.rs']},rg),/worktree/);
 }finally{await rm(f.base,{recursive:true,force:true});}
});
test('session usage records successful skills, tool choice and RTK separately without source',async()=>{
 const {recordUsage,readUsage}=await import('../plugins/execution-tools/usage.js');const values=new Map();const ctx={storage:{get:async k=>values.get(k),set:async(k,v)=>values.set(k,structuredClone(v))}};
 await Promise.all([recordUsage(ctx,'s',{tool:'execution_search',bytesBefore:1000,bytesAfter:200,filtered:true}),recordUsage(ctx,'s',{tool:'skill',skill:'local-execution'})]);
 const s=await readUsage(ctx,'s');assert.equal(s.tools.execution_search,1);assert.equal(s.skills['local-execution'],1);assert.equal(s.rtk.filtered,1);assert.equal(s.rtk.bytesBefore,1000);assert.equal((await readUsage(ctx,'other')).rtk.filtered,0);
 assert.ok(!JSON.stringify(s).includes('query'));
});

test('structured search preserves source bytes and reports match truncation and oversized exclusions',async()=>{
 const {search}=await import('../plugins/execution-tools/search.js');const f=await fixture();try{
 const ctx={location:{directory:f.wt},session:{get:async()=>({agent:'local-worker',location:{directory:f.wt}})},permission:{assert:async()=>{}}};const call={sessionID:'s',agent:'local-worker',id:'c'};const rg=process.env.EXECUTION_RG_BINARY||'rg';
 const raw='hello\n'.repeat(205);await writeFile(path.join(f.wt,'many.rs'),raw);
 let r=await search(ctx,call,{mode:'text',query:'hello',paths:['many.rs']},rg);assert.equal(r.matches.length,200);assert.equal(r.totalMatches,205);assert.equal(r.incomplete,true);assert.equal(await readFile(path.join(f.wt,'many.rs'),'utf8'),raw);
 await writeFile(path.join(f.wt,'large.rs'),'hello'.repeat(220000));r=await search(ctx,call,{mode:'text',query:'hello',paths:['large.rs']},rg);assert.equal(r.incomplete,true);assert.equal(r.scannedFiles,0);assert.equal(r.skippedFiles,1);
 }finally{await rm(f.base,{recursive:true,force:true});}
});
test('structured search rejects swapped directories, protected paths and cancelled requests',async()=>{
 const {search}=await import('../plugins/execution-tools/search.js');const f=await fixture();try{
 await mkdir(path.join(f.wt,'src'));await writeFile(path.join(f.wt,'src/code.rs'),'safe');
 const call={sessionID:'s',agent:'local-worker',id:'c'};const rg=process.env.EXECUTION_RG_BINARY||'rg';
 const ctx={location:{directory:f.wt},session:{get:async()=>({agent:'local-worker',location:{directory:f.wt}})},permission:{assert:async()=>{}}};
 await assert.rejects(search(ctx,call,{mode:'files',paths:['.git']},rg),/Protected/);
 const controller=new AbortController();controller.abort();await assert.rejects(search(ctx,{...call,signal:controller.signal},{mode:'files'},rg),/cancelled/);
 ctx.permission.assert=async()=>{await rm(path.join(f.wt,'src'),{recursive:true});await symlink(f.main,path.join(f.wt,'src'));};
 await assert.rejects(search(ctx,call,{mode:'files',paths:['src']},rg),/changed/);
 }finally{await rm(f.base,{recursive:true,force:true});}
});

test('structured search bounds actual reads when files grow during permission approval',async()=>{
 const {search}=await import('../plugins/execution-tools/search.js');const f=await fixture();try{
 for(let i=0;i<9;i++)await writeFile(path.join(f.wt,`grow${i}.rs`),'small');
 let calls=0;const ctx={location:{directory:f.wt},session:{get:async()=>({agent:'local-worker',location:{directory:f.wt}})},permission:{assert:async()=>{if(++calls===2)for(let i=0;i<9;i++)await writeFile(path.join(f.wt,`grow${i}.rs`),'x'.repeat(1024*1024));}}};
 await assert.rejects(search(ctx,{sessionID:'s',agent:'local-worker',id:'c'},{mode:'text',query:'x'},process.env.EXECUTION_RG_BINARY||'rg'),/budget/);
 }finally{await rm(f.base,{recursive:true,force:true});}
});
test('native hooks observe actual skill IDs and shell RTK results',async t=>{
 const bin=process.env.EXECUTION_RTK_BINARY;if(!bin)return t.skip('Set EXECUTION_RTK_BINARY');
 const plugin=(await import('../plugins/execution-tools/index.js')).default;const {readUsage}=await import('../plugins/execution-tools/usage.js');const store=new Map(),hooks=[];
 const ctx={options:{rtk:{enabled:true},tools:{rtk:bin}},tool:{hook:async(n,h)=>hooks.push(h)},session:{hook:async()=>{}},storage:{get:async k=>store.get(k),set:async(k,v)=>store.set(k,v)}};
 await plugin.setup(ctx);const raw=Array.from({length:100},(_,i)=>`src/code.rs:${i+1}: fn repeated_function() { /* repeated evidence */ }`).join('\n');
 const event={sessionID:'s',agent:'local-worker',tool:'shell',status:'completed',input:{command:'rg -n repeated src'},result:{content:[{type:'text',text:raw}],metadata:{exitCode:0}}};
 for(const h of hooks)await h(event);
 for(const h of hooks)await h({sessionID:'s',agent:'local-worker',tool:'skill',status:'completed',input:{id:'local-execution'},result:{metadata:{name:'local-execution'}}});
 const status=await readUsage(ctx,'s');assert.equal(status.skills['local-execution'],1);assert.equal(status.rtk.filtered,1);assert.ok(status.rtk.bytesAfter<status.rtk.bytesBefore);await rm(event.result.metadata.rtkOriginal);
});

test('file mode query is a filename glob, including leading dashes without flag execution',async()=>{
 const {search}=await import('../plugins/execution-tools/search.js');const f=await fixture();try{
 await writeFile(path.join(f.wt,'notes.txt'),'note');await writeFile(path.join(f.wt,'.gitignore'),'ignored.rs\n');await writeFile(path.join(f.wt,'ignored.rs'),'private ignored source');const ctx={location:{directory:f.wt},session:{get:async()=>({agent:'local-worker',location:{directory:f.wt}})},permission:{assert:async()=>{}}};const call={sessionID:'s',agent:'local-worker',id:'c'};const bin=process.env.EXECUTION_RG_BINARY||'rg';
 const r=await search(ctx,call,{mode:'files',query:'*.rs'},bin);assert.deepEqual(r.files,['code.rs']);
 const empty=await search(ctx,call,{mode:'files',query:'--files'},bin);assert.deepEqual(empty.files,[]);
 }finally{await rm(f.base,{recursive:true,force:true});}
});


test('cloud context keeps native review tools and hides local execution tools without logging cloud usage',async()=>{
 const plugin=(await import('../plugins/execution-tools/index.js')).default;
 const {readUsage}=await import('../plugins/execution-tools/usage.js');const contexts=[],after=[],store=new Map();
 const ctx={options:{search:{enabled:true},tools:{rg:'/verified/rg'}},tool:{transform:async()=>{},hook:async(_n,h)=>after.push(h)},session:{hook:async(_n,h)=>contexts.push(h)},storage:{get:async k=>store.get(k),set:async(k,v)=>store.set(k,v)}};
 await plugin.setup(ctx);
 for(const agent of ['cloud-workflow','cloud-plan','cloud-review']){
  const event={agent,tools:{read:{},grep:{},skill:{},context7_query_docs:{},execution_search:{},execution_ast_search:{},execution_status:{}},system:[]};
  for(const h of contexts)await h(event);
  assert.deepEqual(Object.keys(event.tools),['read','grep','skill','context7_query_docs']);assert.equal(event.system.length,0);
  for(const h of after)await h({sessionID:agent,agent,tool:'skill',status:'completed',input:{id:'quality-review'}});
  assert.deepEqual((await readUsage(ctx,agent)).tools,{});
 }
});
