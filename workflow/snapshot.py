import hashlib
import os
from pathlib import Path
from .contract import digest

EXCLUDED_DIRS = {'.git', '.quality', '__pycache__', '.venv', 'node_modules', 'target', '.pytest_cache'}
EXCLUDED_PREFIX = 'docs/superpowers/evidence/'

def snapshot(root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir(): raise ValueError('Project must be a directory')
    files = {}; total = 0
    for directory, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            if (Path(directory) / name).is_symlink(): raise ValueError('Symlink refused: ' + name)
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
        for name in sorted(names):
            path = Path(directory) / name; relative = path.relative_to(root).as_posix()
            if relative.startswith(EXCLUDED_PREFIX): continue
            if name.startswith('.env') or name.endswith(('.pyc', '.log')): continue
            if not path.is_file(): raise ValueError('Nonregular file refused: ' + relative)
            total += path.stat().st_size
            if total > 100_000_000 or len(files) >= 10000: raise ValueError('Snapshot limit exceeded')
            # Executable mode affects behavior even when source bytes are unchanged.
            files[relative] = format(path.stat().st_mode & 0o777, '03o') + ':' + hashlib.sha256(path.read_bytes()).hexdigest()
    if not files: raise ValueError('Empty source snapshot')
    return {'id': digest(files), 'files': files,
            'exclusions': sorted(EXCLUDED_DIRS) + [EXCLUDED_PREFIX, '.env*', '*.pyc', '*.log']}
