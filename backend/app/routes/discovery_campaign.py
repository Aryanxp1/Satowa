"""Local-only semantic discovery and evidence-linked campaign drafts."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.routes.media import require_upload_token
from app.services import evidence_store as store
from app.services.campaign import edit_draft, generate_draft, list_drafts
from app.services.semantic_search import search_project

router = APIRouter(prefix="/api/v1/projects", tags=["Discovery and Campaigns"],
                   dependencies=[Depends(require_upload_token)])


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    limit: int = Field(default=8, ge=1, le=20)


class CampaignRequest(BaseModel):
    channel: str = Field(pattern="^(social|newsletter|volunteer_update)$")


class CampaignEditRequest(BaseModel):
    body: str = Field(min_length=1, max_length=40000)


@router.post("/{project_id}/semantic-search")
async def semantic_search(project_id: str, payload: SearchRequest):
    """Embed current project evidence on demand and rank by vector similarity."""
    with store.connection() as db:
        return await search_project(db, project_id, payload.query.strip(), payload.limit)


@router.post("/{project_id}/search-index")
async def index_search(project_id: str):
    """Explicit bounded indexing; ordinary searches never embed the collection."""
    with store.connection() as db:
        return await search_project(db, project_id, "", index=True)


@router.post("/{project_id}/campaign-drafts", status_code=201)
def create_campaign_draft(project_id: str, payload: CampaignRequest):
    """Save a channel-specific draft using only reviewed/sourced records."""
    with store.connection() as db:
        return generate_draft(db, project_id, payload.channel)


@router.get("/{project_id}/campaign-drafts")
def get_campaign_drafts(project_id: str):
    with store.connection() as db:
        return list_drafts(db, project_id)


@router.put("/{project_id}/campaign-drafts/{draft_id}")
def update_campaign_draft(project_id: str, draft_id: str, payload: CampaignEditRequest):
    with store.connection() as db:
        return edit_draft(db, project_id, draft_id, payload.body)
