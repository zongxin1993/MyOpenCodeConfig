from .schema import check

def validate_review(review, require_complete=True):
    errors = check(review, 'review')
    if errors: return errors
    if require_complete and not review['complete']: errors.append('Review incomplete')
    ids = [f['id'] for f in review['findings']] + [f['id'] for f in review['rejections']]
    if len(ids) != len(set(ids)): errors.append('Duplicate finding/rejection id')
    for finding in review['findings']:
        if finding['status'] == 'resolved' and not finding.get('resolution_evidence'):
            errors.append(finding['id'] + ': resolution evidence required')
    return errors

def risk_score(finding):
    r = finding['risk']; weights = {'impact': .4, 'likelihood': .25, 'breadth': .2, 'time': .15}
    if any(r[k] is None for k in weights): return None
    return round(20 * sum(weights[k] * r[k] for k in weights), 1)
