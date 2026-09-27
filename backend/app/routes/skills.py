"""API routes for Setowa Skills."""
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.skills import (
    SkillExecutionRequest,
    SkillExecutionResult,
    SkillManifest,
    get_default_registry,
    get_default_runtime,
)

logger = logging.getLogger("setowa.routes.skills")

router = APIRouter(prefix="/api/v1/skills", tags=["Skills"])


@router.get("", response_model=List[SkillManifest])
async def list_skills(
    include_all_versions: bool = Query(
        default=False,
        description="Whether to include older registered versions of skills"
    ),
    kind: Optional[str] = Query(
        default=None,
        description="Filter by skill kind (e.g. deterministic, visual-analysis)"
    ),
):
    """List registered Setowa Skills with manifests, inputs, outputs, and permissions."""
    registry = get_default_registry()
    return registry.list_skills(include_all_versions=include_all_versions, kind=kind)


@router.get("/{skill_name}", response_model=SkillManifest)
async def get_skill(
    skill_name: str,
    version: Optional[str] = Query(
        default=None,
        description="Exact semver version to inspect, or None for latest"
    ),
):
    """Retrieve detailed specification and manifest for a specific skill."""
    registry = get_default_registry()
    skill = registry.get(skill_name, version=version)
    if not skill:
        version_str = f"@{version}" if version else ""
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{skill_name}{version_str}' not found in registry."
        )
    return skill.manifest


@router.post("/{skill_name}/execute", response_model=SkillExecutionResult)
async def execute_skill(
    skill_name: str,
    payload: Optional[SkillExecutionRequest] = None,
):
    """Execute a Setowa Skill with validated inputs and context."""
    registry = get_default_registry()
    if not registry.has_skill(skill_name):
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{skill_name}' not found in registry."
        )

    runtime = get_default_runtime()
    req = payload or SkillExecutionRequest(skill_name=skill_name)
    # Ensure skill_name matches route path
    req.skill_name = skill_name

    result = await runtime.execute(req)
    return result
