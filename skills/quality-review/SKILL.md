---
name: quality-review
description: Independently review a plan, code structure, test validity and source-bound evidence; apply pinned BMAD no-code review and report actionable, scored findings.
---

Managed-By: MyOpenCodeConfig quality

# Read-only review and handoff

Project-mode preflight: root obtains quality_info before any file creation and passes the registered profile to each reviewer. For repository-native projects, independently read the listed authorities and follow their task/acceptance rules. The portable schema/artifact/history protocol below applies ONLY to portable projects: do not invent contract IDs, snapshots or generic PASS, create new repository specs/plans/reports, or ask the local worker to do so. Return original findings in task context with stable IDs, severity, concrete evidence and impact, confidence, repair value/effort/regression risk, and deferral owner/deadline/conditions when relevant. Use pinned BMAD lenses read-only, with flat sibling sessions and actual model identities, while native checks and required independent review remain the acceptance boundary. Missing native evidence is incomplete, never a pass. Preserve old findings and actual repair/re-verification in task context. REPOSITORY_NATIVE_REQUIRED means this generic machine gate does not apply; it is not an audit verdict. Do not weaken or add a competing repository quality authority.

Read requirements and expected behavior before implementation details. Verify actual source/callers/guards and test evidence, not only the worker's summary. No shell, source edits, policy changes, or writes to approved plans. All reports return to the native parent, which archives originals verbatim only under .quality/reviews/ without modifying conclusions; the same local-worker owns execution evidence and repairs.

Native completion still requires the selected pinned BMAD workflow and every linked step reached below. Before a final native READY, explicitly close any earlier BMAD_BLOCKED with actual completed steps/lenses, or preserve complete=false and report the gap. Native mode skips portable schema/artifact/history requirements, not the backend review itself. The native parent keeps reports in the project-authorised task context, never creates .quality merely to archive them.

Schemas: call the read-only quality_resource tool with name="schema/review"; do not read engineering resources through external filesystem paths. Every review has round (positive integer, increase on each re-review of the same kind), closed_findings (array), kind=plan/code/structure/tests, semantic contract_id from quality_prepare, actual reviewer role/model/session, complete boolean, exact current snapshot_id for source reviews, raw rejections with reasons and actionable findings. Include independent review session IDs, not the parent's or executor's. Read the schema in full before producing JSON. The root coordinator archives original text and JSON verbatim under .quality/reviews/; execution evidence remains local-worker owned. Zero findings is valid.

## Plan review

Check every necessary requirement has implementation tasks and observable acceptance, missing/ambiguous behavior, interfaces, architectural constraints, environment and migration/recovery details. Do not treat a strong planner's assumptions as verified facts. Return incomplete on missing critical evidence. Approve the semantic plan before actual human plan approval; approval metadata does not change the semantic hash, but any change to requirements/plan does.

Check that each registered lane is feasible for this plan: compare its actual counting unit (files, tests, assertions or targets) and minimum with the planned scope. A minimum of three scanned modules cannot be satisfied by a two-module plan. Do not count functions as modules or prescribe unnecessary files to meet a threshold. Unknown counter semantics require evidence/clarification before plan readiness, not an assumed match.

## Pinned BMAD backend

Backend provenance is the pinned public BMAD commit described by this installed skill and quality_info.
Quick: quality_resource(name="bmad/quick/workflow.md").
Thorough: quality_resource(name="bmad/thorough/workflow.md").
Linked quality_resource:<name> references are logical tool requests, never filesystem paths. Call quality_resource for every linked step/prompt reached. It serves only fixed public package assets and redacts installation path prefixes; it cannot read arbitrary user files.

Read the selected workflow and its linked steps fully as reached. These are deployment-time official render_skill.py outputs from the pinned complete upstream resources, with workflow.fixes=handoff, workflow.interactive=false, no arbitrary project hooks and the blind-hunter finding quota disabled. Do not invoke raw upstream SKILL.md, install/update commands or project custom scripts during review. If files/provenance are missing, return BMAD_BLOCKED/complete=false, not a claim of BMAD review. Report backend and actually completed lenses.

