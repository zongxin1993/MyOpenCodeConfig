import json,tempfile,unittest
from pathlib import Path
from integrations.execution import parse_execution
from workflow.execution_setup import plan_execution
class OptionalTests(unittest.TestCase):
 def test_uncertified_processes_fail_closed_before_config_changes(self):
  lock=json.loads(Path('integrations/execution.lock.json').read_text())
  for key,mode in [('serena','symbols-readonly'),('browser','playwright-cli')]:
   with self.subTest(key=key),tempfile.TemporaryDirectory() as td:
    with self.assertRaisesRegex(ValueError,'certification'):plan_execution(Path(td),parse_execution({key:{'mode':mode}}),lock)
 def test_redistributed_resources_match_fixed_source_digests(self):
  import hashlib
  lock=json.loads(Path('integrations/execution.lock.json').read_text())
  for key,row in lock.items():
   self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
   if row.get('redistribute'):
    for name,expected in row['files'].items():
     self.assertEqual(hashlib.sha256((Path('integrations/execution-upstream')/key/name).read_bytes()).hexdigest(),expected)
 def test_rtk_discovery_rejects_unknown_and_project_duplicate(self):
  from workflow.execution_setup import discover_rtk
  with tempfile.TemporaryDirectory() as td:
   home=Path(td).resolve();project=home/'project';a=home/'.config/opencode/plugins';b=project/'.opencode/plugin';a.mkdir(parents=True);b.mkdir(parents=True)
   (a/'rtk.ts').write_text('unknown');(b/'rtk.ts').write_text('unknown')
   self.assertEqual(len(discover_rtk(home,[project])),2)
