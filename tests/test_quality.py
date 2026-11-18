import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow.contract import validate_contract
from workflow.snapshot import snapshot
from workflow.runner import run_lane
from workflow.gate import evaluate_gate
from workflow.review import validate_review

def contract():
 return {'version':1,'requirements':[{'id':'REQ-1','source':'User requirement','statement':'Reject non-integer input','required':True}], 'plan':{'risk':'low','tasks':[{'id':'TASK-1','requirements':['REQ-1']}], 'acceptance':[{'id':'AC-1','requirement':'REQ-1','criterion':'unittest observes rejection','lane':'tests'}], 'architecture':[{'id':'ARCH-1','statement':'Module stays independent','lane':'tests'}], 'unknowns':[]}, 'approvals':{'design':'fixture simulated approval','plan':'fixture simulated plan approval','simulated':True}}
def policy():
 return {'version':1,'lanes':[{'id':'tests','argv':[sys.executable,'-m','unittest','-v'],'parser':'unittest','timeout':5,'min_checks':1,'environment':'Current Python, stdlib unittest','required':True}]}
def review(kind,cid,sid,findings=None):
 return {'version':1,'kind':kind,'contract_id':cid,'snapshot_id':sid,'reviewer':{'agent':'cloud-plan-review' if kind=='plan' else 'cloud-review','model':'cloud/model','session':'review-'+kind},'summary':'Independent inspected evidence','findings':findings or [],'rejections':[],'complete':True}
def finding(**changes):
 d={'id':'F-1','category':'correctness','location':'module.py:1','title':'Invalid input accepted','evidence':'Confirmed reachable call','consequence':'Wrong result','scope':'One API, callers named','confidence':'confirmed','severity':'high','origin':'introduced','disposition':'fix','status':'open','defer':None,'repair':{'value':'Prevents wrong result','effort':'small','regression_risk':'low','verification':'tests'},'risk':{'impact':5,'likelihood':3,'breadth':2,'time':4}}
 d.update(changes);return d
class ContractTests(unittest.TestCase):
 def test_valid_and_missing_acceptance_or_orphan_tasks(self):
  self.assertEqual(validate_contract(contract(),policy()),[])
  for mutate in [lambda c:c['plan'].update(acceptance=[]),lambda c:c['plan']['tasks'][0].update(requirements=['REQ-unknown']),lambda c:c['plan']['acceptance'][0].update(criterion=''),lambda c:c['plan']['unknowns'].append({'question':'Storage semantics','critical':True,'resolved':False})]:
   c=contract();mutate(c);self.assertTrue(validate_contract(c,policy()))
 def test_unknown_fields_duplicate_ids_unknown_lane_and_bad_policy(self):
  for mutate in [lambda c:c.update(typo=True),lambda c:c['requirements'].append(c['requirements'][0]),lambda c:c['plan']['acceptance'][0].update(lane='absent')]:
   c=contract();mutate(c);self.assertTrue(validate_contract(c,policy()))
  p=policy();p['lanes'][0]['min_checks']=0;self.assertTrue(validate_contract(contract(),p))
 def test_approval_record_does_not_change_reviewed_semantic_contract(self):
  from workflow.contract import contract_id
  c=contract();before=contract_id(c);c['approvals']['plan']='Actual later confirmation'
  self.assertEqual(before,contract_id(c));c['plan']['acceptance'][0]['criterion']='Changed outcome'
  self.assertNotEqual(before,contract_id(c))
