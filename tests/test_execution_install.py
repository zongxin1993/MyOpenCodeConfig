import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class TransactionTests(unittest.TestCase):
 def test_atomic_changes_and_recovery_preserve_concurrent_edit(self):
  from workflow.execution_setup import FileTransaction
  with tempfile.TemporaryDirectory() as td:
   root=Path(td).resolve();a=root/'a';b=root/'b';a.write_bytes(b'old');b.write_bytes(b'keep')
   tx=FileTransaction(root/'backup',{a:b'new',b:b'next'})
   tx.prepare();tx.write(a);a.write_bytes(b'user-change')
   conflicts=tx.rollback();self.assertEqual(a.read_bytes(),b'user-change');self.assertEqual(b.read_bytes(),b'keep');self.assertEqual(conflicts,[str(a)])
 def test_preflight_conflict_and_symlink_refused(self):
  from workflow.execution_setup import FileTransaction
  with tempfile.TemporaryDirectory() as td:
   root=Path(td).resolve();a=root/'a';a.write_bytes(b'old');tx=FileTransaction(root/'backup',{a:b'new'});tx.prepare();a.write_bytes(b'concurrent')
   with self.assertRaises(ValueError):tx.write(a)
   link=root/'link';link.symlink_to(a)
   with self.assertRaises(ValueError):FileTransaction(root/'backup2',{link:b'x'}).prepare()
 def test_deletion_and_new_file_roll_back(self):
  from workflow.execution_setup import FileTransaction
  with tempfile.TemporaryDirectory() as td:
   root=Path(td).resolve();a=root/'a';b=root/'new';a.write_bytes(b'old');tx=FileTransaction(root/'backup',{a:None,b:b'new'});tx.prepare();tx.write(a);tx.write(b)
   self.assertFalse(a.exists());self.assertEqual(tx.rollback(),[]);self.assertEqual(a.read_bytes(),b'old');self.assertFalse(b.exists())
 def test_preflight_snapshot_protects_values_read_before_prepare(self):
  from workflow.execution_setup import FileTransaction,digest
  with tempfile.TemporaryDirectory() as td:
   root=Path(td).resolve();a=root/'a';a.write_bytes(b'old');expected={a:digest(b'old')};a.write_bytes(b'user-new')
   tx=FileTransaction(root/'backup',{a:b'computed-from-old'},expected=expected)
   with self.assertRaises(ValueError):tx.prepare()
   self.assertEqual(a.read_bytes(),b'user-new')
 def test_active_owned_skill_modification_is_not_overwritten(self):
  from workflow.execution_setup import verify_owned_files,digest
  with tempfile.TemporaryDirectory() as td:
   f=Path(td).resolve()/'SKILL.md';f.write_bytes(b'Managed-By: MyOpenCodeConfig execution\nuser edit')
   with self.assertRaises(ValueError):verify_owned_files({str(f):digest(b'Managed-By: MyOpenCodeConfig execution\noriginal')})
 def test_one_recovery_symlink_conflict_does_not_stop_other_restores(self):
  from workflow.execution_setup import FileTransaction
  with tempfile.TemporaryDirectory() as td:
   root=Path(td).resolve();a=root/'a';b=root/'b';a.write_bytes(b'old-a');b.write_bytes(b'old-b');tx=FileTransaction(root/'backup',{a:b'new-a',b:b'new-b'});tx.prepare();tx.write(a);tx.write(b);b.unlink();b.symlink_to(a)
   self.assertEqual(tx.rollback(),[str(b)]);self.assertEqual(a.read_bytes(),b'old-a');self.assertTrue(b.is_symlink())
 def test_renamed_compact_rtk_discovery_is_not_missed(self):
  from workflow.execution_setup import discover_rtk
  with tempfile.TemporaryDirectory() as td:
   home=Path(td).resolve();p=home/'.config/opencode/plugins';p.mkdir(parents=True);(p/'output.ts').write_text("export default {id:'rtk',async setup(){}}")
   self.assertEqual(len(discover_rtk(home)),1)
 def test_provisioning_failure_preserves_existing_active_binary(self):
  from setup_execution_tools import provision_package
  with tempfile.TemporaryDirectory() as td:
   root=Path(td).resolve();source=root/'source';dest=root/'active';source.mkdir();dest.mkdir();(source/'package.json').write_text('{}');(source/'package-lock.json').write_text('{}');(dest/'node_modules').mkdir();(dest/'node_modules/bin').write_text('existing-good')
   def failing(*args,**kwargs):raise OSError('offline')
   with self.assertRaises(OSError):provision_package(source,dest,runner=failing)
   self.assertEqual((dest/'node_modules/bin').read_text(),'existing-good')
 def test_recovery_rejects_corrupt_backup_and_restores_other_files(self):
  from workflow.execution_setup import FileTransaction
  with tempfile.TemporaryDirectory() as td:
   root=Path(td).resolve();a=root/'a';b=root/'b';a.write_bytes(b'old-a');b.write_bytes(b'old-b');tx=FileTransaction(root/'backup',{a:b'new-a',b:b'new-b'});tx.prepare();tx.write(a);tx.write(b);Path(tx.records[1]['backup']).write_bytes(b'tampered')
   self.assertEqual(tx.rollback(),[str(b)]);self.assertEqual(a.read_bytes(),b'old-a');self.assertEqual(b.read_bytes(),b'new-b')
 def test_custom_xdg_rtk_is_detected_before_apply(self):
  from workflow.execution_setup import discover_rtk
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as td:
   root=Path(td).resolve();p=root/'xdg/opencode/plugins';p.mkdir(parents=True);(p/'output.ts').write_text("export default {id:'rtk'}")
   with patch.dict('os.environ',{'XDG_CONFIG_HOME':str(root/'xdg')}):self.assertEqual(len(discover_rtk(root/'home')),1)
 def test_new_reference_does_not_overwrite_user_added_file(self):
  from workflow.execution_setup import execution_skill_changes
  with tempfile.TemporaryDirectory() as td:
   root=Path(td).resolve();src=root/'repo/skills/local-execution';dest=root/'home/.agents/skills/local-execution';src.mkdir(parents=True);dest.mkdir(parents=True)
   (src/'reference.md').write_text('new upstream reference');(dest/'reference.md').write_text('user note')
   with self.assertRaises(ValueError):execution_skill_changes(root/'home',['local-execution'],root/'repo',{})
   self.assertEqual((dest/'reference.md').read_text(),'user note')
