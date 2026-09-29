# Security and boundaries

Keep Cloudinary, NVIDIA, optional Gemini, reviewer tokens and DATABASE_URL server-side in host secret settings or ignored local files. Rotate any credential exposed in chat or logs. Never commit local databases or private media. Browser pilot tokens stay in memory; provider secrets are never serialized to the UI.

The current remote service is a single-reviewer pilot. It is not production account authentication. Full role/project/session/CSRF/login-rate-limit work remains a release blocker. Production startup is intentionally blocked until it is implemented and verified.

Permission revocation prevents new NVIDIA analysis and removes media from search/report/campaign source selection. Stale campaigns withhold their prior body and links. Revocation in Setowa does not physically delete an already public Cloudinary object; deletion requires a separate deliberate action.

NVIDIA errors omit raw response bodies and credentials. Registered Cloudinary URLs are resolved server-side. Visual outputs are unreviewed proposals, not impact measurements. The workspace/story CSP blocks third-party scripts, framing, and arbitrary connection destinations. Inline styling remains permitted for the existing UI.

Report vulnerabilities privately to the repository owner without including live secrets. Run isolated tests and provider mocks before deployment; a dependency audit does not replace application security review.

PostgreSQL migration 2 enables deny-by-default RLS on Setowa tables. No anon/authenticated policies are added. The backend uses a server-side owner connection; this does not substitute for the outstanding per-user project authorization.
