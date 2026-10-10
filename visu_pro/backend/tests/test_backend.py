"""Backend tests that run without Unreal or an OpenAI key.

A fake viewer (asyncio TCP server speaking the same JSON-lines protocol) stands in for Unreal.
Run from backend/:  .venv\\Scripts\\python -m pytest -q
"""
import asyncio
import json
import os
import socket
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = _free_port()
os.environ["VIEWER_CONTROL_PORT"] = str(PORT)
os.environ["VIEWER_TOKEN"] = "test-token"
os.environ["OPENAI_API_KEY"] = ""
os.environ["UE_ENGINE_DIR"] = str(Path(__file__).parent / "no-engine-here")

from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402
from design import DesignProposal, SetPaint, SetWheelStyle, ResetDesign, validate_actions  # noqa: E402
from registry import MODELS  # noqa: E402

MODEL = "bmw-m4-competition-2021"


class FakeViewer:
    """Minimal stand-in for bmw_viewer.runtime with the same command semantics."""

    def __init__(self):
        self.model_id = None
        self.design = {"paint": None, "wheel_style": None}
        self.received = []

    def handle(self, msg):
        self.received.append(msg)
        if msg.get("token") != "test-token":
            return {"id": msg.get("id"), "ok": False, "error": "unauthorized"}
        cmd, args = msg["command"], msg.get("args", {})
        if cmd == "get_viewer_status":
            return {"id": msg["id"], "ok": True, "result": {"ready": self.model_id is not None,
                                                             "model_id": self.model_id, "design": self.design}}
        if cmd == "open_model":
            self.model_id = args["model_id"]
            return {"id": msg["id"], "ok": True, "result": {"loaded": True, "model_id": self.model_id}}
        if cmd == "set_paint":
            self.design["paint"] = args["paint_id"]
            return {"id": msg["id"], "ok": True, "result": {"applied": True}}
        if cmd == "set_wheel_style":
            self.design["wheel_style"] = args["style_id"]
            return {"id": msg["id"], "ok": True, "result": {"applied": True}}
        if cmd == "reset_design":
            self.design = {"paint": None, "wheel_style": None}
            return {"id": msg["id"], "ok": True, "result": {"applied": True}}
        return {"id": msg["id"], "ok": False, "error": "unsupported"}


@pytest.fixture()
def fake_viewer():
    viewer = FakeViewer()
    loop = asyncio.new_event_loop()
    started = threading.Event()

    async def on_client(reader, writer):
        line = await reader.readline()
        writer.write((json.dumps(viewer.handle(json.loads(line))) + "\n").encode())
        await writer.drain()
        writer.close()

    async def main():
        server = await asyncio.start_server(on_client, "127.0.0.1", PORT)
        started.set()
        async with server:
            await server.serve_forever()

    t = threading.Thread(target=lambda: loop.run_until_complete(main()), daemon=True)
    t.start()
    started.wait(5)
    yield viewer
    loop.call_soon_threadsafe(loop.stop)


@pytest.fixture()
def client():
    app_module.viewer.state = type(app_module.viewer.state)()  # reset backend viewer state
    return TestClient(app_module.app)


# ---------------------------------------------------------------- pure validation
def test_registry_contains_m4():
    assert MODELS[MODEL].display_name == "2021 BMW M4 Competition"


def test_validate_orders_and_dedupes():
    actions = [SetWheelStyle(type="set_wheel_style", style_id="sport"),
               SetPaint(type="set_paint", paint_id="white"),
               SetPaint(type="set_paint", paint_id="racing_red"),
               ResetDesign(type="reset_design")]
    valid, issues = validate_actions(MODELS[MODEL], actions)
    assert [a.type for a in valid] == ["reset_design", "set_paint", "set_wheel_style"]
    assert valid[1].paint_id == "racing_red" and not issues


