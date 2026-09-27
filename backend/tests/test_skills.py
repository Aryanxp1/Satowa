"""Focused test suite for Setowa Skill Runtime (Milestone T012)."""
import asyncio
from typing import Any, Dict
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.main import app
from app.skills import (
    BaseSkill,
    SkillExecutionRequest,
    SkillExecutionResult,
    SkillExecutionStatus,
    SkillInputDefinition,
    SkillManifest,
    SkillOutputDefinition,
    SkillRegistry,
    SkillRuntime,
    validate_manifest,
    validate_permissions,
    validate_skill_inputs,
    get_default_registry,
    get_default_runtime,
)
from app.skills.builtins import MediaMetadataSkill, EvidenceComparisonSkill

client = TestClient(app)


# Mock helper skill for unit testing
class EchoSkill(BaseSkill):
    """Simple test skill that echoes inputs."""
    def __init__(self, name: str = "echo-tool", version: str = "1.0.0", permissions=None):
        manifest = SkillManifest(
            name=name,
            version=version,
            description="Echo test skill for runtime validation.",
            kind="deterministic",
            permissions=permissions or ["media:read"],
            inputs=[
                SkillInputDefinition(name="message", type="string", description="Text to echo", required=True),
                SkillInputDefinition(name="count", type="number", description="Multiplier", required=False, default=1),
            ],
            outputs=[
                SkillOutputDefinition(name="echoed", type="string", description="Echoed output"),
            ],
        )
        super().__init__(manifest)

    async def execute(self, inputs: Dict[str, Any], context: Dict[str, Any]) -> SkillExecutionResult:
        msg = inputs.get("message", "")
        count = int(inputs.get("count") or 1)
        return SkillExecutionResult(
            skill_name=self.name,
            skill_version=self.version,
            status=SkillExecutionStatus.SUCCESS,
            outputs={"echoed": msg * count},
            evidence={"context_user": context.get("user_id")},
            metadata={"test_mode": True},
        )


class CrashingSkill(BaseSkill):
    """Skill that raises an unexpected exception during execution."""
    def __init__(self):
        manifest = SkillManifest(
            name="crash-tool",
            version="1.0.0",
            description="Intentionally buggy skill for error-handling tests.",
            kind="deterministic",
            inputs=[],
            outputs=[],
        )
        super().__init__(manifest)

    async def execute(self, inputs: Dict[str, Any], context: Dict[str, Any]) -> SkillExecutionResult:
        raise RuntimeError("Simulated internal runtime error in skill implementation")


# -----------------------------------------------------------------------------
# 1. Valid Manifest
# -----------------------------------------------------------------------------
def test_valid_manifest():
    manifest = SkillManifest(
        name="tree-risk",
        version="1.0.0",
        description="Assess visible tree-fall risk from field media.",
        kind="visual-analysis",
        inputs=[
            SkillInputDefinition(name="image_url", type="string", description="Field photo"),
            SkillInputDefinition(name="location", type="string", required=False),
        ],
        outputs=[
            SkillOutputDefinition(name="risk_level", type="string"),
            SkillOutputDefinition(name="confidence", type="number"),
        ],
        permissions=["media:read", "ai:inference"],
    )
    is_valid, errors = validate_manifest(manifest)
    assert is_valid is True
    assert errors == []
    assert manifest.full_id == "tree-risk@1.0.0"


# -----------------------------------------------------------------------------
# 2. Invalid Manifest (bad name, bad version, duplicates, bad perm)
# -----------------------------------------------------------------------------
def test_invalid_manifest_rejections():
    # Bad name
    with pytest.raises(ValidationError):
        SkillManifest(name="UPPER_CASE_INVALID", version="1.0.0", description="desc")

    # Bad semver
    with pytest.raises(ValidationError):
        SkillManifest(name="valid-name", version="not-a-semver", description="desc")

    # Duplicate inputs and bad perm format
    dup_manifest = SkillManifest(
        name="dup-inputs",
        version="1.0.0",
        description="desc",
        inputs=[
            SkillInputDefinition(name="param1", type="string"),
            SkillInputDefinition(name="param1", type="string"),
        ],
        permissions=["invalid_perm_format_without_colon"],
    )
    is_valid, errors = validate_manifest(dup_manifest)
    assert is_valid is False
    assert any("Duplicate input parameter name: 'param1'" in e for e in errors)
    assert any("Invalid permission format" in e for e in errors)


# -----------------------------------------------------------------------------
# 3. Skill Registration
# -----------------------------------------------------------------------------
def test_skill_registration():
    registry = SkillRegistry()
    skill = EchoSkill()
    registered_manifest = registry.register(skill)
    assert registered_manifest.name == "echo-tool"
    assert registry.has_skill("echo-tool")
    assert registry.get("echo-tool") is skill


