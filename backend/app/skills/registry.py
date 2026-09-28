"""In-memory and discoverable registry for Setowa Skills."""
import logging
from typing import Dict, List, Optional, Tuple
from app.skills.loader import BaseSkill
from app.skills.models import SkillManifest
from app.skills.validation import validate_manifest

logger = logging.getLogger("setowa.skills.registry")


def _parse_semver_key(v: str) -> Tuple[int, int, int, str]:
    """Parse semver string for deterministic comparison (major, minor, patch, prerelease)."""
    try:
        parts = v.split("-", 1)
        core = parts[0]
        prerelease = parts[1] if len(parts) > 1 else ""
        major, minor, patch = (int(x) for x in core.split("."))
        # Empty prerelease sorts higher than any prerelease tag in semver (e.g. 1.0.0 > 1.0.0-rc1)
        prerelease_weight = "z" if not prerelease else prerelease
        return (major, minor, patch, prerelease_weight)
    except Exception:
        return (0, 0, 0, v)


class SkillRegistry:
    """Registry maintaining registered Setowa Skills, supporting multiple versions."""

    def __init__(self):
        # Maps skill_name -> {version_str: BaseSkill}
        self._skills: Dict[str, Dict[str, BaseSkill]] = {}

    def register(self, skill: BaseSkill, overwrite: bool = False) -> SkillManifest:
        """Register a skill implementation.
        
        Raises:
            ValueError: If manifest is invalid or skill version is already registered and overwrite is False.
        """
        is_valid, errors = validate_manifest(skill.manifest)
        if not is_valid:
            raise ValueError(f"Invalid skill manifest for '{skill.name}': {'; '.join(errors)}")

        name = skill.name
        version = skill.version

        if name in self._skills and version in self._skills[name] and not overwrite:
            raise ValueError(
                f"Skill '{name}' at version '{version}' is already registered. Set overwrite=True to update."
            )

        if name not in self._skills:
            self._skills[name] = {}

        self._skills[name][version] = skill
        logger.info(f"Registered skill {skill.full_id}")
        return skill.manifest

    def unregister(self, name: str, version: Optional[str] = None) -> bool:
        """Unregister a specific version or all versions of a skill.
        
        Returns:
            True if removed, False if not found.
        """
        if name not in self._skills:
            return False

        if version is not None:
            if version in self._skills[name]:
                del self._skills[name][version]
                if not self._skills[name]:
                    del self._skills[name]
                logger.info(f"Unregistered skill {name}@{version}")
                return True
            return False
        else:
            del self._skills[name]
            logger.info(f"Unregistered all versions of skill '{name}'")
            return True

    def get(self, name: str, version: Optional[str] = None) -> Optional[BaseSkill]:
        """Resolve a skill by name and optional version.
        
        If version is omitted, returns the highest semantic version available.
        """
        if name not in self._skills or not self._skills[name]:
            return None

        versions = self._skills[name]
        if version is not None:
            return versions.get(version)

        # Resolve latest version
        sorted_versions = sorted(versions.keys(), key=_parse_semver_key, reverse=True)
        return versions[sorted_versions[0]]

    def get_by_id(self, full_id: str) -> Optional[BaseSkill]:
        """Resolve a skill by 'name@version' identifier."""
        if "@" in full_id:
            name, version = full_id.split("@", 1)
            return self.get(name, version)
        return self.get(full_id)

    def has_skill(self, name: str, version: Optional[str] = None) -> bool:
        """Check whether a skill exists in the registry."""
        return self.get(name, version) is not None

    def list_skills(self, include_all_versions: bool = False, kind: Optional[str] = None) -> List[SkillManifest]:
        """List registered skills.
        
        Args:
            include_all_versions: If False, returns only the latest version of each skill.
            kind: Optional filter by skill kind.
        """
        results: List[SkillManifest] = []

        for name, versions in self._skills.items():
            if not versions:
                continue

            if include_all_versions:
                for skill in versions.values():
                    if kind is None or skill.manifest.kind == kind:
                        results.append(skill.manifest)
            else:
                latest_skill = self.get(name)
                if latest_skill and (kind is None or latest_skill.manifest.kind == kind):
                    results.append(latest_skill.manifest)

        # Sort alphabetically by name
        results.sort(key=lambda m: (m.name, _parse_semver_key(m.version)))
        return results

    def clear(self) -> None:
        """Clear all registered skills (useful for testing)."""
        self._skills.clear()
