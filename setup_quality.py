#!/usr/bin/env python3
"""Prepare pinned BMAD outputs, back up, and install the portable quality runtime."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import configure
from workflow.runtime import Runtime, read_json
from workflow.schema import check

ROOT = Path(__file__).resolve().parent
MARKER = 'Managed-By: MyOpenCodeConfig quality'

def plugin_preferences(home, models):
    """Merge only integration-critical preferences; never credentials or other UI choices."""
    desired = {}
    extensions = models.get('extensions', {})
    if extensions.get('plannotator'):
        desired[home / '.plannotator/config.json'] = {'agentSwitch': 'disabled'}
    if extensions.get('quota'):
        desired[home / '.config/opencode/opencode-quota/settings.jsonc'] = {
            'version': 6, 'providers': {'checking': {'waitForQuotaReset': False}},
            'system': {'exportFile': False, 'telemetry': False}}
    def merge(current, values):
        for key, value in values.items():
            if isinstance(value, dict):
                old = current.get(key, {})
                if not isinstance(old, dict): raise ValueError('Invalid plugin preference object')
                current[key] = merge(copy.deepcopy(old), value)
            else: current[key] = value
        return current
    result = {}
    for path, values in desired.items():
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Symlink plugin preference refused')
        current = read_json(path) if path.exists() else {}
        if not isinstance(current, dict): raise ValueError('Plugin preferences must be a JSON object')
        result[path] = merge(current, values)
    return result

def preflight_skill(path):
    if path.is_symlink(): raise ValueError('Refuse foreign skill symlink: ' + path.name)
    if path.exists() and (not (path / 'SKILL.md').is_file() or MARKER not in (path / 'SKILL.md').read_text()):
        raise ValueError('Refuse foreign skill: ' + path.name)

def merge_registration(settings, project, policy, integration=None):
    result = copy.deepcopy(settings)
    if project is not None:
        if integration is None and check(policy, 'policy'): raise ValueError('Invalid project policy')
        if integration is not None and policy is not None: raise ValueError('Native profile cannot have portable policy')
        root = str(Path(project).resolve(strict=True))
        result['projects'] = [p for p in result['projects'] if p['root'] != root]
        entry = {'root': root, 'integration': copy.deepcopy(integration)} if integration is not None else {'root': root, 'policy': copy.deepcopy(policy)}
        result['projects'].append(entry)
    Runtime(result)  # validates exact roots and policies before any configuration write
    return result

def prepare_runtime(source, render_python, destination):
    lock = read_json(ROOT / 'integrations/bmad/lock.json')
    source = Path(source).resolve(strict=True)
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    origin = subprocess.check_output(['git', '-C', str(source), 'remote', 'get-url', 'origin'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip()
    if head != lock['commit'] or origin != lock['repository'] or dirty:
        raise ValueError('BMAD checkout must be clean, official, and at the pinned commit')
    # The release name changes whenever shipped execution/protocol/skill resources change.
    paths = [ROOT / 'configure.py', ROOT / 'templates.json']
    for folder in ['workflow', 'schemas', 'skills', 'integrations', 'examples', 'plugins']:
        paths += [p for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    identity = hashlib.sha256()
    for p in sorted(paths):
        identity.update(p.relative_to(ROOT).as_posix().encode()); identity.update(p.read_bytes())
    release = destination / identity.hexdigest()[:20]
    manifest_path = release / 'release.json'
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        for relative, expected in manifest['files'].items():
            p = release / relative
            if p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
                raise ValueError('Installed runtime was modified; refusing silent overwrite')
        return release, manifest['bmad']
    if release.exists(): raise ValueError('Incomplete runtime directory; inspect before retrying')
    release.mkdir(parents=True)
    try:
        for folder in ['workflow', 'schemas', 'examples', 'integrations', 'plugins', 'skills']:
            shutil.copytree(ROOT / folder, release / folder, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for name in ['configure.py','templates.json']:
            shutil.copy2(ROOT/name,release/name)
        # Keep complete supporting BMAD resources, never merely SKILL.md.
        for sub in ['skills/method/bmad-code-review', 'skills/core-tools/bmad/scripts']:
            shutil.copytree(source / sub, release / 'upstream/bmad' / sub,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for name in ['LICENSE', 'README.md']:
            shutil.copy2(source / name, release / 'upstream/bmad' / name)
        workspace = release / 'bmad-runtime'; (workspace / '_bmad').mkdir(parents=True)
        (workspace / '_bmad/config.toml').write_text('[core]\noutput_folder = "{project-root}/reports"\n')
        # Official renderer rejects overrides not consumed by the selected mode.
        overrides = release / 'integrations/bmad/overrides.toml'
        quick_overrides = release / 'integrations/bmad/quick-overrides.toml'
        quick_overrides.write_text(overrides.read_text().split('[[workflow.thorough_lenses]]')[0])
        rendered = {}
        for mode in ['quick', 'thorough']:
            script = release / 'upstream/bmad' / lock['renderer']
            command = [str(render_python), str(script), '--project-root', str(workspace),
                       '--skill', str(release / 'upstream/bmad' / lock['skill']),
                       '--overrides', str(quick_overrides if mode == 'quick' else overrides),
                       '--set', 'workflow.review=' + mode]
            result = subprocess.run(command, capture_output=True, text=True, timeout=90)
            if result.returncode or 'HALT:' in result.stdout:
                raise ValueError('Official BMAD rendering failed: ' + (result.stdout + result.stderr)[-1500:])
            matches = []
            for m in workspace.rglob('manifest.json'):
                d = read_json(m)
                if d['inputs']['resolved_values'].get('customization.workflow.review') == mode:
                    matches.append(m.parent / 'workflow.md')
            if len(matches) != 1: raise ValueError('Cannot identify rendered BMAD mode')
            rendered[mode] = str(matches[0])
        provenance = {'repository': lock['repository'], 'commit': head, 'release_line': lock['release_line'],
                      'rendered': rendered, 'host_adapter': 'quality-review',
                      'note': 'Official deployment-time renderer output; no project hooks or source edits at runtime'}
        (release / 'integrations/bmad/provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
        files = {p.relative_to(release).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in release.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        manifest_path.write_text(json.dumps({'files': files, 'bmad': rendered}, indent=2) + '\n')
        return release, rendered
    except BaseException:
        # Failed staging contains no active config; leave it for inspection, not a partial install.
        raise

def install(args):
    if args.apply:
        from workflow.registration import registry_lock
        with registry_lock(args.root.expanduser().resolve() / '.config/opencode-quality/settings.json'):
            return _install(args)
    return _install(args)

def _install(args):
    home = args.root.expanduser().resolve()
    from workflow.execution_setup import content,digest
    observed={}
    def observe(path):
        path=Path(path);observed.setdefault(path,digest(content(path)))
    for fixed in [home/'.config/opencode/opencode.json',home/'.config/opencode/.workflow-generated-state.json',home/'.config/opencode-quality/settings.json',home/'.plannotator/config.json',home/'.config/opencode/opencode-quota/settings.jsonc']:
        observe(fixed)
    config = home / '.config/opencode/opencode.json'; state = config.parent / '.workflow-generated-state.json'
    private = home / '.config/opencode-quality/settings.json'
    settings = read_json(private) if private.exists() else {'projects': []}
    integration = None
    if args.repository_native:
        integration = {'mode': 'repository-native', 'authorities': args.authority,
                       'instructions': args.native_instructions.read_text()}
    settings = merge_registration(settings, args.project, read_json(args.policy) if args.policy else None, integration)
    base = read_json(config); raw_config = config.read_bytes(); models = read_json(args.models)
    templates = read_json(ROOT / 'templates.json')
    previous = read_json(state) if state.exists() else None
    compiled, generated = configure.compile_config(base, models, templates, previous)
    preferences = plugin_preferences(home, models)
    from integrations.execution import parse_execution
    from workflow.execution_setup import plan_execution, FileTransaction, verify_owned_files, execution_skill_changes
    verify_owned_files((previous or {}).get('execution_skill_files',{}))
    execution_options=parse_execution(models.get('execution'))
    execution_plan=plan_execution(home,execution_options,read_json(ROOT/'integrations/execution.lock.json'),[p['root'] for p in settings['projects']])
    for plugin in compiled.get('plugins',[]):
        package=plugin if isinstance(plugin,str) else plugin.get('package','')
        if execution_options['rtk']['enabled'] and 'rtk' in package.lower() and 'execution-tools' not in package:raise ValueError('RTK package collision; reconcile before execution setup')

    targets = [home / '.agents/skills' / name for name in ['quality-planning', 'quality-review']]
    execution_targets=[home/'.agents/skills'/name for name in execution_plan['skills']]
    for target in targets:
        observe(target/'SKILL.md');preflight_skill(target)
    for target in execution_targets:
        for source in (ROOT/'skills'/target.name).rglob('*'):
            if source.is_file():observe(target/source.relative_to(ROOT/'skills'/target.name))
        if target.is_symlink() or target.exists() and ('Managed-By: MyOpenCodeConfig execution' not in (target/'SKILL.md').read_text()):raise ValueError('Foreign execution skill collision: '+target.name)

    execution_changes=execution_skill_changes(home,execution_plan['skills'],ROOT,(previous or {}).get('execution_skill_files',{}))
    servers = compiled.setdefault('mcp', {}).setdefault('servers', {})
    for p in execution_plan['remove']:observe(p)
    for p in (previous or {}).get('execution_skill_files',{}):observe(p)
    old_server = servers.get('quality')
    if old_server and 'myopencodeconfig/quality' not in str(old_server.get('cwd', '')):
        raise ValueError('Foreign MCP quality server already exists')
    # Validate the whole managed config before preparing/installing anything active.
    if not args.apply:
        return {'applied': False, 'projects': [p['root'] for p in settings['projects']],
                'roles': generated['roles'], 'execution':execution_plan, 'source_pin': read_json(ROOT / 'integrations/bmad/lock.json')['commit']}
    release, rendered = prepare_runtime(args.source, args.render_python,
                                        home / '.local/share/myopencodeconfig/quality')
    if 'routing_plugin' in generated:
        plugin = generated['routing_plugin']
        old_package = plugin['package']
        package = str(release / 'plugins/cloud-session-router')
        for entry in compiled['plugins']:
            if isinstance(entry, dict) and entry.get('package') == old_package:
                entry['package'] = package
        plugin['package'] = package
    for plugin in generated.get('extension_plugins', []):
        if plugin['package'] == str(ROOT / 'plugins/worktree-policy'):
            old_package = plugin['package']; package = str(release / 'plugins/worktree-policy')
            for entry in compiled.get('plugins', []):
                if isinstance(entry, dict) and entry.get('package') == old_package: entry['package'] = package
            plugin['package'] = package
    if 'execution_plugin' in generated:
        entry=generated['execution_plugin'];old_package=entry['package'];entry['package']=str(release/'plugins/execution-tools');entry['options']['tools']=execution_plan['tools']
        for plugin in compiled.get('plugins',[]):
            if isinstance(plugin,dict) and plugin.get('package')==old_package:plugin.update(copy.deepcopy(entry))
    for project in settings['projects']:

        for lane in project.get('policy', {}).get('lanes', []):
            lane['argv'] = [arg.replace('__QUALITY_RUNTIME__', str(release)) for arg in lane['argv']]
    Runtime(settings)
    server = {'type': 'local', 'command': [sys.executable, '-m', 'workflow.server', '--settings', str(private)],
              'cwd': str(release), 'codemode': False}
    servers['quality'] = server
    substitutions = {'__RUNTIME__': str(release), '__PYTHON__': sys.executable,
                     '__SETTINGS__': str(private), '__BMAD_QUICK__': rendered['quick'], '__BMAD_THOROUGH__': rendered['thorough']}
    skill_texts = {}
    for target in targets:
        text = (ROOT / 'skills' / target.name / 'SKILL.md').read_text()
        for token, value in substitutions.items(): text = text.replace(token, value)
        skill_texts[target.name] = text
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=config.parent/'backups'/('quality-workflow-'+stamp)
    changes={}
    for target,text in skill_texts.items():changes[home/'.agents/skills'/target/'SKILL.md']=text.encode()
    changes.update(execution_changes)
    # Remove only previously owned execution skill bytes; keep any external additions.
    current_skill_paths={str(p) for p in changes if '/.agents/skills/' in str(p)}
    for p,expected in (previous or {}).get('execution_skill_files',{}).items():
        if p not in current_skill_paths:
            target=Path(p)
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise ValueError('Managed skill modified externally: '+p)
            changes[target]=None
    generated['execution_skill_files']={str(p):hashlib.sha256(raw).hexdigest() for p,raw in changes.items() if raw is not None and any(str(p).startswith(str(t)+'/') for t in execution_targets)}
    for p in execution_plan['remove']:changes[Path(p)]=None
    for target,data in preferences.items():changes[target]=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
    for target,data in [(private,settings),(state,generated),(config,compiled)]:changes[target]=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
    from workflow.execution_setup import content
    if all(content(p)==raw for p,raw in changes.items()):return {'applied':False,'changed':False,'runtime':str(release)}
    tx=FileTransaction(backup,changes,expected=observed);tx.prepare()
    if config.read_bytes()!=raw_config:raise ValueError('Config changed concurrently; no active files written')
    tx.commit()
    return {'applied': True, 'backup': str(backup), 'runtime': str(release),
            'bmad': rendered, 'projects': [p['root'] for p in settings['projects']],
            'config_sha256': hashlib.sha256(config.read_bytes()).hexdigest()}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path.home()); p.add_argument('--models', type=Path, required=True)
    p.add_argument('--source', type=Path); p.add_argument('--render-python', type=Path)
    p.add_argument('--project', type=Path); p.add_argument('--policy', type=Path); p.add_argument('--apply', action='store_true')
    p.add_argument('--repository-native', action='store_true')
    p.add_argument('--authority', action='append', default=[])
    p.add_argument('--native-instructions', type=Path)
    a = p.parse_args()
    if a.repository_native:
        if not a.project or a.policy or not a.authority or not a.native_instructions:
            p.error('Native registration requires --project, --authority and --native-instructions, without --policy')
    elif a.authority or a.native_instructions or bool(a.project) != bool(a.policy):
        p.error('Use --project with --policy, or a complete --repository-native registration')
    if a.apply and (not a.source or not a.render_python): p.error('Apply requires a pinned source checkout and Python3.11+ renderer environment')
    try: print(json.dumps(install(a), ensure_ascii=False, indent=2))
    except (ValueError, OSError, subprocess.SubprocessError) as exc: p.exit(1, 'Quality install rejected: ' + str(exc) + '\n')
if __name__ == '__main__': main()
