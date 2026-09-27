"""Skill runtime executor enforcing contracts, permissions, and safe error handling."""
import logging
import time
from typing import Any, Dict, Optional
from app.skills.models import (
    SkillExecutionRequest,
    SkillExecutionResult,
    SkillExecutionStatus,
)
from app.skills.registry import SkillRegistry
from app.skills.validation import validate_permissions, validate_skill_inputs

logger = logging.getLogger("setowa.skills.runtime")


class SkillRuntime:
    """Authoritative runtime orchestrating skill invocation, validation, and error boundaries."""

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    async def execute(self, request: SkillExecutionRequest) -> SkillExecutionResult:
        """Execute a skill with contract validation, telemetry, and error safety.
        
        Guarantees:
        - Never raises uncaught exceptions to caller.
        - Predictable 4-state lifecycle status (success, failed, invalid_input, unavailable).
        - Explicit diagnostic error messages without raw secret leakage.
        """
        start_time = time.perf_counter()
        skill_name = request.skill_name
        skill_version = request.skill_version

        # 1. Resolve skill from registry
        skill = self.registry.get(skill_name, skill_version)
        if not skill:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            version_str = f"@{skill_version}" if skill_version else ""
            error_msg = f"Skill '{skill_name}{version_str}' is unavailable or not registered."
            logger.warning(error_msg)
            return SkillExecutionResult(
                skill_name=skill_name,
                skill_version=skill_version or "unknown",
                status=SkillExecutionStatus.UNAVAILABLE,
                outputs={},
                errors=[error_msg],
                metadata={"latency_ms": latency_ms},
            )

        resolved_version = skill.version

        # 2. Permission validation
        perms_valid, perm_errors = validate_permissions(skill.manifest, request.execution_context)
        if not perms_valid:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning(f"Permission validation failed for {skill.full_id}: {perm_errors}")
            return SkillExecutionResult(
                skill_name=skill_name,
                skill_version=resolved_version,
                status=SkillExecutionStatus.INVALID_INPUT,
                outputs={},
                errors=perm_errors,
                metadata={"latency_ms": latency_ms, "permission_error": True},
            )

        # 3. Input contract validation
        inputs_valid, input_errors = validate_skill_inputs(skill.manifest, request.inputs)
        if not inputs_valid:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning(f"Input validation failed for {skill.full_id}: {input_errors}")
            return SkillExecutionResult(
                skill_name=skill_name,
                skill_version=resolved_version,
                status=SkillExecutionStatus.INVALID_INPUT,
                outputs={},
                errors=input_errors,
                metadata={"latency_ms": latency_ms},
            )

        # 4. Invoke skill execution within safe error boundary
        try:
            result = await skill.execute(request.inputs, request.execution_context)
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            # Ensure runtime metadata is attached
            result.metadata.setdefault("latency_ms", latency_ms)
            result.metadata.setdefault("skill_id", skill.full_id)
            return result
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(f"Unhandled error executing skill {skill.full_id}: {exc}")
            return SkillExecutionResult(
                skill_name=skill_name,
                skill_version=resolved_version,
                status=SkillExecutionStatus.FAILED,
                outputs={},
                errors=[f"Skill execution failed: {type(exc).__name__} - {str(exc)}"],
                metadata={"latency_ms": latency_ms, "exception_type": type(exc).__name__},
            )
