import tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pathlib import Path
from workflow.structure import check_structure
class StructureTests(unittest.TestCase):
 def test_real_forbidden_import_and_clean_and_empty(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'app').mkdir();(root/'app/core.py').write_text('from app import api\n');(root/'app/api.py').write_text('value=1\n')
   self.assertEqual(check_structure(root,['app'],['app.core:app.api'])['failures'],1)
   (root/'app/core.py').write_text('value=1\n');self.assertEqual(check_structure(root,['app'],['app.core:app.api'])['failures'],0)
   with self.assertRaises(ValueError):check_structure(root,['missing'],[])
if __name__=='__main__':unittest.main()
