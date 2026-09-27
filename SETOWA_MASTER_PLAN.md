# SETOWA — Master Product, Architecture & Execution Plan

> **Canonical product name:** SETOWA
>
> **Spelling is locked:** `S-E-T-O-W-A`
>
> **Purpose of this document:** This file is the shared source of product direction for the Setowa team, Antigravity/AI coding agents, and teammates joining the repository later. It explains the product evolution, what was learned from the Cloudinary conversation, how the existing LEX work fits into Setowa, the new Skills + Workflow architecture, the Cloudinary integration strategy, the execution roadmap, and exactly how a new teammate/agent should use this document.

---

## 1. Executive Summary

Setowa is evolving from the original LEX concept into a broader **AI-powered impact and sustainability media platform**.

The previous work is **not being discarded**. The existing LEX evidence-verification system becomes a core intelligence capability inside Setowa.

The new product vision is:

> **Setowa helps sustainability and social-good teams turn large collections of real-world images and videos into organized, searchable, analyzable, and verifiable impact evidence. Users can install reusable visual-AI Skills and compose them into Workflows, with Cloudinary serving as the central media pipeline.**

The product has four major ideas:

1. **Media Pipeline** — large collections of images/videos flow through Cloudinary and Setowa.
2. **Skills** — specialized, reusable visual/multimodal AI capabilities that can be installed and used by users.
3. **Workflows** — a visual builder, conceptually similar to a developer workflow editor, where users connect Skills into repeatable pipelines.
4. **Impact & Verification** — results are traceable to source media, can pass through human verification, and can be turned into sustainability/impact reports or stories.

The hackathon Product Specification shown to the team is the umbrella for this direction: an AI-powered impact and sustainability media platform that organizes field media by project/location/timeline, compares before/after evidence, supports AI-powered discovery, generates reports/summaries, and preserves traceability to source assets and transformations.

The important architectural addition is that **Skills + Workflows become the platform layer that makes these capabilities composable**.

---

# 2. Why the Product Direction Changed

The original product focused heavily on before/after evidence verification. That work was valuable and remains valuable, but the Cloudinary discussion highlighted a broader opportunity.

The team’s interpretation of the conversation with the Cloudinary representative was that the project should demonstrate:

- a real **media pipeline** rather than simple image storage;
- **deep Cloudinary integration** rather than a superficial integration;
- a product that visibly belongs to a **social-good / sustainability** context;
- a strong, useful user experience rather than a collection of disconnected AI demos;
- developer/automation access, including a **CLI** capability;
- an architecture where Cloudinary is an important part of the actual media lifecycle.

The official Cloudinary hackathon deck reinforces this general direction. It describes Cloudinary as an API-first programmable media platform for storing, transforming, optimizing, embedding, and working with images/videos, notes that it is well suited to media-heavy AI pipelines, and asks participants to demonstrate deep integration, innovation, a good UI, and usefulness. It also explicitly calls out sustainability/social-good applications as a bonus direction. See the supplied **Hackathon Welcome Deck.pdf**, pages 2–5.

The official Cloudinary guidance also says sponsor-track projects should demonstrate deep use of the platform rather than simply using it as a place to dump media. It gives media transformation/optimization inside an AI pipeline as an example of the type of deeper integration it looks for. It also warns against using every possible platform feature without a strategic reason.

**Resulting product decision:** Keep the strong evidence engine, but make it part of a larger media-intelligence platform rather than the entire product.

---

# 3. Product Positioning

## 3.1 Product Name

**Setowa**

Use `Setowa` everywhere in user-facing copy.

Avoid introducing another new product name. The previous working name **LEX** now refers to the earlier implementation/core evidence engine only when discussing historical code or the migration.

## 3.2 One-Line Description

> **Setowa turns field media into verified, searchable sustainability impact.**

Alternative internal description:

> **An AI-powered visual-intelligence platform for sustainability and social-good organizations.**

## 3.3 The Core Problem

Sustainability, environmental, infrastructure, and community teams can generate large amounts of photos and videos from field activities. Raw media is difficult to organize, search, analyze, compare, and convert into trustworthy evidence at scale.

Setowa is designed to help teams move from:

```text
Raw images/videos
      ↓
Organized media
      ↓
AI analysis
      ↓
Composable Skills
      ↓
Workflow execution
      ↓
Evidence + verification
      ↓
Impact understanding
      ↓
Reports / stories / shareable outputs
```

## 3.4 The Product Should Feel Like a Social-Good App

The sustainability/social-good context must be visible in the product experience, not only in the README.

The UI should communicate:

- real-world environmental/community use cases;
- evidence and impact rather than generic AI experimentation;
- media timelines and projects;
- transparent results and uncertainty;
- human verification where appropriate;
- measurable/traceable outcomes;
- useful reports/stories that can communicate impact.

The product should **not** present AI-generated guesses as authoritative facts. It should distinguish model output, uncertainty, source evidence, and human approval.

---

# 4. Product Specification (PS) Alignment

The supplied PS concept can be summarized as an:

> **AI-Powered Impact & Sustainability Media Platform**

The PS describes a system for organizations that generate large amounts of field media and need to organize, verify, and turn that media into reliable insight and impact stories.

The PS goals shown to the team include capabilities such as:

- intelligently organizing large collections of images and videos;
- identifying relevant projects, activities, locations, and visual signals;
- comparing before/after media to show visible project or environmental changes;
- making media searchable through AI-powered metadata, tagging, and semantic discovery;
- generating visual reports, summaries, and campaign-ready content;
- preserving traceability to original source assets and transformations.

### How Setowa maps to the PS

| PS capability | Setowa implementation direction |
|---|---|
| Large media collections | Cloudinary ingestion + Media Library |
| Project/location/timeline organization | Setowa workspace metadata + asset relationships |
| Before/after comparison | Existing LEX evidence engine as a built-in Skill/capability |
| AI metadata/tagging | Media Intelligence Skills |
| Semantic discovery | Search/discovery layer over media metadata and AI outputs |
| Visual signals | Reusable Skills |
| Reports/summaries | Impact/Report workflow nodes |
| Traceability | Cloudinary source asset IDs/URLs + provenance records |
| Social-good/sustainability use | Core product UX and demo domain |
| Reusable AI capabilities | Setowa Skill system |
| User-composable pipelines | Setowa Workflow Builder |
| Developer automation | Setowa CLI |

