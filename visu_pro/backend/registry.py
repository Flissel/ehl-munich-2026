"""Server-side registry of models and the design options each model supports.

The browser only ever sends IDs. Anything not listed here is rejected. Asset paths and the
viewer executable are NOT in this registry; the Unreal side maps model IDs to its own trusted
asset paths (unreal/BMWVisualizer/Content/Python/bmw_viewer/registry.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field

PAINTS: dict[str, str] = {
    "black": "Sapphire Black metallic",
    "white": "Alpine White",
    "silver": "Brooklyn Silver metallic",
    "racing_red": "Racing Red",
    "midnight_blue": "Midnight Blue metallic",
}

WHEEL_STYLES: dict[str, str] = {
    "standard": "Standard - Orbit Grey alloy (factory finish)",
    "sport": "Sport - Gold Bronze M finish",
}


@dataclass(frozen=True)
class ModelEntry:
    id: str
    display_name: str
    paints: tuple[str, ...]
    wheel_styles: tuple[str, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)


MODELS: dict[str, ModelEntry] = {
    "bmw-m4-competition-2021": ModelEntry(
        id="bmw-m4-competition-2021",
        display_name="2021 BMW M4 Competition",
        paints=tuple(PAINTS),
        wheel_styles=tuple(WHEEL_STYLES),
        notes=(
            "Wheel styles are finish presets on the stock rim geometry: the source asset contains a "
            "single rim design, so no alternate rim meshes are available.",
        ),
    ),
}


def get_model(model_id: str) -> ModelEntry | None:
    return MODELS.get(model_id)
