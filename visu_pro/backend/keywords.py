"""Offline fallback interpreter used when OPENAI_API_KEY is not set.

Maps simple keywords to the same whitelisted actions the AI may use.
"""
from __future__ import annotations

import re

from design import DesignProposal

PAINT_WORDS = [
    ("midnight_blue", r"\b(midnight|navy|dark blue|blue)\b"),
    ("racing_red", r"\b(red|racing red)\b"),
    ("silver", r"\b(silver|grey|gray)\b"),
    ("white", r"\bwhite\b"),
    ("black", r"\bblack\b"),
]
WHEEL_WORDS = [  # checked in order; "standard" first so "racing red ... standard wheels" works
    ("standard", r"\b(standard|stock|normal|default|original)\s+(wheel|wheels|rims?)\b"),
    ("sport", r"\b(sport|sporty|performance|bronze|gold)\s+(wheel|wheels|rims?)\b|\b(wheel|wheels|rims?)\b.*\b(sport|sporty)\b"),
]
GEOMETRY_WORDS = r"\b(bumper|fender|diffuser|hood|bonnet|spoiler|bodywork|body kit|widen|reshape)\b"


def interpret(prompt: str) -> DesignProposal:
    text = prompt.lower()
    actions, notes = [], []
    if re.search(r"\b(reset|original design|undo)\b", text):
        actions.append({"type": "reset_design"})
    paint_text = re.sub(r"\b(wheel|wheels|rims?)\b.*", "", text) if "wheel" in text else text
    for pid, pat in PAINT_WORDS:
        if re.search(pat, paint_text):
            actions.append({"type": "set_paint", "paint_id": pid})
            notes.append(pid.replace("_", " ") + " paint")
            break
    for wid, pat in WHEEL_WORDS:
        if re.search(pat, text):
            actions.append({"type": "set_wheel_style", "style_id": wid})
            notes.append(wid + " wheels")
            break
    unsupported = []
    if re.search(GEOMETRY_WORDS, text):
        unsupported.append({"request": "body geometry change", "category": "geometry_modification",
                            "reason": "Geometry redesign is not supported in this MVP."})
    summary = ("Applying " + " and ".join(notes) + ".") if notes else \
        ("Resetting to the original design." if actions else "No supported change recognised.")
    return DesignProposal.model_validate({"summary": summary, "actions": actions, "unsupported": unsupported})