OpenCode host substitutions (these override incompatible platform mechanics only):
- Gather: the worker/parent supplies real baseline/source snapshot, complete changed/untracked scope and diff artifact before review. Read those artifacts. Missing/empty/oversized omitted scope is incomplete; do not run git/shell or infer a clean review from missing input.
- Subagents: use a flat sibling topology. The root cloud-workflow directly dispatches cloud-review and, for medium/high risk, fresh cloud-structure-review and cloud-test-review sessions. OpenCode may enforce a single subagent depth: cloud-review MUST NOT spawn nested lenses or increase host depth. The root supplies the selected BMAD edge-case/intent and verification-gap prompts/context via quality_resource, collects the actual sibling reports through native callbacks, and returns them to the code reviewer for final triage when needed. Never ask the user to paste reports. All reviewer children are leaves. Low-risk code review covers behavior, structure and test validity itself; any explicitly requested independent lens is still supplied as a root sibling.
- Verification: every alleged gap, including verification-gap output, must be checked against actual tests, callers and existing coverage before classification. No minimum finding count. Preserve rejected raw IDs/reasons before root-cause grouping.
- Persistence: no review writes, even if official step 5 says append to plan. Return findings/triage in full for the root coordinator to store verbatim under .quality/reviews/ with unique round originals. Reviewer children never write. Preserve approved plan/spec bytes. No automatic source patches.
- Incomplete: failed/missing active lens, unreadable target or missing evidence is complete=false / NEEDS_EVIDENCE; never report clean PASS. Ambiguous requirements become decision findings for the parent, not guessed repairs. Low-risk quick review still checks behavior, structure and test validity; medium/high risk requires standalone structure/tests kinds for the final gate.

## Finding format and priority

For every finding record file/line, concrete consequence, reachability/evidence, impact scope, confidence (confirmed/probable/unverified), severity, origin, disposition, status, and repair value/effort/regression risk/verification. Risk dimensions impact/likelihood/breadth/time each 0..5 or null (unknown), with reasoning in the original report; the custom numeric score is sorting assistance, not an external standard or override of blockers.

critical/high/medium, unresolved fix/decision/investigate, and unmet necessary acceptance are blocking. Cosmetic preference alone is not a defect. A low/nit preexisting issue can be deferred only with explicit acceptance, owner, reason, until date and early re-evaluation trigger; an implementing model cannot approve its own exemption. Newly introduced issues are fixed or escalated, not silently deferred. A resolved finding must cite actual current re-verification, not a promise. Earlier original findings stay immutable across rounds.

The final parent calls quality_gate against current bytes and actual evidence. Code repairs return to the same local-worker; material spec/plan defects return to cloud planning and user confirmation. Stop after three unsuccessful rounds for the same blocker. Read-only review cannot claim to have run any checks itself.

History protocol: preserve every review as .quality/reviews/<kind>-<round>.json before using a latest pointer. The gate reads preserved rounds itself and uses the highest round per kind; a later failure cannot be hidden by submitting an older clean report. To close any previous open critical/high/medium finding, add closed_findings entries {"id":"<kind>:<old-round>:<finding-id>","reason":"actual resolution and checks","evidence":"<current-snapshot-id>:<passed-lane-id>"}. This references real current verification; it is not proof of semantic correctness. Every prior blocking finding must be explicitly accounted for. Resolved current findings use the same snapshot:lane syntax in resolution_evidence.

Pinned BMAD source commit: e435a22574fe55722841086e5566420178b98df3 (preview line). All public resource requests enforce deployment manifest hashes; integrity failure is BMAD_BLOCKED. Public BMAD assets require no external_directory permission. Separately authorised approved-plan snapshots are read-only and do not grant access to settings, credentials or unrelated material.

Semantic-contract revisions: history closure applies only within the same contract_id. If cloud planning materially changes the contract, preserve old-contract reports verbatim for provenance, but do not pretend source tests ran to close plan defects. The new semantic contract receives a fresh independent plan review; describe the corrections in its original text. quality_gate ignores archived old-contract rounds and rejects caller-selected stale-contract artifacts. Do not include old-contract reports among the latest review pointers.

Plan-only readiness: before implementation, document corrections may close historical plan findings with evidence="contract:<current-contract-id>" and a concrete document/acceptance verification reason. This is an independent document review, never a claim that product tests ran. The coordinator can preserve exact plan-review text/JSON under docs/superpowers/plans/reviews/ and call quality_prepare with plan_reviews to compute plan_gate. Non-schema original reports stay verbatim as raw-*.md outside the gate JSON set. Incomplete valid rounds remain history; only the latest must be complete, and every historical actual blocker still requires closure. Final source/code findings continue to require current passed lane references.


## Worker continuity

The main coordinator owns worker routing. With session routing enabled, host storage retains the validated worker ID and injects its recovery state independently of compaction. An ID-free repair call resumes the verified original worker. A reviewer returns findings and current-version evidence even if that ID is absent from its own context; it must not turn missing routing metadata into an unfinished code audit. Never invent an ID or passively wait for another callback from an idle executor. An ambiguous or truly unavailable worker remains explicitly blocked pending reconciliation; replacement requires explicit authorisation where the approved plan mandates the same session, proof the old executor is not running and a complete handoff. Freeze and project-native acceptance rules are unchanged.
