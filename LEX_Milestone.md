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

The local synthetic sample demonstrates this workflow without provider calls. It is **not** evidence that Gemini can judge real cleanup pairs accurately. Any quantity such as kilograms must come from a separately entered measurement and source, never from image inference.

## Boundaries for this milestone

Cloudinary owns original media and delivery; Setowa stores references and review state. Gemini is optional and can refuse. Setowa does not claim automatic impact scoring, field verification, general semantic search, video understanding, or a production-ready public auth system. MomentSearch and SentrySearch are design references, not integrated dependencies.

Before submission, prioritize one permissioned real site with comparable before/after images, a labeled poor-comparison case, reviewer checks, and a report that can be traced back to its originals. Then rehearse the synthetic fallback for a provider outage. See [TIMELINE.md](TIMELINE.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [the evidence workflow API](backend/EVIDENCE_WORKFLOW.md).
