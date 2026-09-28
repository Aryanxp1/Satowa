"""Public read-only Impact Story routes for Setowa (Milestone T018).

Provides public presentation and public-safe API projections for published
sustainability impact stories without requiring internal workspace authentication.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.schemas.api import PublicImpactStory
from app.services import evidence_store as store
from app.services.public_story import (
    get_public_impact_story,
    render_public_story_html,
)

# Public router without upload/admin authentication dependencies
public_router = APIRouter(tags=["Public Impact"])


@public_router.get("/share/{public_token}", response_class=HTMLResponse)
def get_public_impact_story_page(public_token: str, request: Request):
    """Serve a polished, read-only HTML impact story page for public viewing.

    Gated strictly to published stories with a valid share token.
    Draft, in_review, or non-existent stories return 404.
    """
    clean_token = public_token.strip()
    base_url = str(request.base_url).rstrip("/")
    canonical_url = f"{base_url}/share/{clean_token}"

    with store.connection() as db:
        story = get_public_impact_story(db, clean_token, base_url=base_url)
        if not story:
            raise HTTPException(
                status_code=404,
                detail="The requested impact story is not available or has not been published.",
            )

        html_content = render_public_story_html(story, canonical_url=canonical_url)
        return HTMLResponse(content=html_content, status_code=200)


@public_router.get("/api/v1/public/impact/{public_token}", response_model=PublicImpactStory)
def get_public_impact_story_api(public_token: str, request: Request):
    """Return a public-safe JSON projection of a published impact story.

    Excludes all internal reviewer tokens, database identifiers, and unverified claims.
    Draft, in_review, or non-existent stories return 404.
    """
    clean_token = public_token.strip()
    base_url = str(request.base_url).rstrip("/")

    with store.connection() as db:
        story = get_public_impact_story(db, clean_token, base_url=base_url)
        if not story:
            raise HTTPException(
                status_code=404,
                detail="The requested impact story is not available or has not been published.",
            )
        return story
