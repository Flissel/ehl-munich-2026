"""Headless project builder for the BMW Studio Unreal project.

Run via scripts/build_unreal.ps1, which executes:
    UnrealEditor-Cmd.exe BMWVisualizer.uproject -run=pythonscript
        -script="<this file>" -unattended -nullrhi
Pass stages through the env var BMW_BUILD_STAGES (comma separated):
    import, materials, showroom  (default: all)

The build is idempotent: re-running replaces generated assets under /Game/BMWStudio
but never touches the source ZIP or extracted files.
"""
import json
import os
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(HERE) not in sys.path:
    sys.path.append(os.path.dirname(HERE))

from bmw_studio_build import profile_bmw_m4_2021 as profile  # noqa: E402
from bmw_viewer.registry import normalize_slot  # noqa: E402

PROJECT_DIR = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
REPO_ROOT = os.path.normpath(os.path.join(PROJECT_DIR, "..", ".."))
SOURCE_DIR = os.path.join(REPO_ROOT, "assets", "extracted", "bmw-m4-competition-2021")
FBX_PATH = os.path.join(SOURCE_DIR, "source", "BMW M4 2021 v1.fbx")
TEX_DIR = os.path.join(SOURCE_DIR, "textures")
REPORT_PATH = os.path.join(REPO_ROOT, "assets", "imported", "bmw-m4-competition-2021_import_report.json")

ROOT = "/Game/BMWStudio"
VEHICLE_DIR = f"{ROOT}/Vehicles/BMW_M4_2021"
MESH_NAME = "SM_BMW_M4_2021"
MAT_DIR = f"{ROOT}/Materials"
VEH_MAT_DIR = f"{VEHICLE_DIR}/Materials"
TEX_ASSET_DIR = f"{VEHICLE_DIR}/Textures"
MAP_PATH = f"{ROOT}/Maps/Showroom"

BUILD_RECOMPUTE_NORMALS = os.environ.get("BMW_RECOMPUTE_NORMALS", "1") == "1"

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()


def log(msg):
    unreal.log(f"[BMWBuild] {msg}")


