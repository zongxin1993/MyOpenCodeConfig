import {readdir,readFile} from 'node:fs/promises';import path from 'node:path';import {homedir} from 'node:os';
import {inspectWorktree} from '../worktree-policy/git-worktree.js';
export async function assertSingleRtk(directory){
 const roots=new Set([path.join(homedir(),'.config/opencode')]);
 if(process.env.OPENCODE_CONFIG_DIR)roots.add(process.env.OPENCODE_CONFIG_DIR);
 if(process.env.XDG_CONFIG_HOME)roots.add(path.join(process.env.XDG_CONFIG_HOME,'opencode'));
 let root=directory;try{root=(await inspectWorktree(directory)).directory;}catch{/* Non-Git read-only locations get local discovery only. */}
 let current=directory;
 while(true){roots.add(path.join(current,'.opencode'));if(current===root||path.dirname(current)===current)break;current=path.dirname(current);}
 for(const base of roots)for(const folder of ['plugin','plugins']){
  const location=path.join(base,folder);let entries;
  try{entries=await readdir(location,{withFileTypes:true});}catch(e){if(e.code==='ENOENT')continue;throw e;}
  for(const file of entries){
   if(!/\.(?:js|ts|mjs)$/.test(file.name))continue;
   const body=await readFile(path.join(location,file.name),'utf8');
   if(/rtk/i.test(file.name)||/\bid\s*:\s*['"`]rtk['"`]|\bfrom\s*['"`][^'"`]*rtk/i.test(body))throw Error('Duplicate or unmanaged RTK discovery entry; reconcile before execution: '+path.join(location,file.name));
  }
 }
}