# -----------------------------------------------------------------------------
# 4. Duplicate Registration
# -----------------------------------------------------------------------------
def test_duplicate_registration_prevention():
    registry = SkillRegistry()
    skill1 = EchoSkill(name="echo-tool", version="1.0.0")
    skill2 = EchoSkill(name="echo-tool", version="1.0.0")

    registry.register(skill1)
    # Attempt duplicate without overwrite
    with pytest.raises(ValueError) as excinfo:
        registry.register(skill2, overwrite=False)
    assert "already registered" in str(excinfo.value)

    # Overwrite succeeds
    registry.register(skill2, overwrite=True)
    assert registry.get("echo-tool", "1.0.0") is skill2


# -----------------------------------------------------------------------------
# 5. Skill Discovery & Filtering
# -----------------------------------------------------------------------------
def test_skill_discovery_and_filtering():
    registry = SkillRegistry()
    registry.register(EchoSkill(name="echo-a", version="1.0.0"))
    registry.register(EchoSkill(name="echo-a", version="1.1.0"))
    registry.register(MediaMetadataSkill(version="1.0.0"))

    # Latest only
    latest_list = registry.list_skills(include_all_versions=False)
    assert len(latest_list) == 2
    echo_a = next(s for s in latest_list if s.name == "echo-a")
    assert echo_a.version == "1.1.0"

    # All versions
    all_list = registry.list_skills(include_all_versions=True)
    assert len(all_list) == 3

    # Filter by kind
    det_list = registry.list_skills(kind="deterministic")
    assert len(det_list) == 2


# -----------------------------------------------------------------------------
# 6. Version Resolution
# -----------------------------------------------------------------------------
def test_version_resolution():
    registry = SkillRegistry()
    registry.register(EchoSkill(name="my-tool", version="1.0.0"))
    registry.register(EchoSkill(name="my-tool", version="1.2.0"))
    registry.register(EchoSkill(name="my-tool", version="1.10.0"))
    registry.register(EchoSkill(name="my-tool", version="2.0.0"))

    # Resolve latest without version arg
    latest = registry.get("my-tool")
    assert latest.version == "2.0.0"

    # Resolve exact version
    v120 = registry.get("my-tool", "1.2.0")
    assert v120.version == "1.2.0"

    v110 = registry.get_by_id("my-tool@1.10.0")
    assert v110.version == "1.10.0"

    # Non-existent version
    assert registry.get("my-tool", "9.9.9") is None


# -----------------------------------------------------------------------------
# 7. Invalid Skill Input
# -----------------------------------------------------------------------------
def test_invalid_skill_input_validation():
    registry = SkillRegistry()
    registry.register(EchoSkill())
    runtime = SkillRuntime(registry)

    # Missing mandatory "message"
    req_missing = SkillExecutionRequest(skill_name="echo-tool", inputs={})
    res_missing = asyncio.run(runtime.execute(req_missing))
    assert res_missing.status == SkillExecutionStatus.INVALID_INPUT
    assert any("Missing required input parameter: 'message'" in e for e in res_missing.errors)

    # Invalid type for "count"
    req_bad_type = SkillExecutionRequest(
        skill_name="echo-tool",
        inputs={"message": "hello", "count": "not-a-number"}
    )
    res_bad_type = asyncio.run(runtime.execute(req_bad_type))
    assert res_bad_type.status == SkillExecutionStatus.INVALID_INPUT
    assert any("expected number" in e for e in res_bad_type.errors)


# -----------------------------------------------------------------------------
# 8. Successful Execution
# -----------------------------------------------------------------------------
def test_successful_skill_execution():
    registry = SkillRegistry()
    registry.register(EchoSkill())
    runtime = SkillRuntime(registry)

    req = SkillExecutionRequest(
        skill_name="echo-tool",
        inputs={"message": "Ping! ", "count": 3},
        execution_context={"user_id": "test-analyst"},
    )
    res = asyncio.run(runtime.execute(req))
    assert res.status == SkillExecutionStatus.SUCCESS
    assert res.outputs == {"echoed": "Ping! Ping! Ping! "}
    assert res.evidence["context_user"] == "test-analyst"
    assert "latency_ms" in res.metadata
    assert res.metadata["latency_ms"] >= 0.0


# -----------------------------------------------------------------------------
# 9. Failed Execution
# -----------------------------------------------------------------------------
def test_failed_execution_error_boundary():
    registry = SkillRegistry()
    registry.register(CrashingSkill())
    runtime = SkillRuntime(registry)

    req = SkillExecutionRequest(skill_name="crash-tool", inputs={})
    res = asyncio.run(runtime.execute(req))
    assert res.status == SkillExecutionStatus.FAILED
    assert len(res.errors) > 0
    assert "Simulated internal runtime error" in res.errors[0]
    assert res.metadata.get("exception_type") == "RuntimeError"


# -----------------------------------------------------------------------------
# 10. Unavailable Dependency or Skill
# -----------------------------------------------------------------------------
def test_unavailable_skill_or_dependency():
    registry = SkillRegistry()
    runtime = SkillRuntime(registry)

    # Skill not registered
    req = SkillExecutionRequest(skill_name="non-existent-skill", skill_version="1.0.0")
    res = asyncio.run(runtime.execute(req))
    assert res.status == SkillExecutionStatus.UNAVAILABLE
    assert any("unavailable or not registered" in e for e in res.errors)


