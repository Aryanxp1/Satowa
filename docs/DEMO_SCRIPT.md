# SETOWA Demonstration Script & Presentation Narrative

> **Presentation Timing:** 5 Minutes  
> **Audience:** Hackathon Judges, Sustainability Stakeholders, Technical Evaluators  
> **Core Theme:** Provenance, Programmable Media, and Verifiable Ecological Impact

---

## 1. Opening: The Problem SETOWA Solves (0:00 – 0:45)

**Spoken Narrative:**
> "Billions of dollars are committed annually to global climate and ecological restoration—coastal cleanups, mangrove reforestation, river remediation. Yet the verification pipeline is fundamentally broken. Organizations take photos on smartphones, store them in scattered cloud drives, and write marketing reports claiming thousands of kilograms of carbon or waste offset with zero auditable provenance.
>
> This creates a massive trust deficit: **Greenwashing vs. Ground Truth**.
>
> **SETOWA** is the open, intelligent verification engine that bridges this gap. It transforms raw, chaotic field media—photos, drone sweeps, and cleanup videos—into structured, verifiable, and publicly shareable Impact Stories powered by Cloudinary's programmable media pipeline and Gemini's multimodal intelligence.
>
> In SETOWA: **AI proposes observations, but humans certify evidence.**"

---

## 2. End-to-End Demo Sequence (0:45 – 4:00)

| Step | Time | What to Show | Key Point to Highlight |
|---|---|---|---|
| **1. The Platform** | 0:45 | `http://localhost:8000/` Workspace | Unified control plane organized by Project, Site, and Chronological Visits. |
| **2. Field Ingestion** | 1:15 | Media Library & Cloudinary Assets | Automated upload of before/after photos and field cleanup video with derived metadata. |
| **3. Frame Analytics** | 1:45 | Video Frame Inspection (Nyali Creek) | Cloudinary video frame derivation at exact time offsets (`1.5s`, `4.0s`, `8.0s`) with poster generation. |
| **4. Media Intelligence** | 2:15 | Gemini Visual Observations | Multimodal signal extraction detecting discarded PET plastics, net fragments, and mudflats without hallucinating weights. |
| **5. Skills & Workflows** | 2:45 | Skill Runtime & Visual Workflow DAG | Contract-bound skills (`waste-detection`, `evidence-comparison`) orchestrated in an executable DAG. |
| **6. Human Verification** | 3:15 | Review Queue & Certifications | Auditor confirms before/after observation pair and correlates it with a physical weigh slip (`320 kg`). |
| **7. Public Impact Share** | 3:45 | `/share/pst_demo_mombasa_coastal_2026` | Public-safe, token-gated visual story displaying provenance, uncertainty score, and full media transparency. |

---

## 3. Cloudinary: Where Cloudinary is Meaningfully Used

Cloudinary is not a static storage bucket in SETOWA; it is the **core programmable visual engine**:

1. **Intelligent Ingestion & Metadata:** Uploads raw field media, stores spatial-temporal EXIF/GPS tags, and generates unique public asset IDs (`setowa/projects/...`).
2. **Video Frame Extraction:** Programmatically derives key frames at timestamp offsets (`so_1.5`, `so_4.0`, `so_8.0`) for video frame analytics without client-side video decoding.
3. **Automated Posters & Web Delivery:** Produces lightweight video poster images and optimized WebP/AVIF formats with dynamic responsive transforms (`f_auto,q_auto,w_800`).
4. **Before/After Media Delivery:** Streams synchronized visual assets to comparison viewports and public impact stories with sub-second global CDN latency.

---

## 4. AI: Where Gemini is Used

Gemini provides **multimodal media intelligence grounded in real visual evidence**:

1. **Visual Signal Detection:** Identifies discrete physical features (e.g., stranded fishing nets, macro-plastics, mangrove root health, vegetation coverage).
2. **Uncertainty & Confidence Scoring:** Returns calibrated confidence metrics (`0.89`, `0.92`) and explicitly flags low-confidence or obscured conditions.
3. **Structured Observation Extraction:** Conforms strictly to Pydantic/JSON schemas—Gemini never outputs freeform hallucinations or unverified carbon calculations.
4. **Ground Truth Discipline:** Gemini reports *what is visible*; it does not claim *why* or quantify unobserved metrics.

---

## 5. Skills: Why Reusable Skills Matter

1. **Standardized Contracts:** Every analytical capability is packaged as a SETOWA Skill with explicit input/output schemas and versioning.
2. **Decoupled Architecture:** Analytical algorithms (e.g., waste detection, vegetation index, canopy coverage) can be developed, tested, or swapped independently without touching workflow or UI logic.
3. **Auditability:** Skill execution logs capture exact model parameters, latency, and input hashes for complete audit trails.

---

## 6. Workflows: Why Composability Matters

1. **Topological DAG Execution:** Complex verification processes are structured as directed acyclic graphs (`WorkflowEngine`).
2. **Deterministic Data Flow:** Outputs of earlier steps (e.g., media fetching -> frame derivation) feed cleanly into parallel or downstream steps (AI observation -> comparison -> evidence packaging).
3. **Resilience & State Tracking:** Step-level execution tracking allows diagnosing failures, retrying individual nodes, and inspecting intermediate artifacts.

---

## 7. Verification: Why AI Output is Not Automatically Truth

1. **AI Proposes, Humans Certify:** An AI model cannot legally or ethically sign off on carbon or plastic credits.
2. **Review Queue Workflow:** The SETOWA Review Queue presents AI observations alongside raw visual evidence to certified human auditors.
3. **Explicit Uncertainty Disclosures:** Observations maintain status flags (`provisional` -> `under_review` -> `approved` / `rejected`). If an observation has high uncertainty, it cannot be promoted to verified evidence without manual corroboration.

---

## 8. Impact: How Verified Evidence Becomes an Impact Story

1. **Multi-Source Corroboration:** AI visual evidence (before/after photos and video frames) is linked directly with physical ground truth (e.g., municipal weigh slips, scale tickets).
2. **Chronological Event Stream:** Story events represent real field visits with exact timestamps, GPS coordinates, and verified media artifacts.
3. **Honest Metrics:** The impact story reports concrete, verifiable quantities (e.g., `320.0 kg net waste collected`) rather than speculative extrapolation.

---

## 9. Public Share: Safe, Transparent Stakeholder Engagement

1. **Token-Gated Publishing:** Impact stories can be shared publicly via secure, unguessable tokens (`/share/{token}`).
2. **Zero Secret Leakage:** Public endpoints and rendered HTML strictly filter out internal database IDs, reviewer API keys, cloud secrets, and draft revisions.
3. **Trust & Provenance:** External funders, regulators, and community members can zoom into original high-resolution Cloudinary assets, view the verification badges, and inspect the methodological notes.

---

## 10. Closing (4:30 – 5:00)

**Spoken Narrative:**
> "By combining Cloudinary's programmable visual delivery with Gemini's multimodal reasoning and human verification governance, SETOWA delivers the missing infrastructure for climate accountability.
>
> We don't ask you to trust a PDF certificate. We show you the evidence, step by step, from the field to the public."
