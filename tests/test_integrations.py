import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import configure
from test_configure import base,spec,T

class IntegrationTests(unittest.TestCase):
 def enabled(self):
  s=spec();s['extensions']={k:True for k in ('context7','quota','plannotator','worktree')};return s
 def test_pins_permissions_and_local_bindings(self):
  b=base();b['plugins']=['unrelated'];out,state=configure.compile_config(b,self.enabled(),T)
  packages=[x if isinstance(x,str) else x['package'] for x in out['plugins']]
  self.assertIn('@upstash/context7-opencode@0.2.2',packages);self.assertIn('@slkiser/opencode-quota@6.3.0',packages)
  plan=next(x for x in out['plugins'] if isinstance(x,dict) and x['package']=='@plannotator/opencode@0.28.67')
  self.assertEqual(plan['options']['workflow'],'user-managed')
  self.assertEqual(out['agents']['local-worker']['model'],'local/local-model#workflow-balanced')
  self.assertEqual(out['providers'],configure.compile_config(b,spec(),T)[0]['providers'])
  def allowed(role,action):return any(p.get('action')==action and p.get('effect')=='allow' for p in out['agents'][role]['permissions'])
  self.assertTrue(allowed('cloud-workflow','workflow_worktree'));self.assertTrue(allowed('cloud-workflow','submit_plan'))
  self.assertTrue(any(p.get('action')=='external_directory' and p.get('resource','').endswith('/.plannotator/plans/*') and p.get('effect')=='allow' for p in out['agents']['cloud-review']['permissions']));self.assertTrue(allowed('cloud-review','context7_query-docs'));self.assertFalse(allowed('cloud-review','submit_plan'))
  self.assertIn('WORKTREE ISOLATION',out['agents']['local-worker']['system'])
  self.assertEqual(out['plugins'][0],'unrelated')
 def test_idempotence_removal_and_modified_owned_entry(self):
  s=self.enabled();out,state=configure.compile_config(base(),s,T)
  again,state2=configure.compile_config(out,s,T,state);self.assertEqual((out,state),(again,state2))
  fixed,_=configure.compile_config(out,spec(),T,state);self.assertFalse(fixed.get('plugins'))
  broken=copy.deepcopy(out);broken['plugins'][2]['options']['workflow']='all-agents'
  with self.assertRaises(ValueError):configure.compile_config(broken,s,T,state)
 def test_invalid_extension_or_unowned_collision_is_rejected(self):
  for e in ({'memory':True},{'context7':'yes'}):
   s=spec();s['extensions']=e
   with self.assertRaises(ValueError):configure.compile_config(base(),s,T)
  b=base();b['plugins']=['@plannotator/opencode@0.28.66']
  with self.assertRaises(ValueError):configure.compile_config(b,self.enabled(),T)
