from datetime import date
import json
from .contract import contract_id, validate_contract
from .evidence import validate_evidence
from .review import validate_review, risk_score
from .snapshot import snapshot
from .files import safe_quality_dir

def accepted_debt(f):
    d = f['defer']
    if f['severity'] not in ('low', 'nit') or f['origin'] != 'preexisting' or f['disposition'] != 'defer' or not d:
        return False
    try: valid = date.fromisoformat(d['until']) >= date.today()
    except (ValueError, KeyError): return False
    return valid and d.get('accepted_by') not in ('self', 'model', '')

def blocking_finding(f):
    return f['status'] == 'open' and not accepted_debt(f)

def review_history(root, supplied, cid):
    """Use every preserved round, not only the caller-selected clean report."""
    history = list(supplied); errors = []
    folders = [safe_quality_dir(root, 'reviews')]
    plan_folder = root / 'docs/superpowers/plans/reviews'
    current = root
    for part in ('docs', 'superpowers', 'plans', 'reviews'):
        current /= part
        if current.is_symlink(): raise ValueError('Symlink review history refused')
    folders.append(plan_folder)
    for folder in folders:
      if folder.exists():
        paths = list(folder.glob('*.json'))
        if len(paths) > 200: return [], ['Review history limit exceeded']
        for path in paths:
            try:
                if path.is_symlink() or path.stat().st_size > 2_000_000: raise ValueError()
                value = json.loads(path.read_text())
                if value.get('contract_id') == cid: history.append(value)
            except (ValueError, OSError, AttributeError): errors.append('Invalid preserved review round')
    rounds = {}
    for r in history:
        invalid = validate_review(r, require_complete=False)
        if invalid:
            errors += invalid; continue
        if r['contract_id'] != cid:
            errors.append('Review has stale contract'); continue
        key = (r['kind'], r.get('round', 1))
        if key in rounds and rounds[key] != r: errors.append('Conflicting review round')
        rounds[key] = r
    latest = {}
    for (kind, number), r in sorted(rounds.items()): latest[kind] = r
    return (rounds, latest), errors

def evaluate_plan(root, contract, policy, reviews):
    """Document-only plan readiness, intentionally independent of execution evidence."""
    errors = validate_contract(contract, policy, approved=False)
    if errors: return {'status': 'BLOCKED', 'reasons': errors}
    cid = contract_id(contract)
    # Old semantic contracts remain provenance, not current acceptance pointers.
    applicable = [r for r in reviews if isinstance(r, dict) and r.get('contract_id') == cid and r.get('kind') == 'plan']
    history, errors = review_history(root, applicable, cid)
    if not history: return {'status': 'NEEDS_EVIDENCE', 'reasons': errors}
    rounds, latest = history; current = latest.get('plan')
    if not current: return {'status': 'NEEDS_EVIDENCE', 'reasons': errors + ['Missing independent plan review']}
    errors += validate_review(current)
    if current['reviewer']['agent'] != 'cloud-plan-review': errors.append('Plan reviewer role mismatch')
    for f in current['findings']:
        if f['status'] == 'resolved' and f.get('resolution_evidence') != 'contract:' + cid:
            errors.append('Resolved plan finding lacks current contract verification')
    closures = {c['id']: c for c in current.get('closed_findings', [])}; blockers = []
    for (kind, number), old in rounds.items():
        if kind != 'plan' or number >= current.get('round', 1): continue
        for f in old['findings']:
            if not blocking_finding(f): continue
            ref = 'plan:' + str(number) + ':' + f['id']
            if closures.get(ref, {}).get('evidence') != 'contract:' + cid:
                blockers.append('Plan finding not independently closed: ' + ref)
    blockers += [f['id'] + ': ' + f['title'] for f in current['findings'] if blocking_finding(f)]
    return {'status': 'BLOCKED' if blockers else 'NEEDS_EVIDENCE' if errors else 'PASS',
            'reasons': blockers + errors, 'contract_id': cid, 'scope': 'Plan readiness only, no implementation/test execution claimed'}

