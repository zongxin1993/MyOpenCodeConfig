import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflow.runtime import Runtime
from setup_quality import merge_registration
from test_quality import policy


def native_profile():
    return {'mode': 'repository-native', 'authorities': ['AGENTS.md'],
            'instructions': 'Use repository checks; no generated contracts or reports.'}


class NativeRegistrationTests(unittest.TestCase):
    def test_native_preflight_never_reads_contract_runs_or_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / 'AGENTS.md').write_text('Native rules')
            before = sorted(root.rglob('*'))
            runtime = Runtime({'projects': [{'root': td, 'integration': native_profile()}]})
            self.assertEqual(runtime.info()['project_profiles'][str(root.resolve())]['mode'], 'repository-native')
            for result in (runtime.prepare(td, '/nonexistent/contract.json'),
                           runtime.gate(td, '../../bad', '../../bad', []),
                           runtime.run(td, '/nonexistent')):
                self.assertEqual(result['status'], 'REPOSITORY_NATIVE_REQUIRED')
                self.assertFalse(result['generic_gate_applicable'])
                self.assertNotIn('snapshot', result)
                self.assertNotIn('contract_id', result)
            self.assertEqual(sorted(root.rglob('*')), before)

    def test_native_invalid_or_ambiguous_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / 'AGENTS.md').write_text('Rules')
            good = {'root': td, 'integration': native_profile()}
            cases = []
            for key, value in [('mode', 'unknown'), ('instructions', ''),
                               ('authorities', []), ('authorities', ['../AGENTS.md']),
                               ('authorities', ['/etc/passwd']), ('authorities', ['missing.md']),
                               ('authorities', [1]), ('authorities', ['AGENTS.md', 'AGENTS.md'])]:
                entry = copy.deepcopy(good); entry['integration'][key] = value; cases.append(entry)
            cases.append({**good, 'policy': policy()})
            for entry in cases:
                with self.subTest(entry=entry), self.assertRaises(ValueError):
                    Runtime({'projects': [entry]})

    def test_native_registration_preserves_other_policy_and_copies_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / 'AGENTS.md').write_text('Rules')
            other = root / 'other'; other.mkdir()
            original = {'projects': [{'root': str(other), 'policy': policy()}]}
            profile = native_profile()
            result = merge_registration(original, root, None, integration=profile)
            profile['instructions'] = 'changed'
            self.assertEqual(result['projects'][0], original['projects'][0])
            self.assertNotEqual(result['projects'][1]['integration'], profile)
            self.assertNotIn('policy', result['projects'][1])

    def test_native_cli_is_nonzero_and_stdio_does_not_report_generic_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / 'AGENTS.md').write_text('Rules')
            settings = root / 'settings.json'
            settings.write_text(json.dumps({'projects': [{'root': td, 'integration': native_profile()}]}))
            result = subprocess.run([sys.executable, '-m', 'workflow', 'run', '--settings', str(settings),
                                     '--project', td, '--contract', '.quality/absent.json'], capture_output=True, text=True)
            self.assertEqual(json.loads(result.stdout)['status'], 'REPOSITORY_NATIVE_REQUIRED')
            self.assertNotEqual(result.returncode, 0)
            request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
                'name': 'quality_prepare', 'arguments': {'project': td, 'contract': 'unused'}}}
            reply = subprocess.run([sys.executable, '-m', 'workflow.server', '--settings', str(settings)],
                                   input=json.dumps(request) + '\n', capture_output=True, text=True, check=True)
            body = json.loads(reply.stdout)['result']['structuredContent']
            self.assertEqual(body['status'], 'REPOSITORY_NATIVE_REQUIRED')
            self.assertFalse((root / '.quality').exists())

    def test_installer_preview_accepts_native_without_policy_and_rejects_mix(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td); project = home / 'project'; project.mkdir()
            (project / 'AGENTS.md').write_text('Native rules')
            config = home / '.config/opencode/opencode.json'; config.parent.mkdir(parents=True)
            config.write_text('{}')
            instructions = home / 'instructions.md'; instructions.write_text('Native validation only')
            models = home / 'models.json'
            models.write_text(json.dumps({'version': 1, 'defaults': {
                'cloud': {'provider': 'c', 'model': 'c'}, 'local': {'provider': 'l', 'model': 'l'}}, 'roles': {}}))
            command = [sys.executable, 'setup_quality.py', '--root', str(home), '--models', str(models),
                       '--project', str(project), '--repository-native', '--authority', 'AGENTS.md',
                       '--native-instructions', str(instructions)]
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)['projects'], [str(project.resolve())])
            self.assertEqual(config.read_text(), '{}')
            mixed = subprocess.run(command + ['--policy', 'unread-policy.json'], capture_output=True, text=True)
            self.assertNotEqual(mixed.returncode, 0)
            self.assertEqual(config.read_text(), '{}')


if __name__ == '__main__':
    unittest.main()