# --------------------------------------------------------------------------- import
def stage_import():
    if not os.path.isfile(FBX_PATH):
        raise RuntimeError(f"FBX not found: {FBX_PATH} (run scripts/extract_assets.ps1 first)")
    if eal.does_directory_exist(VEHICLE_DIR):
        eal.delete_directory(VEHICLE_DIR)

    # AssetImportTask ignores in-memory Interchange pipelines, so we keep a project-local copy of
    # the engine's default pipeline asset, configure it, and pass it as an override pipeline.
    pipeline_path = f"{ROOT}/Pipelines/BMW_StaticCombinedPipeline"
    if eal.does_asset_exist(pipeline_path):
        eal.delete_asset(pipeline_path)
    src_pipeline = unreal.load_asset("/Interchange/Pipelines/DefaultFBXOBJAssetsPipeline.DefaultFBXOBJAssetsPipeline")
    if src_pipeline is None:
        raise RuntimeError("Engine pipeline /Interchange/Pipelines/DefaultFBXOBJAssetsPipeline not found")
    pipeline = asset_tools.duplicate_asset(pipeline_path.rsplit("/", 1)[1], pipeline_path.rsplit("/", 1)[0], src_pipeline)
    if pipeline is None:
        raise RuntimeError(f"Could not duplicate {src_pipeline.get_path_name()} (class {src_pipeline.get_class().get_name()})")
    log(f"Using pipeline {pipeline.get_path_name()} ({pipeline.get_class().get_name()})")
    mesh_p = pipeline.get_editor_property("mesh_pipeline")
    mesh_p.set_editor_property("import_static_meshes", True)
    mesh_p.set_editor_property("combine_static_meshes_behavior", unreal.InterchangeCombineStaticMeshesBehavior.ALL)
    mesh_p.set_editor_property("build_nanite", False)
    mesh_p.set_editor_property("generate_lightmap_u_vs", False)
    mesh_p.set_editor_property("import_skeletal_meshes", False)
    # The FBX carries animation curves on some nodes; force everything to static meshes.
    common = pipeline.get_editor_property("common_meshes_properties")
    common.set_editor_property("force_all_mesh_as_type", unreal.InterchangeForceMeshType.IFMT_STATIC_MESH)
    common.set_editor_property("convert_statics_with_animated_transform_to_skeletals", False)
    # The exported normals render faceted; rebuild them from the FBX smoothing groups instead.
    common.set_editor_property("recompute_normals", BUILD_RECOMPUTE_NORMALS)
    common.set_editor_property("recompute_tangents", True)
    common.set_editor_property("compute_weighted_normals", True)
    pipeline.get_editor_property("animation_pipeline").set_editor_property("import_animations", False)
    pipeline.get_editor_property("material_pipeline").get_editor_property("texture_pipeline") \
        .set_editor_property("import_textures", False)
    # The Corona materials can't be translated (and their textures point to the author's PC),
    # so we skip material import; slots keep the FBX material names and get curated materials later.
    pipeline.get_editor_property("material_pipeline").set_editor_property("import_materials", False)
    pipeline.set_editor_property("asset_name", MESH_NAME)
    eal.save_loaded_asset(pipeline)

    params = unreal.ImportAssetParameters()
    params.set_editor_property("is_automated", True)
    params.set_editor_property("replace_existing", True)
    overrides = params.get_editor_property("override_pipelines")
    overrides.append(unreal.SoftObjectPath(pipeline.get_path_name()))
    params.set_editor_property("override_pipelines", overrides)
    source = unreal.InterchangeManager.create_source_data(FBX_PATH)
    manager = unreal.InterchangeManager.get_interchange_manager_scripted()
    if not manager.import_asset(VEHICLE_DIR, source, params):
        raise RuntimeError("Interchange import_asset returned False")

    imported = eal.list_assets(VEHICLE_DIR, recursive=True)
    log(f"Imported {len(imported)} objects")
    meshes = [p for p in imported if isinstance(eal.load_asset(p), unreal.StaticMesh)]
    others = [p for p in imported if not isinstance(eal.load_asset(p), unreal.StaticMesh)]
    if others:
        log(f"WARNING unexpected non-static-mesh assets: {others[:10]}")
    if len(meshes) != 1:
        raise RuntimeError(f"Expected exactly one combined static mesh, got: {meshes}")
    mesh_path = meshes[0].split(".")[0]
    target = f"{VEHICLE_DIR}/{MESH_NAME}"
    if mesh_path != target:
        eal.rename_asset(mesh_path, target)
    mesh = eal.load_asset(target)
    smooth_normals(mesh)
    write_report(mesh, imported)
    eal.save_directory(VEHICLE_DIR)


SMOOTHING_ANGLE_DEG = float(os.environ.get("BMW_SMOOTHING_ANGLE", "50"))


def smooth_normals(mesh):
    """The source FBX is low-poly with all smoothing groups = 0 (it was smoothed at render time in
    3ds Max), so it renders faceted. Recompute normals with an opening-angle threshold: smooth across
    gentle curvature, keep creases sharper than SMOOTHING_ANGLE_DEG. Geometry is not changed."""
    gs = unreal
    dm = unreal.new_object(unreal.DynamicMesh)
    read = gs.GeometryScriptMeshReadLOD()
    dm, outcome = gs.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(
        mesh, dm, gs.GeometryScriptCopyMeshFromAssetOptions(), read)
    if outcome != gs.GeometryScriptOutcomePins.SUCCESS:
        raise RuntimeError(f"copy_mesh_from_static_mesh failed: {outcome}")
    split = gs.GeometryScriptSplitNormalsOptions()
    split.set_editor_property("split_by_opening_angle", True)
    split.set_editor_property("opening_angle_deg", SMOOTHING_ANGLE_DEG)
    calc = gs.GeometryScriptCalculateNormalsOptions()
    calc.set_editor_property("angle_weighted", True)
    calc.set_editor_property("area_weighted", True)
    gs.GeometryScript_Normals.compute_split_normals(dm, split, calc)
    gs.GeometryScript_Normals.compute_tangents(dm, gs.GeometryScriptTangentsOptions())
    opts = gs.GeometryScriptCopyMeshToAssetOptions()
    opts.set_editor_property("enable_recompute_normals", False)
    opts.set_editor_property("enable_recompute_tangents", False)
    opts.set_editor_property("replace_materials", False)
    dm, outcome = gs.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(
        dm, mesh, opts, gs.GeometryScriptMeshWriteLOD())
    if outcome != gs.GeometryScriptOutcomePins.SUCCESS:
        raise RuntimeError(f"copy_mesh_to_static_mesh failed: {outcome}")
    eal.save_loaded_asset(mesh)
    log(f"Normals recomputed (opening angle {SMOOTHING_ANGLE_DEG} deg)")


