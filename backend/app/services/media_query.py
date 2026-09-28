"""Media Query and Spatial-Temporal Grouping Service for Setowa (T015).

Provides multi-dimensional querying, sorting, pagination, timeline bucketing,
and project/site aggregate summaries over real persisted SQLite data.
"""
from datetime import date, datetime
import json
import math
from typing import Any, Dict, List, Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.schemas.api import (
    MediaItemResponse,
    PaginatedMediaQueryResponse,
    ProjectSummaryResponse,
    SiteSummaryResponse,
    TimelineBucket,
    TimelineMediaResponse,
)
from app.services import evidence_store as store


def validate_date_string(date_val: Optional[str], param_name: str) -> Optional[str]:
    """Validate that date_val conforms to YYYY-MM-DD or standard ISO-8601."""
    if not date_val:
        return None
    val = date_val.strip()
    if not val:
        return None
    # Try YYYY-MM-DD
    if len(val) == 10:
        try:
            datetime.strptime(val, "%Y-%m-%d")
            return val
        except ValueError:
            pass
    # Try ISO-8601
    try:
        datetime.fromisoformat(val.replace("Z", "+00:00"))
        return val
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid date format for '{param_name}': '{date_val}'. Expected YYYY-MM-DD or ISO 8601 string."
        )


class MediaQueryFilters(BaseModel):
    """Filter parameters for multi-dimensional media searches."""
    project_id: Optional[str] = None
    site_id: Optional[str] = None
    media_type: Optional[Literal["image", "video"]] = None
    permission_status: Optional[Literal["granted", "pending_verification", "revoked"]] = None
    source: Optional[str] = None
    filename: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    date_basis: Literal["created_at", "captured_at", "effective"] = "created_at"
    min_lat: Optional[float] = None
    max_lat: Optional[float] = None
    min_lng: Optional[float] = None
    max_lng: Optional[float] = None
    tag: Optional[str] = None
    signal: Optional[str] = None
    ai_status: Optional[str] = None
    sort: Literal["desc", "asc", "chronological", "reverse_chronological"] = "desc"
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=200)


def row_to_media_item(row: dict) -> MediaItemResponse:
    """Helper to convert a database row dict to MediaItemResponse."""
    meta = None
    if row.get("metadata_json"):
        try:
            meta = json.loads(row["metadata_json"])
        except Exception:
            pass
    return MediaItemResponse(
        asset_id=row["asset_id"],
        public_id=row["public_id"],
        version=row["version"],
        secure_url=row["secure_url"],
        thumbnail_url=row.get("thumbnail_url"),
        preview_url=row.get("preview_url"),
        source=row["source"],
        media_type=row.get("media_type") or "image",
        width=row.get("width"),
        height=row.get("height"),
        duration=row.get("duration"),
        format=row["format"],
        permission_status=row.get("permission_status") or "granted",
        processing_status=row.get("processing_status") or "ready",
        site_id=row.get("site_id"),
        project_id=row.get("project_id"),
        captured_at=row.get("captured_at"),
        visit_id=row.get("visit_id"),
        original_filename=row.get("original_filename"),
        created_at=row.get("created_at"),
        metadata=meta,
    )


