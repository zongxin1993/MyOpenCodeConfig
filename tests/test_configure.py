import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import configure as c

T={'agents':{'cloud-workflow':{'mode':'primary','system':'Delegate local-worker; review cloud-review.','permissions':[{'action':'subagent','resource':'local-worker','effect':'allow'}]},'cloud-design':{'mode':'primary','system':'Design'},'cloud-plan':{'mode':'primary','system':'Plan'},'cloud-review':{'mode':'all','system':'Review'},'local-worker':{'mode':'subagent','system':'Implement'},'local-build':{'mode':'primary','system':'Build'},'local-inspect':{'mode':'subagent','system':'Inspect'}},'commands':{'implement':{'agent':'local-build','model':'old','template':'Implement'}}}
for name in ('cloud-plan-review','cloud-structure-review','cloud-test-review'):
 T['agents'][name]={'mode':'subagent','system':'Read only review'}
def spec():return {'version':1,'defaults':{'cloud':{'provider':'openai','model':'cloud-model','variant':'high'},'local':{'provider':'local','model':'local-model','variant':'workflow-balanced','variants':[{'id':'workflow-balanced','body':{'reasoning_budget_tokens':2048,'max_tokens':24576}}]}},'roles':{}}
def base():return {'providers':{'local':{'settings':{'apiKey':'PRIVATE_SENTINEL'},'body':{'max_tokens':24576},'models':{'local-model':{'limit':{'context':131072}}}}},'agents':{'strata-worker':{'model':'old'},'unrelated':{'system':'keep'}},'commands':{'mine':{'template':'mine'}},'compaction':{'auto':True}}
class ConfigureTests(unittest.TestCase):
 def test_migration_preserves_private_and_unowned_config(self):
  b=base();original=copy.deepcopy(b);out,state=c.compile_config(b,spec(),T)
  self.assertNotIn('strata-worker',out['agents']);self.assertEqual(out['agents']['local-worker']['model'],'local/local-model#workflow-balanced')
  self.assertEqual(out['providers']['local']['settings'],{'apiKey':'PRIVATE_SENTINEL'})
  self.assertEqual(out['compaction'],{'auto':True});self.assertEqual(out['agents']['unrelated'],{'system':'keep'});self.assertEqual(out['commands']['mine'],{'template':'mine'});self.assertEqual(b,original)
  self.assertNotIn('PRIVATE_SENTINEL',json.dumps(state));self.assertEqual(out['agents']['cloud-workflow']['permissions'][0]['resource'],'local-worker')
 def test_migration_preserves_extra_role_restrictions(self):
  b=base();deny={'action':'shell','resource':'*','effect':'deny'}
  b['agents']['strata-worker']['permissions']=[deny]
  b['agents']['cloud-workflow']={'permissions':[{'action':'subagent','resource':'strata-worker','effect':'deny'}]}
  out,_=c.compile_config(b,spec(),T)
  self.assertEqual(out['agents']['local-worker']['permissions'],[deny])
  self.assertEqual(out['agents']['cloud-workflow']['permissions'],[{'action':'subagent','resource':'local-worker','effect':'deny'}])
 def test_default_variants_exist_when_every_local_role_overrides(self):
  s=spec()
  for role in ['local-worker','local-build','local-inspect']:s['roles'][role]={'model':'alternate','variant':None,'variants':[]}
  out,_=c.compile_config(base(),s,T)
  self.assertEqual(out['agents']['summary']['model'],'local/local-model#workflow-balanced')
  self.assertEqual(out['providers']['local']['models']['local-model']['variants'][0]['id'],'workflow-balanced')
 def test_override_changes_binding_and_identity_together(self):
  s=spec();s['roles']['cloud-review']={'model':'audit-model','variant':'medium'};out,_=c.compile_config(base(),s,T)
  self.assertEqual(out['agents']['cloud-review']['model'],'openai/audit-model#medium');self.assertIn('audit-model',out['agents']['cloud-review']['description']);self.assertIn('openai/audit-model#medium',out['agents']['cloud-workflow']['system'])
 def test_owned_variant_update_and_idempotency(self):
  s=spec();out,state=c.compile_config(base(),s,T);again,state2=c.compile_config(out,s,T,state);self.assertEqual(out,again);self.assertEqual(state,state2)
  s['defaults']['local']['variants'][0]['body']['reasoning_budget_tokens']=4096
  changed,_=c.compile_config(out,s,T,state);self.assertEqual(changed['providers']['local']['models']['local-model']['variants'][0]['body']['reasoning_budget_tokens'],4096)
 def test_rejects_unknown_role_and_conflicting_variants(self):
  s=spec();s['roles']['clod-review']={}
  with self.assertRaises(ValueError):c.compile_config(base(),s,T)
  s=spec();s['roles']['local-worker']={'variants':[{'id':'workflow-balanced','body':{'reasoning_budget_tokens':999}}]}
  with self.assertRaises(ValueError):c.compile_config(base(),s,T)
 def test_existing_unowned_variant_cannot_be_overwritten(self):
  b=base();b['providers']['local']['models']['local-model']['variants']=[{'id':'workflow-balanced','body':{'x':1}}]
  with self.assertRaises(ValueError):c.compile_config(b,spec(),T)
 def test_invalid_spec_does_not_write_target(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'opencode.json';p.write_text(json.dumps(base()));before=p.read_bytes();s=spec();s['defaults']['cloud']['typo']=1
   with self.assertRaises(ValueError):c.install(p,s,T,True)
   self.assertEqual(p.read_bytes(),before);self.assertFalse((p.parent/'backups').exists())
 def test_install_backs_up_once_and_noop_has_no_side_effects(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'opencode.json';p.write_text(json.dumps(base()));before=p.read_bytes()
   info=c.install(p,spec(),T,True);self.assertTrue(info['changed']);backup=Path(info['backup']);self.assertEqual((backup/'opencode.json').read_bytes(),before);self.assertEqual((backup/'opencode.json').stat().st_mode&0o777,0o600)
   current=p.read_bytes();again=c.install(p,spec(),T,True);self.assertFalse(again['changed']);self.assertEqual(p.read_bytes(),current);self.assertEqual(len(list((p.parent/'backups').iterdir())),1)
if __name__=='__main__':unittest.main()
