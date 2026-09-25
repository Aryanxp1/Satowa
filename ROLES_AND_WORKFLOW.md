# Team LEX — Setowa workflow

**Aryan Vishwakarma** leads integration, architecture, review, and release coordination. **Farhan Akhtar** owns the backend, evidence rules, Cloudinary/Gemini integration, and API validation. **Shubh Gunjan** owns the frontend experience, responsive presentation, and showcase/pitch assets. Responsibilities can overlap; a PR should identify its author and reviewers.

## Branches

- `dev` is the integration branch. Feature branches merge there through a PR after review and checks.
- `main` is the release branch. Promote a tested `dev` state through a PR; avoid direct commits.
- Use short descriptive branches and `feat:`, `fix:`, `docs:`, or `chore:` commit prefixes.

For a Setowa change, check the affected browser flow and run `cd backend && python -m pytest -q`. Reviewers should inspect report integrity, evidence ordering, source links, and any change to auth or provider data handling. Never put `credential.json`, `.env`, SQLite data, reviewer tokens, or permissioned source media in Git. Use `credential.example.json` for shape only.

## Before release or submission

Aryan confirms the integrated demo and relevant PR. Farhan verifies the backend and exported report. Shubh verifies presentation and responsive views. The team records what was built before the event, what was built during it, and which media is synthetic or permissioned. Repository privacy is a development setting; change it only after checking the organizer's access/submission rules.