def _build_where_clause(filters: MediaQueryFilters) -> tuple[str, list[Any], str]:
    """Build parameterized SQL WHERE conditions and identify target date expression."""
    clauses = ["1=1"]
    params: list[Any] = []

    if filters.project_id:
        clauses.append(
            "(assets.project_id = ? OR assets.site_id IN (SELECT id FROM sites WHERE project_id = ?))"
        )
        params.extend([filters.project_id, filters.project_id])

    if filters.site_id:
        clauses.append("assets.site_id = ?")
        params.append(filters.site_id)

    if filters.media_type:
        clauses.append("assets.media_type = ?")
        params.append(filters.media_type.lower())

    if filters.permission_status:
        clauses.append("assets.permission_status = ?")
        params.append(filters.permission_status.lower())

    if filters.source:
        clauses.append("assets.source LIKE ?")
        params.append(f"%{filters.source.strip()}%")

    if filters.filename:
        clauses.append("(assets.original_filename LIKE ? OR assets.public_id LIKE ?)")
        search_term = f"%{filters.filename.strip()}%"
        params.extend([search_term, search_term])

    # Date basis resolution
    if filters.date_basis == "captured_at":
        target_date_expr = "assets.captured_at"
    elif filters.date_basis == "effective":
        target_date_expr = "COALESCE(assets.captured_at, assets.created_at)"
    else:
        target_date_expr = "assets.created_at"

    if filters.date_from:
        val_from = filters.date_from.strip()
        clauses.append(f"{target_date_expr} >= ?")
        params.append(val_from)

    if filters.date_to:
        val_to = filters.date_to.strip()
        # If date-only string (length 10, e.g. '2026-09-24'), expand to end of day
        if len(val_to) == 10:
            val_to = f"{val_to}T23:59:59.999999"
        clauses.append(f"{target_date_expr} <= ?")
        params.append(val_to)

    # Structured AI Intelligence Discovery Filters
    if filters.tag:
        clean_tag = filters.tag.strip().lower().replace("-", "_").replace(" ", "_")
        clauses.append("assets.asset_id IN (SELECT asset_id FROM media_intelligence WHERE tags_json LIKE ?)")
        params.append(f'%"{clean_tag}"%')

    if filters.signal:
        clean_signal = filters.signal.strip().lower().replace("-", "_").replace(" ", "_")
        clauses.append("assets.asset_id IN (SELECT asset_id FROM media_intelligence WHERE signals_json LIKE ?)")
        params.append(f'%"{clean_signal}"%')

    if filters.ai_status:
        clauses.append("assets.asset_id IN (SELECT asset_id FROM media_intelligence WHERE status = ?)")
        params.append(filters.ai_status.strip().lower())

    # Spatial bounding box on sites
    spatial_clauses = []
    spatial_params: list[Any] = []
    if filters.min_lat is not None:
        spatial_clauses.append("latitude >= ?")
        spatial_params.append(filters.min_lat)
    if filters.max_lat is not None:
        spatial_clauses.append("latitude <= ?")
        spatial_params.append(filters.max_lat)
    if filters.min_lng is not None:
        spatial_clauses.append("longitude >= ?")
        spatial_params.append(filters.min_lng)
    if filters.max_lng is not None:
        spatial_clauses.append("longitude <= ?")
        spatial_params.append(filters.max_lng)

    if spatial_clauses:
        spatial_subquery = (
            f"assets.site_id IN (SELECT id FROM sites WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND {' AND '.join(spatial_clauses)})"
        )
        clauses.append(spatial_subquery)
        params.extend(spatial_params)

    where_sql = " AND ".join(clauses)
    return where_sql, params, target_date_expr


def query_media_assets(db, filters: MediaQueryFilters) -> PaginatedMediaQueryResponse:
    """Execute multi-dimensional media search with sorting and pagination."""
    where_sql, params, target_date_expr = _build_where_clause(filters)

    # Count total matching rows
    count_sql = f"SELECT COUNT(*) as total FROM assets WHERE {where_sql}"
    total_row = db.execute(count_sql, tuple(params)).fetchone()
    total = total_row["total"] if total_row else 0

    # Determine sort order
    if filters.sort in ("asc", "chronological"):
        order_direction = "ASC"
    else:
        order_direction = "DESC"

    order_sql = f"ORDER BY {target_date_expr} {order_direction}, assets.asset_id {order_direction}"

    # Calculate pagination offset
    offset = (filters.page - 1) * filters.limit
    query_sql = f"SELECT * FROM assets WHERE {where_sql} {order_sql} LIMIT ? OFFSET ?"
    query_params = list(params) + [filters.limit, offset]

    raw_rows = store.rows(db, query_sql, tuple(query_params))
    items = [row_to_media_item(r) for r in raw_rows]

    total_pages = math.ceil(total / filters.limit) if total > 0 else 1

    applied_filters = {
        k: v for k, v in filters.model_dump().items()
        if v is not None and k not in ("page", "limit")
    }

    return PaginatedMediaQueryResponse(
        items=items,
        total=total,
        page=filters.page,
        limit=filters.limit,
        total_pages=total_pages,
        filters=applied_filters,
    )


def query_media_timeline(db, filters: MediaQueryFilters) -> TimelineMediaResponse:
    """Group matching media assets into chronological or reverse-chronological date buckets."""
    where_sql, params, target_date_expr = _build_where_clause(filters)

    if filters.sort in ("asc", "chronological"):
        order_direction = "ASC"
    else:
        order_direction = "DESC"

    order_sql = f"ORDER BY {target_date_expr} {order_direction}, assets.asset_id {order_direction}"
    # Timeline returns all matching records up to a safe bounded batch (e.g. 500)
    query_sql = f"SELECT * FROM assets WHERE {where_sql} {order_sql} LIMIT 500"
    raw_rows = store.rows(db, query_sql, tuple(params))
    items = [row_to_media_item(r) for r in raw_rows]

    # Organize items into buckets by date (YYYY-MM-DD)
    bucket_map: Dict[str, List[MediaItemResponse]] = {}
    for item in items:
        # Determine bucket date
        date_str = "unknown_date"
        anchor = item.captured_at if filters.date_basis == "captured_at" else (item.captured_at or item.created_at)
        if anchor and len(anchor) >= 10:
            date_str = anchor[:10]
        if date_str not in bucket_map:
            bucket_map[date_str] = []
        bucket_map[date_str].append(item)

    buckets = [
        TimelineBucket(date=d, count=len(bucket_items), items=bucket_items)
        for d, bucket_items in bucket_map.items()
    ]

    applied_filters = {
        k: v for k, v in filters.model_dump().items()
        if v is not None and k not in ("page", "limit")
    }

    return TimelineMediaResponse(
        total_items=len(items),
        total_dates=len(buckets),
        filters=applied_filters,
        buckets=buckets,
    )


