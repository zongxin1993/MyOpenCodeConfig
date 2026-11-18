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
if __name__=='__main__':unittest.main()
