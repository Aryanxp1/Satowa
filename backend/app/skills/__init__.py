"""Setowa Skill System Package."""
from typing import Optional
from app.skills.models import (
    SkillManifest,
    SkillInputDefinition,
    SkillOutputDefinition,
    SkillExecutionStatus,
    SkillExecutionRequest,
    SkillExecutionResult,
)
from app.skills.loader import BaseSkill
from app.skills.registry import SkillRegistry
from app.skills.runtime import SkillRuntime
from app.skills.validation import (
    validate_manifest,
    validate_skill_inputs,
    validate_permissions,
)
from app.skills.builtins import (
    register_builtins,
    MediaMetadataSkill,
    EvidenceComparisonSkill,
    FieldFrameObservationSkill,
    MediaIntelligenceSkill,
)

_default_registry: Optional[SkillRegistry] = None
_default_runtime: Optional[SkillRuntime] = None


def get_default_registry() -> SkillRegistry:
    """Get or initialize the shared global SkillRegistry populated with built-in skills."""
    global _default_registry
    if _default_registry is None:
        _default_registry = SkillRegistry()
        register_builtins(_default_registry)
    return _default_registry


def get_default_runtime() -> SkillRuntime:
    """Get or initialize the shared global SkillRuntime backed by the default registry."""
    global _default_runtime
    if _default_runtime is None:
        _default_runtime = SkillRuntime(get_default_registry())
    return _default_runtime


__all__ = [
    "SkillManifest",
    "SkillInputDefinition",
    "SkillOutputDefinition",
    "SkillExecutionStatus",
    "SkillExecutionRequest",
    "SkillExecutionResult",
    "BaseSkill",
    "SkillRegistry",
    "SkillRuntime",
    "validate_manifest",
    "validate_skill_inputs",
    "validate_permissions",
    "get_default_registry",
    "get_default_runtime",
    "MediaMetadataSkill",
    "EvidenceComparisonSkill",
    "FieldFrameObservationSkill",
    "MediaIntelligenceSkill",
]


