# Setowa Render pilot

The current hosted app is a **single-reviewer pilot** at [setowa.onrender.com](https://setowa.onrender.com). It uses a named token in tab memory. A hosted deployment and working provider connection must be verified against the release commit before showing it as current.

Use [DEPLOYMENT.md](../DEPLOYMENT.md) for the current Docker root, environment variables, PostgreSQL migration, and verification requirements. Keep all keys and the database connection string in Render's private environment settings. Cloudinary is needed for real uploads; NVIDIA is optional for semantic indexing and single-image analysis. Without an AI key, manual review and labeled keyword search work. The former Gemini requirement in this guide has been retired.

Check `/api/v1/health`, `/api/v1/ready`, and anonymous `401` on `/api/v1/projects`. Then sign in with the reviewer token through `/demo/` and test media, review, search, campaign, report, and restart persistence. A configured key in readiness is **not** proof that a live provider request succeeded.

This pilot is not account-based multi-user authentication. Never present synthetic media or template drafts as verified field impact. See [README.md](../README.md#project-todo) for unfinished release work.
