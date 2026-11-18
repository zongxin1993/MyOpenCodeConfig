import copy,json,os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_quality import contract,policy,review,finding
from workflow.contract import contract_id
from workflow.snapshot import snapshot
from workflow.evidence import collect_evidence
from workflow.gate import evaluate_gate
from workflow.runtime import Runtime
class HistoryTests(unittest.TestCase):
 def test_old_pass_is_rejected_after_later_failed_attempt(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'test_x.py').write_text('import unittest,os\nclass T(unittest.TestCase):\n def test_ok(self):self.assertFalse(os.getenv("QUALITY_FORCE_FAIL"))\n')
   c,p=contract(),policy();e=collect_evidence(root,c,p,root/'.quality/logs');sid=snapshot(root)['id'];rs=[review('plan',contract_id(c),''),review('code',contract_id(c),sid)]
   self.assertEqual(evaluate_gate(root,c,p,e,rs)['status'],'PASS')
   os.environ['QUALITY_FORCE_FAIL']='1'
   try:new=collect_evidence(root,c,p,root/'.quality/logs')
   finally:os.environ.pop('QUALITY_FORCE_FAIL')
   self.assertEqual(new['lanes'][0]['status'],'FAIL');self.assertNotEqual(evaluate_gate(root,c,p,e,rs)['status'],'PASS')
 def test_newer_blocking_review_cannot_be_hidden_by_old_clean_review(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'test_x.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self):pass\n')
   c,p=contract(),policy();e=collect_evidence(root,c,p,root/'.quality/logs');sid=snapshot(root)['id'];rs=[review('plan',contract_id(c),''),review('code',contract_id(c),sid)]
   folder=root/'.quality/reviews';folder.mkdir();new=review('code',contract_id(c),sid,[finding()]);new['round']=2
   (folder/'code-2.json').write_text(json.dumps(new));self.assertNotEqual(evaluate_gate(root,c,p,e,rs)['status'],'PASS')
 def test_low_severity_required_fix_cannot_disappear_next_round(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'test_x.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self):pass\n')
   c,p=contract(),policy();e=collect_evidence(root,c,p,root/'.quality/logs');sid=snapshot(root)['id'];rs=[review('plan',contract_id(c),''),review('code',contract_id(c),sid)]
   folder=root/'.quality/reviews';folder.mkdir();old=review('code',contract_id(c),sid,[finding(severity='low')]);(folder/'code-1.json').write_text(json.dumps(old));rs[-1]['round']=2
   self.assertEqual(evaluate_gate(root,c,p,e,rs)['status'],'BLOCKED')
 def test_failed_optional_lane_cannot_close_blocker(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'test_x.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self):pass\n')
   c,p=contract(),policy();p['lanes'].append(dict(p['lanes'][0],id='optional',required=False,argv=[sys.executable,'-c','raise SystemExit(1)']))
   e=collect_evidence(root,c,p,root/'.quality/logs');sid=snapshot(root)['id'];old=review('code',contract_id(c),sid,[finding()]);new=review('code',contract_id(c),sid);new.update(round=2,closed_findings=[{'id':'code:1:F-1','reason':'claimed repair','evidence':sid+':optional'}])
   folder=root/'.quality/reviews';folder.mkdir();(folder/'code-1.json').write_text(json.dumps(old))
   self.assertEqual(evaluate_gate(root,c,p,e,[review('plan',contract_id(c),''),new])['status'],'BLOCKED')
 def test_executable_mode_changes_snapshot(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'check.sh';p.write_text('#!/bin/sh\nexit 0\n');p.chmod(0o755);before=snapshot(root)['id'];p.chmod(0o644);self.assertNotEqual(before,snapshot(root)['id'])
 def test_symlink_logs_rejected_before_execution(self):
  with tempfile.TemporaryDirectory() as td,tempfile.TemporaryDirectory() as outside:
   root=Path(td);(root/'docs/superpowers/specs').mkdir(parents=True);(root/'docs/superpowers/specs/c.json').write_text(json.dumps(contract()));(root/'x.py').write_text('x');(root/'.quality').mkdir();(root/'.quality/logs').symlink_to(outside)
   r=Runtime({'projects':[{'root':str(root),'policy':policy()}]})
   with self.assertRaises(ValueError):r.run(str(root),'docs/superpowers/specs/c.json')
   self.assertEqual(list(Path(outside).iterdir()),[])
if __name__=='__main__':unittest.main()
