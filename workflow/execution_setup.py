"""Digest-checked file transactions and execution preflight. Never restore over user edits."""
import hashlib,json,os
from pathlib import Path

def digest(raw):return None if raw is None else hashlib.sha256(raw).hexdigest()
def content(path):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):raise ValueError('Symlink transaction target refused: '+str(path))
    if path.exists() and not path.is_file():raise ValueError('Expected file target: '+str(path))
    return path.read_bytes() if path.exists() else None

def atomic_file(path,raw):
    from configure import atomic_write
    if raw is None:path.unlink(missing_ok=True)
    else:path.parent.mkdir(parents=True,exist_ok=True);atomic_write(path,raw)

class FileTransaction:
    def __init__(self,backup,changes,expected=None):
        self.backup=Path(backup);self.changes={Path(k):v for k,v in changes.items()};self.records=[];self.expected=expected or {}
    def prepare(self):
        before={p:content(p) for p in self.changes}
        for p,raw in before.items():
            if p in self.expected and digest(raw)!=self.expected[p]:raise ValueError("Concurrent preflight change: "+str(p))
        self.backup.mkdir(parents=True,mode=0o700,exist_ok=False)
        for i,(p,raw) in enumerate(before.items()):
            saved=self.backup/str(i)
            if raw is not None:saved.write_bytes(raw);saved.chmod(0o600)
            self.records.append({'path':str(p),'backup':str(saved),'before':digest(raw),'after':digest(self.changes[p]),'written':False})
        self._save()
    def _save(self):
        atomic_file(self.backup/'transaction.json',(json.dumps(self.records,indent=2)+'\n').encode())
    def write(self,path):
        path=Path(path);row=next(r for r in self.records if r['path']==str(path))
        if digest(content(path))!=row['before']:raise ValueError('Concurrent file change: '+str(path))
        # Journal intent before mutation so an interruption can recover by before/after digest.
        row['written']=True;self._save();atomic_file(path,self.changes[path])
    def commit(self):
        try:
            for p in self.changes:self.write(p)
        except BaseException:
            conflicts=self.rollback()
            if conflicts:raise ValueError('Recovery conflicts; preserved concurrent edits: '+', '.join(conflicts))
            raise
    def rollback(self):
        conflicts=[]
        for row in reversed(self.records):
            if not row['written']:continue
            p=Path(row['path'])
            try:current=digest(content(p))
            except (ValueError,OSError):conflicts.append(str(p));continue
            if current==row['before']:continue
            if current!=row['after']:conflicts.append(str(p));continue
            saved=Path(row['backup'])
            try:original=content(saved) if row['before'] is not None else None
            except (ValueError,OSError):conflicts.append(str(p));continue
            if digest(original)!=row['before']:conflicts.append(str(p));continue
            atomic_file(p,original)
        return conflicts

def discover_rtk(home,projects=()):
    """Detect conventional auto-discovery files before adding a single managed filter."""
    import re,subprocess
    roots={Path(p).resolve() for p in projects}
    for project in list(roots):
        try:
            env={k:v for k,v in os.environ.items() if k not in ('GIT_DIR','GIT_WORK_TREE','GIT_COMMON_DIR','GIT_INDEX_FILE')};env['GIT_OPTIONAL_LOCKS']='0'
            raw=subprocess.check_output(['git','-C',str(project),'worktree','list','--porcelain','-z'],env=env,stderr=subprocess.DEVNULL,text=True,timeout=10)
            roots.update(Path(x[9:]).resolve() for x in raw.split('\0') if x.startswith('worktree '))
        except (OSError,subprocess.SubprocessError):pass
    bases={Path(home)/'.config/opencode',*[p/'.opencode' for p in roots]}
    if os.environ.get('XDG_CONFIG_HOME'):bases.add(Path(os.environ['XDG_CONFIG_HOME']).resolve()/'opencode')
    for name in ('OPENCODE_CONFIG_DIR',):
        if os.environ.get(name):bases.add(Path(os.environ[name]).resolve())
    found=[]
    for base in bases:
        for folder in ('plugins','plugin'):
            p=base/folder
            if p.is_dir():
                for item in p.iterdir():
                    if item.suffix in ('.js','.ts','.mjs') and ('rtk' in item.name.lower() or re.search(rb"\bid\s*:\s*['\"`]rtk['\"`]|\bfrom\s*['\"`][^'\"`]*rtk",content(item),re.I)):
                        found.append(item)
    return found

