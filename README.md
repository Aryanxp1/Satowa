# Setowa

**Setowa** (*Setu*, bridge + *Wa*, harmony) is the cleanup evidence workspace built by **Team LEX** for Code Cubicle 6.0. It connects dated field media to cautious before/after observations, human review, and reports that cite their sources.

Run the local app:

```bash
./run_local.sh
```

Open [the workspace](http://127.0.0.1:8000/) or [the product showcase](http://127.0.0.1:8000/showcase/). [START_HERE.md](./START_HERE.md) explains setup and the guided synthetic walkthrough.

The working flow is: **site and visits → permissioned photos → before/after pair → AI proposal or explicit uncertainty → human approval → evidence-linked report**. Photos do not establish waste weight or environmental impact; quantities enter reports only when someone records a measurement and its source.

The backend uses FastAPI, SQLite, Cloudinary for media uploads, and optional Gemini image comparison. The frontend is a lightweight local web app. The synthetic sample works without provider calls. Keys live only in ignored local configuration and are never committed.

Team LEX: Aryan Vishwakarma (lead and integration), Farhan Akhtar (backend and evidence), and Shubh Gunjan (frontend and showcase). The [workflow](./ROLES_AND_WORKFLOW.md) routes feature pull requests through `dev` before a release reaches `main`.

Original planning and submission materials remain available: [PLANNING.md](./PLANNING.md), [TIMELINE.md](./TIMELINE.md), [IDEATION_FRAMEWORK.md](./IDEATION_FRAMEWORK.md), and [SUBMISSION_KIT/](./SUBMISSION_KIT/). The older plans are historical; the current implementation is described here and in [START_HERE.md](./START_HERE.md).
