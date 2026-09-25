# AGENTS.md — Multi-Agent Coordination Protocol
# Setowa / LEX — Code Cubicle 6.0
# Created: 2026-09-26

## Agent Roles

| Agent | Role | Scope |
|:---|:---|:---|
| **Antigravity (AGY)** | Architect + Technical Lead | Planning, auditing, reviewing, updating `.ai/` files. Does NOT write application code. |
| **Cline** | Primary Builder | Implements all application code changes per task specs from AGY. Runs tests. |
| **User (Aryan)** | Product Owner + Final Approver | Approves all architectural decisions. Signs off on each completed task. |

## Collaboration Rules

1. **AGY defines tasks.** Cline executes them. Never the reverse.
2. **Each task has an ID** (T001, T002, ...). Reference the ID in all commits, PR descriptions, and `.ai/CHANGELOG.md` entries.
3. **Cline reads `.ai/TASK_BOARD.md`** before starting any work session to understand the current state.
4. **Cline updates `.ai/HANDOFF.md`** upon completing a task or stopping mid-task.
5. **AGY does not modify application code**, schemas, or tests. AGY only modifies `.ai/` files and communicates instructions.
6. **No task is "done" until all acceptance criteria are met** and the user has explicitly confirmed.

## Communication Protocol

- Cline → AGY: Update `HANDOFF.md` with results, blockers, and open questions.
- AGY → Cline: Update `TASK_BOARD.md` and `HANDOFF.md` with next instructions.
- User → All: Directs via chat. All direction is captured in `DECISIONS.md` when it affects architecture.

## Scope Hard Limits (Inviolable)

- NO microservices, Redis, vector databases, MomentSearch, SentrySearch.
- NO wholesale rewrites of working code.
- NO modifications to evidence chain validation logic (it is correct).
- NO auto-approval of AI output. Human review gate is mandatory.
- NO LLM calls during report generation.
