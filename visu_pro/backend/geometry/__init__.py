"""Future geometry redesign pipeline (NOT implemented in the MVP).

Design intent, so geometry work can be added without touching the material path:

* A geometry change is a *job* that produces a NEW versioned mesh asset; the original import is
  never modified. Versions live under assets/geometry_versions/<model_id>/<version>/ with a
  manifest (source version, operation, parameters, tool versions, checksums).
* Operations are explicit and versioned (e.g. "front_bumper.offset_v1", "fender.widen_v1"), each
  implemented by a backend such as Blender's Python API (bpy, run headless:
  `blender -b -P op.py -- args`) or Unreal's Geometry Script / procedural meshes.
* The AI may only *select* an operation and bounded numeric parameters from a whitelist; it never
  emits raw geometry or scripts.
* Results must be re-imported through the same Interchange pipeline and registered as a new
  model version before the viewer can show them.
* Concept images are a separate output type and are never substituted for a 3D mesh.
"""
from __future__ import annotations

from dataclasses import dataclass

PIPELINE_VERSION = "0.0-not-implemented"


@dataclass(frozen=True)
class GeometryOperation:
    id: str            # e.g. "fender.widen_v1"
    description: str
    backend: str       # "blender" | "unreal_geometry_script"


# Empty on purpose: no geometry operation is reliable enough to offer yet.
OPERATIONS: dict[str, GeometryOperation] = {}


def capabilities() -> dict:
    return {
        "pipeline_version": PIPELINE_VERSION,
        "operations": [op.__dict__ for op in OPERATIONS.values()],
        "status": "planned",
        "message": "Geometry redesign (bumpers, fenders, diffusers, hoods, custom bodywork) is not "
                   "available in this MVP. Only material/finish configuration is applied to the 3D car.",
    }
