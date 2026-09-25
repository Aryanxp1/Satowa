# LEX --- Hackathon Implementation Brief

## Milestone 1: Reviewable Cleanup Report from Field Evidence

> **Primary rule:** AI proposes → evidence supports → human verifies →
> approved evidence becomes the report.

This document is the source of truth for the first implementation
milestone. Do not expand the scope until this flow works end-to-end.

------------------------------------------------------------------------

## 1. Problem Statement

The hackathon PS asks for an AI-powered media platform that helps
organizations turn field photos/videos into reliable evidence,
comparisons, insights and reports.

For the first milestone, we are intentionally narrowing this to a
concrete cleanup-reporting workflow:

1.  Organise two visits at one cleanup site.
2.  Select a before/after photo pair.
3.  AI analyzes the pair and drafts an observation.
4.  The organizer reviews the observation and evidence.
5.  Approved observations are persisted.
6.  A report is generated ONLY from saved approved observations and
    original evidence links.

Do not build a generic AI media platform. Cloudinary already provides
much of the underlying media infrastructure and AI capabilities.

------------------------------------------------------------------------

## 2. Product Pitch

### Core pitch

**Create a reviewable cleanup report from field evidence.**

### Product principle

**AI proposes. Evidence supports. Human verifies.**

The system must prioritize traceability and reviewability over
impressive but unverifiable AI claims.

------------------------------------------------------------------------

## 3. Milestone 1 --- Exact User Flow

### Step 1 --- Create cleanup site

User creates/selects a cleanup site.

Minimum fields:

-   Site name
-   Optional location/address
-   Optional description

### Step 2 --- Create two visits

For the same site, create:

-   Visit A / Before
-   Visit B / After

Each visit should have:

-   Site ID
-   Visit date
-   Visit label/type
-   Uploaded Cloudinary assets

For the first demo, two visits are enough.

### Step 3 --- Upload media

Upload photos through Cloudinary.

Store the Cloudinary asset identifiers/URLs in our application database.

Do not build custom media storage.

Cloudinary should remain the source of truth for original media.

### Step 4 --- Select a before/after pair

The organizer manually selects:

-   One photo from the earlier visit
-   One photo from the later visit

Important acceptance rule:

> Both photos must belong to the same cleanup site, and the before visit
> must precede the after visit.

Automatic pair suggestion is OUT OF SCOPE for Milestone 1.

### Step 5 --- AI comparison

Send the selected pair to the AI analysis layer.

Ask the model to:

-   Compare the two images.
-   Identify observable visual differences.
-   Draft a concise cleanup-related observation.
-   Avoid inventing facts.
-   Clearly state uncertainty when the comparison is unreliable.

Example:

> "Less visible litter is present along the photographed section in the
> after image."

Bad example:

> "35 kg of waste was collected."

Photos alone cannot establish a numeric measurement such as weight.

### Step 6 --- Evidence

Every observation must retain its supporting source assets.

Minimum:

-   before_asset_id
-   after_asset_id
-   Cloudinary URLs/identifiers
-   AI-generated observation

The UI must make it obvious which images support the observation.

### Step 7 --- Human review

Organizer can:

-   Approve
-   Edit
-   Reject

Rules:

-   An unreviewed observation cannot appear in a report.
-   Editing an approved observation returns it to `pending`.
-   Changing its evidence also returns it to `pending`.
-   Rejected observations must never appear in the report.

### Step 8 --- Persist review

Save the review record in the database.

At minimum:

``` text
observation_id
site_id
before_asset_id
after_asset_id
ai_observation
approved_observation
review_status
reviewed_at
```

Prefer also storing:

``` text
created_at
updated_at
reviewed_by
ai_analysis_metadata
```

### Step 9 --- Export report

Generate a report from the SAVED database records.

Never regenerate the observation with an LLM during report generation.

The report should contain:

-   Cleanup site
-   Visit dates
-   Approved observation text
-   Before image/source
-   After image/source
-   Original Cloudinary evidence links

Rejected/pending observations must not appear.

------------------------------------------------------------------------

# 4. Acceptance Criteria

The milestone is complete only when all of these work:

### A. Evidence must match

The system prevents/blocks invalid comparisons where:

