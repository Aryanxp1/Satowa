"""Project hierarchy and grouping API routes for Setowa (T015)."""
import json
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.routes.media import require_upload_token
from app.schemas.api import (
    PaginatedMediaQueryResponse,
    ProjectCreate,
    ProjectSummaryResponse,
)
from app.services import evidence_store as store
from app.services.media_query import (
    MediaQueryFilters,
    get_project_summary,
    list_project_summaries,
    query_media_assets,
    validate_date_string,
)

router = APIRouter(prefix="/api/v1", tags=["Projects"], dependencies=[Depends(require_upload_token)])


@router.get("/projects", response_model=List[ProjectSummaryResponse])
def get_projects():
    """Retrieve all projects with computed media and site metrics."""
    with store.connection() as db:
        return list_project_summaries(db)


@router.post("/projects", response_model=ProjectSummaryResponse, status_code=201)
def create_project_endpoint(payload: ProjectCreate):
    """Create a new project container."""
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Project name must not be blank")

    with store.connection() as db:
        if store.get_project(db, payload.id):
            raise HTTPException(status_code=409, detail=f"Project '{payload.id}' already exists")

        meta_str = json.dumps(payload.metadata) if payload.metadata else None
        store.create_project(
            db,
            {
                "id": payload.id,
                "name": name,
                "description": payload.description.strip(),
                "created_at": store.timestamp(),
                "metadata_json": meta_str,
            },
        )
        return get_project_summary(db, payload.id)


@router.get("/projects/{project_id}", response_model=ProjectSummaryResponse)
def get_project_detail(project_id: str):
    """Retrieve details and aggregate metrics for a specific project."""
    with store.connection() as db:
        return get_project_summary(db, project_id)


@router.get("/projects/{project_id}/media", response_model=PaginatedMediaQueryResponse)
def get_project_media(
    project_id: str,
    media_type: Optional[Literal["image", "video"]] = None,
    permission_status: Optional[Literal["granted", "pending_verification", "revoked"]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort: Literal["desc", "asc", "chronological", "reverse_chronological"] = "desc",
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """Query media assets belonging to a specific project."""
    validated_date_from = validate_date_string(date_from, "date_from")
    validated_date_to = validate_date_string(date_to, "date_to")

    with store.connection() as db:
        # Verify project exists
        if not store.get_project(db, project_id):
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

        filters = MediaQueryFilters(
            project_id=project_id,
            media_type=media_type,
            permission_status=permission_status,
            date_from=validated_date_from,
            date_to=validated_date_to,
            sort=sort,
            page=page,
            limit=limit,
        )
        return query_media_assets(db, filters)
