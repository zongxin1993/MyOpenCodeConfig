import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class InstallTests(unittest.TestCase):
 def test_registered_profiles_are_copied_not_live_references(self):
  from setup_quality import merge_registration
  from test_quality import policy
  with tempfile.TemporaryDirectory() as td:
   p=policy();settings=merge_registration({'projects':[]},Path(td),p)
   p['lanes'][0]['argv']=['changed'];self.assertNotEqual(settings['projects'][0]['policy'],p)
   self.assertEqual(len(settings['projects']),1)
 def test_foreign_skill_is_rejected_before_writing(self):
  from setup_quality import preflight_skill
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'SKILL.md').write_text('User skill')
   with self.assertRaises(ValueError):preflight_skill(p)
   self.assertEqual((p/'SKILL.md').read_text(),'User skill')

class PreferenceTests(unittest.TestCase):
 def test_preferences_preserve_unrelated_and_keep_cloud_agent(self):
  from setup_quality import plugin_preferences
  with tempfile.TemporaryDirectory() as td:
   home=Path(td).resolve();p=home/'.plannotator/config.json';p.parent.mkdir();p.write_text('{"identity":"keep","agentSwitch":"build"}')
   out=plugin_preferences(home,{'extensions':{'plannotator':True,'quota':True}})
   self.assertEqual(out[p]['identity'],'keep');self.assertEqual(out[p]['agentSwitch'],'disabled')
   q=home/'.config/opencode/opencode-quota/settings.jsonc';self.assertFalse(out[q]['providers']['checking']['waitForQuotaReset'])
   self.assertEqual(json.loads(p.read_text())['agentSwitch'],'build')
 def test_disabled_extensions_do_not_manage_preferences(self):
  from setup_quality import plugin_preferences
  with tempfile.TemporaryDirectory() as td:self.assertEqual(plugin_preferences(Path(td),{}),{})

if __name__=='__main__':unittest.main()