# -----------------------------------------------------------------------------
# 11. Permission Validation
# -----------------------------------------------------------------------------
def test_permission_validation():
    registry = SkillRegistry()
    registry.register(EchoSkill(permissions=["media:read", "ai:inference"]))
    runtime = SkillRuntime(registry)

    # Satisfied permissions
    req_allowed = SkillExecutionRequest(
        skill_name="echo-tool",
        inputs={"message": "ok"},
        execution_context={"granted_permissions": ["media:read", "ai:inference", "other:perm"]},
    )
    res_allowed = asyncio.run(runtime.execute(req_allowed))
    assert res_allowed.status == SkillExecutionStatus.SUCCESS

    # Missing required permission
    req_denied = SkillExecutionRequest(
        skill_name="echo-tool",
        inputs={"message": "ok"},
        execution_context={"granted_permissions": ["media:read"]},
    )
    res_denied = asyncio.run(runtime.execute(req_denied))
    assert res_denied.status == SkillExecutionStatus.INVALID_INPUT
    assert any("Missing required permissions: ai:inference" in e for e in res_denied.errors)


# -----------------------------------------------------------------------------
# 12. API Listing Endpoint
# -----------------------------------------------------------------------------
def test_api_skills_listing():
    res = client.get("/api/v1/skills")
    assert res.status_code == 200
    skills = res.json()
    assert isinstance(skills, list)
    names = [s["name"] for s in skills]
    assert "media-metadata" in names
    assert "evidence-comparison" in names


# -----------------------------------------------------------------------------
# 13. API Get & Execution Endpoints
# -----------------------------------------------------------------------------
def test_api_skill_detail_and_execution():
    # 1. Detail endpoint
    detail_res = client.get("/api/v1/skills/media-metadata")
    assert detail_res.status_code == 200
    manifest = detail_res.json()
    assert manifest["name"] == "media-metadata"
    assert manifest["kind"] == "deterministic"

    # Detail 404 for unknown skill
    detail_404 = client.get("/api/v1/skills/unknown-skill-xyz")
    assert detail_404.status_code == 404

    # 2. Execution endpoint
    exec_payload = {
        "inputs": {
            "url": "https://res.cloudinary.com/test-cloud/image/upload/v1/sample.jpg"
        },
        "execution_context": {}
    }
    exec_res = client.post("/api/v1/skills/media-metadata/execute", json=exec_payload)
    assert exec_res.status_code == 200
    result = exec_res.json()
    assert result["status"] == "success"
    assert result["outputs"]["format"] == "jpg"
    assert result["outputs"]["media_type"] == "image"

    # Execute 404 for unknown skill
    exec_404 = client.post("/api/v1/skills/unknown-skill-xyz/execute", json={"inputs": {}})
    assert exec_404.status_code == 404


# -----------------------------------------------------------------------------
# 14. Built-in Skill Behavior (media-metadata & evidence-comparison)
# -----------------------------------------------------------------------------
def test_builtin_media_metadata_skill():
    skill = MediaMetadataSkill(version="1.0.0")

    # With video URL
    res = asyncio.run(skill.execute(
        inputs={"url": "https://res.cloudinary.com/demo/video/upload/river_sweep.mp4"},
        context={}
    ))
    assert res.status == SkillExecutionStatus.SUCCESS
    assert res.outputs["media_type"] == "video"
    assert res.outputs["format"] == "mp4"

    # With raw media dictionary
    res_dict = asyncio.run(skill.execute(
        inputs={
            "media": {
                "media_type": "image",
                "format": "webp",
                "width": 1920,
                "height": 1080,
                "secure_url": "https://res.cloudinary.com/demo/image/upload/clean.webp",
                "thumbnail_url": "https://res.cloudinary.com/demo/image/upload/c_thumb/clean.webp",
            }
        },
        context={}
    ))
    assert res_dict.status == SkillExecutionStatus.SUCCESS
    assert res_dict.outputs["format"] == "webp"
    assert res_dict.outputs["dimensions"] == {"width": 1920, "height": 1080}

    # Empty inputs invalid
    res_empty = asyncio.run(skill.execute(inputs={}, context={}))
    assert res_empty.status == SkillExecutionStatus.INVALID_INPUT


def test_builtin_evidence_comparison_skill():
    skill = EvidenceComparisonSkill(version="1.0.0")

    # Missing inputs
    res_missing = asyncio.run(skill.execute(inputs={"before_url": "http://example.com/1.jpg"}, context={}))
    assert res_missing.status == SkillExecutionStatus.INVALID_INPUT

    # With mock comparison inputs
    res = asyncio.run(skill.execute(
        inputs={
            "before_url": "https://res.cloudinary.com/demo/image/upload/before.jpg",
            "after_url": "https://res.cloudinary.com/demo/image/upload/after.jpg",
        },
        context={}
    ))
    assert res.status == SkillExecutionStatus.SUCCESS
    assert "status" in res.outputs
    # Confidence is bounded and disclaimed
    assert "confidence_disclaimer" in res.metadata
