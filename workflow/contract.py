import hashlib
import json
from .schema import check

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def contract_id(contract):
    """Approval provenance is appended later; semantic changes invalidate reviews."""
    return digest({k: contract[k] for k in ('version', 'requirements', 'plan')})

def validate_contract(contract, policy, approved=True):
    errors = check(contract, 'contract') + check(policy, 'policy')
    if errors: return errors
    if approved and any(contract['approvals'][k].strip().upper() in ('PENDING', 'UNKNOWN', 'TODO') for k in ('design', 'plan')):
        errors.append('Actual recorded design and plan approval required')
    reqs = contract['requirements']; plan = contract['plan']
    groups = [('requirements', reqs), ('tasks', plan['tasks']),
              ('acceptance', plan['acceptance']), ('architecture', plan['architecture']),
              ('lanes', policy['lanes'])]
    for label, items in groups:
        ids = [i['id'] for i in items]
        if len(ids) != len(set(ids)): errors.append(label + ': duplicate id')
    rids = {r['id'] for r in reqs}; lids = {l['id'] for l in policy['lanes']}
    covered = set(); accepted = set()
    for task in plan['tasks']:
        for rid in task['requirements']:
            if rid not in rids: errors.append(task['id'] + ': unknown requirement ' + rid)
            covered.add(rid)
    for ac in plan['acceptance']:
        if ac['requirement'] not in rids: errors.append(ac['id'] + ': unknown requirement')
        if ac['lane'] not in lids: errors.append(ac['id'] + ': unknown lane')
        accepted.add(ac['requirement'])
    for rule in plan['architecture']:
        if rule['lane'] not in lids: errors.append(rule['id'] + ': unknown lane')
    for req in reqs:
        if req['required'] and (req['id'] not in covered or req['id'] not in accepted):
            errors.append(req['id'] + ': missing task or acceptance')
    for unknown in plan['unknowns']:
        if unknown['critical'] and not unknown['resolved']:
            errors.append('Unresolved critical fact: ' + unknown['question'])
    # Every referenced lane is mandatory, irrespective of its optional label.
    return errors