### Important scope rule

The PS contains **a broad product vision**. Not every feature has to be fully implemented for the hackathon.

The implementation should prioritize one coherent end-to-end experience over many partially finished features.

---

# 5. The Central New Idea: Skills

## 5.1 What a Setowa Skill Is

A **Setowa Skill** is a reusable, versioned capability that takes defined inputs and produces defined structured outputs.

A Skill may contain:

- an AI model call;
- a prompt or prompt template;
- image/video analysis;
- deterministic computer-vision logic;
- business rules;
- external data lookups;
- transformation steps;
- output validation;
- evidence references;
- uncertainty information.

A Skill is **not simply a prompt**.

The goal is to turn specialized media intelligence into a component that can be installed, configured, validated, versioned, and composed with other Skills.

## 5.2 Example Skill: Tree/Fall Risk Assessment

Example domain idea:

```text
Input
  ├── image/video
  ├── optional location
  ├── optional weather data
  └── optional contextual data

        ↓

Tree Risk Skill

        ↓

Structured output
  ├── risk level
  ├── confidence
  ├── observed factors
  ├── uncertainty reason
  └── evidence references
```

The important architectural principle is that a safety-related or risk-related Skill must remain decision-support tooling. It should not silently present a probabilistic model result as a guaranteed real-world prediction.

## 5.3 Other Possible Skills

Examples for demonstration/roadmap purposes:

- Road Hazard Detection
- Waste Classification
- Vegetation/Green-Cover Analysis
- Flood Evidence Detection
- Environmental Cleanup Evidence
- Infrastructure Condition Detection
- Before/After Evidence Verification
- Media Quality/Usability Check
- Field Activity Classification
- Impact Narrative Preparation

These examples are intentionally modular. Setowa provides the platform; domain experts can define domain-specific Skills.

## 5.4 Skills Created by Other People

The long-term vision is that third parties can create Skills against a **Setowa Skill Specification** and make them available through a registry/library.

For the hackathon, **do not make a complete public marketplace a dependency**.

The architecture should support:

```text
Built-in Skills
+
Installed Skills
+
Future Third-Party Skills
```

A strong hackathon implementation can demonstrate the architecture using a small number of real Skills and leave a marketplace/registry as a future extension.

---

# 6. Skill Contract / Specification

The Skill system must be contract-driven.

A Skill should declare at minimum:

```yaml
name: road-hazard
version: 1.0.0
kind: visual-analysis

input_schema:
  - media
  - optional: location
  - optional: context

output_schema:
  - findings
  - confidence
  - uncertainty_reason
  - evidence

permissions:
  media: read
  metadata: read
  external_data: optional

runtime:
  provider: gemini
```

The exact implementation format may be JSON, YAML, or another repository-native format. Do not introduce a new format without checking the existing architecture and T010 work.

## 6.1 Required Skill Properties

Every Skill should have:

- stable name/identifier;
- semantic version;
- human-readable description;
- explicit input types;
- explicit output schema;
- configuration parameters, if any;
- permissions/capabilities required;
- execution metadata;
- provenance/evidence references when applicable;
- uncertainty information for AI outputs;
- validation rules;
- compatibility/version information.

## 6.2 Skill Safety/Trust Principles

A Skill must not:

- fabricate measurements;
- silently turn model confidence into factual accuracy;
- claim certainty when evidence is insufficient;
- lose the relationship between output and source media;
- mutate unrelated project/site data without explicit authorization.

For evidence-sensitive results, human review remains the final gate where appropriate.

---

# 7. Workflow Builder — The Main Product Feature

The main differentiating feature is the **Setowa Workflow Builder**.

The conceptual inspiration is a developer environment such as VS Code:

```text
VS Code
  → editor
  → extensions / skills
  → tools
  → workflows through developer actions

Setowa
  → media workspace
  → Skills
  → Workflow Builder
  → media pipelines
  → AI analysis
  → impact/evidence outputs
```

The analogy is conceptual, not a requirement to copy VS Code’s UI exactly.

## 7.1 Workflow Mental Model

A user should be able to create something like:

```text
[Media Input]
      ↓
[Waste Detection]
      ↓
[Location / Project Classification]
      ↓
[Before/After Evidence]
      ↓
[Human Review]
      ↓
[Impact Summary]
```

Or:

```text
[Field Video]
      ↓
[Frame / Media Preparation]
      ↓
[Road Detection]
      ↓
[Hazard Detection]
      ↓
[Severity Analysis]
      ↓
[Report]
```

Or:

```text
[Before Media] ─────┐
                    ↓
          [Evidence Comparison]
                    ↑
[After Media] ──────┘
                    ↓
             [Human Review]
                    ↓
             [Verified Impact]
```

## 7.2 Workflow Nodes

Likely node categories:

- Media Input
- Cloudinary Media Transform
- Media Filter
- Skill
- Data Lookup
- Comparison
- Conditional/Branch
- Human Review
- Report/Export
- Impact Story

The exact first implementation should stay smaller. Start with the minimum node types needed to demonstrate a complete workflow.

## 7.3 Workflow Definition

Workflows should be stored as structured, versionable data rather than only as UI state.

Conceptually:

```json
{
  "name": "cleanup-impact",
  "version": 1,
  "nodes": [
    {"id": "input", "type": "media_input"},
    {"id": "cleanup", "type": "skill", "skill": "cleanup-analysis@1"},
    {"id": "verify", "type": "human_review"},
    {"id": "report", "type": "impact_report"}
  ],
  "edges": [
    {"from": "input", "to": "cleanup"},
    {"from": "cleanup", "to": "verify"},
    {"from": "verify", "to": "report"}
  ]
}
```

The actual schema should be aligned with the T010 architecture and repository conventions.

## 7.4 Workflow Principles

