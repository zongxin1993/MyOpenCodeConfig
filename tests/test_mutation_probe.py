import importlib.util,tempfile,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'examples/mutation_probe.py';s=importlib.util.spec_from_file_location('mutation_probe',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class MutationTests(unittest.TestCase):
 def test_real_assertion_kills_and_vacuous_test_misses(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'tests').mkdir();(root/'value.py').write_text('def value():return 2\n');test=root/'tests/test_value.py';test.write_text('import unittest\nfrom value import value\nclass T(unittest.TestCase):\n def test_value(self):self.assertEqual(value(),2)\n')
   before=(root/'value.py').read_bytes();self.assertTrue(m.probe(root,'value.py','value')['detected']);self.assertEqual(before,(root/'value.py').read_bytes())
   test.write_text('import unittest\nclass T(unittest.TestCase):\n def test_value(self):self.assertTrue(True)\n');self.assertFalse(m.probe(root,'value.py','value')['detected'])
 def test_absolute_source_path_is_rejected_without_touching_original(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'tests').mkdir();source=root/'value.py';source.write_text('def value():return 2\n');(root/'tests/test_value.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_value(self):pass\n')
   with self.assertRaises(ValueError):m.probe(root,str(source),'value')
   self.assertEqual(source.read_text(),'def value():return 2\n')
if __name__=='__main__':unittest.main()
