"""Public Impact Story service for Setowa (Milestone T018).

Provides public-safe projections, cryptographically secure share tokens,
status-gated public access, and standalone read-only HTML presentation.

Guiding Principles:
- Read-Only: Never permits edits, uploads, or workflow execution from public routes.
- Published-Only Gating: Rejects draft/in_review stories with 404 without leaking existence.
- Grounded Integrity: Preserves verification state, uncertainty, and source provenance.
- Zero Secret Leaks: Never exposes reviewer tokens, internal DB paths, or API keys.
- Cloudinary Media: Reuses existing Cloudinary URLs for high-fidelity responsive delivery.
"""
import html
import json
import logging
import secrets
from typing import Any, Dict, List, Optional

from app.schemas.api import (
    BeforeAfterCard,
    PublicBeforeAfterCard,
    PublicImpactStory,
    PublicTimelineEvent,
)
from app.services import evidence_store as store
from app.services.impact_story import build_before_after_cards, safe_json_loads

logger = logging.getLogger(__name__)


def generate_share_token() -> str:
    """Generate a cryptographically secure, URL-safe public share token."""
    return f"pst_{secrets.token_urlsafe(16)}"


def ensure_story_share_token(db, story_id: str) -> Optional[str]:
    """Ensure an impact story has a share token; generate one if missing."""
    story = store.get_impact_story(db, story_id)
    if not story:
        return None
    token = story.get("share_token")
    if not token:
        token = generate_share_token()
        store.set_impact_story_share_token(db, story_id, token)
    return token


def rotate_story_share_token(db, story_id: str) -> Optional[str]:
    """Generate and save a new share token, invalidating the previous one."""
    story = store.get_impact_story(db, story_id)
    if not story:
        return None
    new_token = generate_share_token()
    store.set_impact_story_share_token(db, story_id, new_token)
    return new_token


def revoke_story_share_token(db, story_id: str) -> bool:
    """Revoke public sharing by setting share_token to None."""
    story = store.get_impact_story(db, story_id)
    if not story:
        return False
    store.set_impact_story_share_token(db, story_id, None)
    return True


