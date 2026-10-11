"""Design actions for the web viewer.

Level 1 - appearance: any color + finish on the body paint, on all wheels or on one component.
Level 2 - shape: bounded parametric adjustments of EXISTING parts (scale, move, hide, ride height,
          wheel size, track width). These are real 3D transforms of the model's meshes, not newly
          generated geometry; freeform redesign (e.g. sculpting a new bumper) stays unsupported.

The AI only chooses action types, component ids and numbers. Every value is validated and clamped
on the server, and component ids must come from the model's component list.
"""
from __future__ import annotations

import re
from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from design import ChangeCategory

Finish = Literal["gloss", "metallic", "matte", "satin", "chrome", "carbon"]
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class _S(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetBodyColor(_S):
    type: Literal["set_body_color"]
    color_hex: str = Field(description="#RRGGBB")
    finish: Finish


class SetWheelColor(_S):
    type: Literal["set_wheel_color"]
    color_hex: str = Field(description="#RRGGBB")
    finish: Finish


class SetComponentColor(_S):
    type: Literal["set_component_color"]
    component_id: str
    color_hex: str = Field(description="#RRGGBB")
    finish: Finish


class ScaleComponent(_S):
    type: Literal["scale_component"]
    component_id: str
    factor_x: float = Field(description="width factor 0.7-1.5 (1 = unchanged)")
    factor_y: float = Field(description="height factor 0.7-1.5")
    factor_z: float = Field(description="length factor 0.7-1.5")


class MoveComponent(_S):
    type: Literal["move_component"]
    component_id: str
    dx_cm: float = Field(description="towards the car's left (+) / right (-), -15..15")
    dy_cm: float = Field(description="up (+) / down (-), -15..15")
    dz_cm: float = Field(description="forward (+) / backward (-), -15..15")


class HideComponent(_S):
    type: Literal["hide_component"]
    component_id: str
    hidden: bool


class SetRideHeight(_S):
    type: Literal["set_ride_height"]
    offset_cm: float = Field(description="-6..6, negative = lower")


class SetWheelSize(_S):
    type: Literal["set_wheel_size"]
    delta_inches: float = Field(description="-1..3, relative to the stock wheels")


class SetTrackWidth(_S):
    type: Literal["set_track_width"]
    offset_cm: float = Field(description="0..8 per side, pushes wheels outward")


class SetBodyProportions(_S):
    type: Literal["set_body_proportions"]
    front_overhang_cm: float = Field(description="longer (+) / shorter (-) nose, -10..30, 0 = unchanged")
    rear_overhang_cm: float = Field(description="longer (+) / shorter (-) tail, -10..30")
    wheelbase_cm: float = Field(description="longer (+) / shorter (-) wheelbase, -10..30")
    body_width_cm: float = Field(description="wider body per side, 0..10")
    fender_flare_cm: float = Field(description="wide-body fender flares per side, 0..10")
    roof_height_cm: float = Field(description="roof up (+) / chopped (-), -8..6")


class ResetWebDesign(_S):
    type: Literal["reset_design"]


WebAction = Union[SetBodyColor, SetWheelColor, SetComponentColor, ScaleComponent, MoveComponent,
                  HideComponent, SetRideHeight, SetWheelSize, SetTrackWidth, SetBodyProportions, ResetWebDesign]


class WebUnsupported(_S):
    request: str
    category: ChangeCategory
    reason: str


class WebDesignProposal(_S):
    summary: str = Field(description="1-3 sentences describing exactly what will change")
    actions: list[WebAction]
    unsupported: list[WebUnsupported]


LIMITS = {
    "factor": (0.7, 1.5), "move": (-15.0, 15.0), "ride": (-6.0, 6.0), "wheel": (-1.0, 3.0), "track": (0.0, 8.0),
    "front_overhang_cm": (-10.0, 30.0), "rear_overhang_cm": (-10.0, 30.0), "wheelbase_cm": (-10.0, 30.0),
    "body_width_cm": (0.0, 10.0), "fender_flare_cm": (0.0, 10.0), "roof_height_cm": (-8.0, 6.0),
}


def _clamp(v: float, key: str, notes: list[str], label: str) -> float:
    lo, hi = LIMITS[key]
    c = max(lo, min(hi, float(v)))
    if c != v:
        notes.append(f"{label} limited to {c:g} (allowed {lo:g}..{hi:g})")
    return c


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def validate_web_actions(actions: list[WebAction], components: list[dict]) -> tuple[list[dict], list[dict]]:
    """Returns (valid actions as dicts with clamped values, rejected [{action, error}]).
    Component references may be ids or display names (resolved case-insensitively)."""
    lookup = {}
    for c in components:
        lookup[_norm(c["id"])] = c["id"]
        lookup[_norm(c["name"])] = c["id"]
    valid, rejected = [], []
    for a in actions[:16]:
        notes: list[str] = []
        d = a.model_dump()
        cid = d.get("component_id")
        if cid is not None:
            resolved = lookup.get(_norm(cid))
            if resolved is None:
                rejected.append({"action": d, "error": f"unknown component '{cid}'"})
                continue
            d["component_id"] = resolved
        if "color_hex" in d and not HEX.match(d["color_hex"]):
            rejected.append({"action": d, "error": f"invalid color '{d['color_hex']}'"})
            continue
        if isinstance(a, ScaleComponent):
            for k in ("factor_x", "factor_y", "factor_z"):
                d[k] = _clamp(d[k], "factor", notes, k)
        elif isinstance(a, MoveComponent):
            for k in ("dx_cm", "dy_cm", "dz_cm"):
                d[k] = _clamp(d[k], "move", notes, k)
        elif isinstance(a, SetRideHeight):
            d["offset_cm"] = _clamp(d["offset_cm"], "ride", notes, "ride height")
        elif isinstance(a, SetWheelSize):
            d["delta_inches"] = _clamp(d["delta_inches"], "wheel", notes, "wheel size")
        elif isinstance(a, SetTrackWidth):
            d["offset_cm"] = _clamp(d["offset_cm"], "track", notes, "track width")
        elif isinstance(a, SetBodyProportions):
            for k in ("front_overhang_cm", "rear_overhang_cm", "wheelbase_cm", "body_width_cm",
                      "fender_flare_cm", "roof_height_cm"):
                d[k] = _clamp(d[k], k, notes, k.replace("_", " "))
        if notes:
            d["notes"] = notes
        valid.append(d)
    return valid, rejected


def build_instructions(model_name: str, components: list[dict], selected: str | None) -> str:
    comp_list = "\n".join(f"  - {c['id']}: {c['name']}" for c in components)
    sel = f"\nThe user currently has '{selected}' selected; 'this part' refers to it." if selected else ""
    return f"""You are the design assistant of a web 3D car configurator showing a {model_name}.
Translate the user's request into actions. Available actions:

LEVEL 1 - appearance (any color as #RRGGBB, finish one of gloss|metallic|matte|satin|chrome|carbon):
- set_body_color: the main body paint.
- set_wheel_color: all four rims.
- set_component_color: one component (e.g. mirrors, roof, spoiler, grille, splitter, calipers via wheels).
LEVEL 2 - shape changes. The car is deformed as ONE connected shell (panels never detach):
- set_body_proportions: whole-body shape. front_overhang_cm / rear_overhang_cm (-10..30, longer nose/tail),
  wheelbase_cm (-10..30), body_width_cm (0..10 per side), fender_flare_cm (0..10, wide-body arches),
  roof_height_cm (-8..6). Use 0 for anything unchanged. Use THIS for "longer/wider/lower-roof body",
  "wide-body kit", "stretch the car" etc. - never approximate those by scaling many panels.
- scale_component: soft local reshape of one part: factor_x (width) / factor_y (height) / factor_z (length),
  each 0.7-1.5, 1 = unchanged. The edit blends into neighbouring panels. Use for single parts
  ("bigger spoiler", "deeper front splitter", "taller hood bulge").
- move_component: soft local move of one part: dx_cm (left +), dy_cm (up +), dz_cm (forward +), each -15..15
  (e.g. "front splitter lower and further forward").
- hide_component: hidden true/false (e.g. "remove the spoiler").
- set_ride_height: offset_cm -6..6 (negative lowers the car).
- set_wheel_size: delta_inches -1..3 relative to stock.
- set_track_width: offset_cm 0..8 per side (wider stance).
- reset_design: back to the original car.

Component ids (use exactly these):
{comp_list}{sel}

Rules:
- Use the closest supported actions; translate words into concrete values (e.g. "a bit lower" -> -3 cm,
  "much bigger spoiler" -> factor 1.4, "British racing green" -> #004225 metallic).
- component_id must be one of the ids listed below (e.g. "front-bumper", not "Front bumper").
- Never invent component ids, action types, file paths or code.
- Prefer few, coherent actions. Keep part scale factors within 0.85-1.25 and moves within 8 cm unless the
  user explicitly asks for extremes; do not touch parts the user did not ask about.
- Requests for NEW detailed geometry (new air-intake shapes, sculpted surfaces, different bumper design
  language) cannot be generated. Approximate the overall intent with set_body_proportions and/or a few
  moderate part edits (e.g. "more aggressive bumper" -> front bumper/splitter slightly longer and lower,
  fender flares), say in the summary that it is an approximation, and list the detail that cannot be
  produced in `unsupported` (category geometry_modification). Concept images are never produced.
- `summary`: 1-3 sentences describing exactly what will be changed."""


# --------------------------------------------------------------------------- offline demo mode
COLORS = {
    "midnight blue": "#0c1d4f", "navy": "#0c1d4f", "dark blue": "#0c1d4f", "blue": "#1c4fb8",
    "racing red": "#b3060c", "red": "#b3060c", "white": "#e8e8e4", "black": "#0b0c10",
    "silver": "#a9acb2", "grey": "#5a5d63", "gray": "#5a5d63", "green": "#0f5a2e",
    "british racing green": "#004225", "yellow": "#e8c400", "orange": "#e05a00", "gold": "#b08a3a",
    "bronze": "#8c6239", "purple": "#4b2a7a",
}
PARTS = {"mirror": ["mirror-left", "mirror-right"], "roof": ["roof"], "spoiler": ["rear-spoiler"],
         "grille": ["kidney-grille"], "hood": ["hood"], "splitter": ["front-splitter"],
         "diffuser": ["rear-diffuser"], "front bumper": ["front-bumper"], "rear bumper": ["rear-bumper"]}


def keyword_proposal(prompt: str) -> WebDesignProposal:
    t = prompt.lower()
    acts: list[dict] = []
    color = next((hx for name, hx in sorted(COLORS.items(), key=lambda kv: -len(kv[0])) if name in t), None)
    finish = next((f for f in ("matte", "chrome", "carbon", "satin", "metallic") if f in t), "gloss")
    part = next((ids for name, ids in PARTS.items() if name in t), None)
    if color and part and not re.search(r"\b(paint|car|body)\b", t):
        acts += [{"type": "set_component_color", "component_id": c, "color_hex": color, "finish": finish} for c in part]
    elif color and re.search(r"\b(wheel|wheels|rims?)\b", t) and not re.search(r"\b(paint|body|car)\b", t):
        acts.append({"type": "set_wheel_color", "color_hex": color, "finish": finish})
    elif color:
        acts.append({"type": "set_body_color", "color_hex": color, "finish": finish})
    if re.search(r"\b(lower|lowered|slammed)\b", t):
        acts.append({"type": "set_ride_height", "offset_cm": -3})
    if re.search(r"\b(bigger|larger)\s+(wheel|wheels|rims?)\b", t):
        acts.append({"type": "set_wheel_size", "delta_inches": 1})
    if re.search(r"\b(wider|wide)\s+(stance|track)\b", t):
        acts.append({"type": "set_track_width", "offset_cm": 3})
    if re.search(r"\b(bigger|larger)\s+spoiler\b", t):
        acts.append({"type": "scale_component", "component_id": "rear-spoiler", "factor_x": 1.1, "factor_y": 1.4, "factor_z": 1.3})
    if re.search(r"\b(remove|delete|no)\s+(the\s+)?spoiler\b", t):
        acts.append({"type": "hide_component", "component_id": "rear-spoiler", "hidden": True})
    longer = bool(re.search(r"\b(longer|stretch|stretched|extended)\b", t))
    wider = bool(re.search(r"\b(wide-?body|wider body|flares?)\b", t))
    if longer or wider:
        acts.append({"type": "set_body_proportions", "front_overhang_cm": 10 if longer else 0,
                     "rear_overhang_cm": 8 if longer else 0, "wheelbase_cm": 10 if longer else 0,
                     "body_width_cm": 0, "fender_flare_cm": 5 if wider else 0, "roof_height_cm": 0})
    if re.search(r"\breset\b", t):
        acts = [{"type": "reset_design"}]
    unsupported = []
    if re.search(r"\b(redesign|sculpt|new shape|aggressive)\b", t):
        unsupported.append({"request": "freeform reshaping", "category": "geometry_modification",
                            "reason": "New geometry cannot be generated; only scale/move/hide of existing parts."})
    summary = f"Demo mode recognised {len(acts)} change(s)." if acts else "No supported change recognised."
    return WebDesignProposal.model_validate({"summary": summary, "actions": acts, "unsupported": unsupported})