def get_project_summary(db, project_id: str) -> ProjectSummaryResponse:
    """Retrieve aggregate summary for a specific project."""
    project = store.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    meta = None
    if project.get("metadata_json"):
        try:
            meta = json.loads(project["metadata_json"])
        except Exception:
            pass

    metrics_query = """
    SELECT
        (SELECT COUNT(*) FROM sites WHERE project_id = ?) as site_count,
        (SELECT COUNT(*) FROM assets WHERE project_id = ? OR site_id IN (SELECT id FROM sites WHERE project_id = ?)) as media_count,
        (SELECT COUNT(*) FROM assets WHERE (project_id = ? OR site_id IN (SELECT id FROM sites WHERE project_id = ?)) AND media_type = 'image') as image_count,
        (SELECT COUNT(*) FROM assets WHERE (project_id = ? OR site_id IN (SELECT id FROM sites WHERE project_id = ?)) AND media_type = 'video') as video_count,
        (SELECT MIN(created_at) FROM assets WHERE project_id = ? OR site_id IN (SELECT id FROM sites WHERE project_id = ?)) as earliest_date,
        (SELECT MAX(created_at) FROM assets WHERE project_id = ? OR site_id IN (SELECT id FROM sites WHERE project_id = ?)) as latest_date
    """
    params = (project_id, project_id, project_id, project_id, project_id, project_id, project_id, project_id, project_id, project_id, project_id)
    stats = store.one(db, metrics_query, params) or {}

    return ProjectSummaryResponse(
        project_id=project["id"],
        name=project["name"],
        description=project.get("description") or "",
        created_at=project["created_at"],
        site_count=stats.get("site_count") or 0,
        media_count=stats.get("media_count") or 0,
        image_count=stats.get("image_count") or 0,
        video_count=stats.get("video_count") or 0,
        earliest_date=stats.get("earliest_date"),
        latest_date=stats.get("latest_date"),
        metadata=meta,
    )


def list_project_summaries(db) -> List[ProjectSummaryResponse]:
    """Retrieve summaries for all projects in the workspace."""
    projects = store.list_projects(db)
    return [get_project_summary(db, p["id"]) for p in projects]


def get_site_summary(db, site_id: str) -> SiteSummaryResponse:
    """Retrieve aggregate summary for a specific site."""
    site = store.get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")

    meta = None
    if site.get("metadata_json"):
        try:
            meta = json.loads(site["metadata_json"])
        except Exception:
            pass

    metrics_query = """
    SELECT
        (SELECT COUNT(*) FROM assets WHERE site_id = ?) as media_count,
        (SELECT COUNT(*) FROM assets WHERE site_id = ? AND media_type = 'image') as image_count,
        (SELECT COUNT(*) FROM assets WHERE site_id = ? AND media_type = 'video') as video_count,
        (SELECT MIN(created_at) FROM assets WHERE site_id = ?) as earliest_date,
        (SELECT MAX(created_at) FROM assets WHERE site_id = ?) as latest_date
    """
    stats = store.one(db, metrics_query, (site_id, site_id, site_id, site_id, site_id)) or {}

    return SiteSummaryResponse(
        site_id=site["id"],
        project_id=site.get("project_id"),
        name=site["name"],
        location=site.get("location") or "",
        description=site.get("description") or "",
        latitude=site.get("latitude"),
        longitude=site.get("longitude"),
        created_at=site.get("created_at"),
        media_count=stats.get("media_count") or 0,
        image_count=stats.get("image_count") or 0,
        video_count=stats.get("video_count") or 0,
        earliest_date=stats.get("earliest_date"),
        latest_date=stats.get("latest_date"),
        metadata=meta,
    )


def list_site_summaries(db, project_id: Optional[str] = None) -> List[SiteSummaryResponse]:
    """Retrieve summaries for sites, optionally filtered by project_id."""
    if project_id:
        sites = store.rows(db, "SELECT * FROM sites WHERE project_id = ? ORDER BY name, id", (project_id,))
    else:
        sites = store.rows(db, "SELECT * FROM sites ORDER BY name, id")
    return [get_site_summary(db, s["id"]) for s in sites]
