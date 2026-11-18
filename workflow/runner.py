"""Execute an already-approved argv; never accept commands from review text."""
import hashlib
import json
import os
import platform
import re
import signal
import subprocess
import time
import uuid
from pathlib import Path
from .snapshot import snapshot

def run_lane(root, lane, output):
    root = Path(root).resolve(strict=True); output = Path(output).resolve()
    # Artifacts must be outside source or in the reserved evidence directory.
    if output == root or root in output.parents:
        relative = output.relative_to(root).as_posix()
        if not (relative == '.quality' or relative.startswith('.quality/') or
                relative == 'docs/superpowers/evidence' or relative.startswith('docs/superpowers/evidence/')):
            raise ValueError('Output must be outside source snapshot')
    output.mkdir(parents=True, exist_ok=True)
    before = snapshot(root); start = time.time(); code = None; text = ''; reason = ''
    process = None
    try:
        process = subprocess.Popen(lane['argv'], cwd=root, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        raw, _ = process.communicate(timeout=lane['timeout']); code = process.returncode
        text = raw.decode('utf-8', errors='replace')
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL); raw, _ = process.communicate()
        text = raw.decode('utf-8', errors='replace'); reason = 'timeout'
    except OSError as exc:
        reason = 'execution unavailable: ' + type(exc).__name__
    after = snapshot(root); count = 0; skipped = 0; failures = 0
    if lane['parser'] == 'unittest':
        matches = re.findall(r'^Ran (\d+) tests? in ', text, re.M)
        count = int(matches[-1]) if matches else 0
        skips = re.findall(r'skipped=(\d+)', text); skipped = int(skips[-1]) if skips else 0
        if not re.search(r'^OK(?:\s|$)', text, re.M): failures = 1
    elif lane['parser'] == 'json':
        try:
            result = json.loads(text.strip())
            count, skipped, failures = (result[k] for k in ['checks', 'skipped', 'failures'])
            if any(type(v) is not int or v < 0 for v in [count, skipped, failures]): raise ValueError()
        except (ValueError, KeyError, TypeError):
            count = 0; reason = 'missing/invalid structured result'
    else: reason = 'unsupported result parser'
    if code != 0 or count < lane['min_checks'] or skipped or failures: reason = reason or 'failed/skipped/empty checks'
    if before['id'] != after['id']: reason = 'source changed during verification'
    log = output / (lane['id'] + '-' + uuid.uuid4().hex + '.log')
    log.write_text(text); log.chmod(0o600)
    return {'id': lane['id'], 'status': 'FAIL' if reason else 'PASS', 'reason': reason,
            'command': lane['argv'], 'cwd': str(root), 'exit_code': code, 'checks': count,
            'skipped': skipped, 'failures': failures, 'started': start, 'finished': time.time(),
            'runtime': platform.python_version(), 'before': before['id'], 'after': after['id'],
            'log': str(log), 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()}
