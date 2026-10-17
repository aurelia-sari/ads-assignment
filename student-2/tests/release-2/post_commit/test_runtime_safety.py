"""Offline checks: disabled integrations never reach MCP/AI or mutate storage."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "api"))
from app import app


@pytest.mark.parametrize("flag,path", [
    ("AI_MODE_ENABLED", "/ai/recommend"), ("MCP_ENABLED", "/mcp/search-places"),
    ("RAG_ENABLED", "/rag/reindex"), ("MULTI_AGENT_ENABLED", "/agents/workflows"),
])
def test_disabled_before_any_transport(flag, path):
    with patch.dict(os.environ, {flag: "false"}), patch("requests.sessions.Session.request") as transport:
        response = app.test_client().post(path, json={})
        assert response.status_code == 503
        transport.assert_not_called()


def test_ai_enabled_keeps_input_validation():
    with patch.dict(os.environ, {"AI_MODE_ENABLED": "true"}):
        assert app.test_client().post("/ai/recommend", json={}).status_code == 400


def test_db_reinitialisation_preserves_data(tmp_path):
    import sqlite3
    db = tmp_path / "mounted" / "student2.db"
    env = {**os.environ, "DB_PATH": str(db), "PYTHONDONTWRITEBYTECODE": "1"}
    command = [sys.executable, "-B", str(ROOT / "db/init_db.py")]
    subprocess.run(command, env=env, check=True, capture_output=True, timeout=30)  # noqa: S603 fixed seed script with current Python
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE places SET description='Persistence sentinel' WHERE id=1")
    subprocess.run(command, env=env, check=True, capture_output=True, timeout=30)  # noqa: S603 fixed seed script with current Python
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT description FROM places WHERE id=1").fetchone()[0] == "Persistence sentinel"
    with patch.dict(os.environ, {"DB_PATH": str(db)}):
        spec = importlib.util.spec_from_file_location("student2_database_app", ROOT / "db/app.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.DATABASE_NAME == str(db)
        assert module.app.test_client().get("/places/1").json["description"] == "Persistence sentinel"
