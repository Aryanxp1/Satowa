# LEX / Setowa — Coding Agent Prompts & Operating Protocol

Use `LEX_MASTER_ARCHITECTURE.md` as the technical source of truth. This file contains copy-paste prompts for Antigravity and Cline.

## 1. Antigravity — repository audit

```text
You are the Architect/Technical Lead for LEX / Setowa.

Before changing code, audit the repository completely.

Read:
- README.md
- START_HERE.md
- ARCHITECTURE.md
- PLANNING.md
- LEX_Milestone.md
- backend/EVIDENCE_WORKFLOW.md
- .ai/* if present
- backend routes/services/demo/UI
- tests
- Cloudinary integration
- Gemini integration
- run_local.sh
- credential configuration

The repository already contains substantial teammate/Codex work. DO NOT rebuild from scratch.

Return:
1. current architecture
2. current folder structure
3. working features
4. APIs/routes
5. DB schema
6. Cloudinary path
7. AI path
8. review/versioning path
9. report path
10. tests
11. missing/weak pieces
12. conflicts/duplicates
13. risks
14. recommended next tasks
15. exact files for the next task

Do not modify code during this audit.
```

## 2. Antigravity — architecture lock

```text
Reconcile the repository with LEX_MASTER_ARCHITECTURE.md.

Do not perform a giant refactor just for aesthetics.

Rules:
- preserve working FastAPI + SQLite + Cloudinary + optional Gemini architecture
- server owns business rules
- report uses persisted approved records only
- approved text stays separate from AI draft
- edits/evidence changes invalidate approval
- version checks protect stale approvals
- synthetic demo remains available
- no microservices
- no vector DB for Milestone 1
- no wholesale MomentSearch/SentrySearch integration
- no Cloudinary reimplementation

Update .ai/PROJECT_STATE.md, ARCHITECTURE.md, DECISIONS.md, TASK_BOARD.md, HANDOFF.md and CHANGELOG.md.

Produce current-vs-target folder mapping and a dependency-aware task plan.
Do not implement feature work yet.
```

## 3. Antigravity — task decomposition

```text
Break remaining work into small coding-agent tasks.

Each task must have:
- one owner
- limited files
- explicit acceptance criteria
- explicit tests
- no overlapping active ownership

Preferred task size: one logical feature, roughly 1–5 files where practical, one commit/PR.

Update TASK_BOARD.md with:
TASK-ID / Title / Owner / Status / Files / Dependencies / Acceptance Criteria / Tests / Notes.

Do not create Phase 2 tasks yet.
```

## 4. Cline — builder initialization

```text
You are the implementation engineer for one scoped Setowa task.

Read:
- LEX_MASTER_ARCHITECTURE.md
- .ai/AGENTS.md
- .ai/PROJECT_STATE.md
- .ai/ARCHITECTURE.md
- .ai/TASK_BOARD.md
- .ai/HANDOFF.md
- relevant existing code

Task:
[TASK ID]
[TITLE]
[REQUIREMENTS]

Before coding:
1. inspect existing implementation
2. identify exact files to change
3. propose smallest implementation
4. reuse existing code

Then implement.

After coding:
- run relevant tests
- run broader tests when practical
- check syntax/type/lint
- verify existing behavior
- update HANDOFF.md
- update CHANGELOG.md if needed

Final response:
- files changed
- behavior changed
- tests run/result
- risks
- next action

Do not claim completion with failing tests.
Do not perform unrelated refactors.
```

## 5. Cline — Cloudinary

```text
Implement only the Cloudinary path required by the current task.

Requirements:
- server-side signed upload
- secrets never reach browser
- persist public ID, secure URL and version where available
- link asset to visit
- preserve source/permission metadata where supported
- no duplicate local media storage
- preserve synthetic demo behavior
- provider failure must not corrupt workflow state

Inspect existing implementation first and reuse it.

Test valid upload metadata, persistence, missing credentials, provider failure and correct visit association.

Do not implement semantic search, video retrieval, embeddings or vector DB.
```

## 6. Cline — pair validation

```text
Implement/review before/after validation.

Server must enforce:
before_asset != after_asset
before_asset.visit.site_id == after_asset.visit.site_id
before_visit.visit_date < after_visit.visit_date

Client checks are UX only.

Test same-site valid pair, different-site rejection, same-asset rejection, invalid/equal date ordering and missing assets.

Do not add automatic pair discovery.
```

## 7. Cline — AI comparison

```text
Implement/review the image comparison layer.

Structured output:
{
  status,
  observation,
  reasoning_summary,
  confidence,
  limitations
}

Allowed status:
supported | uncertain | insufficient_evidence | provider_unavailable

Rules:
- describe observable differences
- no invented measurements
- no unsupported exact counts
- no causal claims
- no environmental impact claims from two photos alone
- explicitly refuse unreliable comparisons
- concise user-facing explanation only
- never expose chain-of-thought

Gemini is optional. Provider failure becomes a controlled state.
Do not modify review state inside the provider adapter.
```

## 8. Cline — review workflow

```text
Implement/review observation review state.

States:
pending / approved / rejected

Rules:
- pending cannot enter report
- rejected cannot enter report
- approved can enter report
- editing approved text resets to pending
- changing approved evidence resets to pending
- stale expected_version cannot approve newer revision
- ai_observation and approved_text remain separate
- retain revision history

Business rules must be server-side.
```