- deterministic and inspectable;
- resumable where practical;
- observable per node;
- source-aware;
- versioned;
- able to report failures without corrupting prior evidence;
- reusable across media collections;
- runnable from both the UI and CLI;
- backed by the same server-side domain logic.

---

# 8. Cloudinary's Role — It Must Be Deep, Not Decorative

Cloudinary is the central media layer in Setowa.

The app should not communicate:

> "We use Cloudinary to store our images."

It should communicate:

> "Cloudinary powers the media lifecycle that feeds Setowa's AI workflows."

## 8.1 Media Lifecycle

The intended pipeline is:

```text
User / CLI
     ↓
Bulk Media Ingestion
     ↓
Cloudinary Upload
     ↓
Cloudinary Asset Metadata
     ↓
Transform / Optimize / Prepare Media
     ↓
Setowa Workspace
     ↓
AI Skill Execution
     ↓
Structured Results
     ↓
Evidence / Human Review
     ↓
Impact Output
```

## 8.2 Cloudinary Capabilities to Use Strategically

Relevant capabilities include:

- image and video upload;
- asset metadata and identifiers;
- optimized delivery;
- URL-based transformations;
- responsive/format/quality optimization;
- thumbnails and derivatives;
- video handling;
- media delivery;
- AI/media analysis capabilities where useful.

The official challenge deck describes Cloudinary as an API-first programmable media platform for storing, transforming, and optimizing images and videos and explicitly notes that it is suitable for media-heavy AI pipelines.

## 8.3 Avoid Platformmaxxing

The team should **not** add every Cloudinary feature simply to increase the number of Cloudinary products touched.

Each Cloudinary feature should have a user-visible reason in the Setowa media pipeline.

The strategy is:

```text
Deep integration > many disconnected integrations
```

---

# 9. Important Distinction: Cloudinary Agent Skills vs Setowa Skills

This is critical and must not be confused.

## 9.1 Cloudinary Agent Skills

These are skills used by the **AI coding assistant**.

They help an agent such as Antigravity understand Cloudinary and generate correct integration code. Cloudinary documentation describes its agent skills as providing first-class context to AI coding assistants and includes skills for Cloudinary documentation and transformations.

These skills live in the **developer/tooling layer**.

```text
Antigravity
   ↓
Cloudinary Agent Skills
   ↓
Better Cloudinary implementation
```

## 9.2 Setowa Skills

These are the **product's runtime capabilities** used by Setowa users.

```text
Setowa User
   ↓
Setowa Workflow
   ↓
Setowa Skill
   ↓
Image/Video/Context
   ↓
Structured Result
```

They are separate systems.

### Rule

**Do not name or architect these as though they are the same thing.**

---

# 10. SDK, Starter Kit, Skills Pack, AI Power Start, MCP, CLI — What They Mean

## SDK — Software Development Kit

A Cloudinary SDK is the application/library layer that lets Setowa talk to Cloudinary without manually implementing every raw API call.

Conceptually:

```text
Setowa backend/frontend
       ↓
Cloudinary SDK
       ↓
Cloudinary APIs
```

Use the SDK appropriate to the existing project stack.

## Starter Kit

A Cloudinary Starter Kit is a pre-built application foundation for a supported stack, such as React or Next.js, intended to get a Cloudinary-integrated application running quickly.

It is primarily a **starting point/bootstrap**, not a mandatory architectural dependency for an existing mature application.

For Setowa, do not rebuild the project simply to say we used a Starter Kit. The current application already exists and the challenge also allows the Skills Pack/AI Power Start route.

## Skills Pack / Agent Skills

Cloudinary's Agent Skills provide AI coding assistants with Cloudinary-specific context and implementation guidance.

They help the agent produce correct Cloudinary code, transformations, delivery patterns, and related integrations.

## AI Power Start

Cloudinary's current documentation describes AI Power Start as a one-prompt onboarding flow that can:

1. configure AI tooling;
2. detect the framework;
3. install/configure the appropriate SDK and environment setup;
4. guide credential configuration;
5. validate the Cloudinary setup.

Cloudinary says this works with AI coding assistants including Antigravity.

## MCP

MCP is a tooling/protocol layer that lets AI agents interact with external capabilities through structured tools.

Cloudinary provides MCP servers that allow AI coding assistants to work with Cloudinary operations and generate Cloudinary integration code.

For Setowa, MCP is **developer-agent infrastructure**, not the same thing as the product's Skill system.

## CLI — Command Line Interface

A CLI gives developers/operators a terminal interface to automate Setowa actions.

Setowa's CLI should eventually support operations such as:

```bash
satova ingest ./field-media
satova skill list
satova skill install tree-risk
satova skill validate tree-risk
satova workflow list
satova workflow validate road-safety
satova workflow run road-safety ./field-media
```

The exact commands are subject to the T010 architecture and repository conventions.

### Important CLI architecture rule

The CLI must be a **thin interface to the same domain services used by the web application**.

Do not duplicate Cloudinary upload logic, Gemini logic, Skill execution logic, or evidence-validation logic inside the CLI.

---

# 11. Existing LEX Work — Preserve It and Reposition It

The earlier project was called **LEX**. The existing backend contains a meaningful evidence-verification foundation.

That work should become part of Setowa rather than being thrown away.

## Existing capabilities already built

The project history includes the following completed milestones before the Setowa evolution:

### T001 — Control Plane

Created/maintained `.ai/` governance files including:

- `AGENTS.md`
- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `DECISIONS.md`
- `HANDOFF.md`
- `PROJECT_STATE.md`
- `TASK_BOARD.md`

### T002 — Schema Alignment

Added/updated evidence-related fields such as:

- `permission_status`
- `thumbnail_url`

Also hardened backward-compatible migrations and review behavior.

### T003 — Test Baseline

Established the baseline test workflow.

### T004 — Fake-Accuracy Claim Removal

Removed unsupported demo claims such as hardcoded accuracy/automation numbers.

Confidence is not treated as factual accuracy.

### T005 — Evidence Pair Validation Hardening

The server became authoritative for pair validation, including checks around:

