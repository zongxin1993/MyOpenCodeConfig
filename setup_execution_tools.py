#!/usr/bin/env python3
"""Explicit setup-time CLI provisioning from checked npm dependency locks. No task-time downloads."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def inventory(root):
    result={}
    for p in sorted(root.rglob('*')):
        if p.name in ('receipt.json','.package-lock.json'):continue
        if p.is_symlink():result[p.relative_to(root).as_posix()]='link:'+os.readlink(p)
        elif p.is_file():result[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result

def provision_package(source,destination,runner=subprocess.run):
    source=Path(source);destination=Path(destination)
    if destination.is_symlink():raise ValueError('Tool directory symlink refused')
    receipt=destination/'receipt.json'
    if receipt.is_file():
        expected=json.loads(receipt.read_text())
        if inventory(destination)!=expected:raise ValueError('Tool installation modified; refusing replacement')
        for name in ('package.json','package-lock.json'):
            if (destination/name).read_bytes()!= (source/name).read_bytes():raise ValueError('Tool dependency lock changed')
        return
    destination.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.'+destination.name+'-',dir=destination.parent))
    try:
        for name in ('package.json','package-lock.json'):shutil.copy2(source/name,staging/name)
        runner(['npm','ci','--prefix',str(staging),'--ignore-scripts','--no-audit','--no-fund'],check=True,timeout=180)
        if not (staging/'node_modules').is_dir():raise ValueError('Missing installed package tree')
        expected=inventory(staging)
        if destination.exists():
            if inventory(destination)!=expected:raise ValueError('Existing unreceipted tool differs; preserved without modification')
            (destination/'receipt.json').write_text(json.dumps(expected,sort_keys=True,indent=2)+'\n')
        else:
            (staging/'receipt.json').write_text(json.dumps(expected,sort_keys=True,indent=2)+'\n');os.replace(staging,destination)
    finally:
        if staging.exists():shutil.rmtree(staging)

def install(root,browser=False):
    lock=json.loads((ROOT/'integrations/execution.lock.json').read_text());results=[]
    if not shutil.which('npm'):raise ValueError('npm is required for fixed CLI provisioning')
    rtk=shutil.which('rtk')
    if not rtk or subprocess.check_output([rtk,'--version'],text=True).split()[-1]!=lock['rtk']['version']:
        raise ValueError('Install RTK '+lock['rtk']['version']+' from its pinned upstream release before enabling RTK; do not install an unpinned global replacement')
    for key,folder in [('ast_grep','ast-grep')]+([('playwright','playwright')] if browser else []):
        version=lock[key]['version'];name='ast-grep' if key=='ast_grep' else 'playwright-cli'
        destination=Path(root).expanduser().resolve()/'.local/share/myopencodeconfig/tools'/(name+'-'+version)
        provision_package(ROOT/'integrations/toolchains'/folder,destination)
        results.append({'tool':name,'version':version,'directory':str(destination)})
    return results
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path.home());p.add_argument('--browser',action='store_true');a=p.parse_args()
    try:print(json.dumps(install(a.root,a.browser),indent=2))
    except (ValueError,OSError,subprocess.SubprocessError) as e:p.exit(1,str(e)+'\n')