def write_report(mesh, imported):
    bounds = mesh.get_bounds()
    slots = []
    for i, sm in enumerate(mesh.get_editor_property("static_materials")):
        mi = sm.get_editor_property("material_interface")
        slots.append({"index": i, "slot_name": str(sm.get_editor_property("material_slot_name")),
                      "material": mi.get_path_name() if mi else None})
    report = {
        "fbx": FBX_PATH,
        "mesh": mesh.get_path_name(),
        "bounds_origin": [bounds.origin.x, bounds.origin.y, bounds.origin.z],
        "bounds_extent": [bounds.box_extent.x, bounds.box_extent.y, bounds.box_extent.z],
        "material_slots": slots,
        "imported_objects": len(imported),
    }
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    log(f"Report written: {REPORT_PATH} ({len(slots)} slots, extent {report['bounds_extent']})")


# --------------------------------------------------------------------------- materials
def _expr(mat, cls, x, y):
    return mel.create_material_expression(mat, cls, x, y)


def _vec_param(mat, name, default, x, y):
    e = _expr(mat, unreal.MaterialExpressionVectorParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", unreal.LinearColor(*default, 1.0))
    return e


def _scalar_param(mat, name, default, x, y):
    e = _expr(mat, unreal.MaterialExpressionScalarParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", float(default))
    return e


def _new_material(path):
    if eal.does_asset_exist(path):  # reuse the package and clear its graph
        m = eal.load_asset(path)
        mel.delete_all_material_expressions(m)
        return m
    folder, name = path.rsplit("/", 1)
    return asset_tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())


def build_master_materials():
    P = unreal.MaterialProperty
    # --- Car paint: clear coat, parameterized color/metallic/roughness
    m = _new_material(f"{MAT_DIR}/M_CarPaint")
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_CLEAR_COAT)
    mel.connect_material_property(_vec_param(m, "PaintColor", (0.1, 0.1, 0.1), -400, -200), "", P.MP_BASE_COLOR)
    mel.connect_material_property(_scalar_param(m, "Metallic", 0.7, -400, 0), "", P.MP_METALLIC)
    mel.connect_material_property(_scalar_param(m, "Roughness", 0.3, -400, 100), "", P.MP_ROUGHNESS)
    # ClearCoat / ClearCoatRoughness pins aren't exposed to Python (MP_CUSTOM_DATA*); the clear
    # coat shading model's unconnected defaults (1.0 / 0.1) give a proper lacquer layer.
    mel.recompile_material(m)

    # --- Generic opaque surface (optionally textured, optionally emissive)
    m = _new_material(f"{MAT_DIR}/M_Surface")
    color = _vec_param(m, "BaseColor", (0.5, 0.5, 0.5), -700, -300)
    tex = _expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -700, -100)
    tex.set_editor_property("parameter_name", "BaseTexture")
    tex.set_editor_property("texture", eal.load_asset("/Engine/EngineResources/WhiteSquareTexture"))
    mul = _expr(m, unreal.MaterialExpressionMultiply, -350, -200)
    mel.connect_material_expressions(color, "", mul, "A")
    mel.connect_material_expressions(tex, "RGB", mul, "B")
    mel.connect_material_property(mul, "", P.MP_BASE_COLOR)
    mel.connect_material_property(_scalar_param(m, "Metallic", 0.0, -400, 0), "", P.MP_METALLIC)
    mel.connect_material_property(_scalar_param(m, "Roughness", 0.5, -400, 100), "", P.MP_ROUGHNESS)
    em = _vec_param(m, "EmissiveColor", (0.0, 0.0, 0.0), -700, 250)
    em_s = _scalar_param(m, "EmissiveStrength", 0.0, -700, 400)
    em_mul = _expr(m, unreal.MaterialExpressionMultiply, -350, 300)
    mel.connect_material_expressions(em, "", em_mul, "A")
    mel.connect_material_expressions(em_s, "", em_mul, "B")
    mel.connect_material_property(em_mul, "", P.MP_EMISSIVE_COLOR)
    mel.recompile_material(m)

    # --- Glass: translucent with surface forward shading for reflections
    m = _new_material(f"{MAT_DIR}/M_Glass")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    m.set_editor_property("two_sided", True)
    mel.connect_material_property(_vec_param(m, "BaseColor", (0.02, 0.02, 0.02), -400, -200), "", P.MP_BASE_COLOR)
    mel.connect_material_property(_scalar_param(m, "Metallic", 0.0, -400, -50), "", P.MP_METALLIC)
    mel.connect_material_property(_scalar_param(m, "Roughness", 0.02, -400, 50), "", P.MP_ROUGHNESS)
    mel.connect_material_property(_scalar_param(m, "Opacity", 0.3, -400, 150), "", P.MP_OPACITY)
    mel.connect_material_property(_scalar_param(m, "Specular", 1.0, -400, 250), "", P.MP_SPECULAR)
    mel.recompile_material(m)

    # --- Floor: dark, slightly glossy studio floor
    m = _new_material(f"{MAT_DIR}/M_StudioFloor")
    mel.connect_material_property(_vec_param(m, "BaseColor", (0.015, 0.015, 0.017), -400, -100), "", P.MP_BASE_COLOR)
    mel.connect_material_property(_scalar_param(m, "Roughness", 0.22, -400, 50), "", P.MP_ROUGHNESS)
    mel.recompile_material(m)
    eal.save_directory(MAT_DIR)