- asset existence;
- distinct asset IDs;
- supported media properties;
- permission status;
- asset/visit relationships;
- visit/site relationships;
- same-site consistency;
- chronological ordering.

Evidence mutation also resets review state appropriately when approved observations are materially changed.

### T006 — Structured AI Comparison / Uncertainty

The AI comparison contract was formalized around statuses such as:

- `changed`
- `unchanged`
- `uncertain`
- `insufficient_evidence`

The result includes structured explanation fields, confidence, uncertainty reasons, and evidence notes.

AI remains a proposal, not the final source of truth.

### T007 — Real Cloudinary + Gemini Integration

The media/evidence lifecycle was integrated with real Cloudinary assets and Gemini multimodal comparison.

Cloudinary metadata such as secure URLs/public IDs and media dimensions/formats is persisted rather than storing local media binaries in the application.

Provider failures and missing credentials produce safe uncertainty/insufficient-evidence behavior rather than fake success.

### T008 — Judge-Facing Review Experience

The reviewer-facing evidence workflow was completed and hardened.

### T009 — Demo Hardening / End-to-End QA

The full evidence lifecycle was verified:

```text
Site
 → Before Visit
 → Before Asset
 → After Visit
 → After Asset
 → Pair Validation
 → Gemini Comparison
 → Observation pending
 → Human Review
 → Approved Record
 → Report
```

A demo runbook was created.

### T010 — Setowa Migration + Architecture Design

**Status: completed according to the current team plan.**

T010 is the transition milestone from the original LEX-centric product to the Setowa platform model.

The exact T010 implementation should be verified directly in the repository. This document deliberately does not invent specific T010 file changes.

---

# 12. Current Architectural Direction

The target architecture is:

```text
                           SETOWA
              Impact & Sustainability Platform
                              │
          ┌───────────────────┴───────────────────┐
          │                                       │
      WORKSPACE                                  SKILLS
          │                                       │
    Workflow Builder                    Installed / Built-in
          │                                       │
          └───────────────────┬───────────────────┘
                              ↓
                    CLOUDINARY MEDIA PIPELINE
                              ↓
                     Images / Videos / Assets
                              ↓
                        Media Preparation
                              ↓
                    Skill / Workflow Execution
                              ↓
                ┌─────────────┴─────────────┐
                │                           │
          AI / Vision                 Rules / Data
                │                           │
                └─────────────┬─────────────┘
                              ↓
                   Structured Intelligence
                              ↓
                 Evidence + Uncertainty
                              ↓
                      Human Verification
                              ↓
                 Impact / Timeline / Reports
                              ↓
                Shareable Sustainability Story
```

## 12.1 Major Domain Areas

### A. Media Domain

Owns:

- Cloudinary asset references;
- upload/ingestion lifecycle;
- asset metadata;
- thumbnails/derivatives;
- image/video relationships;
- processing state;
- project/site/timeline association.

### B. Skill Domain

Owns:

- Skill definitions;
- manifests;
- versions;
- input/output schemas;
- installation;
- configuration;
- validation;
- execution;
- permissions.

### C. Workflow Domain

Owns:

- workflow definitions;
- nodes;
- edges;
- configuration;
- validation;
- execution state;
- node outputs;
- retry/error semantics.

### D. Intelligence Domain

Owns:

- AI analysis;
- structured outputs;
- uncertainty;
- provenance;
- evidence references.

### E. Verification Domain

Contains the existing LEX evidence engine.

This is responsible for source-of-truth validation and human review.

### F. Impact Domain

Owns:

- verified impact records;
- timelines;
- summaries;
- report generation;
- shareable outputs.

### G. CLI Domain

Provides terminal access to the same services.

---

# 13. Media Pipeline Requirements

The Media Pipeline is one of the most important hackathon-visible parts of Setowa.

## 13.1 Bulk Ingestion

The product should support more than one-at-a-time demo uploads.

Example:

```text
field-media/
  cleanup_001.jpg
  cleanup_002.jpg
  cleanup_003.jpg
  road_001.jpg
  road_002.jpg
  site_walkthrough.mp4
  cleanup_video.mp4
```

The user should be able to ingest a collection and see processing status.

## 13.2 Cloudinary as the Media Source of Truth

Do not persist local media binaries in the Setowa database as the primary media store.

Persist Cloudinary identifiers/references and relevant metadata.

## 13.3 Transformations

Use Cloudinary transformations where they are useful to the workflow, for example:

- optimized delivery;
- thumbnails;
- normalized display sizes;
- relevant crops;
- video derivatives/previews.

Transformations should be visible in the product or demo so a reviewer can understand that Cloudinary is doing real work.

## 13.4 Video

Video is important because the challenge is media-centric rather than image-only.

The first implementation does not need a highly complex video-analysis engine, but the architecture should be video-aware.

Potential pipeline:

```text
Cloudinary Video
      ↓
Preview / frame selection / derived representation
      ↓
Skill
      ↓
Structured result + evidence reference
```

---

# 14. Media Library / Workspace

The Workspace is the operational home for the user.

A useful conceptual navigation model is:

```text
SETOWA

[Media] [Workflows] [Skills] [Impact]
```

## Media

Users can:

- browse assets;
- filter by project/location/time;
- see image/video previews;
- inspect Cloudinary metadata;
- inspect AI-derived metadata;
- open source assets;
- start workflows.

## Workflows

Users can:

- create workflows;
- edit nodes/edges;
- select Skills;
- configure inputs;
- validate workflows;
- run workflows;
- inspect execution results.

## Skills

Users can:

- browse installed/built-in Skills;
- inspect versions;
- install/enable Skills;
- inspect inputs/outputs;
- view documentation/configuration.

## Impact

Users can:

- see verified findings;
- browse timelines;
- compare before/after evidence;
- create reports/stories;
- inspect provenance.

---

# 15. Evidence and Trust Architecture

The original LEX project's strongest feature should remain part of Setowa.

The core rule is:

> **AI can propose. The system validates. Humans can verify. Provenance remains attached to the evidence.**

## 15.1 Source Traceability

Every AI-derived result should retain enough information to answer:

