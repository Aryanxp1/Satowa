# Setowa delivery plan

The chosen Code Cubicle direction is a **reviewable cleanup report from field evidence**. Team LEX is solving one problem statement through a complete workflow rather than combining challenges or claiming general media intelligence.

## Product decision

Organizers often have photos from separate cleanup visits but lack a defensible chain from those images to a public claim. Setowa records the site and visit dates, preserves original Cloudinary references, lets AI propose a narrowly visual observation, and asks a person to approve the exact words that appear in a report. Measurements require an explicit source.

## Current local scope

The site/visit/pair/review/report flow, synthetic sample, setup page, project navigation, light/dark theme, SQLite persistence, Cloudinary upload path, and optional Gemini comparison are implemented. Automated tests cover server rules. The sample does not call real providers.

## Before feature freeze

1. Collect permissioned photos from at least two visits at one site, including a comparable pair and a deliberately weak pair. Record rights and source labels.
2. Run the live Cloudinary upload and Gemini comparison with those images. Check both the draft's factual wording and the refusal path with a human reviewer; record failures without embellishing them.
3. Rehearse create → review → reload → export on the final environment. Compare report text and links with the saved review and original Cloudinary assets.
4. Remove or clearly label any controls that depend on unavailable credentials. Keep the synthetic sample as a transparent backup.
5. Prepare a short screen recording and pitch grounded in the working flow and documented limits.

Do not add automatic impact scoring, video retrieval, broad analytics, or a second problem statement until this path has been demonstrated reliably. A public deployment also requires a separate auth, persistence, and operations pass.
