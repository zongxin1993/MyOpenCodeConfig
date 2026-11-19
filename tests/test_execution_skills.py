import unittest
from pathlib import Path
class ExecutionSkillTests(unittest.TestCase):
 def test_local_skill_preserves_approval_native_evidence_and_same_worker(self):
  text=Path('skills/local-execution/SKILL.md').read_text()
  for rule in ['approved','worktree','native','same worker','awaiting_review','original logs','compress']:
   self.assertIn(rule,text)
 def test_rust_skill_references_are_shipped(self):
  text=Path('skills/rust-diagnostics/SKILL.md').read_text()
  for name in ['ownership','error-handling','concurrency']:
   self.assertTrue(Path('skills/rust-diagnostics/references/'+name+'.md').is_file());self.assertIn(name,text)
 def test_ast_skill_has_full_supporting_reference(self):
  self.assertTrue(Path('skills/ast-grep/references/rule_reference.md').is_file())
