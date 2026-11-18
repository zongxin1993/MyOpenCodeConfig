"""Narrow local registration: no commands and no project writes."""
import copy
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import uuid
import subprocess
from .files import atomic_json

AUTHORITY_NAMES = ('PROJECT_CONSTITUTION.md', 'AGENTS.md', 'quality-policy.toml')
PROJECT_MARKERS = (*AUTHORITY_NAMES, 'README.md', 'package.json', 'pyproject.toml', 'Cargo.toml',
                   'go.mod', 'Makefile', 'CMakeLists.txt', 'pom.xml', 'build.gradle', 'deno.json')
INSTRUCTIONS = (
    'Automatically discovered repository-native project. Before creating files, read the listed '
    'project rules and actual user task. With no authority files, do not invent rules: use the '
    'confirmed task context and inspect the actual new project. Keep plans, approval quotes, '
    'review findings and progress in task context or the repository-authorized system. '
    'Do not create portable specs/contracts/.quality protocols or a competing acceptance authority. '
    'Cloud plans and independently audits; the same local worker implements, tests and repairs. '
    'Discover actual verification entry points and choose checks by task impact; no commands, '
    'dependencies, environments or passing evidence were approved or executed by registration. '
    'Preserve required independent review, issue severity/impact/confidence, repair value/cost '
    'and explicit deferral decisions. Missing evidence blocks completion. Resolve actual rule '
    'conflicts with the user instead of weakening checks. REPOSITORY_NATIVE_REQUIRED is not PASS.'
)


@contextmanager
def registry_lock(path):
    path = Path(path).absolute()
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('Symlink registry refused')
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + '.lock')
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode): raise ValueError('Invalid registry lock')
        fcntl.flock(fd, fcntl.LOCK_EX)
        if path.is_symlink(): raise ValueError('Symlink registry refused')
        yield path
    finally:
        os.close(fd)


def specific_root(project):
    path = Path(project)
    if not path.is_absolute(): raise ValueError('Use the absolute current project directory')
    root = path.resolve(strict=True)
    if root in (Path('/'), Path.home().resolve()) or not root.is_dir():
        raise ValueError('Use a specific project, not home or filesystem root')
    return root


def discover(root, registered=()):
    candidates = []
    git_root = None
    for candidate in (root, *root.parents):
        if candidate in (Path('/'), Path.home().resolve()): break
        candidates.append(candidate)
        marker = candidate / '.git'
        if marker.is_symlink(): raise ValueError('Symlink Git marker refused')
        if marker.is_dir() or marker.is_file():
            root = candidate
            git_root = candidate
            break
    if git_root is None:
        for candidate in candidates:
            if str(candidate) in registered or any((candidate / n).exists() for n in PROJECT_MARKERS):
                root = candidate
                break
    names = []
    markers = []
    for name in PROJECT_MARKERS:
        path = root / name
        if path.is_symlink(): raise ValueError('Symlink project rule refused')
        if path.exists():
            if not path.is_file() or path.stat().st_size > 262144:
                raise ValueError('Unsupported/oversized project rule; do not truncate')
            markers.append(name)
            if name in AUTHORITY_NAMES: names.append(name)
    marker = root / '.git'
    if not markers and not (marker.is_dir() or marker.is_file()) and str(root) not in registered:
        raise ValueError('No project markers; initialise the authorised project before onboarding')
    return root, {'mode': 'repository-native', 'authorities': names, 'instructions': INSTRUCTIONS}


def linked_registration(requested, settings):
    """Map a genuine linked worktree to its nearest already registered profile."""
    def git_paths(directory):
        try:
            value = subprocess.check_output(['git', '-C', str(directory), 'rev-parse',
                '--path-format=absolute', '--git-dir', '--git-common-dir', '--show-toplevel'],
                text=True, stderr=subprocess.DEVNULL, timeout=10).strip().splitlines()
            return tuple(Path(p).resolve(strict=True) for p in value) if len(value) == 3 else None
        except (OSError, subprocess.SubprocessError): return None
    paths = git_paths(requested)
    if paths is None: return None
    git_dir, common, checkout = paths
    if git_dir == common or common / 'worktrees' not in git_dir.parents: return None
    matches = []
    for project in settings['projects']:
        source = Path(project['root']).resolve(strict=True); other = git_paths(source)
        if other is None or other[1] != common: continue
        relative = source.relative_to(other[2]); mapped = checkout / relative
        if mapped != requested and mapped not in requested.parents: continue
        entry = copy.deepcopy(project); entry['root'] = str(mapped)
        # Fixed executable policies must never accidentally run against the original checkout.
        for lane in entry.get('policy', {}).get('lanes', []):
            values = [arg.split('=', 1)[-1] if arg.startswith('-') else arg for arg in lane['argv']]
            if any(arg == str(source) or arg.startswith(str(source) + os.sep) for arg in values):
                raise ValueError('Policy points at source checkout; adapt before worktree execution')
        matches.append((len(mapped.parts), entry))
    if not matches: return None
    deepest = max(depth for depth, _ in matches)
    candidates = [entry for depth, entry in matches if depth == deepest]
    if any({k:v for k,v in entry.items() if k!='root'} !=
           {k:v for k,v in candidates[0].items() if k!='root'} for entry in candidates):
        raise ValueError('Conflicting profiles for the same Git worktree; reconcile explicitly')
    return candidates[0]


def onboard(settings_path, project):
    from .runtime import Runtime, read_json
    requested = specific_root(project)
    with registry_lock(settings_path) as path:
        settings = read_json(path)
        current = Runtime(settings)
        # Never bypass an explicit project policy, including an enclosing policy
        # when a child contains its own Git marker or manifest. Nearest wins.
        ancestors = [Path(p) for p in current.projects if Path(p) == requested or Path(p) in requested.parents]
        if ancestors:
            root = max(ancestors, key=lambda p: len(p.parts))
        else:
            inherited = linked_registration(requested, settings)
            if inherited:
                root = Path(inherited['root'])
            else:
                root, integration = discover(requested, current.projects)
        if str(root) in current.projects:
            profile = current.info()['project_profiles'][str(root)]
            return {'status': 'ONBOARDING_READY', 'onboarding': 'reused', 'project': str(root),
                    **profile, 'acceptance_pass': False, 'backup_created': False}
        updated = copy.deepcopy(settings)
        entry = inherited if inherited else {'root': str(root), 'integration': integration}
        updated['projects'].append(entry)
        Runtime(updated)
        backups = path.parent / 'backups'
        if backups.is_symlink(): raise ValueError('Symlink backup directory refused')
        backups.mkdir(mode=0o700, exist_ok=True)
        backup = backups / ('auto-register-' + uuid.uuid4().hex + '.json')
        with backup.open('xb') as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(path.read_bytes())
        atomic_json(path, updated)
        profile = entry.get('integration', {'mode': 'portable'})
        return {'status': 'ONBOARDING_READY', 'onboarding': 'registered', 'project': str(root),
                **profile, 'acceptance_pass': False, 'backup_created': True}