def evaluate_gate(root, contract, policy, evidence, reviews):
    errors = validate_contract(contract, policy)
    if errors: return {'status': 'BLOCKED', 'reasons': errors}
    try:
        errors += validate_evidence(root, contract, policy, evidence)
        sid = snapshot(root)['id']
    except (ValueError, OSError, TypeError):
        return {'status': 'NEEDS_EVIDENCE', 'reasons': ['Unreadable/invalid evidence or source']}
    if errors: return {'status': 'NEEDS_EVIDENCE', 'reasons': errors}
    if type(reviews) is not list: return {'status': 'NEEDS_EVIDENCE', 'reasons': ['Reviews must be a list']}
    cid = contract_id(contract); kinds = set(); sessions = set(); debt = []; blockers = []
    try: history, invalid = review_history(root, reviews, cid)
    except (OSError, ValueError): return {'status': 'NEEDS_EVIDENCE', 'reasons': ['Invalid review history']}
    errors += invalid
    if not history: return {'status': 'NEEDS_EVIDENCE', 'reasons': errors}
    rounds, latest = history
    configs = {l['id']: l for l in policy['lanes']}
    lane_ids = {l['id'] for l in evidence['lanes']
                if l['id'] in configs and l['status'] == 'PASS' and l['exit_code'] == 0
                and l['checks'] >= configs[l['id']]['min_checks'] and not l['skipped'] and not l['failures']}
    valid_resolutions = {sid + ':' + lid for lid in lane_ids}
    for (kind, number), old in rounds.items():
        current = latest[kind]
        if number >= current.get('round', 1): continue
        closures = {c['id']: c for c in current.get('closed_findings', [])}
        for f in old['findings']:
            if not blocking_finding(f): continue
            ref = kind + ':' + str(number) + ':' + f['id']
            closure = closures.get(ref)
            permitted = valid_resolutions | ({'contract:' + cid} if kind == 'plan' else set())
            if not closure or closure['evidence'] not in permitted:
                blockers.append('Historical finding not explicitly reverified: ' + ref)
    for review in latest.values():
        invalid = validate_review(review)
        if invalid:
            errors += invalid; continue
        kind = review['kind']
        expected_agent = {'plan': 'cloud-plan-review', 'code': 'cloud-review',
                          'structure': 'cloud-structure-review', 'tests': 'cloud-test-review'}[kind]
        if review['reviewer']['agent'] != expected_agent: errors.append('Reviewer role mismatch')
        session = review['reviewer']['session']
        if session in sessions: errors.append('Independent review sessions required')
        sessions.add(session)
        if kind in kinds: errors.append('Duplicate review kind: ' + kind)
        kinds.add(kind)
        if review['contract_id'] != cid: errors.append('Review has stale contract')
        if kind != 'plan' and review['snapshot_id'] != sid: errors.append('Review has stale source')
        for f in review['findings']:
            if f['status'] == 'resolved':
                permitted = valid_resolutions | ({'contract:' + cid} if kind == 'plan' else set())
                if f.get('resolution_evidence') not in permitted: errors.append('Resolution lacks current verification evidence')
                continue
            if blocking_finding(f):
                blockers.append(f['id'] + ': ' + f['title']); continue
            debt.append({'id': f['id'], 'risk_score': risk_score(f), 'defer': f['defer']})
    needed = {'plan', 'code'}
    if contract['plan']['risk'] in ('medium', 'high'): needed |= {'structure', 'tests'}
    errors += ['Missing review: ' + k for k in sorted(needed - kinds)]
    return {'status': 'BLOCKED' if blockers else 'NEEDS_EVIDENCE' if errors else 'PASS_WITH_DEBT' if debt else 'PASS',
            'reasons': blockers + errors, 'debt': debt, 'contract_id': cid, 'snapshot_id': sid}
