"""Impact story and sustainability timeline API routes for Setowa (Milestone T017)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.routes.media import require_upload_token
from app.schemas.api import (
    GenerateImpactStoryRequest,
    ImpactStoryResponse,
    ShareStoryResponse,
    TimelineEvent,
    UpdateImpactStoryRequest,
)
from app.services import evidence_store as store
from app.services.impact_story import (
    generate_impact_story,
    get_impact_story_by_id,
    get_project_impact_story,
    get_story_timeline_events,
    update_impact_story_fields,
)
from app.services.public_story import (
    ensure_story_share_token,
    revoke_story_share_token,
    rotate_story_share_token,
)

router = APIRouter(prefix="/api/v1", tags=["Impact Stories"], dependencies=[Depends(require_upload_token)])


@router.get("/projects/{project_id}/impact-story", response_model=ImpactStoryResponse)
def get_project_impact_story_endpoint(project_id: str):
    """Retrieve the current impact story for a project."""
    with store.connection() as db:
        if not store.get_project(db, project_id):
            site = store.get_site(db, project_id)
            if site and site.get("project_id"):
                project_id = site["project_id"]
        if not store.get_project(db, project_id):
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        story = get_project_impact_story(db, project_id)
        if not story:
            raise HTTPException(
                status_code=404,
                detail=f"Impact story for project '{project_id}' has not been generated yet. Call POST /api/v1/projects/{project_id}/impact-story/generate."
            )
        return story


@router.post("/projects/{project_id}/impact-story/generate", response_model=ImpactStoryResponse)
async def generate_project_impact_story_endpoint(
    project_id: str,
    payload: GenerateImpactStoryRequest = GenerateImpactStoryRequest(),
):
    """Generate or regenerate an impact story and chronological timeline from persisted project evidence."""
    with store.connection() as db:
        if not store.get_project(db, project_id):
            site = store.get_site(db, project_id)
            if site and site.get("project_id"):
                project_id = site["project_id"]
        if not store.get_project(db, project_id):
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        try:
            return await generate_impact_story(
                db,
                project_id=project_id,
                title=payload.title,
                description=payload.description,
                force_regenerate=payload.force_regenerate,
                include_ai_summary=payload.include_ai_summary,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate impact story: {str(e)}")


@router.get("/impact-stories/{story_id}", response_model=ImpactStoryResponse)
def get_impact_story_endpoint(story_id: str):
    """Retrieve an existing impact story by ID."""
    with store.connection() as db:
        story = get_impact_story_by_id(db, story_id)
        if not story:
            raise HTTPException(status_code=404, detail=f"Impact story '{story_id}' not found")
        return story


@router.put("/impact-stories/{story_id}", response_model=ImpactStoryResponse)
def update_impact_story_endpoint(story_id: str, payload: UpdateImpactStoryRequest):
    """Update editable attributes of an existing impact story."""
    updates = {}
    if payload.title is not None:
        updates["title"] = payload.title.strip()
    if payload.description is not None:
        updates["description"] = payload.description.strip()
    if payload.status is not None:
        updates["status"] = payload.status.strip()
    if payload.summary_narrative is not None:
        updates["summary_narrative"] = payload.summary_narrative.strip()

    with store.connection() as db:
        story = update_impact_story_fields(db, story_id, updates)
        if not story:
            raise HTTPException(status_code=404, detail=f"Impact story '{story_id}' not found")
        return story


@router.get("/impact-stories/{story_id}/timeline", response_model=List[TimelineEvent])
def get_impact_story_timeline_endpoint(story_id: str):
    """Retrieve only the chronological timeline events for a story."""
    with store.connection() as db:
        story = store.get_impact_story(db, story_id)
        if not story:
            raise HTTPException(status_code=404, detail=f"Impact story '{story_id}' not found")
        return get_story_timeline_events(db, story_id)


@router.post("/impact-stories/{story_id}/share", response_model=ShareStoryResponse)
def share_impact_story_endpoint(story_id: str):
    """Ensure a share token exists for the impact story, returning share metadata."""
    with store.connection() as db:
        story = store.get_impact_story(db, story_id)
        if not story:
            raise HTTPException(status_code=404, detail=f"Impact story '{story_id}' not found")
        token = ensure_story_share_token(db, story_id)
        status = story.get("status", "draft")
        return ShareStoryResponse(
            story_id=story_id,
            project_id=story["project_id"],
            status=status,
            share_token=token,
            share_url=f"/share/{token}" if token else None,
            is_public=(status == "published" and bool(token)),
        )


@router.post("/impact-stories/{story_id}/share/rotate", response_model=ShareStoryResponse)
def rotate_impact_story_share_endpoint(story_id: str):
    """Rotate the share token for an impact story, invalidating any previous share URL."""
    with store.connection() as db:
        story = store.get_impact_story(db, story_id)
        if not story:
            raise HTTPException(status_code=404, detail=f"Impact story '{story_id}' not found")
        new_token = rotate_story_share_token(db, story_id)
        status = story.get("status", "draft")
        return ShareStoryResponse(
            story_id=story_id,
            project_id=story["project_id"],
            status=status,
            share_token=new_token,
            share_url=f"/share/{new_token}" if new_token else None,
            is_public=(status == "published" and bool(new_token)),
        )


@router.post("/impact-stories/{story_id}/share/revoke", response_model=ShareStoryResponse)
def revoke_impact_story_share_endpoint(story_id: str):
    """Revoke public sharing for an impact story."""
    with store.connection() as db:
        story = store.get_impact_story(db, story_id)
        if not story:
            raise HTTPException(status_code=404, detail=f"Impact story '{story_id}' not found")
        revoke_story_share_token(db, story_id)
        status = story.get("status", "draft")
        return ShareStoryResponse(
            story_id=story_id,
            project_id=story["project_id"],
            status=status,
            share_token=None,
            share_url=None,
            is_public=False,
        )

