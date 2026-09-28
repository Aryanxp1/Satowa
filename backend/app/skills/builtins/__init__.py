from app.skills.builtins.media_metadata import MediaMetadataSkill
from app.skills.builtins.evidence_comparison import EvidenceComparisonSkill
from app.skills.builtins.field_frame_observation import FieldFrameObservationSkill
from app.skills.builtins.media_intelligence import MediaIntelligenceSkill
from app.skills.registry import SkillRegistry


def register_builtins(registry: SkillRegistry) -> SkillRegistry:
    """Register all standard built-in Setowa skills into the target registry."""
    registry.register(MediaMetadataSkill(version="1.0.0"), overwrite=True)
    registry.register(EvidenceComparisonSkill(version="1.0.0"), overwrite=True)
    registry.register(FieldFrameObservationSkill(version="1.0.0"), overwrite=True)
    registry.register(MediaIntelligenceSkill(version="1.0.0"), overwrite=True)
    return registry


__all__ = [
    "MediaMetadataSkill",
    "EvidenceComparisonSkill",
    "FieldFrameObservationSkill",
    "MediaIntelligenceSkill",
    "register_builtins",
]