- which media asset produced this result?
- what Cloudinary asset was used?
- which transformation/derivative was used?
- which Skill and version produced the result?
- which model/provider was used?
- what confidence/uncertainty was reported?
- was a human review performed?
- what was ultimately approved?

## 15.2 Confidence != Accuracy

Do not reintroduce unsupported statements like:

```text
99.4% accurate
10x faster
```

unless such claims are actually benchmarked and supported.

A model confidence field means what the model reports about its own inference, not factual truth.

## 15.3 Human-in-the-Loop

Human review should be a first-class workflow capability, especially for evidence or impact claims where uncertainty matters.

Potential statuses:

```text
pending
approved
rejected
needs_review
uncertain
insufficient_evidence
```

The exact data model should follow the existing repository implementation.

---

# 16. Natural-Language Discovery

Semantic discovery is part of the wider PS and should be integrated after the core pipeline is stable.

Example user query:

> "Show me river cleanup evidence from this project."

Potential pipeline:

```text
User query
    ↓
Search/discovery service
    ↓
Metadata / tags / AI descriptions / project context
    ↓
Relevant Cloudinary assets
    ↓
Workflow / evidence details
```

The result must preserve links back to original media.

Semantic search is an enhancement to structured filtering, not a replacement for deterministic filters.

---

# 17. Sustainability / Impact Output

The final experience should communicate actual impact evidence.

Example:

```text
Project: Riverbank Cleanup

Media collected: 184
Assets analyzed: 163
Items requiring review: 14
Verified before/after pairs: 21

Timeline
 ├── Site visit 1
 ├── Cleanup activity
 ├── Site visit 2
 └── Verified change
```

Then generate a visual report/story from the verified evidence.

The narrative generator must not invent impact claims unsupported by the underlying records.

A strong implementation can use Cloudinary media transformations and delivery to make the output visually compelling while retaining source traceability.

---

# 18. CLI Strategy

CLI is a real interface, not a demo-only script.

## First useful command groups

### Media

```bash
satova ingest <path>
satova media list
```

### Skills

```bash
satova skill list
satova skill install <skill>
satova skill validate <skill>
```

### Workflows

```bash
satova workflow list
satova workflow validate <workflow>
satova workflow run <workflow> <input>
```

### Inspection

```bash
satova run status <run-id>
satova run logs <run-id>
```

Do not implement every command at once. One end-to-end CLI path is more valuable than a large shell interface with weak backend integration.

### Preferred demo command

The eventual hackathon demo should aim for something like:

```bash
satova ingest ./demo/field-media
satova workflow run impact-evidence ./demo/field-media
```

The exact final command syntax can differ based on the repository implementation.

---

# 19. Execution Roadmap After T010

T010 is considered complete in the current team plan. The next work should proceed in small, verifiable milestones.

## T011 — Media Pipeline + Bulk Ingestion

### Goal
Build the foundation for large media collections.

### Scope

- bulk image/video ingestion;
- Cloudinary upload integration;
- asset metadata persistence;
- project/site association;
- processing state;
- optimized delivery/thumbnail pipeline;
- safe error handling.

### Non-goals

- full public Skill marketplace;
- complex semantic search;
- dozens of AI Skills.

### Acceptance Criteria

- user can ingest a collection;
- media is stored through Cloudinary;
- metadata is persisted;
- assets are visible in Workspace;
- image/video preview works;
- transformations/optimized delivery are actually used;
- existing evidence tests remain green.

---

## T012 — Setowa Skill Runtime

### Goal
Define and execute reusable Skills.

### Scope

- Skill manifest/schema;
- registration/loading;
- versioning;
- input/output validation;
- execution abstraction;
- structured results;
- uncertainty/provenance;
- at least one real built-in Skill.

### First real Skill candidates

Prefer one Skill that clearly aligns with the sustainability demo, while exposing the architecture required for future Skills.

The existing before/after evidence capability should be made available as a built-in Skill/capability where practical.

---

## T013 — Workflow Engine + Builder

### Goal
Make Skills composable.

### Scope

- workflow schema;
- node graph;
- validation;
- execution engine;
- execution state;
- minimal visual builder;
- result inspection.

### First demo workflow

```text
Media Input
   ↓
Visual Skill
   ↓
Evidence Comparison / Analysis
   ↓
Human Review
   ↓
Impact Report
```

---

## T014 — Field Video Ingestion + Frame Analytics (COMPLETE)

> *Roadmap Note:* Originally titled "AI Media Intelligence" in early planning, T014 was intentionally implemented as Field Video Ingestion + Frame Analytics to build on Cloudinary's native video capabilities and provide derived frame extraction for multimodal analysis.

### Goal
Ingest field videos using Cloudinary native video capabilities (`resource_type="video"`), extract frame derivatives on-the-fly (`so_<ts>`, `.jpg`), and preserve frame-level provenance for multimodal analysis.

### Scope
- Video ingestion and validation (MP4/WebM/MOV, 50 MiB limit);
- Cloudinary video transformations and poster frame derivation;
- Sampled frame extraction (interval, uniform, custom);
- Frame provenance model (`video_frames`, `frame_analyses`);
- Built-in `field-frame-observation@1.0.0` Skill via SkillRuntime;
- Video analytics UI with interactive timeline in Setowa Workspace.

---

## T015 — Project / Location / Timeline Media Grouping + Spatial-Temporal Queries (COMPLETE)

> *Roadmap Note:* Originally titled "Search & Semantic Discovery" in early planning, T015 was intentionally implemented as Project / Location / Timeline Media Grouping and Spatial-Temporal Queries to establish deterministic organization of ingested media before layering AI intelligence.

### Goal
Group large collections of media assets by project, geographic site, and timeline; support multi-dimensional filtering and spatial-temporal queries across ingested image and video collections.

### Scope
- Projects model and site geospatial coordinates (`latitude`, `longitude`);
- Multi-dimensional asset query engine (`query_assets`);
- Day-bucketed timeline aggregation (`get_timeline`);
- Project summary metrics and site media listings;
- REST APIs (`/api/v1/media/query`, `/api/v1/media/timeline`, `/api/v1/sites`);
- Auto-assignment to default project for unassigned media.

