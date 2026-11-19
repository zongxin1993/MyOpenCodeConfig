import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import configure
from test_configure import base,spec
class ExecutionConfigTests(unittest.TestCase):
 def test_missing_execution_keeps_old_config(self):
  from integrations.execution import parse_execution
  self.assertFalse(any(v for k,v in parse_execution(None).items() if k in ('worker_skill','rust_skills')))
  b,s=base(),spec();a,st=configure.compile_config(b,s,json.loads(Path('templates.json').read_text()));s['execution']={}
  b2,st2=configure.compile_config(b,s,json.loads(Path('templates.json').read_text()));self.assertEqual(a,b2);self.assertEqual(st,st2)
 def test_unknown_and_unsafe_modes_rejected(self):
  from integrations.execution import parse_execution
  for x in [{'unknown':True},{'rtk':{'enabled':'yes'}},{'serena':{'mode':'edit'}},{'browser':{'mode':'personal-profile'}},{'rust_skills':['all']},{'worker_skill':1}]:
   with self.subTest(x=x),self.assertRaises(ValueError):parse_execution(x)
 def test_managed_execution_only_and_models_unchanged(self):
  b,s=base(),spec();s['execution']={'rtk':{'enabled':True,'profile':'safe-output'},'ast_grep':{'enabled':True},'worker_skill':True}
  t=json.loads(Path('templates.json').read_text());out,state=configure.compile_config(b,s,t)
  expected,_=configure.compile_config(b,spec(),t);self.assertEqual(out['providers'],expected['providers']);self.assertEqual(out['compaction'],b['compaction'])
  self.assertEqual(len([p for p in out['plugins'] if 'execution-tools' in p['package']]),1)
  again,st=configure.compile_config(out,s,t,state);self.assertEqual(again,out);self.assertEqual(st,state)
  s.pop('execution');disabled,_=configure.compile_config(out,s,t,state)
  self.assertFalse(any('execution-tools' in p['package'] for p in disabled.get('plugins',[])))

 def test_structured_search_is_explicit_and_only_local_roles_receive_permission(self):
  b,s=base(),spec();s['execution']={'search':{'enabled':True},'worker_skill':True}
  out,_=configure.compile_config(b,s,json.loads(Path('templates.json').read_text()))
  for role in ('local-worker','local-build','local-inspect'):
   self.assertIn('execution_search',out['agents'][role]['system'])
   self.assertTrue(any(p.get('action')=='execution_search' for p in out['agents'][role]['permissions']))
  for role in ('cloud-workflow','cloud-plan','cloud-review'):
   self.assertFalse(any(p.get('action')=='execution_search' for p in out['agents'][role].get('permissions',[])))
  self.assertEqual(out['providers'],configure.compile_config(b,spec(),json.loads(Path('templates.json').read_text()))[0]['providers'])

 def test_search_only_setup_installs_entry_skill_and_requires_rg(self):
  from integrations.execution import parse_execution
  from workflow.execution_setup import plan_execution
  from unittest.mock import patch
  options=parse_execution({'search':{'enabled':True}})
  with patch('shutil.which',return_value='/bin/echo'):
   plan=plan_execution(Path('/tmp/fixture'),options,{})
  self.assertIn('local-execution',plan['skills']);self.assertIn('rg',plan['tools'])
  with patch('shutil.which',return_value=None),self.assertRaisesRegex(ValueError,'rg'):
   plan_execution(Path('/tmp/fixture'),options,{})

 def test_node_execution_suite(self):
  import subprocess
  result=subprocess.run(['node','--test','tests/test_execution_tools.mjs'],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_short_worker_entry_replaces_heavy_execution_plan_loader(self):
  b,s=base(),spec();s['execution']={'worker_skill':True}
  t=json.loads(Path('templates.json').read_text());out,_=configure.compile_config(b,s,t)
  for role in ['local-worker','local-build']:
   text=out['agents'][role]['system'];self.assertNotIn('Load executing-plans',text);self.assertIn('Load local-execution',text);self.assertIn('test-driven-development',text)
  self.assertIn('uses local-execution',out['agents']['cloud-workflow']['system'])
 def test_short_entry_covers_implement_command_and_disable_preserves_legacy(self):
  b,s=base(),spec();t=json.loads(Path('templates.json').read_text());legacy=t['commands']['implement']['template']
  s['execution']={'worker_skill':True};out,_=configure.compile_config(b,s,t)
  self.assertIn('local-execution',out['commands']['implement']['template']);self.assertNotIn('Load executing-plans',out['commands']['implement']['template'])
  for role in ['local-worker','local-build']:self.assertIn('verification-before-completion',out['agents'][role]['system'])
  s['execution']={};out,_=configure.compile_config(b,s,t);self.assertEqual(out['commands']['implement']['template'],legacy)
