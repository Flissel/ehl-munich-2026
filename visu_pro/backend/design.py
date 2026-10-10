"""Design proposal schema, validation and conversion to viewer commands.

Change categories (kept deliberately distinct):
  * material_configuration  - existing asset/material configuration (supported now)
  * component_replacement   - swap in an existing 3D component (future; no alternate parts in asset)
  * geometry_modification   - generated/modified editable geometry (future; see geometry/ pipeline)
  * concept_image           - 2D concept image only (never substituted for a 3D change)
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from registry import PAINTS, WHEEL_STYLES, ModelEntry

PaintId = Literal["black", "white", "silver", "racing_red", "midnight_blue"]
WheelStyleId = Literal["standard", "sport"]

assert set(PaintId.__args__) == set(PAINTS), "PaintId literal out of sync with registry"
assert set(WheelStyleId.__args__) == set(WHEEL_STYLES), "WheelStyleId literal out of sync with registry"


class ChangeCategory(str, Enum):
    material_configuration = "material_configuration"
    component_replacement = "component_replacement"
    geometry_modification = "geometry_modification"
    concept_image = "concept_image"
    other = "other"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetPaint(_Strict):
    type: Literal["set_paint"]
    paint_id: PaintId


class SetWheelStyle(_Strict):
    type: Literal["set_wheel_style"]
    style_id: WheelStyleId


class ResetDesign(_Strict):
    type: Literal["reset_design"]


# Plain union (JSON schema "anyOf"): OpenAI strict structured outputs support anyOf, not oneOf.
# Each member has a distinct Literal `type` and extra="forbid", so validation is unambiguous.
DesignAction = Union[SetPaint, SetWheelStyle, ResetDesign]


class UnsupportedRequest(_Strict):
    request: str = Field(description="The part of the user's request that cannot be applied")
    category: ChangeCategory
    reason: str


class DesignProposal(_Strict):
    """What the AI must return. Also accepted from the manual design endpoint."""
    summary: str = Field(description="Short explanation of the proposed design for the user")
    actions: list[DesignAction] = Field(description="Supported actions to apply, in order")
    unsupported: list[UnsupportedRequest] = Field(
        description="Requested changes that are not supported by this MVP and will NOT be applied")


class ValidationIssue(_Strict):
    action: str
    error: str


MAX_ACTIONS = 3


def validate_actions(model: ModelEntry, actions: list[DesignAction]) -> tuple[list[DesignAction], list[ValidationIssue]]:
    """Re-validate actions against the model's allowed options and normalize the order.

    Result order is: reset (if any) -> paint -> wheels; duplicates keep the last occurrence.
    """
    issues: list[ValidationIssue] = []
    reset: ResetDesign | None = None
    paint: SetPaint | None = None
    wheels: SetWheelStyle | None = None
    for a in actions:
        if isinstance(a, ResetDesign):
            reset = a
        elif isinstance(a, SetPaint):
            if a.paint_id not in model.paints:
                issues.append(ValidationIssue(action=a.type, error=f"paint '{a.paint_id}' not available for {model.id}"))
            else:
                paint = a
        elif isinstance(a, SetWheelStyle):
            if a.style_id not in model.wheel_styles:
                issues.append(ValidationIssue(action=a.type, error=f"wheel style '{a.style_id}' not available for {model.id}"))
            else:
                wheels = a
        else:  # pragma: no cover - the discriminated union makes this unreachable
            issues.append(ValidationIssue(action=str(getattr(a, "type", "?")), error="unsupported action"))
    ordered = [x for x in (reset, paint, wheels) if x is not None]
    return ordered[:MAX_ACTIONS], issues


def to_viewer_command(action: DesignAction) -> tuple[str, dict]:
    if isinstance(action, SetPaint):
        return "set_paint", {"paint_id": action.paint_id}
    if isinstance(action, SetWheelStyle):
        return "set_wheel_style", {"style_id": action.style_id}
    if isinstance(action, ResetDesign):
        return "reset_design", {}
    raise ValueError(f"no viewer command for {action!r}")


def describe(action: DesignAction) -> str:
    if isinstance(action, SetPaint):
        return f"Paint: {PAINTS[action.paint_id]}"
    if isinstance(action, SetWheelStyle):
        return f"Wheels: {WHEEL_STYLES[action.style_id]}"
    return "Reset to original design"
