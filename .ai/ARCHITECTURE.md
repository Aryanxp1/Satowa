# ARCHITECTURE.md — Setowa / LEX Architecture Reference
# Source of Truth: LEX_MASTER_ARCHITECTURE.md

## 1. Product Overview
Setowa transforms unstructured field photos and metadata into a verifiable, audit-ready environmental cleanup report.

### Core Trust Model
```
AI PROPOSES
     ↓
EVIDENCE SUPPORTS
     ↓
HUMAN VERIFIES
     ↓
APPROVED RECORD
     ↓
TRACEABLE REPORT
```

## 2. Core Invariants
1. **Human Verification Gate:** AI never automatically approves an observation. `review_status` defaults to `pending`.
2. **Review State Reset:** Any edit to an observation or underlying evidence resets `review_status` to `pending`.
3. **Optimistic Locking:** Every observation update requires matching `version` to prevent concurrent overwrite (`409 Conflict`).
4. **Deterministic Reports:** Report generation performs zero LLM calls; queries only database-approved observations with approved text.
5. **Traceable Asset URLs:** Original storage URLs (Cloudinary) are preserved end-to-end; no mock local URLs in reports.
6. **Valid Evidence Pairs:** Pair validation enforces same site, chronological ordering (before < after), and distinct assets.
7. **Explicit Measurement Provenance:** Any metric requires named human reviewer and declared source.

## 3. Storage & Schema Principles
- SQLite database (`evidence_store.py`)
- Migrations must be non-destructive (column inspection + `ALTER TABLE`)
- Review status states: `pending`, `approved`, `rejected` (with `unreliable` AI outputs mapped to `pending` with `reliability_reason` preserved)