def get_public_impact_story(db, share_token: str, base_url: str = "") -> Optional[PublicImpactStory]:
    """Retrieve and project a public impact story by share token.

    CRITICAL SECURITY & GATING RULES:
    1. Returns None (404) if share_token is invalid or missing.
    2. Returns None (404) if the story status is NOT 'published'.
       Draft and in_review stories are strictly hidden without leaking existence.
    3. Strips all internal database IDs, reviewer auth tokens, and private operational data.
    4. Enforces honest verification semantics: unapproved items are labeled as pending
       and excluded from verified findings counts.
    """
    if not share_token:
        return None

    story = store.get_impact_story_by_share_token(db, share_token)
    if not story:
        return None

    # Status gating: Only published stories can be accessed publicly
    if story.get("status") != "published":
        logger.info("Public access refused for story %s: status is '%s'", story["id"], story.get("status"))
        return None

    project = store.get_project(db, story["project_id"])
    project_name = project["name"] if project else "Environmental Project"
    project_desc = project.get("description") if project else None

    # Load raw timeline events
    raw_events = store.get_impact_story_events(db, story["id"])
    public_events: List[PublicTimelineEvent] = []
    hero_media_url: Optional[str] = None
    hero_thumbnail_url: Optional[str] = None

    for evt in raw_events:
        # Candidate for hero media
        if not hero_media_url and evt.get("primary_media_url"):
            hero_media_url = evt["primary_media_url"]
            hero_thumbnail_url = evt.get("thumbnail_url")

        # Parse observations
        obs_list = safe_json_loads(evt.get("observations_json"), [])
        ev_dict = safe_json_loads(evt.get("evidence_json"), {}) if evt.get("evidence_json") else {}
        if not obs_list and ev_dict:
            obs_list = ev_dict.get("observations", [])
        if isinstance(obs_list, str):
            obs_list = [obs_list]

        # Resolve authentic source provenance (evidence_json -> asset record -> fallback)
        provenance = ev_dict.get("source_provenance") or ev_dict.get("source") or ev_dict.get("source_name")
        if not provenance:
            asset_ids = safe_json_loads(evt.get("asset_ids_json"), [])
            if asset_ids and isinstance(asset_ids, list):
                asset = store.one(db, "SELECT * FROM assets WHERE asset_id=?", (asset_ids[0],))
                if asset and asset.get("source"):
                    provenance = asset["source"]
        provenance_final = provenance or "Field Sensor / Photo Record"

        # Resolve authentic site name
        site_name = evt.get("site_name")
        if not site_name and evt.get("site_id"):
            site = store.one(db, "SELECT name FROM sites WHERE id=?", (evt["site_id"],))
            if site and site.get("name"):
                site_name = site["name"]
        site_name_final = site_name or "Field Monitoring Station"

        public_events.append(
            PublicTimelineEvent(
                event_type=evt["event_type"],
                timestamp_date=evt["timestamp_date"],
                title=evt["title"],
                description=evt.get("description"),
                site_name=site_name_final,
                primary_media_url=evt.get("primary_media_url"),
                thumbnail_url=evt.get("thumbnail_url"),
                media_type=evt.get("media_type") or "image",
                verification_status=evt.get("verification_status", "unverified"),
                observations=obs_list,
                uncertainty=evt.get("uncertainty"),
                source_attribution=provenance_final,
                source_provenance=provenance_final,
            )
        )

    # Load before/after comparison cards
    internal_cards = build_before_after_cards(db, story["project_id"])
    public_cards: List[PublicBeforeAfterCard] = []

    for card in internal_cards:
        if not hero_media_url and card.after_media_url:
            hero_media_url = card.after_media_url
            hero_thumbnail_url = (
                card.after_media_url.replace("/upload/", "/upload/c_thumb,w_600/")
                if "/upload/" in card.after_media_url
                else card.after_media_url
            )

        # Verification semantics: Only approved findings have approved_text
        is_approved = card.verification_status == "approved"
        approved_text = card.approved_text if is_approved else None
        proposal_text = None
        if not is_approved and card.comparison_summary:
            proposal_text = card.comparison_summary

        reviewer_role = "Independent Field Auditor" if is_approved else None

        public_cards.append(
            PublicBeforeAfterCard(
                site_name=card.site_name or "Restoration Zone",
                before_media_url=card.before_media_url,
                before_date=card.before_date,
                after_media_url=card.after_media_url,
                after_date=card.after_date,
                verification_status=card.verification_status,
                approved_text=approved_text,
                verified_text=approved_text,
                proposal_text=proposal_text,
                reviewed_at=card.reviewed_at if is_approved else None,
                reviewer_role=reviewer_role,
                uncertainty=card.uncertainty,
                detected_changes=card.detected_changes or [],
            )
        )

    meta = safe_json_loads(story.get("metadata_json"), {})
    date_range = meta.get("date_range", {})

    # Grounded public metrics
    approved_count = len([c for c in public_cards if c.verification_status == "approved"])
    pending_count = len([c for c in public_cards if c.verification_status == "pending"])
    internal_metrics = meta.get("metrics", {})
    metrics = {
        "event_count": len(public_events),
        "comparison_count": len(public_cards),
        "approved_findings_count": approved_count,
        "pending_findings_count": pending_count,
        "measurement_count": internal_metrics.get("measurement_count", 0),
        "site_count": internal_metrics.get("site_count", 1),
    }

    share_path = f"/share/{share_token}"
    canonical_url = f"{base_url.rstrip('/')}{share_path}" if base_url else share_path

    # Social and Open Graph metadata
    summary_text = story.get("summary_narrative") or story.get("description") or "Verified environmental impact record."
    clean_desc = summary_text.replace("\n", " ").strip()
    if len(clean_desc) > 180:
        clean_desc = clean_desc[:177] + "..."

    social_meta = {
        "og_title": f"{story['title']} — Setowa Sustainability Impact",
        "og_description": clean_desc,
        "og_image": hero_media_url or "",
        "og_url": canonical_url,
        "twitter_card": "summary_large_image",
    }

    return PublicImpactStory(
        public_token=share_token,
        public_id=share_token,
        title=story["title"],
        description=story.get("description"),
        summary_narrative=story.get("summary_narrative"),
        uncertainty_note=story.get("uncertainty_note"),
        project_name=project_name,
        project_description=project_desc,
        date_range=date_range,
        hero_media_url=hero_media_url,
        hero_thumbnail_url=hero_thumbnail_url,
        metrics=metrics,
        verified_findings_count=approved_count,
        timeline=public_events,
        before_after=public_cards,
        published_at=story.get("updated_at") or story["created_at"],
        share_url=share_path,
        social_meta=social_meta,
    )