---

## T016 — AI Media Intelligence + Discovery Foundation (ACTIVE)

### Goal
Turn raw SETOWA media (images, videos, and derived frames) into structured, traceable AI metadata that powers discovery, Skills, Workflows, future semantic search, and impact analysis.

### Scope
- Per-media AI analysis service;
- Structured intelligence schema (description, visual tags, detected signals, observations, activity classification, warnings, uncertainty, provenance);
- Asset-level intelligence persistence (`media_intelligence` table);
- Frame-level intelligence compatibility;
- Built-in `media-intelligence@1.0.0` Skill via existing SkillRuntime;
- Controlled tags and visual signals taxonomy;
- Provenance and source references linking AI records to Cloudinary media;
- Safe re-analysis and batch analysis support;
- REST APIs for media analysis and intelligence retrieval;
- Media Library UI extensions showing AI status, tags, signals, warnings, and uncertainty;
- Deterministic filtering on structured intelligence (tags, signals, status);
- Tests and live Gemini validation.

### Non-goals (T016 Strict Exclusions)
- Vector databases, embeddings, semantic similarity search;
- Impact reports, sustainability dashboards, public pages;
- Distributed workers or background queues (safe synchronous execution used);
- New authentication or Cloudinary architecture.

---

## T017 — Sustainability Timeline / Impact Story (UPCOMING)

### Goal
Turn verified records into an understandable impact narrative and project timeline.

Potential outputs:
- project timeline;
- before/after cards;
- verified findings;
- uncertainty callouts;
- visual report;
- Cloudinary-powered media presentation.

---

## T018 — Public / Shareable Impact Experience (UPCOMING)

### Goal
Create a polished public-facing representation of verified impact.

The output should be generated from approved/verified data and media.

Potential experience:
```text
Project
  ↓
Timeline
  ↓
Evidence
  ↓
Verified Change
  ↓
Impact Story
```

---

## T019 — Hackathon Demo & Production Hardening (UPCOMING)

### Goal
Make the complete system reliable and easy to demonstrate.

Requirements:
- deterministic demo data;
- one-click/local startup;
- CLI path;
- complete end-to-end workflow;
- visible Cloudinary usage;
- clean UI;
- clear error/uncertainty states;
- tests;
- demo runbook;
- pitch/demo narrative.

---

# 20. Recommended End-to-End Demo

The final demo should not show every capability.

It should tell one coherent story.

## Opening

**Setowa**

> "Field teams collect hundreds of photos and videos. The problem isn't taking the media — it's turning it into trustworthy, searchable evidence of impact."

## Demo flow

### Step 1 — Ingest

Run the CLI or Workspace ingestion on a folder of field media.

```text
field-media/
  before_01.jpg
  before_02.jpg
  after_01.jpg
  after_02.jpg
  cleanup.mp4
  site_walkthrough.mp4
```

Cloudinary receives and manages the media.

### Step 2 — Workspace

Show the media collection, project context, thumbnails, video, metadata, and processing state.

### Step 3 — Skills

Open the Skill Library.

Show that the user can select/install a domain-specific Skill.

### Step 4 — Workflow Builder

Create or open:

```text
Impact Evidence Workflow
```

Then show the nodes:

```text
Media
 ↓
Analysis Skill
 ↓
Before/After Evidence
 ↓
Human Review
 ↓
Impact Output
```

### Step 5 — Run

Execute the workflow on the media collection.

### Step 6 — Results

Show structured results, uncertainty, and traceability.

### Step 7 — Verify

Show the human review step.

### Step 8 — Impact

Generate a sustainability/impact report/story from verified evidence.

This demonstrates:

```text
Cloudinary
+ Media Pipeline
+ AI
+ Skills
+ Workflow Builder
+ Verification
+ Sustainability
+ Social Good
+ CLI
```

without needing to implement an enormous number of unrelated features.

---

# 21. UI/UX Direction

The product should feel like a **media intelligence workspace**, not an admin dashboard.

## Landing / Intro

The landing page should explain:

1. the real-world problem;
2. what Setowa does;
3. why media evidence matters;
4. how Skills/Workflows help;
5. entry into Workspace.

Primary CTA:

**Enter Workspace**

## Workspace

The workspace should feel operational and visual.

Suggested top-level structure:

```text
Media | Workflows | Skills | Impact
```

## Workflow Builder

Visual node-based UI.

It should feel like a tool users can compose, configure, validate, and run.

## Skill Detail

Show:

- name;
- description;
- version;
- inputs;
- outputs;
- provider/model if relevant;
- permissions;
- documentation/configuration;
- example usage.

## Evidence/Result UI

Always make it possible to inspect the source media behind a result.

---

# 22. Architecture Rules for All Future Work

These rules should be followed unless a documented architectural decision changes them.

## Rule 1 — Preserve source traceability

Every AI/Skill result must remain linked to its source media and relevant Cloudinary references.

## Rule 2 — AI is not automatically truth

Model output is an inference/proposal. Validation and human review remain important for evidence-sensitive claims.

## Rule 3 — Cloudinary must be used meaningfully

Do not use Cloudinary as a passive file bucket.

## Rule 4 — Skills are contracts

Skills require explicit inputs/outputs and versioning.

## Rule 5 — Workflows are data, not only UI

The visual editor must serialize to a structured workflow definition.

## Rule 6 — UI and CLI share domain logic

Do not implement separate business logic paths.

## Rule 7 — Do not overbuild the marketplace

Support extensibility now; build a full public ecosystem only when necessary.

## Rule 8 — Do not rebuild the whole app without evidence

T010 exists specifically to migrate the current project. Inspect the current repository before changing architecture.

## Rule 9 — Avoid fake benchmark claims

Do not add accuracy/speed/impact numbers unless measured and documented.

## Rule 10 — Keep uncertainty visible

Uncertain or insufficient evidence should remain visibly uncertain.

## Rule 11 — Prefer one complete vertical slice

A working media → Skill → Workflow → verification → impact path is preferable to many disconnected features.

