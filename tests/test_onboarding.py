import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflow.runtime import Runtime
from test_quality import policy


class OnboardingTests(unittest.TestCase):
    def test_registered_ancestor_policy_cannot_be_bypassed_by_git_or_manifest(self):
        for outer_git in (True, False):
            with self.subTest(outer_git=outer_git), tempfile.TemporaryDirectory() as td:
                registry, outer = self.fixture(Path(td))
                if not outer_git: (outer / '.git').rmdir()
                project = outer / 'package'; project.mkdir()
                nested = project / 'src'; nested.mkdir(); (nested / 'package.json').write_text('{}')
                settings = {'projects': [{'root': str(project.resolve()), 'policy': policy()}]}
                registry.write_text(json.dumps(settings)); before = registry.read_bytes()
                result = Runtime(settings, settings_path=registry).onboard(str(nested))
                self.assertEqual(result['project'], str(project.resolve()))
                self.assertEqual(result['mode'], 'portable')
                self.assertEqual(registry.read_bytes(), before)

    def test_readme_is_discovery_metadata_not_a_persistent_authority(self):
        with tempfile.TemporaryDirectory() as td:
            registry, project = self.fixture(Path(td)); readme = project / 'README.md'; readme.write_text('Info')
            runtime = Runtime(json.loads(registry.read_text()), settings_path=registry)
            runtime.onboard(str(project)); readme.unlink()
            self.assertIn(str(project.resolve()), runtime.info()['project_profiles'])
    def test_registry_or_backup_symlink_cannot_redirect_writes(self):
        with tempfile.TemporaryDirectory() as td:
            registry, project = self.fixture(Path(td))
            original = registry.read_bytes(); target = Path(td) / 'target.json'; target.write_bytes(original)
            registry.unlink(); registry.symlink_to(target)
            runtime = Runtime(json.loads(original), settings_path=registry)
            with self.assertRaises(ValueError): runtime.onboard(str(project))
            self.assertEqual(target.read_bytes(), original)
            registry.unlink(); registry.write_bytes(original)
            elsewhere = Path(td) / 'elsewhere'; elsewhere.mkdir()
            (registry.parent / 'backups').symlink_to(elsewhere, target_is_directory=True)
            with self.assertRaises(ValueError): runtime.onboard(str(project))
            self.assertEqual(registry.read_bytes(), original)
            self.assertEqual(list(elsewhere.iterdir()), [])
    def test_nested_non_git_project_and_existing_manual_root_are_reused(self):
        with tempfile.TemporaryDirectory() as td:
            registry, project = self.fixture(Path(td)); (project / '.git').rmdir()
            nested = project / 'src'; nested.mkdir()
            runtime = Runtime(json.loads(registry.read_text()), settings_path=registry)
            self.assertEqual(runtime.onboard(str(nested))['project'], str(project.resolve()))
            (project / 'AGENTS.md').unlink()
            # A manually registered portable root need not have a Git marker or manifest.
            registry.write_text(json.dumps({'projects': [{'root': str(project.resolve()), 'policy': policy()}]}))
            self.assertEqual(runtime.onboard(str(nested))['mode'], 'portable')
    def fixture(self, root):
        registry = root / 'private/settings.json'
        registry.parent.mkdir()
        registry.write_text('{"projects": []}')
        project = root / 'project'; project.mkdir(); (project / '.git').mkdir()
        (project / 'AGENTS.md').write_text('Use native tests, no generated task files.')
        return registry, project

    def test_new_nested_project_is_persisted_without_project_writes(self):
        with tempfile.TemporaryDirectory() as td:
            registry, project = self.fixture(Path(td))
            nested = project / 'src'; nested.mkdir()
            before = sorted(str(x.relative_to(project)) for x in project.rglob('*'))
            runtime = Runtime(json.loads(registry.read_text()), settings_path=registry)
            result = runtime.onboard(str(nested))
            self.assertEqual(result['onboarding'], 'registered')
            self.assertEqual(result['project'], str(project.resolve()))
            self.assertEqual(result['mode'], 'repository-native')
            self.assertFalse(result['acceptance_pass'])
            self.assertEqual(sorted(str(x.relative_to(project)) for x in project.rglob('*')), before)
            self.assertEqual(registry.stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(list((registry.parent / 'backups').glob('*.json'))), 1)
            old = registry.read_bytes()
            self.assertEqual(runtime.onboard(str(project))['onboarding'], 'reused')
            self.assertEqual(registry.read_bytes(), old)
            self.assertEqual(len(list((registry.parent / 'backups').glob('*.json'))), 1)

    def test_existing_portable_policy_and_other_session_refresh_are_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            registry, project = self.fixture(Path(td)); existing = Path(td) / 'existing'; existing.mkdir()
            settings = {'projects': [{'root': str(existing.resolve()), 'policy': policy()}]}
            registry.write_text(json.dumps(settings))
            first = Runtime(settings, settings_path=registry)
            second = Runtime(settings, settings_path=registry)
            self.assertEqual(first.onboard(str(existing))['mode'], 'portable')
            first.onboard(str(project))
            self.assertIn(str(project.resolve()), second.info()['project_profiles'])
            self.assertEqual(json.loads(registry.read_text())['projects'][0], settings['projects'][0])

    def test_empty_git_repo_is_not_given_invented_authorities_or_commands(self):
        with tempfile.TemporaryDirectory() as td:
            registry, project = self.fixture(Path(td)); (project / 'AGENTS.md').unlink()
            result = Runtime(json.loads(registry.read_text()), settings_path=registry).onboard(str(project))
            self.assertEqual(result['authorities'], [])
            saved = json.loads(registry.read_text())['projects'][0]
            self.assertNotIn('policy', saved)
            self.assertFalse((project / '.quality').exists())

    def test_unsafe_or_unrecognised_directory_does_not_change_registry(self):
        with tempfile.TemporaryDirectory() as td:
            registry, project = self.fixture(Path(td)); unknown = Path(td) / 'unknown'; unknown.mkdir()
            runtime = Runtime(json.loads(registry.read_text()), settings_path=registry)
            original = registry.read_bytes()
            for path in ('/', str(Path.home()), str(unknown), 'relative/path'):
                with self.subTest(path=path), self.assertRaises(ValueError): runtime.onboard(path)
            (project / 'AGENTS.md').unlink(); (project / 'AGENTS.md').symlink_to(registry)
            with self.assertRaises(ValueError): runtime.onboard(str(project))
            self.assertEqual(registry.read_bytes(), original)

    def test_parallel_registrations_merge_without_lost_projects(self):
        with tempfile.TemporaryDirectory() as td:
            registry, project = self.fixture(Path(td)); projects = [project]
            for i in range(3):
                p = Path(td) / ('project' + str(i)); p.mkdir(); (p / 'package.json').write_text('{}'); projects.append(p)
            code = ('import sys; from workflow.runtime import Runtime,read_json; '
                    'Runtime(read_json(sys.argv[1]),settings_path=sys.argv[1]).onboard(sys.argv[2])')
            children = [subprocess.Popen([sys.executable, '-c', code, str(registry), str(p)],
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE) for p in projects]
            outcomes = [(child, child.communicate(timeout=20)) for child in children]
            for child, (stdout, stderr) in outcomes:
                self.assertEqual(child.returncode, 0, stderr.decode())
            self.assertEqual({p['root'] for p in json.loads(registry.read_text())['projects']},
                             {str(p.resolve()) for p in projects})

    def test_deployed_stdio_onboards_and_immediately_reports_mode(self):
        with tempfile.TemporaryDirectory() as td:
            registry, project = self.fixture(Path(td))
            requests = [{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
                'name': 'quality_onboard', 'arguments': {'project': str(project)}}},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'quality_info', 'arguments': {}}}]
            result = subprocess.run([sys.executable, '-m', 'workflow.server', '--settings', str(registry)],
                input=''.join(json.dumps(r) + '\n' for r in requests), capture_output=True, text=True, check=True)
            replies = [json.loads(line)['result']['structuredContent'] for line in result.stdout.splitlines()]
            self.assertEqual(replies[0]['onboarding'], 'registered')
            self.assertEqual(replies[1]['project_profiles'][str(project.resolve())]['mode'], 'repository-native')


if __name__ == '__main__': unittest.main()