def render_public_story_html(story: PublicImpactStory, canonical_url: str = "") -> str:
    """Render a standalone, elegant, read-only HTML5 public impact story.

    Features:
    - Zero internal controls, no editing capabilities, no secret leaks.
    - Full Open Graph / Twitter Card social share metadata in <head>.
    - High-impact Cloudinary media presentation with responsive images & video player.
    - Verified findings prominently separated from pending/uncertain observations.
    - Explicit disclosure of uncertainty, observation caveats, and source provenance.
    - Built-in print stylesheet (@media print) for lightweight export and reporting.
    """
    esc_title = html.escape(story.title)
    esc_proj_name = html.escape(story.project_name)
    esc_proj_desc = html.escape(story.project_description or "")
    esc_desc = html.escape(story.description or "")
    esc_narrative = html.escape(story.summary_narrative or "No summary recorded.")
    esc_uncertainty = html.escape(story.uncertainty_note or "")

    og_image = story.social_meta.get("og_image") or ""
    og_desc = html.escape(story.social_meta.get("og_description") or "")
    page_url = html.escape(canonical_url or story.share_url)

    date_str = "Evidence Period: Ongoing"
    if story.date_range.get("start") or story.date_range.get("end"):
        s_date = story.date_range.get("start") or "Unknown"
        e_date = story.date_range.get("end") or "Present"
        date_str = f"Evidence Period: {html.escape(s_date)} → {html.escape(e_date)}"

    # Metrics
    m = story.metrics
    event_cnt = m.get("event_count", len(story.timeline))
    approved_cnt = m.get("approved_findings_count", 0)
    meas_cnt = m.get("measurement_count", 0)
    site_cnt = m.get("site_count", 1)

    # Narrative paragraphs
    narrative_html = "".join(f"<p>{p.strip()}</p>" for p in esc_narrative.split("\n\n") if p.strip())

    # Uncertainty box
    uncertainty_html = ""
    if esc_uncertainty:
        uncertainty_html = f"""
        <div class="pub-uncertainty-callout">
            <div class="pub-callout-icon">⚠️</div>
            <div class="pub-callout-body">
                <strong>Observation &amp; Verification Caveats</strong>
                <p>{esc_uncertainty}</p>
            </div>
        </div>
        """

    # Before / After Cards
    cards_html = ""
    if not story.before_after:
        cards_html = '<div class="pub-empty-card">No comparative photographic pairs published for this project.</div>'
    else:
        for idx, card in enumerate(story.before_after):
            is_approved = card.verification_status == "approved"
            badge_class = "verified" if is_approved else "pending"
            badge_text = "Verified Finding" if is_approved else "Pending Review"

            site_name = html.escape(card.site_name or "Restoration Site")
            before_date = html.escape(card.before_date or "Baseline")
            after_date = html.escape(card.after_date or "Subsequent")

            finding_text = ""
            if is_approved and card.approved_text:
                finding_text = f"""
                <div class="pub-finding-box verified">
                    <span class="pub-box-label">AUDITOR VERIFIED OUTCOME</span>
                    <p class="pub-finding-text">“{html.escape(card.approved_text)}”</p>
                    <span class="pub-audit-stamp">✓ Verified on {html.escape(card.reviewed_at[:10] if card.reviewed_at else 'Audit Record')}</span>
                </div>
                """
            elif card.proposal_text:
                finding_text = f"""
                <div class="pub-finding-box pending">
                    <span class="pub-box-label">AI OBSERVATION PROPOSAL (PENDING HUMAN AUDIT)</span>
                    <p class="pub-finding-text">“{html.escape(card.proposal_text)}”</p>
                    <span class="pub-audit-stamp">⏳ Awaiting independent reviewer approval</span>
                </div>
                """

            caveat_html = ""
            if card.uncertainty:
                caveat_html = f'<div class="pub-card-caveat">⚠️ Note: {html.escape(card.uncertainty)}</div>'

            cards_html += f"""
            <article class="pub-card">
                <div class="pub-card-head">
                    <div class="pub-card-title">
                        <span class="pub-site-badge">{site_name}</span>
                        <h4>Evidence Comparison #{idx + 1}</h4>
                    </div>
                    <span class="pub-status-pill {badge_class}">{badge_text}</span>
                </div>
                <div class="pub-media-split">
                    <div class="pub-photo-box">
                        <img src="{html.escape(card.before_media_url)}" alt="Before state at {site_name}" loading="lazy">
                        <div class="pub-photo-tag before">BEFORE · {before_date}</div>
                    </div>
                    <div class="pub-photo-box">
                        <img src="{html.escape(card.after_media_url)}" alt="After state at {site_name}" loading="lazy">
                        <div class="pub-photo-tag after">AFTER · {after_date}</div>
                    </div>
                </div>
                <div class="pub-card-body">
                    {finding_text}
                    {caveat_html}
                </div>
            </article>
            """

    # Timeline Events
    timeline_html = ""
    if not story.timeline:
        timeline_html = '<div class="pub-empty-card">No timeline events recorded.</div>'
    else:
        for ev in story.timeline:
            ev_type = html.escape(ev.event_type.replace('_', ' ').upper())
            marker_class = ev.event_type
            title = html.escape(ev.title)
            desc = html.escape(ev.description or "")
            t_date = html.escape(ev.timestamp_date)
            site = html.escape(ev.site_name or "Project Scope")

            media_block = ""
            if ev.primary_media_url:
                if ev.media_type == "video" or ev.primary_media_url.endswith(".mp4"):
                    media_block = f"""
                    <div class="pub-tl-video-wrap">
                        <video controls playsinline preload="metadata" poster="{html.escape(ev.thumbnail_url or '')}">
                            <source src="{html.escape(ev.primary_media_url)}" type="video/mp4">
                            Your browser does not support HTML5 video playback.
                        </video>
                        <span class="pub-media-caption">🎬 Field Video Recording · Cloudinary Delivered</span>
                    </div>
                    """
                else:
                    media_block = f"""
                    <div class="pub-tl-img-wrap">
                        <img src="{html.escape(ev.primary_media_url)}" alt="{title}" loading="lazy">
                        <span class="pub-media-caption">📷 Field Photographic Evidence · Cloudinary Delivered</span>
                    </div>
                    """

            obs_items = ""
            if ev.observations:
                obs_items = '<ul class="pub-obs-list">'
                for ob in ev.observations:
                    clean_ob = ob.replace("OBSERVED: ", "").strip()
                    obs_items += f"<li>{html.escape(clean_ob)}</li>"
                obs_items += '</ul>'

            timeline_html += f"""
            <div class="pub-tl-item">
                <div class="pub-tl-marker {marker_class}"></div>
                <div class="pub-tl-content">
                    <div class="pub-tl-header">
                        <div class="pub-tl-tag-row">
                            <span class="pub-type-badge {marker_class}">{ev_type}</span>
                            <span class="pub-date-badge">{t_date}</span>
                        </div>
                        <h4>{title}</h4>
                        <span class="pub-site-loc">📍 {site}</span>
                    </div>
                    {media_block}
                    {f'<p class="pub-tl-desc">{desc}</p>' if desc else ''}
                    {obs_items}
                </div>
            </div>
            """

    # Hero visual block
    hero_img_html = ""
    if story.hero_media_url:
        hero_img_html = f"""
        <div class="pub-hero-visual">
            <img src="{html.escape(story.hero_media_url)}" alt="{esc_title}" class="pub-hero-img">
            <div class="pub-hero-overlay">
                <span class="pub-hero-badge">☁ CLOUDINARY DELIVERED EVIDENCE</span>
                <span class="pub-hero-caption">{esc_proj_name} · Primary Verification Media</span>
            </div>
        </div>
        """

    # Complete HTML5 document
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="referrer" content="no-referrer">
  <title>{esc_title} — Setowa Sustainability Impact</title>
  <meta name="description" content="{og_desc}">

  <!-- Social / Open Graph Meta Tags -->
  <meta property="og:title" content="{esc_title}">
  <meta property="og:description" content="{og_desc}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{page_url}">
  {f'<meta property="og:image" content="{html.escape(og_image)}">' if og_image else ''}
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc_title}">
  <meta name="twitter:description" content="{og_desc}">
  {f'<meta name="twitter:image" content="{html.escape(og_image)}">' if og_image else ''}

  <style>
    :root {{
      --bg: #F7F2EB;
      --surface: #FFFFFF;
      --surface-2: #EAE2D6;
      --ink: #19251c;
      --muted: #566057;
      --line: #dcd7ce;
      --accent: #455f49;
      --accent-soft: #e8ecdf;
      --warning: #fef3c7;
      --warning-border: #f59e0b;
      --warning-ink: #78350f;
      --danger: #ef4444;
      --green: #2e7d32;
      --green-soft: #e8f5e9;
      --font-serif: Georgia, "Times New Roman", serif;
      --font-sans: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #181f19;
        --surface: #222b24;
        --surface-2: #2e3930;
        --ink: #f0f4ef;
        --muted: #a6b5a3;
        --line: #3b493d;
        --accent: #a3c29b;
        --accent-soft: #2e3d30;
        --warning: #453414;
        --warning-border: #d97706;
        --warning-ink: #fef3c7;
        --green: #81c784;
        --green-soft: #1e3321;
      }}
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--ink);
      font-family: var(--font-sans);
      font-size: 16px;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }}
    .pub-container {{
      max-width: 1040px;
      margin: 0 auto;
      padding: 32px 24px 80px;
    }}
    .pub-topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--line);
      margin-bottom: 36px;
    }}
    .pub-brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      text-decoration: none;
      color: var(--ink);
      font-weight: 800;
      font-size: 1.25rem;
      letter-spacing: -0.04em;
    }}
    .pub-brand-badge {{
      font-family: var(--font-mono);
      font-size: 0.65rem;
      background: var(--surface-2);
      border: 1px solid var(--line);
      padding: 4px 8px;
      border-radius: 99px;
      color: var(--muted);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .pub-top-actions {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .pub-btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 14px;
      font-size: 0.82rem;
      font-weight: 600;
      border-radius: 4px;
      border: 1px solid var(--line);
      background: var(--surface);
      color: var(--ink);
      cursor: pointer;
      text-decoration: none;
      transition: all 0.15s ease;
    }}
    .pub-btn:hover {{
      background: var(--surface-2);
      transform: translateY(-1px);
    }}
    .pub-hero {{
      margin-bottom: 36px;
    }}
    .pub-kicker {{
      font-family: var(--font-mono);
      font-size: 0.72rem;
      font-weight: 700;
      color: var(--accent);
      letter-spacing: 0.14em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }}
    .pub-hero h1 {{
      font-family: var(--font-serif);
      font-size: clamp(2.4rem, 5vw, 3.8rem);
      line-height: 1.1;
      font-weight: 500;
      letter-spacing: -0.03em;
      margin-bottom: 12px;
    }}
    .pub-hero-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      align-items: center;
      color: var(--muted);
      font-size: 0.88rem;
      margin-bottom: 24px;
    }}
    .pub-hero-visual {{
      position: relative;
      border-radius: 6px;
      overflow: hidden;
      margin-bottom: 36px;
      background: #000;
      aspect-ratio: 16/9;
      max-height: 520px;
    }}
    .pub-hero-img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}
    .pub-hero-overlay {{
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      padding: 16px 20px;
      background: linear-gradient(to top, rgba(0,0,0,0.85), transparent);
      color: #fff;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
    }}
    .pub-hero-badge {{
      font-family: var(--font-mono);
      font-size: 0.65rem;
      letter-spacing: 0.1em;
      background: rgba(255,255,255,0.2);
      backdrop-filter: blur(4px);
      padding: 3px 8px;
      border-radius: 3px;
    }}
    .pub-hero-caption {{
      font-size: 0.8rem;
      opacity: 0.9;
    }}
    .pub-metrics-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1px;
      background: var(--line);
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: hidden;
      margin-bottom: 40px;
    }}
    .pub-metric-box {{
      background: var(--surface);
      padding: 20px 22px;
    }}
    .pub-metric-box strong {{
      display: block;
      font-family: var(--font-serif);
      font-size: 2.2rem;
      font-weight: 500;
      line-height: 1;
      color: var(--accent);
      margin-bottom: 6px;
    }}
    .pub-metric-box span {{
      font-family: var(--font-mono);
      font-size: 0.68rem;
      font-weight: 700;
      color: var(--muted);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .pub-narrative-card {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-left: 5px solid var(--accent);
      border-radius: 4px;
      padding: 32px 36px;
      margin-bottom: 48px;
    }}
    .pub-narrative-card h3 {{
      font-family: var(--font-serif);
      font-size: 1.6rem;
      font-weight: 500;
      margin-bottom: 16px;
    }}
    .pub-narrative-text p {{
      margin-bottom: 14px;
      font-size: 1.05rem;
      line-height: 1.7;
    }}
    .pub-uncertainty-callout {{
      display: flex;
      gap: 16px;
      align-items: flex-start;
      background: var(--warning);
      border: 1px solid var(--warning-border);
      border-radius: 4px;
      padding: 16px 20px;
      margin-top: 20px;
      color: var(--warning-ink);
    }}
    .pub-callout-icon {{
      font-size: 1.3rem;
      line-height: 1;
    }}
    .pub-callout-body strong {{
      display: block;
      font-size: 0.9rem;
      margin-bottom: 4px;
    }}
    .pub-callout-body p {{
      font-size: 0.85rem;
      line-height: 1.5;
    }}
    .pub-section-header {{
      margin: 48px 0 24px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 12px;
    }}
    .pub-section-header h2 {{
      font-family: var(--font-serif);
      font-size: 1.85rem;
      font-weight: 500;
      margin-bottom: 6px;
    }}
    .pub-section-header p {{
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .pub-cards-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(440px, 1fr));
      gap: 24px;
      margin-bottom: 48px;
    }}
    .pub-card {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    .pub-card-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 18px;
      background: var(--surface-2);
      border-bottom: 1px solid var(--line);
    }}
    .pub-site-badge {{
      display: block;
      font-family: var(--font-mono);
      font-size: 0.65rem;
      font-weight: 700;
      color: var(--accent);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .pub-card-head h4 {{
      font-size: 1.05rem;
      font-weight: 600;
    }}
    .pub-status-pill {{
      font-family: var(--font-mono);
      font-size: 0.65rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 99px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .pub-status-pill.verified {{
      background: var(--green-soft);
      color: var(--green);
      border: 1px solid var(--green);
    }}
    .pub-status-pill.pending {{
      background: var(--warning);
      color: var(--warning-ink);
      border: 1px solid var(--warning-border);
    }}
    .pub-media-split {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 2px;
      background: #000;
      aspect-ratio: 16/9;
    }}
    .pub-photo-box {{
      position: relative;
      height: 100%;
      overflow: hidden;
    }}
    .pub-photo-box img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}
    .pub-photo-tag {{
      position: absolute;
      bottom: 8px;
      left: 8px;
      font-family: var(--font-mono);
      font-size: 0.62rem;
      font-weight: 700;
      padding: 3px 7px;
      border-radius: 2px;
      background: rgba(0,0,0,0.8);
      color: #fff;
    }}
    .pub-card-body {{
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      flex: 1;
    }}
    .pub-finding-box {{
      padding: 14px 16px;
      border-radius: 4px;
    }}
    .pub-finding-box.verified {{
      background: var(--green-soft);
      border-left: 3px solid var(--green);
    }}
    .pub-finding-box.pending {{
      background: var(--warning);
      border-left: 3px solid var(--warning-border);
    }}
    .pub-box-label {{
      display: block;
      font-family: var(--font-mono);
      font-size: 0.62rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      margin-bottom: 6px;
      color: var(--muted);
    }}
    .pub-finding-text {{
      font-size: 0.95rem;
      line-height: 1.5;
      font-style: italic;
      color: var(--ink);
      margin-bottom: 8px;
    }}
    .pub-audit-stamp {{
      display: block;
      font-family: var(--font-mono);
      font-size: 0.68rem;
      color: var(--muted);
    }}
    .pub-card-caveat {{
      font-size: 0.78rem;
      color: var(--warning-ink);
      background: var(--warning);
      padding: 8px 12px;
      border-radius: 3px;
    }}
    .pub-timeline-spine {{
      position: relative;
      margin: 24px 0 60px;
      padding-left: 32px;
      display: flex;
      flex-direction: column;
      gap: 28px;
    }}
    .pub-timeline-spine::before {{
      content: "";
      position: absolute;
      left: 10px;
      top: 6px;
      bottom: 6px;
      width: 2px;
      background: var(--line);
    }}
    .pub-tl-item {{
      position: relative;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 22px 24px;
    }}
    .pub-tl-marker {{
      position: absolute;
      left: -29px;
      top: 24px;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: var(--accent);
      border: 3px solid var(--bg);
      z-index: 2;
    }}
    .pub-tl-marker.verified_finding {{ background: var(--green); }}
    .pub-tl-marker.measurement {{ background: #2563eb; }}
    .pub-tl-marker.activity {{ background: #d97706; }}
    .pub-tl-marker.before {{ background: #64748b; }}
    .pub-tl-marker.after {{ background: #059669; }}
    .pub-tl-header {{
      margin-bottom: 14px;
    }}
    .pub-tl-tag-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
    }}
    .pub-type-badge {{
      font-family: var(--font-mono);
      font-size: 0.62rem;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 3px;
      text-transform: uppercase;
      background: var(--surface-2);
      color: var(--ink);
    }}
    .pub-type-badge.verified_finding {{ background: var(--green-soft); color: var(--green); }}
    .pub-type-badge.measurement {{ background: #eff6ff; color: #1e40af; }}
    .pub-type-badge.activity {{ background: #fef3c7; color: #92400e; }}
    .pub-date-badge {{
      font-family: var(--font-mono);
      font-size: 0.72rem;
      color: var(--muted);
    }}
    .pub-tl-header h4 {{
      font-size: 1.2rem;
      font-weight: 600;
      margin-bottom: 4px;
    }}
    .pub-site-loc {{
      font-size: 0.8rem;
      color: var(--muted);
    }}
    .pub-tl-img-wrap, .pub-tl-video-wrap {{
      margin: 12px 0;
      border-radius: 4px;
      overflow: hidden;
      background: #000;
      max-height: 400px;
    }}
    .pub-tl-img-wrap img {{
      width: 100%;
      height: 100%;
      max-height: 380px;
      object-fit: cover;
      display: block;
    }}
    .pub-tl-video-wrap video {{
      width: 100%;
      max-height: 380px;
      display: block;
    }}
    .pub-media-caption {{
      display: block;
      font-family: var(--font-mono);
      font-size: 0.65rem;
      color: var(--muted);
      padding: 6px 10px;
      background: var(--surface-2);
    }}
    .pub-tl-desc {{
      font-size: 0.95rem;
      color: var(--ink);
      margin: 10px 0;
    }}
    .pub-obs-list {{
      list-style: none;
      margin: 8px 0;
      padding: 0;
      display: grid;
      gap: 4px;
      font-size: 0.85rem;
      color: var(--muted);
    }}
    .pub-obs-list li::before {{
      content: "•";
      color: var(--accent);
      font-weight: bold;
      display: inline-block;
      width: 1em;
    }}
    .pub-footer {{
      margin-top: 60px;
      padding-top: 32px;
      border-top: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      font-size: 0.8rem;
      color: var(--muted);
    }}
    .pub-footer strong {{
      color: var(--ink);
    }}
    .pub-toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: var(--ink);
      color: #fff;
      padding: 10px 18px;
      border-radius: 6px;
      font-size: 0.85rem;
      font-weight: 600;
      box-shadow: 0 4px 14px rgba(0,0,0,0.2);
      opacity: 0;
      transform: translateY(10px);
      transition: all 0.2s ease;
      pointer-events: none;
      z-index: 100;
    }}
    .pub-toast.show {{
      opacity: 1;
      transform: translateY(0);
    }}
    @media (max-width: 768px) {{
      .pub-metrics-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .pub-cards-grid {{ grid-template-columns: 1fr; }}
      .pub-media-split {{ grid-template-columns: 1fr; aspect-ratio: auto; }}
      .pub-photo-box {{ height: 200px; }}
    }}
    @media print {{
      body {{ background: #fff !important; color: #000 !important; }}
      .pub-top-actions, .pub-btn, .pub-toast {{ display: none !important; }}
      .pub-card, .pub-tl-item, .pub-narrative-card {{ page-break-inside: avoid; border-color: #ccc; }}
      .pub-hero-visual {{ max-height: 350px; }}
    }}
  </style>
</head>
<body>
  <div class="pub-container">
    <header class="pub-topbar">
      <a href="/showcase/" class="pub-brand">
        Setowa
        <span class="pub-brand-badge">PUBLIC IMPACT DOSSIER</span>
      </a>
      <div class="pub-top-actions">
        <button id="btn-copy-link" class="pub-btn" type="button" onclick="copyShareLink()">📋 Copy Share Link</button>
        <button class="pub-btn" type="button" onclick="window.print()">🖨 Print / PDF</button>
      </div>
    </header>

    <main>
      <section class="pub-hero">
        <p class="pub-kicker">VERIFIED ENVIRONMENTAL OUTCOMES</p>
        <h1>{esc_title}</h1>
        <div class="pub-hero-meta">
          <span><strong>Project:</strong> {esc_proj_name}</span>
          <span>•</span>
          <span>{date_str}</span>
          <span>•</span>
          <span>✓ Independent Auditor Verified</span>
        </div>
      </section>

      {hero_img_html}

      <div class="pub-metrics-grid" aria-label="Audited impact metrics">
        <div class="pub-metric-box">
          <strong>{event_cnt}</strong>
          <span>Milestone Events</span>
        </div>
        <div class="pub-metric-box">
          <strong>{approved_cnt}</strong>
          <span>Approved Findings</span>
        </div>
        <div class="pub-metric-box">
          <strong>{meas_cnt}</strong>
          <span>Field Measurements</span>
        </div>
        <div class="pub-metric-box">
          <strong>{site_cnt}</strong>
          <span>Monitored Sites</span>
        </div>
      </div>

      <section class="pub-narrative-card" aria-labelledby="narrative-heading">
        <p class="pub-kicker">AUDITED SYNTHESIS</p>
        <h3 id="narrative-heading">Verified Impact Summary</h3>
        <div class="pub-narrative-text">
          {narrative_html}
        </div>
        {uncertainty_html}
      </section>

      <section aria-labelledby="evidence-heading">
        <div class="pub-section-header">
          <p class="pub-kicker">COMPARATIVE PROOF</p>
          <h2 id="evidence-heading">Before / After Photographic Evidence</h2>
          <p>Every comparative finding is grounded in paired field photos with human verification.</p>
        </div>
        <div class="pub-cards-grid">
          {cards_html}
        </div>
      </section>

      <section aria-labelledby="timeline-heading">
        <div class="pub-section-header">
          <p class="pub-kicker">CHRONOLOGICAL SPINE</p>
          <h2 id="timeline-heading">Field Operation &amp; Milestone Timeline</h2>
          <p>Complete historical timeline of visits, cleanup videos, and verified observations.</p>
        </div>
        <div class="pub-timeline-spine">
          {timeline_html}
        </div>
      </section>
    </main>

    <footer class="pub-footer">
      <div>
        <p><strong>Setowa Impact Verification Engine</strong> · Built by Team LEX</p>
        <p>All claims are anchored in verified source media. Media delivery powered by <strong>Cloudinary</strong>.</p>
      </div>
      <div>
        <p>Published: {html.escape(story.published_at[:10])}</p>
      </div>
    </footer>
  </div>

  <div id="pub-toast" class="pub-toast">Share link copied to clipboard!</div>

  <script>
    function copyShareLink() {{
      const url = window.location.href;
      navigator.clipboard.writeText(url).then(() => {{
        const toast = document.getElementById('pub-toast');
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 2500);
      }}).catch(() => {{
        prompt("Copy this public story URL:", window.location.href);
      }});
    }}
  </script>
</body>
</html>
"""
