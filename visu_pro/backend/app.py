"""BMW Studio backend (FastAPI).

Run (from backend/):  uvicorn app:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from fastapi.responses import FileResponse

import feedback
import geometry
import keywords
import web_design
from ai import parse_structured
from config import REPO_ROOT
from ai import AIFailed, AIUnavailable, propose_design
from config import load_settings
from design import (DesignAction, DesignProposal, ResetDesign, SetPaint, SetWheelStyle, describe,
                    to_viewer_command, validate_actions)
from registry import MODELS, PAINTS, WHEEL_STYLES, ModelEntry, get_model
from viewer import ViewerClient, ViewerCommandFailed, ViewerUnavailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = load_settings()
FRONTEND_DIR = REPO_ROOT / "frontend"
viewer = ViewerClient(settings)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logging.getLogger("bmw").info("AI configured: %s (model %s); viewer port %d",
                                  settings.ai_configured, settings.openai_model, settings.viewer_control_port)
    await asyncio.to_thread(feedback.get_dataset)  # parse the xlsx files once at startup
    yield


app = FastAPI(title="BMW Studio API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


# --------------------------------------------------------------------------- request models
class _Req(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VisualizeRequest(_Req):
    model_id: str = Field(max_length=64)


class ManualDesignRequest(_Req):
    model_id: str = Field(max_length=64)
    actions: list[DesignAction] = Field(min_length=1, max_length=5)


class AIDesignRequest(_Req):
    model_id: str = Field(max_length=64)
    prompt: str = Field(min_length=3, max_length=1000)


class ResetRequest(_Req):
    model_id: str = Field(max_length=64)


def _model_or_404(model_id: str) -> ModelEntry:
    model = get_model(model_id)
    if model is None:
        raise HTTPException(404, detail=f"Unknown model '{model_id}'. Allowed: {sorted(MODELS)}")
    return model


# --------------------------------------------------------------------------- routes
@app.get("/api/health")
async def health():
    return {"status": "ok", "ai_configured": settings.ai_configured, "ai_model": settings.openai_model,
            "viewer": await viewer.status()}


@app.get("/api/models")
async def list_models():
    return {"models": [{
        "id": m.id, "display_name": m.display_name,
        "paints": [{"id": p, "label": PAINTS[p]} for p in m.paints],
        "wheel_styles": [{"id": w, "label": WHEEL_STYLES[w]} for w in m.wheel_styles],
        "notes": list(m.notes),
    } for m in MODELS.values()]}


@app.get("/api/viewer/status")
async def viewer_status():
    return await viewer.status()


@app.post("/api/visualize")
async def visualize(req: VisualizeRequest):
    model = _model_or_404(req.model_id)
    try:
        return await viewer.visualize(model.id)
    except FileNotFoundError as e:
        raise HTTPException(500, detail=str(e))
    except ViewerCommandFailed as e:
        raise HTTPException(502, detail=f"Viewer refused to open the model: {e}")


async def _apply(model: ModelEntry, actions: list[DesignAction]) -> dict:
    """Validate and execute actions; an action counts as applied only if Unreal confirms it."""
    valid, issues = validate_actions(model, actions)
    status = await viewer.status()
    if not status["reachable"]:
        raise HTTPException(503, detail="The Unreal viewer is not running. Click Visualize first.")
    loaded = (status.get("viewer") or {}).get("model_id")
    if loaded != model.id:
        raise HTTPException(409, detail=f"The viewer shows '{loaded}', not '{model.id}'. Click Visualize first.")
    results = []
    for action in valid:
        command, args = to_viewer_command(action)
        entry = {"action": action.model_dump(), "description": describe(action), "applied": False}
        try:
            reply = await viewer.send(command, args)
            entry["applied"] = bool(reply.get("applied"))
            entry["viewer_result"] = reply
        except (ViewerUnavailable, ViewerCommandFailed) as e:
            entry["error"] = str(e)
        results.append(entry)
    final = await viewer.status()
    return {"results": results, "rejected": [i.model_dump() for i in issues],
            "design_state": (final.get("viewer") or {}).get("design")}


@app.post("/api/design/apply")
async def apply_manual(req: ManualDesignRequest):
    return await _apply(_model_or_404(req.model_id), req.actions)


@app.post("/api/design/reset")
async def reset_design(req: ResetRequest):
    return await _apply(_model_or_404(req.model_id), [ResetDesign(type="reset_design")])


async def _interpret(model: ModelEntry, prompt: str) -> tuple[DesignProposal, str]:
    """AI proposal when OPENAI_API_KEY is set, otherwise the offline keyword demo mode."""
    if settings.ai_configured:
        try:
            proposal = await propose_design(settings, model, prompt)
        except AIUnavailable as e:
            raise HTTPException(503, detail=str(e))
        except AIFailed as e:
            raise HTTPException(502, detail=str(e))
        engine = f"OpenAI {settings.openai_model}"
    else:
        proposal, engine = keywords.interpret(prompt), "demo mode: keyword matcher (OPENAI_API_KEY not set)"
    # Re-validate on the server (types are already enforced by the schema).
    proposal = DesignProposal.model_validate(proposal.model_dump())
    valid, _issues = validate_actions(model, proposal.actions)
    proposal.actions = valid
    return proposal, engine


@app.post("/api/design/ai")
async def apply_ai(req: AIDesignRequest):
    model = _model_or_404(req.model_id)
    proposal, engine = await _interpret(model, req.prompt)
    applied = await _apply(model, proposal.actions) if proposal.actions else \
        {"results": [], "rejected": [], "design_state": None}
    return {"proposal": proposal.model_dump(), "engine": engine, **applied}


# --------------------------------------------------------------------------- web heat map app
class WebComponentRef(_Req):
    id: str = Field(pattern=r"^[a-z0-9-]{1,64}$")
    name: str = Field(max_length=80)


class WebDesignRequest(_Req):
    model_id: str = Field(max_length=64)
    prompt: str = Field(min_length=3, max_length=1000)
    component_id: str | None = Field(default=None, max_length=64)
    component_name: str | None = Field(default=None, max_length=80)
    components: list[WebComponentRef] = Field(default_factory=list, max_length=100)


@app.post("/api/web/design")
async def web_design_endpoint(req: WebDesignRequest):
    """Interpret a prompt into validated Level 1 / Level 2 web actions. Nothing is applied here: the
    browser applies them to its own 3D viewer and reports what it actually changed."""
    model = _model_or_404(req.model_id)
    comps = [c.model_dump() for c in req.components]
    if settings.ai_configured:
        instructions = web_design.build_instructions(model.display_name, comps, req.component_name)
        try:
            proposal = await parse_structured(settings, instructions, req.prompt, web_design.WebDesignProposal)
        except AIUnavailable as e:
            raise HTTPException(503, detail=str(e))
        except AIFailed as e:
            raise HTTPException(502, detail=str(e))
        engine = f"OpenAI {settings.openai_model}"
    else:
        proposal = web_design.keyword_proposal(req.prompt)
        engine = "demo mode: keyword matcher (OPENAI_API_KEY not set)"
    proposal = web_design.WebDesignProposal.model_validate(proposal.model_dump())
    actions, rejected = web_design.validate_web_actions(proposal.actions, comps)
    return {"engine": engine, "summary": proposal.summary, "actions": actions, "rejected": rejected,
            "unsupported": [u.model_dump() for u in proposal.unsupported]}


@app.get("/api/feedback/scores")
async def feedback_scores(series: str | None = None):
    if series and series not in feedback.SERIES:
        raise HTTPException(404, detail=f"Unknown series '{series}'. Allowed: {sorted(feedback.SERIES)}")
    ds = feedback.get_dataset()
    if ds.error:
        raise HTTPException(503, detail=ds.error)
    return ds.scores(series)


class DesignStateIn(_Req):
    paint: str | None = Field(default=None, max_length=32)
    wheel_style: str | None = Field(default=None, max_length=32)


class UnrealVisualizeRequest(_Req):
    model_id: str = Field(max_length=64)
    design: DesignStateIn = DesignStateIn()


def _unreal_configured() -> tuple[bool, str]:
    exe = Path(settings.ue_engine_dir) / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
    built = settings.unreal_project_path.parent / "Content" / "BMWStudio" / "Vehicles" / "BMW_M4_2021" / "SM_BMW_M4_2021.uasset"
    if not exe.is_file():
        return False, f"Unreal Engine not found at {exe}. Set UE_ENGINE_DIR in backend/.env."
    if not settings.unreal_project_path.is_file():
        return False, f"Unreal project not found: {settings.unreal_project_path}"
    if not built.is_file():
        return False, "Unreal content not built yet. Run .\\scripts\\build_unreal.ps1 once."
    return True, "Unreal viewer integration is configured (local standalone viewer)."


@app.get("/api/unreal/status")
async def unreal_status():
    ok, msg = _unreal_configured()
    if not ok:
        return {"configured": False, "phase": "not_configured", "message": msg}
    st = await viewer.status()
    return {"configured": True, "phase": st["phase"], "message": msg, "error": st.get("error")}


@app.post("/api/unreal/visualize")
async def unreal_visualize(req: UnrealVisualizeRequest):
    model = _model_or_404(req.model_id)
    ok, msg = _unreal_configured()
    if not ok:
        return {"configured": False, "phase": "not_configured", "message": msg}
    actions: list = []
    if req.design.paint:
        actions.append(SetPaint(type="set_paint", paint_id=req.design.paint))
    if req.design.wheel_style:
        actions.append(SetWheelStyle(type="set_wheel_style", style_id=req.design.wheel_style))
    valid, _ = validate_actions(model, actions)
    viewer.pending_design = [to_viewer_command(a) for a in valid]
    try:
        result = await viewer.visualize(model.id)
    except FileNotFoundError as e:
        return {"configured": False, "phase": "not_configured", "message": str(e)}
    except ViewerCommandFailed as e:
        return {"configured": True, "phase": "error", "message": str(e), "error": str(e)}
    return {"configured": True, "phase": result["phase"], "message": result["message"]}


@app.get("/", include_in_schema=False)
async def index():
    built = FRONTEND_DIR / "dist" / "index.html"
    if built.is_file():
        return FileResponse(built)
    raise HTTPException(404, detail="Frontend not built. Use the Vite dev server (cd frontend; npm run dev) "
                                    "or run npm run build.")


@app.get("/api/capabilities")
async def capabilities():
    return {
        "material_configuration": {"status": "available", "actions": ["set_paint", "set_wheel_style", "reset_design"]},
        "component_replacement": {"status": "planned", "message": "No alternate 3D components are registered yet."},
        "geometry_modification": geometry.capabilities(),
        "concept_image": {"status": "not_offered",
                          "message": "Concept images are never substituted for 3D changes."},
    }
