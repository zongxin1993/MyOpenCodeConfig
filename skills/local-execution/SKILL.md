---
name: local-execution
description: Execute an approved task in the current worktree, using actual diagnostics and native verification without repeated planning.
---
Managed-By: MyOpenCodeConfig execution

# Local execution

1. Read the approved handoff: objective, non-goals, actual worktree/baseline, relevant symbols, required native verification commands, evidence paths and stop conditions. A missing approval or contradictory contract returns to the coordinator.
2. Preserve cloud planning/audit and the same worker for implementation and repairs. Never spawn a reviewer/implementer or change providers, settings or reasoning variants. No writes to the source checkout.
3. Use known facts and current files. Plain names/text use rg/read; syntax questions may use execution_ast_search on explicit files; enable symbol queries only when independently authorised. Zero matches do not establish absence. Do not repeatedly rediscover a supplied fact without a concrete inconsistency.
4. Apply existing test-driven-development and systematic-debugging to the actual change. Read the compiler's location and error; repair the responsible interface/body rather than guessing new dependencies or broad rewrites. Load rust-diagnostics only for an actual Rust diagnostic.
5. Run the approved, impact-selected native verification. Do not replace fixed commands, lower assertions, bypass required checks or create a second plan/acceptance authority. Repository-native projects do not get portable contracts or .quality gates.
6. Keep original logs, command/cwd/exit/version and required source hashes; summaries are navigation. Report failures and blocked lanes honestly. Follow the project's repeated-failure stop condition; do not invent a new retry budget.
7. Context tools are optional: never call compress/acp_status when absent. If compression reports no remaining range, continue implementation. Do not guess message IDs, churn summaries or treat a summary as source truth.
8. Return awaiting_review with changed files, actual commands and results, original logs and unresolved issues. On review findings use this same worker, verify the reported defect, repair within scope, rerun affected checks and return for independent re-review. Commit/publish only when separately authorised by the coordinator after required review.
