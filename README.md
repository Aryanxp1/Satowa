# Setowa

**Cleanup evidence that can be checked.** Setowa is Team LEX's Code Cubicle 6.0 project for turning dated cleanup photos into a human-reviewed, source-linked report. The name combines *Setu* (bridge) and *Wa* (harmony): a bridge between field media and a shared account of what changed.

> **AI proposes → evidence supports → a person verifies → approved records become the report.**

## What works

- Create a cleanup site and dated visits; upload permissioned JPEG, PNG, or WebP photos to Cloudinary with source attribution.
- Select an earlier and later photo from the same site. The API rejects reversed dates, cross-site pairs, and the same asset twice.
- Request an optional Gemini comparison. If credentials or evidence are inadequate, the app explains the uncertainty; a reviewer can write their own observation.
- Approve, edit, or reject observations. Edits reset approval and stale review versions are rejected.
- Export Markdown or JSON reports from saved approved observations, original evidence links, and measurements explicitly recorded with a source. Photos alone never establish a waste quantity.
- Search a project's saved media and video-frame descriptions, reviewer-approved observations, and recorded measurements by meaning using on-demand Gemini embeddings. Results show their review status and evidence links; a Gemini key is required, and no keyword fallback is mislabeled semantic search.
- Generate and edit saved local social, newsletter, and volunteer-update drafts from approved observations and sourced measurements. Numerical claims in observation prose are omitted; quantities come from separate measurement records with a supplied source. Drafts show evidence references, never post automatically, and turn stale if source records change; stale drafts cannot be copied from the workspace. Synthetic examples carry an explicit demo label.
- Walk through a clearly labeled **synthetic** sample without Cloudinary or Gemini calls. It is a product demo, not proof of cleanup impact.

## Run locally

```bash
./run_local.sh
```

Open the [workspace](http://127.0.0.1:8000/) or [showcase](http://127.0.0.1:8000/showcase/). The app redirects `/` to `/demo/`; API docs are at `/docs`. See [START_HERE.md](START_HERE.md) for the guided walkthrough and [backend/README.md](backend/README.md) for backend setup. Local provider keys belong in the ignored `credential.json` (copy `credential.example.json`) or `backend/.env`. Never commit keys or the SQLite database.

## Architecture and project state

The UI is served by FastAPI. SQLite holds Setowa's sites, visits, evidence references, observation revisions, reviews, and measurements. Cloudinary stores uploaded originals; Gemini is an optional comparison service. The [architecture](ARCHITECTURE.md) and [evidence API](backend/EVIDENCE_WORKFLOW.md) explain the flow and its limits.

Semantic search indexes only after a user searches, caches text embeddings in local SQLite, and currently scans up to 24 recent project records per request to bound provider calls. Gemini embedding calls may count toward the account's quota; Setowa does not initiate them automatically. Campaign copy is deliberately template-generated from saved records, with no extra model call or external publishing integration.

[LEX_Milestone.md](LEX_Milestone.md) records Aryan's Milestone 1 acceptance criteria and current validation status. The current focus is **local use**; invited-user auth and deployment are deferred. Real permissioned field-pair evaluation remains to be completed. Do not present the synthetic sample as field evidence or a live provider evaluation.

## Team and collaboration

### Aryan Vishwakarma 🐐
- Leader

### Farhan Akhtar 🥀
- Random Kid

### Shubhr Gunjan 🗿
- Aura

Setowa is the product; **LEX** is the team: Aryan Vishwakarma (lead/integration), Farhan Akhtar (backend/evidence), and Shubh Gunjan (frontend/showcase). Features go through PRs into `dev`; tested releases move from `dev` to `main`. See [ROLES_AND_WORKFLOW.md](ROLES_AND_WORKFLOW.md).

The repository is private during development. If the event requires a public repository, coordinate the release and disclosure of earlier work with the organizers before changing visibility. Git history and [START_HERE.md](START_HERE.md) retain the provenance of earlier work.
