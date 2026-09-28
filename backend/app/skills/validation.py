"""Validation logic for Setowa Skills."""
from typing import Any, Dict, List, Set, Tuple
from app.skills.models import SkillManifest, SkillInputDefinition, SkillOutputDefinition


def validate_manifest(manifest: SkillManifest) -> Tuple[bool, List[str]]:
    """Validate that a SkillManifest is internally consistent and well-formed.
    
    Returns:
        (is_valid, list_of_error_strings)
    """
    errors: List[str] = []

    # Verify input names are unique
    seen_inputs: Set[str] = set()
    for inp in manifest.inputs:
        if inp.name in seen_inputs:
            errors.append(f"Duplicate input parameter name: '{inp.name}'")
        seen_inputs.add(inp.name)

    # Verify output names are unique
    seen_outputs: Set[str] = set()
    for out in manifest.outputs:
        if out.name in seen_outputs:
            errors.append(f"Duplicate output field name: '{out.name}'")
        seen_outputs.add(out.name)

    # Validate permission naming convention (namespace:action, e.g. media:read)
    for perm in manifest.permissions:
        if not isinstance(perm, str) or ":" not in perm or len(perm.split(":")) != 2:
            errors.append(
                f"Invalid permission format '{perm}'. Expected format: 'namespace:action' (e.g. 'media:read')."
            )

    return (len(errors) == 0, errors)


def validate_skill_inputs(
    manifest: SkillManifest,
    inputs: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """Validate runtime inputs against the declared manifest inputs.
    
    Returns:
        (is_valid, list_of_error_strings)
    """
    errors: List[str] = []

    for param in manifest.inputs:
        val = inputs.get(param.name)
        if val is None:
            if param.required and param.default is None:
                errors.append(f"Missing required input parameter: '{param.name}'")
            continue

        # Basic type checking
        expected_type = param.type.lower()
        if expected_type == "string" and not isinstance(val, str):
            errors.append(f"Input '{param.name}' expected string, got {type(val).__name__}")
        elif expected_type == "number" and not isinstance(val, (int, float)):
            errors.append(f"Input '{param.name}' expected number, got {type(val).__name__}")
        elif expected_type == "boolean" and not isinstance(val, bool):
            errors.append(f"Input '{param.name}' expected boolean, got {type(val).__name__}")
        elif expected_type == "object" and not isinstance(val, dict):
            errors.append(f"Input '{param.name}' expected object/dict, got {type(val).__name__}")
        elif expected_type == "array" and not isinstance(val, (list, tuple)):
            errors.append(f"Input '{param.name}' expected array/list, got {type(val).__name__}")

    return (len(errors) == 0, errors)


def validate_permissions(
    manifest: SkillManifest,
    execution_context: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """Validate that execution context satisfies all declared skill permissions.
    
    If context provides 'granted_permissions', every permission declared in
    manifest.permissions must be included in granted_permissions.
    If 'granted_permissions' is absent from context, permissions are granted by default
    unless 'strict_permissions' flag is enabled in execution_context.
    
    Returns:
        (is_valid, list_of_error_strings)
    """
    errors: List[str] = []
    required_perms = manifest.permissions
    if not required_perms:
        return (True, [])

    granted = execution_context.get("granted_permissions")
    if granted is not None:
        if isinstance(granted, (list, set, tuple)):
            granted_set = set(granted)
            missing = [p for p in required_perms if p not in granted_set]
            if missing:
                errors.append(f"Permission denied. Missing required permissions: {', '.join(missing)}")
        else:
            errors.append("Invalid 'granted_permissions' in context: expected a list of permission strings.")
    elif execution_context.get("strict_permissions", False):
        errors.append(
            f"Strict mode active: no permissions granted in context, but skill requires: {', '.join(required_perms)}"
        )

    return (len(errors) == 0, errors)
