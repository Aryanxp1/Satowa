"""Setowa Skill Specification and Runtime Models."""
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator
import re

# Semantic version regex (MAJOR.MINOR.PATCH with optional pre-release)
SEMVER_REGEX = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$")
SKILL_NAME_REGEX = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


class SkillInputDefinition(BaseModel):
    """Specification for an expected skill input parameter."""
    name: str = Field(..., description="Unique parameter name within the skill")
    type: str = Field(..., description="Data type: string, number, boolean, object, array, media, asset_id")
    description: Optional[str] = Field(default=None, description="Human-readable explanation of input purpose")
    required: bool = Field(default=True, description="Whether this input parameter is mandatory")
    default: Optional[Any] = Field(default=None, description="Default value if not provided")


class SkillOutputDefinition(BaseModel):
    """Specification for a declared skill output field."""
    name: str = Field(..., description="Unique output field name")
    type: str = Field(..., description="Data type: string, number, boolean, object, array")
    description: Optional[str] = Field(default=None, description="Human-readable explanation of output field")


class SkillManifest(BaseModel):
    """Declarative specification for a versioned Setowa Skill."""
    name: str = Field(..., description="Machine-readable name, lowercase alphanumeric with dashes/underscores")
    version: str = Field(..., description="Semantic version string (e.g. 1.0.0)")
    description: str = Field(..., description="Concise explanation of skill capability and purpose")
    kind: str = Field(default="visual-analysis", description="Category: visual-analysis, deterministic, media-intelligence")
    inputs: List[SkillInputDefinition] = Field(default_factory=list, description="Declared input schema")
    outputs: List[SkillOutputDefinition] = Field(default_factory=list, description="Declared output schema")
    requires: Dict[str, Any] = Field(default_factory=dict, description="Execution requirements or dependencies")
    permissions: List[str] = Field(default_factory=list, description="Declared permissions: media:read, ai:inference, etc.")
    model: Optional[Dict[str, Any]] = Field(default=None, description="Model/provider configuration if AI-backed")
    entrypoint: Optional[str] = Field(default=None, description="Executable class or callable identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional author, tags, or documentation links")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not SKILL_NAME_REGEX.match(v):
            raise ValueError(
                f"Invalid skill name '{v}'. Must be lowercase alphanumeric, 2-64 characters, with dashes/underscores."
            )
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if not SEMVER_REGEX.match(v):
            raise ValueError(f"Invalid semver version '{v}'. Must follow standard semver (e.g. 1.0.0).")
        return v

    @property
    def full_id(self) -> str:
        """Fully-qualified skill identifier (e.g. tree-risk@1.0.0)."""
        return f"{self.name}@{self.version}"


class SkillExecutionStatus(str, Enum):
    """4-state status for skill execution lifecycle."""
    SUCCESS = "success"
    FAILED = "failed"
    INVALID_INPUT = "invalid_input"
    UNAVAILABLE = "unavailable"


class SkillExecutionRequest(BaseModel):
    """Request contract for executing a Setowa Skill."""
    skill_name: Optional[str] = Field(default=None, description="Name of the skill to execute")
    skill_version: Optional[str] = Field(default=None, description="Exact semver version, or None for latest")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Typed inputs mapped by name")
    execution_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Context flags (user_id, granted_permissions, site_id, etc.)"
    )


class SkillExecutionResult(BaseModel):
    """Predictable output contract for skill execution."""
    skill_name: str
    skill_version: str
    status: SkillExecutionStatus = Field(..., description="Execution outcome: success, failed, invalid_input, unavailable")
    outputs: Dict[str, Any] = Field(default_factory=dict, description="Structured outputs conforming to manifest")
    evidence: Optional[Dict[str, Any]] = Field(default=None, description="Traceable evidence records or references")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal operational warnings")
    errors: List[str] = Field(default_factory=list, description="Diagnostic errors when failed or invalid")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution telemetry: latency_ms, provider, timestamp")
