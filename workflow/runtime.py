"""Registered projects and frozen command policies; MCP methods are read-only."""
import json
from pathlib import Path
from .contract import digest, contract_id, validate_contract
from .snapshot import snapshot
from .gate import evaluate_gate, evaluate_plan
from .evidence import collect_evidence
from .schema import check
from .files import safe_quality_dir, atomic_json

def read_json(path):
    def reject_constant(value): raise ValueError('Nonfinite JSON number')
    return json.loads(Path(path).read_text(), parse_constant=reject_constant)

def project_file(root, relative):
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts: raise ValueError('Use a relative artifact path')
    if not (str(p).startswith('docs/superpowers/specs/') or
            str(p).startswith('docs/superpowers/plans/') or str(p).startswith('.quality/')):
        raise ValueError('Artifact must be in specs, plans, or .quality')
    if p.suffix != '.json': raise ValueError('JSON artifacts only')
    target = (root / p).resolve(strict=True)
    if root not in target.parents: raise ValueError('Artifact escaped registered root')
    current = root
    for part in p.parts:
        current /= part
        if current.is_symlink(): raise ValueError('Symlink artifact refused')
    if target.stat().st_size > 2_000_000: raise ValueError('Artifact too large')
    return target

class Runtime:
    def __init__(self, settings):
        if set(settings) != {'projects'} or type(settings['projects']) is not list:
            raise ValueError('Settings must contain projects only')
        self.projects = {}
        for project in settings['projects']:
            if set(project) != {'root', 'policy'} or check(project['policy'], 'policy'):
                raise ValueError('Invalid registered project/policy')
            root = Path(project['root']).resolve(strict=True)
            if root == Path.home() or root == Path('/') or not root.is_dir():
                raise ValueError('Register a specific project, not home or filesystem root')
            if str(root) in self.projects: raise ValueError('Duplicate project')
            self.projects[str(root)] = project['policy']
    def root(self, project):
        root = Path(project).resolve(strict=True)
        if str(root) not in self.projects: raise ValueError('Project not registered')
        return root
    def info(self):
        return {'projects': list(self.projects), 'tools_read_only': True,
                'resources': list(self._resources()),
                'note': 'Commands run only through the local CLI; resources are fixed public package assets, not user files'}
    def _resources(self):
        package = Path(__file__).resolve().parents[1]
        resources = {'schema/' + p.name.removesuffix('.schema.json'): p for p in (package / 'schemas').glob('*.schema.json')}
        example = package / 'examples/contract.example.json'
        if example.is_file(): resources['example/contract'] = example
        provenance = package / 'integrations/bmad/provenance.json'
        if provenance.is_file():
            data = read_json(provenance)
            for mode in ('quick', 'thorough'):
                entry = Path(data['rendered'][mode]); directory = entry.parent.resolve()
                if package not in directory.parents: raise ValueError('Invalid bundled resource manifest')
                manifest = read_json(directory / 'manifest.json')
                for relative in manifest['outputs']:
                    target = (directory / relative).resolve()
                    if directory not in target.parents: raise ValueError('Invalid bundled resource path')
                    resources['bmad/' + mode + '/' + relative] = target
        return resources
    def resource(self, name):
        # No caller-supplied filesystem path: allowlist only deployed public assets.
        resources = self._resources()
        if name not in resources: raise ValueError('Unknown public package resource')
        target = resources[name]
        if target.is_symlink() or target.stat().st_size > 2_000_000: raise ValueError('Unsafe public resource')
        package = Path(__file__).resolve().parents[1]
        release = package / 'release.json'
        if release.exists():
            import hashlib
            expected = read_json(release)['files'].get(target.relative_to(package).as_posix())
            if not expected or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                raise ValueError('Bundled public resource integrity mismatch')
        text = target.read_text()
        for key, path in sorted(resources.items(), key=lambda x: len(str(x[1])), reverse=True):
            text = text.replace(str(path), 'quality_resource:' + key)
        text = text.replace(str(package), 'quality-runtime:')
        return {'name': name, 'content': text,
                'source': 'Pinned public package resource; no project/user directory contents'}
    def prepare(self, project, contract, plan_reviews=None):
        root = self.root(project); c = read_json(project_file(root, contract)); p = self.projects[str(root)]
        issues = validate_contract(c, p, approved=False)
        result = {'contract_valid': not issues, 'issues': issues, 'contract_id': contract_id(c),
                'policy_id': digest(p), 'snapshot': snapshot(root),
                'lanes': [{k: lane[k] for k in ('id', 'parser', 'environment', 'min_checks', 'required')} for lane in p['lanes']],
                'required_reviews': ['plan', 'code'] + ([] if c.get('plan', {}).get('risk') == 'low' else ['structure', 'tests'])}
        if plan_reviews is not None:
            if not isinstance(plan_reviews, list) or len(plan_reviews) > 20: raise ValueError('Invalid plan review list')
            reviews = [read_json(project_file(root, f)) for f in plan_reviews]
            result['plan_gate'] = evaluate_plan(root, c, p, reviews)
        return result
    def gate(self, project, contract, evidence, reviews):
        root = self.root(project); c = read_json(project_file(root, contract)); p = self.projects[str(root)]
        e = read_json(project_file(root, evidence))
        if type(reviews) is not list or len(reviews) > 4: raise ValueError('Up to four review artifacts')
        rs = [read_json(project_file(root, f)) for f in reviews]
        # Do not let a caller use log references to probe arbitrary local files.
        for lane in e.get('lanes', []):
            log = Path(lane.get('log', '')).resolve()
            if not any(base == log.parent or base in log.parents for base in
                       [root / '.quality', root / 'docs/superpowers/evidence']):
                raise ValueError('Log outside project evidence directory')
        return evaluate_gate(root, c, p, e, rs)
    def run(self, project, contract):
        root = self.root(project); c = read_json(project_file(root, contract)); p = self.projects[str(root)]
        errors = validate_contract(c, p)
        if errors: raise ValueError('; '.join(errors))
        logs = safe_quality_dir(root, 'logs')
        result = collect_evidence(root, c, p, logs)
        output = safe_quality_dir(root) / 'evidence.json'
        # Refuse symlink outputs and parents rather than writing through them.
        if output.is_symlink() or output.parent.is_symlink(): raise ValueError('Unsafe output')
        atomic_json(output, result)
        return {'evidence': '.quality/evidence.json', 'lanes': [{k: l[k] for k in ['id', 'status', 'reason']} for l in result['lanes']]}
