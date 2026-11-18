import hashlib
import json
import uuid
import fcntl
from pathlib import Path
from .contract import digest, contract_id
from .runner import run_lane
from .snapshot import snapshot
from .files import safe_quality_dir, atomic_json

def collect_evidence(root, contract, policy, output):
    lock_path = safe_quality_dir(root) / 'run.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.is_symlink(): raise ValueError('Symlink run lock refused')
    with lock_path.open('a') as lock:
        try: fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('A verification attempt is already running') from None
        return _collect(root, contract, policy, output)

def _collect(root, contract, policy, output):
    run_id = uuid.uuid4().hex
    runs = safe_quality_dir(root, 'runs'); runs.mkdir(parents=True, exist_ok=True)
    key = digest([contract_id(contract), digest(policy)])
    latest = safe_quality_dir(root) / 'latest.json'
    index = json.loads(latest.read_text()) if latest.exists() else {}
    index[key] = run_id
    # Publish the latest attempt BEFORE execution: interrupted attempts invalidate old PASS.
    atomic_json(runs / (run_id + '-started.json'), {'run_id': run_id, 'contract_id': contract_id(contract), 'policy_id': digest(policy)})
    atomic_json(latest, index)
    lanes = [run_lane(root, lane, output) for lane in policy['lanes']]
    result = {'version': 1, 'run_id': run_id, 'contract_id': contract_id(contract), 'policy_id': digest(policy),
              'snapshot_id': snapshot(root)['id'], 'lanes': lanes}
    atomic_json(runs / (run_id + '.json'), result)
    return result

def validate_evidence(root, contract, policy, evidence):
    from .schema import check
    errors = check(evidence, 'evidence')
    if errors: return errors
    current = snapshot(root)['id']
    if evidence['contract_id'] != contract_id(contract): errors.append('Contract changed')
    if evidence['policy_id'] != digest(policy): errors.append('Policy changed')
    if evidence['snapshot_id'] != current: errors.append('Stale source snapshot')
    try:
        folder = safe_quality_dir(root, 'runs')
        latest = json.loads((safe_quality_dir(root) / 'latest.json').read_text())
        key = digest([contract_id(contract), digest(policy)])
        if latest.get(key) != evidence['run_id']: errors.append('Evidence is not the latest verification attempt')
        receipt = folder / (evidence['run_id'] + '.json')
        if receipt.is_symlink() or json.loads(receipt.read_text()) != evidence: errors.append('Run receipt mismatch')
    except (OSError, ValueError, KeyError): errors.append('Missing/invalid verification attempt receipt')
    ids = [l['id'] for l in evidence['lanes']]
    if len(ids) != len(set(ids)): errors.append('Duplicate lane evidence')
    configured = {l['id']: l for l in policy['lanes']}
    referenced = {a['lane'] for a in contract['plan']['acceptance']} | {a['lane'] for a in contract['plan']['architecture']}
    required = referenced | {l['id'] for l in policy['lanes'] if l['required']}
    for lid in required - set(ids): errors.append('Missing lane: ' + lid)
    for lane in evidence['lanes']:
        config = configured.get(lane['id'])
        if not config:
            errors.append('Unknown lane'); continue
        if lane['id'] in required:
            if lane['status'] != 'PASS' or lane['exit_code'] != 0 or lane['checks'] < config['min_checks'] or lane['skipped'] or lane['failures']:
                errors.append('Lane did not pass: ' + lane['id'])
        if lane['command'] != config['argv'] or lane['cwd'] != str(Path(root).resolve()): errors.append('Command/cwd mismatch')
        if lane['before'] != current or lane['after'] != current: errors.append('Lane tested different bytes')
        try:
            p = Path(lane['log'])
            if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != lane['log_sha256']:
                errors.append('Log changed')
        except OSError: errors.append('Missing log')
    return errors
