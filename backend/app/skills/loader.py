"""Skill loader and base class definitions."""
from abc import ABC, abstractmethod
from typing import Any, Dict
from app.skills.models import SkillManifest, SkillExecutionResult


class BaseSkill(ABC):
    """Abstract base class for all executable Setowa Skills."""

    def __init__(self, manifest: SkillManifest):
        self.manifest = manifest

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def version(self) -> str:
        return self.manifest.version

    @property
    def full_id(self) -> str:
        return self.manifest.full_id

    @abstractmethod
    async def execute(
        self,
        inputs: Dict[str, Any],
        context: Dict[str, Any]
    ) -> SkillExecutionResult:
        """Execute the skill logic against validated inputs.
        
        Args:
            inputs: Dictionary of validated input values.
            context: Runtime execution context (user_id, site_id, auth, etc.)
            
        Returns:
            SkillExecutionResult with status and outputs.
        """
        raise NotImplementedError