## 9. Cline — report generation

```text
Implement/review report generation.

The report is a serialization of persisted reviewed data.

Use ONLY:
- approved observation text
- original before/after evidence
- original Cloudinary links
- explicitly recorded measurements

Never:
- call Gemini for report rewriting
- regenerate claims
- include pending/rejected observations
- infer measurements from images

Add tests for approved inclusion, pending/rejected exclusion, exact approved text and original evidence links.
```

## 10. Cline — UI

```text
Improve the UI only as needed for the core demo.

Flow:
site → visits → media → compare → AI result → review → report

Priorities:
1 evidence visibility
2 before/after clarity
3 review status
4 source links
5 uncertainty
6 clean demo flow

Do not add analytics, generic chatbot, campaign generator, semantic search or complex navigation.
Reuse the current UI architecture.
```

## 11. Antigravity — code review

```text
Review this branch as technical lead.

Check:
1 task correctness
2 existing behavior preserved
3 architecture compliance
4 server-side business rules
5 provider boundaries
6 Cloudinary source-of-truth rule
7 no report leakage of pending/rejected claims
8 edit/evidence changes reset approval
9 stale versions rejected
10 invalid pairs rejected
11 secrets not exposed
12 synthetic data clearly labeled
13 code size and cohesion
14 duplicate functionality
15 meaningful tests

Return PASS or CHANGES REQUIRED.
If changes are required, provide a precise fix list for Cline.
```

## 12. Antigravity — integration

```text
Integrate the completed feature branch into dev.

Before merge:
- inspect diff
- inspect tests
- inspect architecture changes
- inspect HANDOFF.md
- run backend test suite
- check for secrets/generated DB files
- verify documentation
- verify acceptance criteria

After merge:
- update PROJECT_STATE.md
- update TASK_BOARD.md
- update CHANGELOG.md
- record important decisions
- write next HANDOFF.md

Do not merge code that breaks the evidence chain.
```

## 13. Stop overengineering prompt

```text
STOP FEATURE EXPANSION.

Milestone 1 only needs:
site → visits → assets → pair → AI draft/refusal → review → persistence → approved-only report.

Do not add vector DB, Redis, queues, microservices, agent frameworks, semantic search, video RAG, automatic pair discovery, impact scoring or multi-project analytics.

Return to the smallest implementation that satisfies the acceptance criteria.
```

## 14. Stop unnecessary rewrite prompt

```text
Do not rewrite the existing module yet.

First identify:
1 what already works
2 exact gap
3 smallest patch
4 regression risks

Only refactor if the existing structure makes the requirement genuinely unsafe or impossible.
Preserve public behavior and tests.
```

## 15. AI accuracy warning prompt

```text
Do not claim that AI comparison accuracy is proven.

The current system demonstrates evidence-aware drafting, structured comparison and explicit refusal.
Real-world accuracy must be evaluated with permissioned real before/after pairs and human review.
Update wording accordingly.
```

## 16. Final integration rehearsal

```text
Run a complete Setowa MVP rehearsal:

1 clean environment
2 create site
3 create earlier visit
4 create later visit
5 upload permissioned photos
6 select valid pair
7 run live AI comparison
8 inspect AI output
9 verify evidence references
10 approve
11 reload
12 verify persistence
13 export report
14 verify exact approved text
15 verify original Cloudinary links
16 verify no pending/rejected claims
17 edit approved text
18 verify it becomes pending
19 reapprove
20 test deliberately weak pair
21 verify refusal/uncertainty
22 test provider-unavailable fallback
23 run full test suite

Do not call the demo complete until all pass.
```

## 17. Agent handoff format

```text
## Task
TASK-XXX

## Status
DONE / BLOCKED / PARTIAL

## Changed
- file
- file

## Behavior
What changed.

## Tests
Command:
Result:

## Risks
Known limitations.

## Next
What the next agent should do.

## Architecture Notes
Important decisions.
```

## 18. Shared state rules

`PROJECT_STATE.md` → what works, broken, blocked, next.

`TASK_BOARD.md` → ownership.

`DECISIONS.md` → why.

`HANDOFF.md` → next-agent context.

`ARCHITECTURE.md` → responsibilities and boundaries.

`CHANGELOG.md` → recent changes.

## 19. Recommended implementation sequence

```text
T001 Repository audit
 ↓
T002 Architecture/state alignment
 ↓
T003 Test baseline
 ↓
T004 Cloudinary/live upload validation
 ↓
T005 Pair validation hardening
 ↓
T006 AI comparison hardening
 ↓
T007 Observation/review hardening
 ↓
T008 Report integrity
 ↓
T009 UI/demo polish
 ↓
T010 Real-media rehearsal
 ↓
T011 Final integration
```

Only after T011 should Phase 2 begin.

## 20. Final rule for every agent

Ask:

> **Does this make the evidence chain more reliable, more traceable, or more demoable?**

If not, defer it.

The goal is not the biggest codebase. The goal is a small, understandable system where original media → AI proposal → supporting evidence → human verification → persisted approval → traceable report works every time.
