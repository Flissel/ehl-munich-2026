"""Trusted, Unreal-side registry of viewable models and allowed design presets.

Nothing here is ever supplied by a network client: commands only carry IDs, which
are looked up in these tables. Unknown IDs are rejected.
"""

# Paint presets: id -> (label, linear RGB base color, metallic, roughness, clearcoat roughness)
PAINTS = {
    "black":         ("Sapphire Black metallic", (0.004, 0.004, 0.005), 0.60, 0.32, 0.03),
    "white":         ("Alpine White",            (0.80, 0.80, 0.78),    0.00, 0.30, 0.03),
    "silver":        ("Brooklyn Silver metallic",(0.42, 0.43, 0.45),    0.90, 0.30, 0.03),
    "racing_red":    ("Racing Red",              (0.45, 0.005, 0.008),  0.15, 0.30, 0.03),
    "midnight_blue": ("Midnight Blue metallic",  (0.004, 0.012, 0.055), 0.75, 0.30, 0.03),
}

# Wheel styles. The source asset has ONE rim geometry, so styles are finish presets
# applied to the rim material slot (no alternate rim meshes exist in the ZIP).
# id -> (label, base color, metallic, roughness)
WHEEL_STYLES = {
    "standard": ("Standard - Orbit Grey alloy (factory finish)", (0.10, 0.10, 0.11), 1.0, 0.35),
    "sport":    ("Sport - Gold Bronze M finish",                 (0.38, 0.23, 0.08), 1.0, 0.28),
}

MODELS = {
    "bmw-m4-competition-2021": {
        "display_name": "2021 BMW M4 Competition",
        # Combined static mesh produced by bmw_studio_build.build (all parts, curated materials)
        "mesh": "/Game/BMWStudio/Vehicles/BMW_M4_2021/SM_BMW_M4_2021",
        # The source FBX is ~1.38x real size; normalize to the real G82 M4 length (4,794 mm).
        "target_length_cm": 479.4,
        # Source long axis is Y; rotate so the car's length runs along world X.
        "yaw": 90.0,
        # Material slots (normalized FBX material names) that the design actions target
        "paint_slots": ["material692"],
        "rim_slots": ["material753"],
        "default_paint": None,       # None = as-authored paint material
        "default_wheel_style": None,
    },
}


def normalize_slot(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())
