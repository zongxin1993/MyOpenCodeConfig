#!/usr/bin/env python3
"""One targeted mutation experiment in a copy, not a general mutation score."""
import argparse,ast,json,re,shutil,subprocess,sys,tempfile
from pathlib import Path

def probe(root,relative,function):
 if Path(relative).is_absolute() or '..' in Path(relative).parts:raise ValueError('Relative source path required')
 root=Path(root).resolve(strict=True);source=(root/relative).resolve(strict=True)
 if root not in source.parents or source.suffix!='.py':raise ValueError('Python source must be inside project')
 current=root
 for part in Path(relative).parts:
  current/=part
  if current.is_symlink():raise ValueError('Symlink source refused')
 with tempfile.TemporaryDirectory(prefix='quality-mutant-') as td:
  clone=Path(td)/'project';shutil.copytree(root,clone,symlinks=True,ignore=shutil.ignore_patterns('.git','.quality','__pycache__','.venv','node_modules','target'))
  if any(p.is_symlink() for p in clone.rglob('*')):raise ValueError('Symlinks not supported in mutation probe')
  command=[sys.executable,'-m','unittest','discover','-s','tests','-v']
  baseline=subprocess.run(command,cwd=clone,capture_output=True,text=True,timeout=60)
  log=baseline.stdout+baseline.stderr
  if baseline.returncode or not re.search(r'Ran [1-9][0-9]* tests? in ',log) or 'skipped=' in log:raise ValueError('Real nonempty passing baseline required')
  target=clone/relative;tree=ast.parse(target.read_text());changed=0
  class Mutator(ast.NodeTransformer):
   def visit_FunctionDef(self,node):
    nonlocal changed
    if node.name!=function:return node
    class Returns(ast.NodeTransformer):
     def visit_Return(self,r):
      nonlocal changed
      changed+=1;return ast.copy_location(ast.Return(value=ast.Constant(value=999999)),r)
    return Returns().visit(node)
  tree=Mutator().visit(tree)
  if not changed:raise ValueError('No targeted return expression')
  target.write_text(ast.unparse(ast.fix_missing_locations(tree))+'\n')
  result=subprocess.run(command,cwd=clone,capture_output=True,text=True,timeout=60);mutant_log=result.stdout+result.stderr
  detected=result.returncode!=0 and 'FAIL:' in mutant_log
  return {'checks':1,'skipped':0,'failures':0 if detected else 1,'mutations':changed,'detected':detected,'baseline_exit':baseline.returncode,'mutant_exit':result.returncode,'baseline_log':log,'mutant_log':mutant_log,'note':'One declared return-value mutation in isolated copy; not exhaustive mutation coverage'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--file',required=True);p.add_argument('--function',required=True);a=p.parse_args()
 try:r=probe(a.root,a.file,a.function);print(json.dumps(r));return bool(r['failures'])
 except (ValueError,OSError,SyntaxError,subprocess.TimeoutExpired) as e:print(json.dumps({'checks':0,'skipped':0,'failures':1,'error':str(e)}));return 2
if __name__=='__main__':raise SystemExit(main())