def plan_execution(home,options,lock,projects=()):
    import shutil,subprocess,platform
    result={'tools':{},'remove':[],'skills':[],'optional':{}}
    root=Path(home)/'.local/share/myopencodeconfig/tools'
    for name,enabled in [('rtk',options['rtk']['enabled']),('ast_grep',options['ast_grep']['enabled'])]:
        if not enabled:continue
        if name=='rtk':candidate=shutil.which('rtk')
        else:
            arch={'arm64':'arm64','x86_64':'x64'}.get(platform.machine(),platform.machine())
            osname={'Darwin':'darwin','Linux':'linux'}.get(platform.system(),platform.system().lower())
            native=root/('ast-grep-'+lock[name]['version'])/'node_modules'/('@ast-grep/cli-'+osname+'-'+arch)/'ast-grep'
            candidate=str(native) if native.is_file() else shutil.which('ast-grep')
        if not candidate:raise ValueError('Install pinned '+name+' before enabling execution capability')
        binary=Path(candidate).resolve(strict=True)
        v=subprocess.check_output([str(binary),'--version'],text=True,timeout=5).strip()
        if v.split()[-1]!=lock[name]['version']:raise ValueError('Pinned '+name+' version mismatch')
        result['tools'][name]=str(binary)
    if options['rtk']['enabled'] and shutil.which('rg'):
        result['tools']['rg']=str(Path(shutil.which('rg')).resolve(strict=True))
    if options['rtk']['enabled']:
        files=discover_rtk(home,projects)
        if len(files)>1:raise ValueError('Multiple RTK discovery entries: reconcile before enabling')
        for p in files:
            if hashlib.sha256(content(p)).hexdigest()!=lock['rtk']['adapter_sha256']:raise ValueError('Unknown RTK discovery hook; refusing takeover: '+str(p))
            result['remove'].append(str(p))
    if options['worker_skill']:result['skills'].append('local-execution')
    if options['rust_skills']:result['skills'].append('rust-diagnostics')
    if options['ast_grep']['enabled']:result['skills'].append('ast-grep')
    # A disabled optional process is not installed, started or exposed. Its independent
    # receipt must certify dependencies, permissions and lifecycle before it can run.
    for name in ('serena','browser'):
        mode=options[name]['mode'];result['optional'][name]={'mode':mode,'certified':False}
        if mode!='off':raise ValueError(name+' remains off: independent process isolation certification required')
    return result


def verify_owned_files(records):
    for name,expected in records.items():
        p=Path(name)
        if digest(content(p))!=expected:raise ValueError('Managed file modified externally: '+name)


def execution_skill_changes(home,names,repository,previous):
    changes={}
    for name in names:
        source_root=Path(repository)/'skills'/name
        for source in source_root.rglob('*'):
            if not source.is_file():continue
            target=Path(home)/'.agents/skills'/name/source.relative_to(source_root)
            raw=source.read_bytes();current=content(target)
            if current is not None and str(target) not in previous and current!=raw:raise ValueError('Unowned skill file collision: '+str(target))
            changes[target]=raw
    return changes

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Recover an owned file transaction without overwriting concurrent edits')
    parser.add_argument('--rollback',required=True,type=Path);args=parser.parse_args()
    backup=args.rollback.expanduser().resolve(strict=True)
    tx=FileTransaction(backup,{})
    tx.records=json.loads(content(backup/'transaction.json'))
    conflicts=tx.rollback()
    print(json.dumps({'restored_unmodified_targets':True,'conflicts':conflicts},indent=2))
    raise SystemExit(1 if conflicts else 0)