def import_texture(filename):
    src = os.path.join(TEX_DIR, filename)
    if not os.path.isfile(src):
        log(f"WARNING texture missing in ZIP, skipping: {filename}")
        return None
    name = "T_" + "".join(c if c.isalnum() else "_" for c in os.path.splitext(filename)[0])[:60]
    path = f"{TEX_ASSET_DIR}/{name}"
    if eal.does_asset_exist(path):
        return eal.load_asset(path)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", src)
    task.set_editor_property("destination_path", TEX_ASSET_DIR)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    asset_tools.import_asset_tasks([task])
    return eal.load_asset(path)


def make_instance(name, parent_path, vectors=None, scalars=None, texture=None, folder=VEH_MAT_DIR):
    path = f"{folder}/{name}"
    if eal.does_asset_exist(path):
        mi = eal.load_asset(path)  # reuse: delete + recreate in one session leaves stale packages
    else:
        mi = asset_tools.create_asset(name, folder, unreal.MaterialInstanceConstant,
                                      unreal.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property("parent", eal.load_asset(parent_path))
    for k, v in (vectors or {}).items():
        mel.set_material_instance_vector_parameter_value(mi, k, unreal.LinearColor(*v, 1.0))
    for k, v in (scalars or {}).items():
        mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
    if texture is not None:
        mel.set_material_instance_texture_parameter_value(mi, "BaseTexture", texture)
    mel.update_material_instance(mi)
    eal.save_loaded_asset(mi)
    return mi


def build_preset_instance(preset_name):
    spec = profile.PRESETS[preset_name]
    kind = spec["kind"]
    parent = {"paint": f"{MAT_DIR}/M_CarPaint", "surface": f"{MAT_DIR}/M_Surface",
              "glass": f"{MAT_DIR}/M_Glass"}[kind]
    vectors, scalars = {}, {}
    if kind == "paint":
        vectors["PaintColor"] = spec["color"]
        scalars.update(Metallic=spec["metallic"], Roughness=spec["roughness"])
    elif kind == "surface":
        vectors["BaseColor"] = spec.get("color", (1, 1, 1))
        scalars.update(Metallic=spec.get("metallic", 0.0), Roughness=spec.get("roughness", 0.5))
        if "emissive" in spec:
            vectors["EmissiveColor"] = spec["emissive"]
            scalars["EmissiveStrength"] = spec.get("emissive_strength", 5.0)
    else:
        vectors["BaseColor"] = spec.get("color", (0.02, 0.02, 0.02))
        scalars.update(Opacity=spec.get("opacity", 0.3), Roughness=spec.get("roughness", 0.02),
                       Metallic=spec.get("metallic", 0.0))
    tex = import_texture(spec["texture"]) if spec.get("texture") else None
    return make_instance(f"MI_{preset_name}", parent, vectors, scalars, tex)


def stage_materials():
    build_master_materials()
    if eal.does_directory_exist(VEH_MAT_DIR):
        # Interchange-created materials live here too; we only replace our MI_ assets.
        pass
    instances = {name: build_preset_instance(name) for name in profile.PRESETS}

    mesh = eal.load_asset(f"{VEHICLE_DIR}/{MESH_NAME}")
    if mesh is None:
        raise RuntimeError("Mesh not imported yet; run the 'import' stage first")
    static_mats = list(mesh.get_editor_property("static_materials"))
    assigned, unmatched = {}, []
    for i, sm in enumerate(static_mats):
        slot = normalize_slot(sm.get_editor_property("material_slot_name"))
        preset = profile.SLOT_PRESETS.get(slot) or profile.preset_for_unlisted(slot)
        if preset is None:
            unmatched.append(slot)
            preset = profile.FALLBACK_PRESET
        sm.set_editor_property("material_interface", instances[preset])
        static_mats[i] = sm
        assigned[slot] = preset
    mesh.set_editor_property("static_materials", static_mats)
    eal.save_loaded_asset(mesh)
    eal.save_directory(VEH_MAT_DIR)
    log(f"Assigned {len(assigned)} slots; fallback used for: {unmatched}")
    # Append the material assignment to the import report
    try:
        with open(REPORT_PATH, encoding="utf-8") as f:
            report = json.load(f)
        report["material_assignment"] = assigned
        report["unmatched_slots_using_fallback"] = unmatched
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except OSError:
        pass


# --------------------------------------------------------------------------- showroom
def _spawn(cls, location=(0, 0, 0), rotation=(0, 0, 0), label=None):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        cls, unreal.Vector(*location), unreal.Rotator(*rotation))
    if label:
        actor.set_actor_label(label)
    return actor


