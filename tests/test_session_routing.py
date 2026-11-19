import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import configure
from test_configure import base, spec, T


class SessionRoutingTests(unittest.TestCase):
    def test_session_cloud_has_no_pinned_agent_or_command_model_local_unchanged(self):
        s = spec(); s['routing'] = {'cloud_model': 'session'}
        old, _ = configure.compile_config(base(), spec(), T)
        out, state = configure.compile_config(base(), s, T)
        for role in configure.ROLES:
            if role.startswith('cloud-'):
                self.assertNotIn('model', out['agents'][role])
                self.assertNotIn('openai/cloud-model#high', out['agents'][role]['description'])
            else:
                self.assertEqual(out['agents'][role]['model'], old['agents'][role]['model'])
        self.assertEqual(out['providers'], old['providers'])
        self.assertEqual(out['compaction'], old['compaction'])
        self.assertEqual(out['model'], 'openai/cloud-model#high')
        self.assertEqual(out['plugins'][-1]['options']['localBindings']['local-worker'],
                         'local/local-model#workflow-balanced')

    def test_cloud_commands_inherit_but_local_commands_remain_fixed(self):
        t = copy.deepcopy(T); t['commands']['review'] = {'agent': 'cloud-review', 'template': 'Review'}
        s = spec(); s['routing'] = {'cloud_model': 'session'}
        out, _ = configure.compile_config(base(), s, t)
        self.assertNotIn('model', out['commands']['review'])
        self.assertEqual(out['commands']['implement']['model'], 'local/local-model#workflow-balanced')

    def test_owned_plugin_is_idempotent_and_fixed_mode_removes_only_owned_entry(self):
        b = base(); b['plugins'] = ['unrelated-plugin']
        s = spec(); s['routing'] = {'cloud_model': 'session'}
        out, state = configure.compile_config(b, s, T)
        again, state2 = configure.compile_config(out, s, T, state)
        self.assertEqual(out, again); self.assertEqual(state, state2)
        reverted, _ = configure.compile_config(out, spec(), T, state)
        self.assertEqual(reverted['plugins'], ['unrelated-plugin'])

    def test_unknown_routing_and_cloud_fixed_override_conflicts_are_rejected(self):
        for routing in ({'cloud_model': 'typo'}, {'unknown': 'session'}):
            s = spec(); s['routing'] = routing
            with self.assertRaises(ValueError): configure.compile_config(base(), s, T)
        s = spec(); s['routing'] = {'cloud_model': 'session'}; s['roles']['cloud-review'] = {'model': 'fixed'}
        with self.assertRaises(ValueError): configure.compile_config(base(), s, T)

    def test_unowned_string_plugin_and_modified_owned_options_are_rejected(self):
        s = spec(); s['routing'] = {'cloud_model': 'session'}
        b = base(); b['plugins'] = [str(configure.ROOT / 'plugins/cloud-session-router')]
        with self.assertRaises(ValueError): configure.compile_config(b, s, T)
        out, state = configure.compile_config(base(), s, T)
        out['plugins'][-1]['options']['localBindings']['local-worker'] = 'wrong/model'
        with self.assertRaises(ValueError): configure.compile_config(out, s, T, state)

    def test_real_javascript_routing_and_runtime_identity(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node.js is required to verify the routing plugin')
        run = subprocess.run([node, '--test', 'tests/test_session_router.mjs', 'tests/test_worker_continuity.mjs'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
