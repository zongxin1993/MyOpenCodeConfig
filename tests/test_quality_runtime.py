import json,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_quality import contract,policy
class RuntimeTests(unittest.TestCase):
 def test_registered_policy_only_and_no_command_execution_tools(self):
  from workflow.runtime import Runtime
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'docs/superpowers/specs').mkdir(parents=True);(root/'x.py').write_text('x')
   cp=root/'docs/superpowers/specs/contract.json';cp.write_text(json.dumps(contract()))
   runtime=Runtime({'projects':[{'root':str(root),'policy':policy()}]})
   result=runtime.prepare(str(root),'docs/superpowers/specs/contract.json')
   self.assertIn('properties',json.loads(runtime.resource('schema/review')['content']));
   with self.assertRaises(ValueError):runtime.resource('../../etc/passwd')
   self.assertTrue(result['contract_valid']);self.assertIn('contract_id',result)
   with self.assertRaises(ValueError):runtime.prepare('/etc','passwd')
   with self.assertRaises(ValueError):runtime.prepare(str(root),'../../etc/passwd')
   with self.assertRaises(ValueError):runtime.prepare(str(root),'x.py')
 def test_stdio_exposes_inspection_and_narrow_registration_without_command_tools(self):
  import workflow.server as server
  self.assertEqual({t['name'] for t in server.TOOLS},{'quality_info','quality_prepare','quality_gate','quality_resource','quality_onboard'})
if __name__=='__main__':unittest.main()
