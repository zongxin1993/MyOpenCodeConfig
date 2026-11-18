import json
import os
from pathlib import Path
import tempfile

def safe_quality_dir(root, suffix=''):
    root = Path(root).resolve(strict=True)
    result = root / '.quality'
    for part in ['.quality'] + ([p for p in Path(suffix).parts] if suffix else []):
        if part in ('..', '/') or Path(part).is_absolute(): raise ValueError('Unsafe evidence directory')
    current = root
    for part in ['.quality'] + list(Path(suffix).parts):
        current /= part
        if current.is_symlink(): raise ValueError('Symlink evidence directory refused')
    result = root / '.quality' / suffix
    if root not in result.resolve().parents: raise ValueError('Evidence directory escaped project')
    return result

def atomic_json(path, value):
    path = Path(path)
    if path.is_symlink(): raise ValueError('Symlink output refused')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as f:
            os.fchmod(f.fileno(), 0o600)
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)