## Rule 12 — Update the `.ai` control plane

Every milestone should update the relevant:

- task board;
- project state;
- architecture/decision records;
- changelog;
- handoff information.

---

# 23. Testing Strategy

Every milestone must preserve existing behavior.

## Unit tests

Test:

- Skill manifest validation;
- input/output schema validation;
- workflow validation;
- node execution;
- Cloudinary metadata parsing;
- provenance;
- uncertainty;
- permission checks;
- evidence relationships.

## Integration tests

Test:

- Cloudinary upload;
- transformations;
- asset persistence;
- workflow execution;
- Skill provider integration;
- report generation.

Live provider tests should remain gated appropriately so normal test runs are deterministic.

## End-to-End tests

At minimum:

```text
ingest
  → workspace
  → skill
  → workflow
  → AI result
  → human review
  → impact output
```

## Known historical test caveat

The earlier project had a known Windows-specific permission test issue caused by filesystem behavior around POSIX `chmod 0o600`. Do not treat this historical environment-specific behavior as a new product regression without checking the current repository/test output.

Always run the current test suite and report current results rather than relying on historical counts.

---

# 24. Repository / Agent Operating Procedure

This document is **not** a replacement for the repository `.ai` control plane.

The implementation agent should read the existing project controls first.

Recommended order:

```text
.ai/AGENTS.md
.ai/ARCHITECTURE.md
.ai/PROJECT_STATE.md
.ai/TASK_BOARD.md
.ai/DECISIONS.md
.ai/CHANGELOG.md
.ai/HANDOFF.md

then

SETOWA_MASTER_PLAN.md

then

actual source code
```

The repository is the source of truth for what is actually implemented.

This document is the source of truth for the **new product direction and roadmap**.

If this document and the code disagree, inspect the code and project control files before making assumptions. Record any meaningful reconciliation in the appropriate `.ai` decision/state file.

---

# 25. Instructions for Antigravity / Coding Agents

When an agent is assigned a Setowa task, it should follow this protocol.

## Step 1 — Read the architecture context

Read all relevant `.ai` files and this document.

## Step 2 — Inspect the current implementation

Do not assume a feature is missing because it appears in this document.

Search the repository for:

- existing implementations;
- existing APIs;
- existing database models;
- existing Cloudinary services;
- existing Gemini/AI services;
- current frontend routes/components;
- test infrastructure;
- T010 changes.

## Step 3 — Identify the smallest milestone

Implement only the requested milestone.

## Step 4 — Reuse existing abstractions

Avoid creating duplicate upload, AI, evidence, provenance, or configuration logic.

## Step 5 — Test continuously

Run focused tests first, then relevant broader tests.

## Step 6 — Review changes

Before completion, inspect:

```bash
git status
git diff
```

## Step 7 — Update project controls

Update the relevant `.ai` files.

## Step 8 — Commit

Use a clear commit message.

## Step 9 — Push

Push to `origin/main` only according to the team workflow.

Never force-push unless the project owner explicitly authorizes it.

## Step 10 — Report

The completion report should include:

- what changed;
- files/areas touched;
- tests run/results;
- known issues;
- next recommended task;
- commit hash.

Then stop. Do not silently begin the next milestone.

---

# 26. Prompt Template for Antigravity

Use this when starting a new implementation task:

```text
You are working on SETOWA (S-E-T-O-W-A), the project defined in SETOWA_MASTER_PLAN.md.

First read:
1. .ai/AGENTS.md
2. .ai/ARCHITECTURE.md
3. .ai/PROJECT_STATE.md
4. .ai/TASK_BOARD.md
5. .ai/DECISIONS.md
6. .ai/CHANGELOG.md
7. .ai/HANDOFF.md
8. SETOWA_MASTER_PLAN.md

Then inspect the current repository and verify what T010 already implemented.

Task: <INSERT SINGLE MILESTONE/TASK>

Important product rules:
- Setowa is the new product identity.
- Existing LEX evidence/verification work must be preserved and reused.
- Cloudinary must be part of the real media pipeline, not only storage.
- Setowa Skills are runtime/product capabilities; do not confuse them with Cloudinary Agent Skills used by the coding agent.
- Workflows must be structured/versioned data, not only frontend state.
- CLI and UI should share the same backend/domain logic.
- Preserve source traceability and uncertainty.
- Do not introduce unsupported accuracy/performance claims.
- Do not implement unrelated roadmap items.

Before coding:
- summarize the relevant current architecture;
- identify files/services that will change;
- identify any conflict with T010;
- state the smallest implementation plan.

Then implement only the requested task.

After implementation:
- run targeted tests;
- run the relevant broader test suite;
- inspect git diff/status;
- update .ai control files;
- commit the change;
- push to origin/main according to repository workflow;
- report the exact result and stop.
```

---

# 27. Instructions for a New Teammate

A teammate joining later should not need the entire previous ChatGPT conversation.

Use this exact onboarding sequence.

## 1. Clone the repository

```bash
git clone <REPO_URL>
cd <REPO_DIRECTORY>
```

## 2. Read the project control files

Read the `.ai/` directory first.

## 3. Read this file

Open:

```text
SETOWA_MASTER_PLAN.md
```

## 4. Start the existing application

Use the repository's current run instructions.

The earlier local run used:

```bash
bash run_local.sh
```

The prior backend could also be started directly through the existing Python environment, but the teammate should confirm the current runbook rather than blindly copying historical commands.

## 5. Run tests

Run the current test suite and record the current results.

## 6. Inspect T010

Before changing anything, identify what Setowa migration/architecture work T010 already completed.

## 7. Pick the assigned next milestone

Do not redesign the project independently from this roadmap.

## 8. Use the `.ai` controls + this document together

The teammate's implementation loop is:

```text
Read controls
  ↓
Read Setowa plan
  ↓
Inspect current code
  ↓
Implement one task
  ↓
Test
  ↓
Update controls
  ↓
Commit
  ↓
Push
```

---

# 28. Prompt Template for a Teammate's ChatGPT

A teammate can give their ChatGPT this prompt after cloning the repo:

```text
I am joining the SETOWA project.

First read these repository files:
- .ai/AGENTS.md
- .ai/ARCHITECTURE.md
- .ai/PROJECT_STATE.md
- .ai/TASK_BOARD.md
- .ai/DECISIONS.md
- .ai/CHANGELOG.md
- .ai/HANDOFF.md
- SETOWA_MASTER_PLAN.md

Then inspect the current code and tests.

Context:
- The previous product was LEX.
- The current product is SETOWA.
- SETOWA is an AI-powered impact and sustainability media platform.
- Cloudinary is the central media pipeline.
- SETOWA has reusable Skills and a visual Workflow Builder.
- The existing LEX evidence-verification system is preserved as a core capability.
- T010 (Setowa migration + architecture design) is already complete according to the project plan.

Do not implement anything yet.

First give me:
1. what is already implemented;
2. what T010 changed;
3. which roadmap milestones remain;
4. what the next smallest useful task is;
5. what files/services would likely change.

Do not invent missing functionality. Use the repository as the implementation source of truth and SETOWA_MASTER_PLAN.md as the product-direction source of truth.
```

---

# 29. Source / Reference Material

This plan is based on the project's prior implementation history, the team's discussion about the product evolution, the supplied Cloudinary hackathon material, and current Cloudinary documentation.

## Supplied hackathon material

**Hackathon Welcome Deck.pdf**

Key relevant pages:

- Page 2 — Cloudinary definition, API-first media platform, storage, transformation, optimization, dynamic media, GenAI tools, media-heavy AI pipelines.
- Page 3 — example image/video transformations.
- Page 4 — challenge framing: use a Cloudinary Starter Kit and/or Skills Pack/AI Power Start; deep integration, innovation, good UI, usefulness; sustainability/social good called out as a bonus.
- Page 5 — functional/production-ready app and innovative Cloudinary media usage.

## Cloudinary resources

Cloudinary Hackathons:

https://cloudinary.com/pages/hackathons/

Cloudinary hackathon guidance:

https://dev.to/cloudinary/how-to-win-a-hackathon-1377

Cloudinary AI Power Start:

https://cloudinary.com/documentation/ai_powerstart

Cloudinary AI Agent tools / MCP / Skills:

https://cloudinary.com/documentation/cloudinary_llm_mcp

Cloudinary image/video APIs overview:

https://cloudinary.com/documentation/cloudinary_developer_get_started

Cloudinary AI-agent onboarding:

https://cloudinary.com/documentation/ai_agents_get_started

The external documentation should be rechecked when implementing a specific Cloudinary feature because Cloudinary APIs, SDKs, agent tooling, and recommended setup patterns can evolve.

---

# 30. Product Language / Messaging Guide

Use these phrases consistently:

### Preferred

- Setowa
- media intelligence platform
- visual intelligence
- media pipeline
- sustainability impact
- field media
- evidence
- verification
- Skill
- Workflow
- Cloudinary-powered media pipeline
- traceable results
- human verification
- uncertainty

### Avoid

- "99.4% accurate" without a benchmark;
- "guaranteed detection";
- "AI proves everything";
- "Cloudinary is just our storage";
- "we built a marketplace" unless a marketplace actually exists;
- implying a model confidence score is factual accuracy;
- claiming measurable sustainability impact unless measured and sourced.

---

# 31. What Success Looks Like

A successful Setowa implementation should allow a reviewer to understand this story quickly:

```text
A sustainability team has a large collection of field photos/videos.

        ↓

Setowa ingests the media through Cloudinary.

        ↓

Cloudinary transforms, optimizes, and delivers the media used by the system.

        ↓

The user installs/selects specialized Skills.

        ↓

The user composes those Skills into a Workflow.

        ↓

The workflow analyzes real media and produces structured results.

        ↓

Results remain linked to their source assets and uncertainties.

        ↓

Evidence-sensitive results can pass through human verification.

        ↓

Verified information becomes a sustainability/impact timeline or report.

        ↓

The same workflows can be automated from the CLI.
```

That is the central Setowa story.

---

# 32. Final Architectural Statement

Setowa should be built as a **media-first, workflow-driven, extensible visual-intelligence platform**.

Cloudinary is the underlying media infrastructure.

Setowa Skills are reusable intelligence modules.

The Workflow Builder is the main composition interface.

The CLI is the automation/developer interface.

The existing LEX evidence engine is a trust/verification capability inside the platform.

The Sustainability/Impact layer is the user-facing outcome.

The platform should optimize for:

```text
Real media
+ real pipeline
+ reusable intelligence
+ composable workflows
+ traceable evidence
+ human verification
+ meaningful social-good use
```

rather than simply accumulating AI features.

---

# 33. Immediate Next Milestone

**T010 is complete.**

The next implementation milestone should begin with:

> **T011 — Media Pipeline + Bulk Ingestion**

Before implementing T011, the agent must inspect the repository and confirm the exact T010 architecture and existing Cloudinary integration. It should then implement the smallest complete bulk-ingestion/media-library vertical slice while preserving all existing evidence behavior.

The team should resist the temptation to simultaneously implement the full Skill marketplace, semantic search, public pages, and every possible AI capability.

Build the pipeline first. Then make Skills real. Then make Workflows composable. Then turn the verified results into the sustainability story.

---

# 34. Quick Mental Model

When anyone on the team forgets what Setowa is, use this:

```text
                       SETOWA
                          │
                Sustainability Media
                       Workspace
                          │
            ┌─────────────┴─────────────┐
            │                           │
        CLOUDINARY                  SKILLS
        Media Pipeline          Reusable AI abilities
            │                           │
            └─────────────┬─────────────┘
                          ↓
                  WORKFLOW BUILDER
                          ↓
                   AI / Vision / Data
                          ↓
                  Evidence + Results
                          ↓
                  Human Verification
                          ↓
                  Impact / Reports
                          ↓
                     Social Good
```

**Setowa is not one AI feature. It is the system that composes media, intelligence, workflows, and verification into useful sustainability outcomes.**

---

_End of SETOWA_MASTER_PLAN.md_
