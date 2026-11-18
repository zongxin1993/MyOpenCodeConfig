import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import configure
ROOT=Path(__file__).resolve().parents[1]
class QualityConfigTests(unittest.TestCase):
 def test_review_lenses_are_flat_siblings(self):
  t=json.loads((ROOT/'templates.json').read_text())
  def allowed(role):return {p['resource'] for p in t['agents'][role]['permissions'] if p['action']=='subagent' and p['effect']=='allow'}
  self.assertTrue({'cloud-review','cloud-structure-review','cloud-test-review'} <= allowed('cloud-workflow'))
  self.assertEqual(allowed('cloud-review'),set())
  self.assertIn('flat sibling',t['agents']['cloud-review']['system'])
 def test_coordinator_can_archive_only_review_artifacts(self):
  t=json.loads((ROOT/'templates.json').read_text())
  allowed=[p['resource'] for p in t['agents']['cloud-workflow']['permissions'] if p['action']=='edit' and p['effect']=='allow']
  self.assertIn('.quality/reviews/*.json',allowed)
  self.assertNotIn('*',allowed)
  self.assertFalse(any(p['action']=='edit' and p['effect']=='allow' for p in t['agents']['cloud-review']['permissions']))
 def test_new_roles_and_model_identity(self):
  t=json.loads((ROOT/'templates.json').read_text());s={'version':1,'defaults':{'cloud':{'provider':'openai','model':'cloud','variant':'high'},'local':{'provider':'local','model':'local','variant':None}},'roles':{'cloud-test-review':{'model':'other'}}}
  out,state=configure.compile_config({},s,t)
  for name in ['cloud-plan-review','cloud-structure-review','cloud-test-review']:
   self.assertIn(name,out['agents']);self.assertEqual(out['agents'][name]['mode'],'subagent')
   self.assertNotIn('shell',[p['action'] for p in out['agents'][name]['permissions'] if p['effect']=='allow'])
  self.assertEqual(out['agents']['cloud-test-review']['model'],'openai/other#high')
  self.assertIn('quality-planning',out['agents']['cloud-workflow']['system'])
  self.assertIn('quality_gate',out['agents']['cloud-workflow']['system'])
 def test_known_old_permissions_migrate_custom_deny_does_not(self):
  t=json.loads((ROOT/'templates.json').read_text());s={'version':1,'defaults':{'cloud':{'provider':'c','model':'c'},'local':{'provider':'l','model':'l'}},'roles':{}}
  old=t['permission_migrations']['cloud-workflow'];out,state=configure.compile_config({'agents':{'cloud-workflow':{'permissions':old}}},s,t)
  self.assertIn({'action':'subagent','resource':'cloud-plan-review','effect':'allow'},out['agents']['cloud-workflow']['permissions'])
  custom=old+[{'action':'subagent','resource':'cloud-plan-review','effect':'deny'}]
  out,_=configure.compile_config({'agents':{'cloud-workflow':{'permissions':custom}}},s,t)
  self.assertEqual(custom,out['agents']['cloud-workflow']['permissions'])
if __name__=='__main__':unittest.main()
