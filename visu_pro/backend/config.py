"""Configuration from environment variables (and an optional backend/.env file)."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")


def _env(name: str, default: str) -> str:
    v = os.environ.get(name, "").strip()
    return v or default


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    openai_timeout: float
    ue_engine_dir: str
    unreal_project_path: Path
    viewer_control_port: int
    viewer_token: str
    viewer_res_x: int
    viewer_res_y: int
    viewer_command_timeout: float
    viewer_open_timeout: float
    viewer_startup_timeout: float
    cors_origins: tuple[str, ...]

    @property
    def ai_configured(self) -> bool:
        return bool(self.openai_api_key)


def load_settings() -> Settings:
    return Settings(
        openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
        openai_model=_env("OPENAI_MODEL", "gpt-5-mini"),
        openai_timeout=float(_env("OPENAI_TIMEOUT_SECONDS", "60")),
        ue_engine_dir=_env("UE_ENGINE_DIR", r"C:\Program Files\Epic Games\UE_5.8"),
        unreal_project_path=Path(_env("UNREAL_PROJECT_PATH",
                                      str(REPO_ROOT / "unreal" / "BMWVisualizer" / "BMWVisualizer.uproject"))),
        viewer_control_port=int(_env("VIEWER_CONTROL_PORT", "30777")),
        # A per-run random token unless configured; passed to the viewer when the backend launches it.
        viewer_token=_env("VIEWER_TOKEN", secrets.token_hex(16)),
        viewer_res_x=int(_env("VIEWER_RES_X", "1600")),
        viewer_res_y=int(_env("VIEWER_RES_Y", "900")),
        viewer_command_timeout=float(_env("VIEWER_COMMAND_TIMEOUT_SECONDS", "10")),
        viewer_open_timeout=float(_env("VIEWER_OPEN_TIMEOUT_SECONDS", "60")),
        viewer_startup_timeout=float(_env("VIEWER_STARTUP_TIMEOUT_SECONDS", "1800")),
        cors_origins=tuple(o.strip() for o in _env(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()),
    )
