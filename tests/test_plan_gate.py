import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_quality import contract,policy,review,finding
from workflow.contract import contract_id
from workflow.gate import evaluate_plan
class PlanGateTests(unittest.TestCase):
 def test_plan_can_close_document_issues_before_any_source_tests(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'source.txt').write_text('baseline');c,p=contract(),policy();c['approvals']['plan']='PENDING';cid=contract_id(c)
   old=review('plan',cid,'',[finding()]);new=review('plan',cid,'');new.update(round=2,closed_findings=[{'id':'plan:1:F-1','reason':'Corrected requirement/acceptance mapping, independently inspected','evidence':'contract:'+cid}])
   self.assertEqual(evaluate_plan(root,c,p,[old,new])['status'],'PASS')
   new['closed_findings']=[];self.assertEqual(evaluate_plan(root,c,p,[old,new])['status'],'BLOCKED')
 def test_incomplete_old_round_does_not_poison_fresh_complete_review(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'source.txt').write_text('baseline');c,p=contract(),policy();cid=contract_id(c);old=review('plan',cid,'');old['complete']=False;new=review('plan',cid,'');new['round']=2
   self.assertEqual(evaluate_plan(root,c,p,[old,new])['status'],'PASS')
 def test_current_resolved_plan_finding_requires_current_contract_reference(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'source.txt').write_text('baseline');c,p=contract(),policy();cid=contract_id(c);f=finding(status='resolved',resolution_evidence='promise to check later');r=review('plan',cid,'',[f])
   self.assertNotEqual(evaluate_plan(root,c,p,[r])['status'],'PASS')
   f['resolution_evidence']='contract:old';self.assertNotEqual(evaluate_plan(root,c,p,[r])['status'],'PASS')
   f['resolution_evidence']='contract:'+cid;self.assertEqual(evaluate_plan(root,c,p,[r])['status'],'PASS')
if __name__=='__main__':unittest.main()
