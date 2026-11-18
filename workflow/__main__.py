import argparse
import json
from .runtime import Runtime, read_json

def main():
    p = argparse.ArgumentParser(description='Run approved checks or inspect the deterministic quality gate')
    p.add_argument('action', choices=['prepare', 'run', 'gate', 'info'])
    p.add_argument('--settings', required=True); p.add_argument('--project'); p.add_argument('--contract')
    p.add_argument('--evidence', default='.quality/evidence.json'); p.add_argument('--review', action='append', default=[])
    a = p.parse_args()
    try:
        r = Runtime(read_json(a.settings))
        if a.action == 'info': value = r.info()
        elif a.action == 'prepare': value = r.prepare(a.project, a.contract)
        elif a.action == 'run': value = r.run(a.project, a.contract)
        else: value = r.gate(a.project, a.contract, a.evidence, a.review)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        if value.get('status') in ('BLOCKED', 'NEEDS_EVIDENCE') or any(l['status'] != 'PASS' for l in value.get('lanes', [])): return 1
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc)}, ensure_ascii=False)); return 2
if __name__ == '__main__': raise SystemExit(main())
