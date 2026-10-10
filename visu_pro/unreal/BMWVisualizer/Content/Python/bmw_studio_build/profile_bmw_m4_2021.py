"""Material profile for '2021-bmw-m4-competition.zip' (BMW M4 2021 v1.fbx).

The FBX was authored in 3ds Max with Corona materials, which Unreal cannot translate.
This maps each FBX material (normalized slot name) to a curated Unreal preset, based on
the colors/opacity/glossiness found in the FBX (see scripts/inspect_fbx.py).
Texture file names refer to files in the ZIP's textures/ folder (the FBX references
.jpg paths on the author's machine; the ZIP ships them as .jpeg).
"""

PRESETS = {
    # Body paint - as authored: dark grey metallic (Corona layered paint, diffuse 0.157)
    "paint_original":  {"kind": "paint", "color": (0.025, 0.026, 0.028), "metallic": 0.8, "roughness": 0.32},
    "carbon":          {"kind": "surface", "texture": "500_F_192085570_QQGRV0eP4FB49VNQN35I61tVpv4e4GsK.jpeg",
                        "color": (0.35, 0.35, 0.37), "metallic": 0.2, "roughness": 0.25},
    "black_plastic":   {"kind": "surface", "color": (0.02, 0.02, 0.02), "roughness": 0.45},
    "black_matte":     {"kind": "surface", "color": (0.01, 0.01, 0.01), "roughness": 0.85},
    "black_gloss":     {"kind": "surface", "color": (0.006, 0.006, 0.006), "roughness": 0.12},
    "chrome":          {"kind": "surface", "color": (0.9, 0.9, 0.9), "metallic": 1.0, "roughness": 0.06},
    "black_chrome":    {"kind": "surface", "color": (0.12, 0.12, 0.11), "metallic": 1.0, "roughness": 0.1},
    "satin_alu":       {"kind": "surface", "color": (0.53, 0.53, 0.53), "metallic": 1.0, "roughness": 0.3},
    "headlight_blue":  {"kind": "surface", "color": (0.0, 0.094, 0.306), "metallic": 0.3, "roughness": 0.1},
    "drl_emissive":    {"kind": "surface", "color": (0.8, 0.9, 1.0), "emissive": (0.2, 0.65, 1.0), "emissive_strength": 8.0},
    "tail_emissive":   {"kind": "surface", "color": (0.3, 0.0, 0.0), "emissive": (1.0, 0.0, 0.0), "emissive_strength": 12.0},
    "light_reflector": {"kind": "surface", "color": (0.8, 0.8, 0.8), "metallic": 1.0, "roughness": 0.15},
    "tail_reflector":  {"kind": "surface", "texture": "Screenshot_35 - Copy.png", "color": (1, 1, 1), "roughness": 0.2},
    "rubber":          {"kind": "surface", "color": (0.018, 0.018, 0.018), "roughness": 0.9},
    "rim_original":    {"kind": "surface", "color": (0.10, 0.10, 0.11), "metallic": 1.0, "roughness": 0.35},
    "wheel_logo":      {"kind": "surface", "texture": "logo.png", "color": (1, 1, 1), "roughness": 0.3},
    "brake_disc":      {"kind": "surface", "texture": "121-62057-3.jpeg", "color": (1, 1, 1), "metallic": 0.9, "roughness": 0.45},
    "caliper_red":     {"kind": "surface", "color": (0.5, 0.0, 0.0), "roughness": 0.2},
    "caliper_decal":   {"kind": "surface", "texture": "Screenshot_41.png", "color": (1, 1, 1), "roughness": 0.3},
    "logo_white":      {"kind": "surface", "color": (0.85, 0.85, 0.85), "roughness": 0.15},
    "plate":           {"kind": "surface", "texture": "nebraska-license-plate-year-2005.jpeg", "color": (1, 1, 1), "roughness": 0.35},
    "leather_black":   {"kind": "surface", "color": (0.03, 0.03, 0.03), "roughness": 0.55},
    "leather_grey":    {"kind": "surface", "color": (0.25, 0.25, 0.25), "roughness": 0.55},
    "trim_grey":       {"kind": "surface", "color": (0.12, 0.12, 0.12), "roughness": 0.5},
    "alcantara":       {"kind": "surface", "texture": "natural-real-grey-alcantara-texture-260nw-712568374.png",
                        "color": (0.35, 0.35, 0.35), "roughness": 0.9},
    "fabric_black":    {"kind": "surface", "texture": "pin-dot-vinyl-fabric-black_-_Copy.jpeg", "color": (1, 1, 1), "roughness": 0.8},
    "screen_a":        {"kind": "surface", "texture": "Screenshot_45.png", "color": (1, 1, 1), "roughness": 0.1},
    "screen_b":        {"kind": "surface", "texture": "bmw_m4_competition_496.png", "color": (1, 1, 1), "roughness": 0.1},
    "screen_c":        {"kind": "surface", "texture": "Screenshot_64.png", "color": (1, 1, 1), "roughness": 0.1},
    "screen_d":        {"kind": "surface", "texture": "Screenshot_66.png", "color": (1, 1, 1), "roughness": 0.1},
    "screen_e":        {"kind": "surface", "texture": "Screenshot_67.png", "color": (1, 1, 1), "roughness": 0.1},
    "interior_detail": {"kind": "surface", "texture": "Screenshot_48.png", "color": (1, 1, 1), "roughness": 0.4},
    "speaker_grille":  {"kind": "surface", "texture": "ghirlle2 - Copy.png", "color": (1, 1, 1), "roughness": 0.5},
    "steering_logo":   {"kind": "surface", "texture": "logo.png", "color": (1, 1, 1), "roughness": 0.3},
    "mirror":          {"kind": "surface", "color": (0.95, 0.95, 0.95), "metallic": 1.0, "roughness": 0.0},
    "glass_window":    {"kind": "glass", "color": (0.01, 0.012, 0.012), "opacity": 0.35, "roughness": 0.02},
    "glass_clear":     {"kind": "glass", "color": (0.05, 0.05, 0.05), "opacity": 0.12, "roughness": 0.01},
    "glass_light_tint": {"kind": "glass", "color": (0.02, 0.03, 0.035), "opacity": 0.25, "roughness": 0.01},
    "glass_frosted":   {"kind": "glass", "color": (0.8, 0.8, 0.8), "opacity": 0.45, "roughness": 0.3},
}