class EvidenceTests(unittest.TestCase):
 def test_snapshot_tracks_untracked_deletion_and_rejects_symlinks(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'x.py').write_text('a');a=snapshot(root)
   (root/'untracked.py').write_text('b');b=snapshot(root);self.assertNotEqual(a['id'],b['id'])
   (root/'x.py').unlink();self.assertNotEqual(b['id'],snapshot(root)['id'])
   (root/'escape').symlink_to('/etc/passwd')
   with self.assertRaises(ValueError):snapshot(root)
 def test_runner_real_success_skip_zero_tests_failure_and_source_change(self):
  with tempfile.TemporaryDirectory() as td,tempfile.TemporaryDirectory() as logs:
   root=Path(td);test=root/'test_x.py';lane=policy()['lanes'][0]
   test.write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
   self.assertEqual(run_lane(root,lane,Path(logs))['status'],'PASS')
   test.write_text('import unittest\nclass T(unittest.TestCase):\n @unittest.skip("skip")\n def test_ok(self): pass\n')
   self.assertEqual(run_lane(root,lane,Path(logs))['status'],'FAIL')
   test.write_text('');self.assertEqual(run_lane(root,lane,Path(logs))['status'],'FAIL')
   bad=dict(lane,argv=[sys.executable,'-c','raise SystemExit(2)']);self.assertEqual(run_lane(root,bad,Path(logs))['status'],'FAIL')
   change=dict(lane,argv=[sys.executable,'-c','from pathlib import Path;Path("changed.py").write_text("x")']);self.assertEqual(run_lane(root,change,Path(logs))['status'],'FAIL')
 def test_runner_timeout_and_missing_tool_are_not_pass(self):
  with tempfile.TemporaryDirectory() as td,tempfile.TemporaryDirectory() as logs:
   (Path(td)/'source.py').write_text('baseline')
   for argv in [['nonexistent-quality-command'],[sys.executable,'-c','import time;time.sleep(5)']]:
    r=run_lane(Path(td),dict(policy()['lanes'][0],argv=argv,timeout=.1),Path(logs));self.assertNotEqual(r['status'],'PASS')
class GateTests(unittest.TestCase):
 def setup_bundle(self,root,logs):
  (root/'test_x.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
  c,p=contract(),policy();from workflow.contract import digest,contract_id
  cid=contract_id(c);sid=snapshot(root)['id']
  from workflow.evidence import collect_evidence
  e=collect_evidence(root,c,p,logs)
  return c,p,e,[review('plan',cid,''),review('code',cid,sid)]
 def test_pass_stale_missing_and_tampered_log(self):
  with tempfile.TemporaryDirectory() as td,tempfile.TemporaryDirectory() as logs:
   root=Path(td);c,p,e,rs=self.setup_bundle(root,Path(logs))
   self.assertEqual(evaluate_gate(root,c,p,e,rs)['status'],'PASS')
   bad=copy.deepcopy(e);bad['lanes']=[];self.assertNotEqual(evaluate_gate(root,c,p,bad,rs)['status'],'PASS')
   Path(e['lanes'][0]['log']).write_text('forged');self.assertNotEqual(evaluate_gate(root,c,p,e,rs)['status'],'PASS')
   (root/'new.py').write_text('new');self.assertNotEqual(evaluate_gate(root,c,p,e,rs)['status'],'PASS')
 def test_missing_lens_high_severity_and_fake_waiver_block(self):
  with tempfile.TemporaryDirectory() as td,tempfile.TemporaryDirectory() as logs:
   root=Path(td);c,p,e,rs=self.setup_bundle(root,Path(logs));rs[-1]['findings']=[finding()]
   self.assertEqual(evaluate_gate(root,c,p,e,rs)['status'],'BLOCKED')
   rs[-1]['findings']=[finding(disposition='defer',defer={'owner':'model','until':'2099-01-01','reason':'expensive','accepted_by':'self','trigger':'later'})]
   self.assertEqual(evaluate_gate(root,c,p,e,rs)['status'],'BLOCKED')
   c['plan']['risk']='high';self.assertNotEqual(evaluate_gate(root,c,p,e,rs)['status'],'PASS')
 def test_review_validation_rejects_incomplete_and_missing_reason(self):
  r=review('code','c','s');self.assertEqual(validate_review(r),[])
  r['complete']=False;self.assertTrue(validate_review(r))
  r=review('code','c','s');r['rejections']=[{'id':'R1','reason':''}];self.assertTrue(validate_review(r))
if __name__=='__main__':unittest.main()