def test_proposal_schema_rejects_invented_values():
    with pytest.raises(Exception):
        DesignProposal.model_validate({"summary": "x", "unsupported": [],
                                       "actions": [{"type": "set_paint", "paint_id": "hot_pink"}]})
    with pytest.raises(Exception):
        DesignProposal.model_validate({"summary": "x", "unsupported": [],
                                       "actions": [{"type": "delete_mesh", "path": "C:/"}]})
    with pytest.raises(Exception):
        DesignProposal.model_validate({"summary": "x", "unsupported": [],
                                       "actions": [{"type": "set_paint", "paint_id": "black", "mesh": "/Game/x"}]})


# ---------------------------------------------------------------- API
def test_models_endpoint(client):
    data = client.get("/api/models").json()
    assert data["models"][0]["id"] == MODEL
    assert {p["id"] for p in data["models"][0]["paints"]} == {"black", "white", "silver", "racing_red", "midnight_blue"}


def test_visualize_rejects_unknown_model(client):
    r = client.post("/api/visualize", json={"model_id": "../../windows/system32"})
    assert r.status_code == 404


def test_visualize_rejects_extra_fields(client):
    r = client.post("/api/visualize", json={"model_id": MODEL, "exe_path": "C:/evil.exe"})
    assert r.status_code == 422


def test_visualize_and_apply_with_viewer(client, fake_viewer):
    r = client.post("/api/visualize", json={"model_id": MODEL})
    assert r.status_code == 200 and r.json()["phase"] == "ready"
    r = client.post("/api/design/apply", json={"model_id": MODEL, "actions": [
        {"type": "set_paint", "paint_id": "midnight_blue"}, {"type": "set_wheel_style", "style_id": "sport"}]})
    body = r.json()
    assert r.status_code == 200, body
    assert all(x["applied"] for x in body["results"])
    assert body["design_state"] == {"paint": "midnight_blue", "wheel_style": "sport"}
    assert all(m.get("token") == "test-token" for m in fake_viewer.received)
    r = client.post("/api/design/reset", json={"model_id": MODEL})
    assert r.json()["design_state"] == {"paint": None, "wheel_style": None}


def test_apply_without_viewer_is_503(client):
    r = client.post("/api/design/apply", json={"model_id": MODEL,
                                               "actions": [{"type": "set_paint", "paint_id": "black"}]})
    assert r.status_code == 503


def test_visualize_without_engine_reports_error(client):
    r = client.post("/api/visualize", json={"model_id": MODEL})
    assert r.status_code == 500 and "Unreal executable not found" in r.json()["detail"]


def test_ai_without_key_is_clear_error(client):
    r = client.post("/api/design/ai", json={"model_id": MODEL, "prompt": "make it red"})
    assert r.status_code == 503 and "OPENAI_API_KEY" in r.json()["detail"]


def test_ai_flow_with_fake_model(client, fake_viewer, monkeypatch):
    async def fake_propose(settings, model, prompt):
        return DesignProposal.model_validate({
            "summary": "Midnight blue with sport wheels.",
            "actions": [{"type": "set_paint", "paint_id": "midnight_blue"},
                        {"type": "set_wheel_style", "style_id": "sport"}],
            "unsupported": [{"request": "wider fenders", "category": "geometry_modification",
                             "reason": "Geometry changes are not supported yet."}]})
    monkeypatch.setattr(app_module, "propose_design", fake_propose)
    client.post("/api/visualize", json={"model_id": MODEL})
    r = client.post("/api/design/ai", json={"model_id": MODEL, "prompt": "midnight blue, sporty wheels, wider fenders"})
    body = r.json()
    assert r.status_code == 200, body
    assert [x["applied"] for x in body["results"]] == [True, True]
    assert body["proposal"]["unsupported"][0]["category"] == "geometry_modification"


def test_openai_schema_is_strict_compatible():
    """The proposal schema must convert to an OpenAI strict JSON schema (no oneOf, all required)."""
    from openai.lib._pydantic import to_strict_json_schema
    schema = json.dumps(to_strict_json_schema(DesignProposal))
    assert "oneOf" not in schema and '"additionalProperties": false' in schema