-   before and after belong to different sites
-   before date is later than after date

### B. Human approval is authoritative

Only `approved` observations can enter a report.

### C. Edits require approval again

If an approved observation's text or evidence changes:

``` text
approved → pending
```

It must be reviewed again.

### D. AI can decline

If images have:

-   very different viewpoints
-   insufficient visual overlap
-   poor quality
-   severe occlusion
-   insufficient evidence

the AI should say the comparison is unreliable instead of inventing a
change.

### E. Persistence

After approving an observation:

1.  Reload the application.
2.  Observation remains approved.
3.  Evidence remains attached.
4.  Report still uses the saved approved record.

### F. Report integrity

Exported report contains exactly the approved/saved observation and
original evidence links.

------------------------------------------------------------------------

# 5. Scope --- DO NOT Build Yet

Do NOT spend Milestone 1 time on:

-   Automatic before/after pair discovery
-   Large sustainability ontology
-   Automatic impact scoring
-   Multi-project analytics
-   Campaign/social-media content generation
-   Full semantic media search
-   Complex video retrieval
-   Complex multimodal RAG
-   Custom vector database unless genuinely required
-   Rebuilding Cloudinary functionality

These are potential Phase 2+ features.

------------------------------------------------------------------------

# 6. Cloudinary Strategy

Cloudinary is a core dependency, not something to compete with.

Use Cloudinary for:

-   Media upload/storage
-   Original asset URLs/IDs
-   Metadata
-   Image/video transformations
-   Existing AI/media analysis capabilities where useful

The application database should store references to Cloudinary assets
and application-specific workflow state.

Do not duplicate original media storage unless there is a concrete
technical requirement.

### Important

Before implementing custom vision/search infrastructure, check whether
Cloudinary already provides the required capability.

We do NOT want to rebuild Cloudinary.

------------------------------------------------------------------------

# 7. Reference Repositories

These are references, not dependencies that must be merged wholesale.

### MomentSearch

Repository: https://github.com/traversaal-ai/momentsearch

Useful ideas:

-   Evidence-oriented retrieval
-   Timestamped evidence
-   Multimodal RAG
-   Evidence/citation linking
-   Confidence gating
-   Keyframe/segment retrieval

Do not integrate the whole repository unless a concrete requirement
appears.

### SentrySearch

Repository: https://github.com/ssrajadh/sentrysearch

Useful ideas:

-   Semantic media retrieval
-   Text → video search
-   Image → video search
-   Embedding retrieval
-   VLM reranking
-   Relevant clip extraction
-   Confidence thresholds

Again, selectively reuse ideas only when needed.

------------------------------------------------------------------------

# 8. AI Behavior Requirements

The AI is an assistant for evidence review, not an authority.

### It SHOULD

-   Describe observable differences.
-   Ground statements in the supplied images.
-   Be concise.
-   State uncertainty.
-   Refuse unsupported conclusions.
-   Separate visual observations from measurements.
-   Return structured output where practical.

### It MUST NOT

-   Invent measurements.
-   Claim causality from two photos alone.
-   Claim exact quantities without evidence.
-   Treat an AI guess as verified fact.
-   Generate a report containing rejected claims.

### Suggested structured response

``` json
{
  "status": "supported | uncertain | insufficient_evidence",
  "observation": "Less visible litter is present along the photographed section.",
  "reasoning_summary": "The after image shows visibly fewer litter items in the overlapping area.",
  "confidence": 0.0,
  "limitations": []
}
```

Do not expose chain-of-thought. `reasoning_summary` should be a short
user-facing explanation, not hidden reasoning.

------------------------------------------------------------------------

# 9. Suggested Data Model

Keep it simple.

## sites

``` text
id
name
location
description
created_at
updated_at
```

## visits

``` text
id
site_id
visit_date
label
created_at
```

## assets

``` text
id
visit_id
cloudinary_public_id
cloudinary_url
resource_type
created_at
```

## observations

``` text
id
site_id
before_asset_id
after_asset_id

ai_observation
approved_observation

review_status
reviewed_by
reviewed_at

ai_confidence
ai_status
ai_limitations

created_at
updated_at
```

Possible review states:

``` text
pending
approved
rejected
```

