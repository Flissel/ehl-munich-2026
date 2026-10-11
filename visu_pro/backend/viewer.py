"""Backend side of the viewer link: launching the Unreal viewer and talking to its control port.

Transport: newline-delimited JSON over TCP on 127.0.0.1 (see unreal/.../bmw_viewer/runtime.py).
The executable, project and arguments come from trusted server configuration only.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from config import Settings

log = logging.getLogger("bmw.viewer")
_ids = itertools.count(1)
_SAFE_ID = re.compile(r"^[a-z0-9-]{1,64}$")


class ViewerUnavailable(Exception):
    """The viewer process is not reachable on its control port."""


class ViewerCommandFailed(Exception):
    """The viewer answered but refused or failed the command."""


@dataclass
class ViewerState:
    phase: str = "not_running"  # not_running | starting | loading_model | ready | error
    requested_model: str | None = None
    launched_at: float | None = None
    last_error: str | None = None
    last_status: dict | None = None
    process: subprocess.Popen | None = field(default=None, repr=False)


class ViewerClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self.state = ViewerState()
        self._open_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        # (command, args) pairs to apply once the model is displayed (e.g. design state from the web app)
        self.pending_design: list[tuple[str, dict]] = []

    # ------------------------------------------------------------------ transport
    async def send(self, command: str, args: dict | None = None, timeout: float | None = None) -> dict:
        timeout = timeout or self.s.viewer_command_timeout
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", self.s.viewer_control_port), timeout=2.0)
        except (OSError, asyncio.TimeoutError) as e:
            raise ViewerUnavailable(f"viewer not reachable on 127.0.0.1:{self.s.viewer_control_port}") from e
        try:
            msg = {"id": next(_ids), "token": self.s.viewer_token, "command": command, "args": args or {}}
            writer.write((json.dumps(msg) + "\n").encode())
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=timeout)
        except asyncio.TimeoutError as e:
            raise ViewerUnavailable(f"viewer did not answer '{command}' within {timeout:.0f}s") from e
        except OSError as e:
            raise ViewerUnavailable(f"connection to viewer lost: {e}") from e
        finally:
            writer.close()
        if not line:
            raise ViewerUnavailable("viewer closed the connection")
        reply = json.loads(line)
        if not reply.get("ok"):
            raise ViewerCommandFailed(reply.get("error") or "unknown viewer error")
        return reply.get("result") or {}

    # ------------------------------------------------------------------ status
    def process_alive(self) -> bool:
        p = self.state.process
        return p is not None and p.poll() is None

    async def status(self) -> dict:
        try:
            st = await self.send("get_viewer_status", timeout=3.0)
        except (ViewerUnavailable, ViewerCommandFailed) as e:
            st = None
            if self.state.phase in ("ready", "loading_model") and not self.process_alive():
                self.state.phase = "not_running"
            elif self.state.phase == "starting" and self.state.process is not None and not self.process_alive():
                self.state.phase = "error"
                self.state.last_error = f"viewer process exited (code {self.state.process.returncode})"
            reachable_error = str(e)
        else:
            reachable_error = None
            self.state.last_status = st
            if st.get("ready"):
                self.state.phase = "ready"
            elif self.state.phase in ("not_running", "error"):
                self.state.phase = "loading_model" if self.state.requested_model else "starting"
        return {
            "phase": self.state.phase,
            "reachable": st is not None,
            "process_launched_by_backend": self.state.process is not None,
            "process_alive": self.process_alive(),
            "requested_model": self.state.requested_model,
            "viewer": st,
            "error": self.state.last_error if self.state.phase == "error" else None,
            "detail": reachable_error,
            "seconds_since_launch": round(time.time() - self.state.launched_at) if self.state.launched_at else None,
        }

    # ------------------------------------------------------------------ launch / open
    def _launch(self, model_id: str) -> None:
        if not _SAFE_ID.match(model_id):  # defence in depth; model_id is already registry-validated
            raise ValueError("invalid model id")
        exe = Path(self.s.ue_engine_dir) / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
        project = self.s.unreal_project_path
        if not exe.is_file():
            raise FileNotFoundError(f"Unreal executable not found: {exe} (set UE_ENGINE_DIR)")
        if not project.is_file():
            raise FileNotFoundError(f"Unreal project not found: {project}")
        args = [str(exe), str(project), "-game", "-windowed",
                f"-ResX={self.s.viewer_res_x}", f"-ResY={self.s.viewer_res_y}", "-nosplash",
                "-BMWViewer", f"-BMWControlPort={self.s.viewer_control_port}", f"-BMWModel={model_id}", "-log"]
        if self.s.viewer_token:
            args.append(f"-BMWToken={self.s.viewer_token}")
        log.info("Launching viewer: %s", " ".join(a for a in args if not a.startswith("-BMWToken")))
        self.state.process = subprocess.Popen(args, cwd=str(project.parent))  # no shell
        self.state.launched_at = time.time()

    async def visualize(self, model_id: str) -> dict:
        """Make sure the viewer runs and shows `model_id`. Returns immediately with the phase."""
        async with self._lock:
            self.state.requested_model = model_id
            self.state.last_error = None
            try:
                result = await self.send("open_model", {"model_id": model_id}, timeout=self.s.viewer_open_timeout)
            except ViewerUnavailable:
                if not self.process_alive():
                    self._launch(model_id)
                self.state.phase = "starting"
                self._start_open_task(model_id)
                return {"phase": "starting", "message": "Launching the Unreal viewer..."}
            if result.get("loaded"):
                self.state.phase = "ready"
                await self._apply_pending_design()
                return {"phase": "ready", "message": f"{model_id} is displayed", "viewer": result}
            self.state.phase = "loading_model"
            self._start_open_task(model_id)
            return {"phase": "loading_model", "message": "Viewer is starting its world..."}

    async def _apply_pending_design(self) -> None:
        """Send design commands queued by the web app; failures are recorded, not raised."""
        pending, self.pending_design = self.pending_design, []
        for command, args in pending:
            try:
                await self.send(command, args)
            except (ViewerUnavailable, ViewerCommandFailed) as e:
                log.warning("Could not apply %s %s in viewer: %s", command, args, e)
                self.state.last_error = f"{command} failed: {e}"

    def _start_open_task(self, model_id: str) -> None:
        if self._open_task and not self._open_task.done():
            self._open_task.cancel()
        self._open_task = asyncio.create_task(self._wait_and_open(model_id))

    async def _wait_and_open(self, model_id: str) -> None:
        deadline = time.time() + self.s.viewer_startup_timeout
        while time.time() < deadline:
            if self.state.process is not None and not self.process_alive():
                self.state.phase = "error"
                self.state.last_error = f"viewer process exited (code {self.state.process.returncode})"
                return
            try:
                result = await self.send("open_model", {"model_id": model_id}, timeout=self.s.viewer_open_timeout)
                if result.get("loaded"):
                    self.state.phase = "ready"
                    log.info("Viewer shows %s", model_id)
                    await self._apply_pending_design()
                    return
                self.state.phase = "loading_model"
            except ViewerUnavailable:
                pass  # still starting (first launch compiles shaders)
            except ViewerCommandFailed as e:
                self.state.phase = "error"
                self.state.last_error = str(e)
                return
            await asyncio.sleep(2.0)
        self.state.phase = "error"
        self.state.last_error = f"viewer did not become ready within {self.s.viewer_startup_timeout:.0f}s"
