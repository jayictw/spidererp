from __future__ import annotations

import os
import subprocess
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


def _db_url() -> str:
    tmp_dir = Path(__file__).resolve().parents[1] / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / f"migration-smoke-{uuid4().hex}.db"
    return f"sqlite:///{db_path}"


def test_alembic_upgrade_head_and_api_smoke():
    db_url = _db_url()
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url

    upgrade = subprocess.run(
        ["py", "-3", "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        check=False,
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        env=env,
    )
    assert upgrade.returncode == 0, upgrade.stderr

    current = subprocess.run(
        ["py", "-3", "-m", "alembic", "-c", "alembic.ini", "current"],
        check=False,
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        env=env,
    )
    assert current.returncode == 0, current.stderr
    assert "0003_v02_fix_rule_versions_updated_at" in current.stdout

    app = create_app(database_url=db_url)
    client = TestClient(app)
    for path in ("/api/v1/jobs", "/api/v1/rules", "/api/v1/samples", "/api/v1/audit"):
        resp = client.get(path)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "items" in body["data"]
        assert "meta" in body["data"]

