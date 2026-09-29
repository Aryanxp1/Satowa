# Setowa Milestone 1 — reviewable cleanup report

This file updates Aryan's original LEX implementation brief to the current Setowa product. The original brief remains in Git history. **Product rule:** AI proposes, evidence supports, a person verifies, and only approved records enter a report.

## Definition of done

A reviewer can create one cleanup site, record an earlier and later visit, attach permissioned photos, select a same-site pair, inspect a cautious comparison or an explicit refusal, edit or reject the observation, approve a supported statement, reload, and export a report containing the saved approved text and its original evidence links.

| Acceptance criterion | Current implementation | Remaining validation |
| --- | --- | --- |
| Same-site, earlier-before-later pair | Server checks site, distinct assets, and strict date order. | Demo with real permissioned visits. |
| AI proposes, human approves | Draft, working text, approved text, and reviewer decision are separate. | Human review of real model outputs. |
| Edits require reapproval | Text or evidence edits reset approval; versions prevent stale review. | Confirm in final browser rehearsal. |
| AI can decline | Missing credentials, poor/retrieval-limited evidence, or model failure produces an unreliable state/reason. | Evaluate good and deliberately bad real pairs. |
| Persistence | SQLite stores visits, assets, observations, revisions, and review state. | Reload and export against the final demo environment. |
| Report integrity | Server queries approved records, keeps original source links, and uses explicitly sourced measurements. | Inspect final exported report against original media. |

The local synthetic sample demonstrates this workflow without provider calls. It is **not** evidence of real-model accuracy. Any quantity such as kilograms must come from a separately entered measurement and source, never from image inference.

## Boundaries for this milestone

Cloudinary owns original media and delivery; Setowa stores references and review state. Optional NVIDIA single-image analysis and explicit 24-record embedding batches support discovery. Search falls back to labeled keyword matches when vectors are unavailable. Automatic NVIDIA pair comparison is not enabled until tested with real comparable images. Campaign drafts use templates grounded in approved observations and sourced measurements, and require human checking before sharing. The named-token Render pilot is not public account authentication. Durable PostgreSQL support exists, but hosted persistence still needs verification. Setowa does not claim automatic impact scoring, independent field verification, validated search relevance, or production-ready public auth. MomentSearch and SentrySearch are design references, not integrated dependencies.

Before submission, prioritize one permissioned real site with comparable before/after images, a labeled poor-comparison case, reviewer checks, and a report that can be traced back to its originals. Then rehearse the synthetic fallback for a provider outage. See [TIMELINE.md](TIMELINE.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [the evidence workflow API](backend/EVIDENCE_WORKFLOW.md).

## Release-candidate update — 2026-09-29

Setowa now has an optional NVIDIA provider path, explicit semantic indexing, no-key keyword fallback, safer campaign invalidation, and PostgreSQL migration support. See [PROJECT_STATUS.md](PROJECT_STATUS.md) for evidence and remaining gates. The complete production milestone is **not complete**: account/project authorization, live NVIDIA evaluation, real field data, full hosted database validation, and final release checks remain outstanding. Gemini is not a readiness requirement. No automatic NVIDIA pair verdict is claimed.