SLOT_PRESETS = {
    "material692": "paint_original",
    "material693": "rim_original",
    "material694": "carbon",
    "material695": "chrome",
    "material696": "glass_light_tint",
    "material697": "black_matte",
    "material698": "carbon",
    "material699": "glass_window",
    "material700": "satin_alu",
    "material701": "black_chrome",
    "material706": "black_plastic",
    "material707": "black_gloss",
    "material708": "headlight_blue",
    "material716": "drl_emissive",
    "material717": "black_gloss",
    "material124": "light_reflector",
    "material161": "light_reflector",
    "material174": "light_reflector",
    "material187": "light_reflector",
    "material718": "glass_frosted",
    "material725": "glass_clear",
    "material279": "tail_reflector",
    "material738": "black_plastic",
    "material739": "tail_emissive",
    "material740": "tail_emissive",
    "material751": "rubber",
    "material752": "rubber",
    "material753": "rim_original",
    "material754": "rim_original",
    "material362": "wheel_logo",
    "material408": "brake_disc",
    "material773": "caliper_red",
    "material774": "caliper_decal",
    "material775": "glass_clear",
    "material776": "satin_alu",
    "material786": "chrome",
    "material787": "chrome",
    "material790": "chrome",
    "material538": "wheel_logo",
    "material574": "wheel_logo",
    "material801": "black_gloss",
    "material802": "logo_white",
    "material803": "logo_white",
    "material804": "logo_white",
    "material805": "logo_white",
    "material826": "plate",
    "material847": "leather_black",
    "material848": "leather_grey",
    "material849": "trim_grey",
    "material850": "alcantara",
    "material1860": "interior_detail",
    "material1063": "steering_logo",
    "material932": "glass_clear",
    "material1824": "speaker_grille",
    "material1522": "screen_a",
    "material1548": "screen_b",
    "material1001": "screen_c",
    "material1082": "screen_d",
    "material1046": "screen_d",
    "material1069": "screen_e",
    "material999": "mirror",
    "material1015": "trim_grey",
    "material1014": "black_plastic",
}

FALLBACK_PRESET = "black_plastic"


def preset_for_unlisted(slot):
    """Unused multi-sub-object placeholder slots exported by 3ds Max ('Tire Slot #3' ...)."""
    if slot.startswith("tireslot"):
        return "rubber"
    if slot.startswith(("brakemainslot", "logosslot", "material870slot")):
        return "black_plastic"
    return None