def build_game_mode():
    path = f"{ROOT}/Blueprints/BP_ShowroomGameMode"
    if eal.does_asset_exist(path):
        bp = eal.load_asset(path)
    else:
        factory = unreal.BlueprintFactory()
        factory.set_editor_property("parent_class", unreal.GameModeBase)
        bp = asset_tools.create_asset("BP_ShowroomGameMode", f"{ROOT}/Blueprints", unreal.Blueprint, factory)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    gen = unreal.BlueprintEditorLibrary.generated_class(bp)
    if gen is None:
        raise RuntimeError("BP_ShowroomGameMode has no generated class")
    cdo = unreal.get_default_object(gen)
    cdo.set_editor_property("default_pawn_class", None)  # camera is driven by the viewer runtime
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    eal.save_loaded_asset(bp)
    return bp


def stage_showroom():
    game_mode = build_game_mode()
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if eal.does_asset_exist(MAP_PATH):
        # Re-using the package is more reliable than delete + recreate in one editor session.
        if not les.load_level(MAP_PATH):
            raise RuntimeError("Failed to load existing showroom level")
        actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for a in actor_sub.get_all_level_actors():
            if not isinstance(a, (unreal.WorldSettings, unreal.Brush)):
                actor_sub.destroy_actor(a)
    elif not les.new_level(MAP_PATH):
        raise RuntimeError("Failed to create showroom level")

    # Floor: wide dark disc + turntable plinth
    floor = _spawn(unreal.StaticMeshActor, (0, 0, -1), label="StudioFloor")
    floor.static_mesh_component.set_static_mesh(eal.load_asset("/Engine/BasicShapes/Plane"))
    floor.set_actor_scale3d(unreal.Vector(400, 400, 1))
    floor.static_mesh_component.set_material(0, eal.load_asset(f"{MAT_DIR}/M_StudioFloor"))

    plinth_mat = make_instance("MI_Plinth", f"{MAT_DIR}/M_Surface",
                               {"BaseColor": (0.03, 0.03, 0.035)}, {"Roughness": 0.35, "Metallic": 0.0},
                               folder=MAT_DIR)
    plinth = _spawn(unreal.StaticMeshActor, (0, 0, -4), label="Turntable")
    plinth.static_mesh_component.set_static_mesh(eal.load_asset("/Engine/BasicShapes/Cylinder"))
    plinth.set_actor_scale3d(unreal.Vector(7.0, 7.0, 0.06))
    plinth.static_mesh_component.set_material(0, plinth_mat)

    # Lighting: soft key light, HDRI sky light, two rect lights for paint highlights
    sun = _spawn(unreal.DirectionalLight, (0, 0, 800), (0, -50, -35), "KeyLight")
    sun.light_component.set_intensity(3.0)
    sun.light_component.set_editor_property("light_source_angle", 8.0)
    sun.light_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)

    sky = _spawn(unreal.SkyLight, (0, 0, 300), label="StudioSkyLight")
    slc = sky.light_component
    slc.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    slc.set_editor_property("source_type", unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
    hdri = unreal.load_object(None, "/Engine/EditorMaterials/AssetViewer/EpicQuadPanorama_CC+EV1.EpicQuadPanorama_CC+EV1")
    if hdri is None:
        raise RuntimeError("Studio HDRI cubemap not found in engine content")
    slc.set_editor_property("cubemap", hdri)
    slc.set_editor_property("intensity", 1.6)
    slc.set_editor_property("real_time_capture", False)

    for label, loc, rot in (("RectLightLeft", (0, -650, 450), (0, -35, 90)),
                            ("RectLightRight", (0, 650, 450), (0, -35, -90)),
                            ("RectLightTop", (0, 0, 700), (0, -90, 0))):
        rl = _spawn(unreal.RectLight, loc, rot, label)
        rl.rect_light_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        rl.rect_light_component.set_editor_property("intensity", 60.0)
        rl.rect_light_component.set_editor_property("source_width", 600.0)
        rl.rect_light_component.set_editor_property("source_height", 250.0)
        rl.rect_light_component.set_editor_property("attenuation_radius", 2500.0)

    # Post process: fixed exposure, mild bloom & vignette
    ppv = _spawn(unreal.PostProcessVolume, label="StudioPostProcess")
    ppv.set_editor_property("unbound", True)
    s = ppv.get_editor_property("settings")
    s.set_editor_property("override_auto_exposure_method", True)
    s.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
    s.set_editor_property("override_auto_exposure_bias", True)
    s.set_editor_property("auto_exposure_bias", 11.0)
    s.set_editor_property("override_vignette_intensity", True)
    s.set_editor_property("vignette_intensity", 0.5)
    ppv.set_editor_property("settings", s)

    # Viewer camera (driven by bmw_viewer.runtime) and a marker for the car position
    cam = _spawn(unreal.CameraActor, (-650, -450, 220), (0, -12, 35), "ShowroomCamera")
    cam.tags = ["ShowroomCamera"]
    cam.camera_component.set_editor_property("field_of_view", 40.0)
    cam.camera_component.set_editor_property("constrain_aspect_ratio", False)
    try:
        cam.set_editor_property("auto_activate_for_player", unreal.AutoReceiveInput.PLAYER0)
    except Exception as e:  # property name differs across versions; runtime also sets view target
        log(f"auto_activate_for_player not set: {e}")
    marker = _spawn(unreal.TargetPoint, (0, 0, 0), label="CarSpawnPoint")
    marker.tags = ["CarSpawnPoint"]
    # Empty, movable car slot; the viewer assigns the registered model mesh on open_model.
    car_slot = _spawn(unreal.StaticMeshActor, (0, 0, 0), label="CarSlot")
    car_slot.static_mesh_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    car_slot.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    car_slot.tags = ["BMWStudioCar"]

    ws = unreal.EditorLevelLibrary.get_editor_world().get_world_settings()
    ws.set_editor_property("default_game_mode", unreal.BlueprintEditorLibrary.generated_class(game_mode))

    les.save_current_level()
    log(f"Showroom saved to {MAP_PATH}")


STAGES = {"import": stage_import, "materials": stage_materials, "showroom": stage_showroom}


def main():
    requested = [s.strip() for s in os.environ.get("BMW_BUILD_STAGES", "import,materials,showroom").split(",") if s.strip()]
    for name in requested:
        if name not in STAGES:
            raise RuntimeError(f"Unknown stage {name!r}; valid: {list(STAGES)}")
    for name in requested:
        log(f"=== stage: {name}")
        STAGES[name]()
    log("BUILD OK")


main()
