"""Small Python static import check; explicit scope, not semantic architecture proof."""
import argparse
import ast
import json
from pathlib import Path

def check_structure(root, sources, forbidden):
    root = Path(root).resolve(strict=True); files = set(); rules = []
    for pair in forbidden:
        parts = pair.split(':')
        if len(parts) != 2 or not all(parts): raise ValueError('Use source.module:forbidden.module')
        rules.append(parts)
    for source in sources:
        try: p = (root / source).resolve(strict=True)
        except OSError: raise ValueError('Missing source target') from None
        if root not in p.parents: raise ValueError('Source escaped root')
        files.update(p.rglob('*.py') if p.is_dir() else [p])
    if not files: raise ValueError('No source targets')
    violations = []
    for path in sorted(files):
        if path.is_symlink() or root not in path.resolve().parents: raise ValueError('Unsafe source target')
        module = '.'.join(path.relative_to(root).with_suffix('').parts)
        if module.endswith('.__init__'): module = module[:-9]
        tree = ast.parse(path.read_text(), filename=str(path))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): imports.extend((alias.name, node.lineno) for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ''
                if node.level:
                    package = module.split('.') if path.name == '__init__.py' else module.split('.')[:-1]
                    if node.level > 1: package = package[:-(node.level - 1)]
                    base = '.'.join(package + ([base] if base else []))
                imports.append((base, node.lineno))
                imports.extend((base + '.' + alias.name, node.lineno) for alias in node.names)
        for source, target in rules:
            if module != source and not module.startswith(source + '.'): continue
            for imported, line in imports:
                if imported == target or imported.startswith(target + '.'):
                    violations.append({'module': module, 'line': line, 'forbidden_import': imported})
    return {'checks': len(files), 'skipped': 0, 'failures': len(violations), 'violations': violations}

def main():
    p = argparse.ArgumentParser(); p.add_argument('--root', default='.')
    p.add_argument('--source', action='append', required=True); p.add_argument('--forbid', action='append', default=[])
    a = p.parse_args()
    try:
        result = check_structure(a.root, a.source, a.forbid); print(json.dumps(result)); return bool(result['failures'])
    except (OSError, ValueError, SyntaxError) as exc:
        print(json.dumps({'checks': 0, 'skipped': 0, 'failures': 1, 'error': str(exc)})); return 2
if __name__ == '__main__': raise SystemExit(main())
