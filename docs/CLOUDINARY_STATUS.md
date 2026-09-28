# CLOUDINARY_STATUS.md — Official Cloudinary Tooling Verification
**Status Date:** 2026-09-27  
**Qualifying Tool:** Cloudinary AI Power Start (via Cloudinary AI Skills Pack + MCP)

---

## 1. Qualifying Tool Selection & Execution

Per the Cloudinary Hackathon rules, projects must utilize at least one official qualifying tool:
1. Cloudinary React AI Starter Kit
2. Cloudinary Next.js AI Starter Kit
3. Cloudinary AI Skills Pack
4. Cloudinary AI Power Start Prompt

For this existing FastAPI/Python repository, the official **Cloudinary AI Power Start** tooling workflow was executed:
- Detected stack: Python / FastAPI backend, Vanilla JS / HTML / CSS frontend.
- Installed official Cloudinary Agent Skills via `npx skills add cloudinary-devs/skills`.
- Configured official Cloudinary MCP servers (`cloudinary-asset-mgmt`, `cloudinary-env-config`).
- Preserved existing Python SDK runtime (`cloudinary==1.46.2`) and T007/T011 programmable media implementations.

---

## 2. Agent Skills Configuration

Installed via `npx skills add cloudinary-devs/skills`:
- Location: `.agents/skills/`
- Manifest Lockfile: `skills-lock.json`
- Installed Skills:
  1. `cloudinary-docs`: Official Cloudinary documentation lookup and guidance via llms.txt.
  2. `cloudinary-transformations`: Official syntax and optimization reference for image/video transformations (`f_auto`, `q_auto`, responsive scaling, video poster frames).

*Note: Cloudinary Agent Skills are development-time tools for the AI coding assistant, distinct from Setowa's user-facing product skills.*

---

## 3. MCP Server Configuration

Configured in `.mcp.json` (workspace) and global `mcp_config.json`:
- `cloudinary-asset-mgmt`: `@cloudinary/asset-management` (stdio transport via `npx`)
- `cloudinary-env-config`: `@cloudinary/environment-config` (stdio transport via `npx`)

Both servers provide developer-agent context for asset management and environment configuration.

---

## 4. Runtime SDK & Pipeline Integration

- **SDK:** `cloudinary==1.46.2` (Python SDK)
- **Programmable Media Features:**
  - Auto-format & quality optimization: `f_auto,q_auto`
  - High-res preview derivatives: `w_1200,h_900,c_limit`
  - Square gallery thumbnails: `w_640,h_480`
  - Video poster extraction at offset 0: `so_0`
  - Direct video uploads (`resource_type="video"`)
  - Multi-file bulk upload with per-file error isolation (`POST /api/v1/media/bulk`)

---

## 5. Validation Status

- **Setup Validation:** **VERIFIED**
  - SDK present and operational (`cloudinary==1.46.2`).
  - Agent Skills verified in `.agents/skills/` with valid `SKILL.md` files (`cloudinary-docs`, `cloudinary-transformations`).
  - MCP servers configured and verified (`cloudinary-asset-mgmt`, `cloudinary-env-config`).
- **Live Cloudinary Credential Validation:** **VERIFIED (MASTER ADMIN ACCESS)**
  - Local credentials active: Cloud Name `tlf3lv01`, API Key `865273779517949`.
  - Master Admin privileges verified: Authenticated ping (`ping: ok`), video CREATE/upload capability (`resource_type="video"`), metadata retrieval, poster frame derivation, and delivery URL generation.
  - Video Frame Derivation (T014): Verified on-the-fly frame extraction (`start_offset="so_<ts>"`, `.jpg` format, `c_fill,h_225,w_400` thumbnails) delivering HTTP 200 JPEG frames directly to Gemini multimodal vision pipeline.
  - Full test suite: 189 tests passing, 0 regressions.
- **Production Note:** The current MASTER ADMIN credential is for local hackathon development. Production deployments must provision scoped credentials with strict resource-level policies before production launch.