------------------------------------------------------------------------

# 10. UI --- Minimum Screens

Do not over-design.

### Dashboard

Shows cleanup sites.

### Site page

Shows:

-   Site information
-   Visits
-   Media

### Visit page

Shows uploaded Cloudinary assets.

### Compare page

Shows:

``` text
BEFORE                 AFTER
[image]                [image]

        [Analyze]
```

### Review page

Shows:

``` text
AI Observation

"Less visible litter..."

Evidence:
[Before] [After]

[Approve] [Edit] [Reject]
```

### Report page

Shows only approved observations and their evidence.

------------------------------------------------------------------------

# 11. Engineering Rules

### Keep architecture simple

Prefer:

``` text
Frontend
    ↓
Backend API
    ↓
Database
    ↓
Cloudinary
    ↓
AI analysis
```

Do not introduce microservices unless necessary.

### Keep business rules server-side

The frontend must not decide whether an observation is approved for
reporting.

The backend/database is authoritative.

### Report generation

Report generation queries:

``` text
WHERE review_status = 'approved'
```

It should use the persisted `approved_observation`.

### Evidence integrity

Never replace original Cloudinary references with generated/re-uploaded
images unless required.

------------------------------------------------------------------------

# 12. Development Order

Implement in this order:

### Phase 1

Project scaffolding + environment

### Phase 2

Site CRUD

### Phase 3

Visit CRUD

### Phase 4

Cloudinary upload integration

### Phase 5

Asset persistence

### Phase 6

Before/after selection

### Phase 7

AI comparison endpoint

### Phase 8

Observation persistence

### Phase 9

Review workflow

### Phase 10

Report generation

### Phase 11

Persistence/reload testing

### Phase 12

Polish/demo UX

Only after all phases pass should we consider Phase 2 features.

------------------------------------------------------------------------

# 13. Phase 2 --- AFTER MVP WORKS

Potential additions:

1.  Automatic before/after pair suggestions
2.  Video upload + timestamped evidence
3.  Semantic media search
4.  Image → video retrieval
5.  Evidence retrieval/RAG
6.  Better confidence/ranking
7.  More sophisticated comparison
8.  Measurement records
9.  Multiple observations per visit
10. Richer report templates

Prioritize based on actual demo value and remaining hackathon time.

------------------------------------------------------------------------

# 14. Definition of Done

A judge/user should be able to do this without developer intervention:

``` text
Create cleanup site
        ↓
Create two visits
        ↓
Upload photos
        ↓
Select before + after
        ↓
Click Analyze
        ↓
Receive AI observation
        ↓
See supporting evidence
        ↓
Approve/edit/reject
        ↓
Reload application
        ↓
Approved observation persists
        ↓
Export report
        ↓
Report contains approved text + original evidence links
```

If this works reliably, Milestone 1 is DONE.

------------------------------------------------------------------------

# 15. Antigravity Working Instructions

You are the primary implementation agent for this milestone.

Before writing substantial code:

1.  Inspect the existing repository.
2.  Identify the current stack and existing Cloudinary integration.
3.  Do not replace working infrastructure unnecessarily.
4.  Create/update a concise implementation plan.
5.  Identify missing environment variables/secrets without exposing
    secrets.
6.  Implement incrementally.
7.  Run tests/build/lint after meaningful changes.
8.  Keep the repository runnable at every milestone.
9.  Document important architectural decisions.
10. Do not silently expand scope.

### If the repository already contains code

Adapt to it.

Do not blindly create a new architecture.

### If a requirement is ambiguous

Choose the smallest implementation that satisfies the acceptance
criteria and document the decision.

### If Cloudinary already provides a capability

Prefer using Cloudinary rather than recreating it.

### If a reference repository provides a useful pattern

Study the implementation and selectively reproduce the required pattern.
Do not merge unrelated systems just because they exist.

------------------------------------------------------------------------

# 16. Important Product Principle

This project is NOT:

> "AI looks at two photos and tells us whether the cleanup worked."

It IS:

> **"A human-reviewable evidence workflow where AI proposes an
> observation, the supporting media is preserved, the organizer verifies
> it, and the final report contains only approved evidence-backed
> statements."**

That distinction should guide every implementation decision.
