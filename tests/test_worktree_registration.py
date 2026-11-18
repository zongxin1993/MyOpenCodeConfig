import json,subprocess,tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow.runtime import Runtime
from test_quality import policy
class WorktreeRegistrationTests(unittest.TestCase):
 def test_worktree_inherits_portable_or_native_without_changing_source(self):
  for native in (False,True):
   with self.subTest(native=native),tempfile.TemporaryDirectory() as td:
    base=Path(td).resolve();main=base/'main';main.mkdir()
    def git(*a):return subprocess.check_output(['git','-C',str(main),*a],stderr=subprocess.DEVNULL,text=True).strip()
    git('init');git('config','user.email','fixture@example.invalid');git('config','user.name','Fixture')
    (main/'AGENTS.md').write_text('Keep task materials in context, use native checks.');git('add','.');git('commit','-m','fixture')
    wt=base/'worktree';git('worktree','add','-b','fixture/task',str(wt))
    entry={'root':str(main)}
    if native:entry['integration']={'mode':'repository-native','authorities':['AGENTS.md'],'instructions':'Preserve native rules.'}
    else:entry['policy']=policy()
    settings={'projects':[entry]};registry=base/'private/settings.json';registry.parent.mkdir();registry.write_text(json.dumps(settings))
    r=Runtime(settings,settings_path=registry);result=r.onboard(str(wt))
    self.assertEqual(result['mode'],'repository-native' if native else 'portable')
    after=json.loads(registry.read_text());self.assertEqual(after['projects'][0],entry)
    self.assertEqual(after['projects'][1],{**entry,'root':str(wt)})
    self.assertEqual(git('status','--porcelain'),'')
    before=registry.read_bytes();self.assertEqual(r.onboard(str(wt))['onboarding'],'reused');self.assertEqual(registry.read_bytes(),before)

 def test_equal_option_source_path_is_rejected_before_policy_inheritance(self):
  with tempfile.TemporaryDirectory() as td:
   from workflow.registration import linked_registration
   base=Path(td).resolve();main=base/'main';main.mkdir()
   def git(*a):return subprocess.check_output(['git','-C',str(main),*a],stderr=subprocess.DEVNULL,text=True).strip()
   git('init');git('config','user.email','fixture@example.invalid');git('config','user.name','Fixture')
   (main/'README.md').write_text('source');git('add','.');git('commit','-m','fixture')
   wt=base/'worktree';git('worktree','add','-b','fixture/task',str(wt))
   p=policy();p['lanes'][0]['argv']=['python3','-m','unittest','discover','--start-directory='+str(main)]
   with self.assertRaises(ValueError):linked_registration(wt,{'projects':[{'root':str(main),'policy':p}]})

 def test_real_worktree_policy_node_suite(self):
  r=subprocess.run(['node','--test','tests/test_worktree_policy.mjs'],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
