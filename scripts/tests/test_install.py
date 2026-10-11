"""Checks for the pure helpers of scripts/install.py (nothing here installs or starts anything)."""
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import install  # noqa: E402


def test_mcp_entry_is_added_and_other_servers_are_kept(tmp_path):
    config = tmp_path / "config" / "mcp.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
    install.add_mcp_server(config, "ehl-market", {"command": "py", "args": ["-m", "ehl_market.server"]})
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["mcpServers"]["other"] == {"command": "x"}
    assert data["mcpServers"]["ehl-market"]["args"] == ["-m", "ehl_market.server"]


def test_mcp_file_is_created_when_missing(tmp_path):
    config = tmp_path / "config" / "mcp.json"
    install.add_mcp_server(config, "ehl-market", {"command": "py"})
    assert json.loads(config.read_text(encoding="utf-8")) == {"mcpServers": {"ehl-market": {"command": "py"}}}


def test_venv_python_path_per_platform(tmp_path):
    assert install.venv_python(tmp_path, windows=True) == tmp_path / "Scripts" / "python.exe"
    assert install.venv_python(tmp_path, windows=False) == tmp_path / "bin" / "python"


def test_openai_key_from_environment_wins(tmp_path):
    (tmp_path / "search").mkdir()
    (tmp_path / "search" / ".env").write_text("OPENAI_API_KEY=from-file\n", encoding="utf-8")
    assert install.find_openai_key(tmp_path, {"OPENAI_API_KEY": "from-env"}) == "from-env"


def test_openai_key_from_search_env_then_root_env(tmp_path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=root\n", encoding="utf-8")
    assert install.find_openai_key(tmp_path, {}) == "root"
    (tmp_path / "search").mkdir()
    (tmp_path / "search" / ".env").write_text("# comment\nOPENAI_API_KEY = 'search'\n", encoding="utf-8")
    assert install.find_openai_key(tmp_path, {}) == "search"


def test_no_openai_key(tmp_path):
    assert install.find_openai_key(tmp_path, {}) is None


def test_car_zips_match_prepare_local():
    sys.path.insert(0, str(SCRIPTS.parent / "demo" / "visu"))
    import prepare_local
    assert {car: zip_name for car, (zip_name, _) in install.CARS.items()} == prepare_local.CARS


def test_missing_cars_lists_only_absent_models(tmp_path):
    models = tmp_path / "models"
    (models / "bmw-x1-2020").mkdir(parents=True)
    (models / "bmw-x1-2020" / "scene.gltf").write_text("{}", encoding="utf-8")
    missing = install.missing_cars(models)
    assert "bmw-x1-2020" not in missing
    assert set(missing) == {"bmw-x5-2019", "bmw-x7-2019"}
