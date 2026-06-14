from __future__ import annotations
import json
import sqlite3
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def cfg_file(tmp_path: Path) -> Path:
    p = tmp_path / "hanipi.json"
    p.write_text(json.dumps({"hives": [], "sensors": [], "exporters": {}}))
    return p


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "data.db"
    conn = sqlite3.connect(str(p))
    conn.execute("""
        CREATE TABLE measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_name TEXT, key TEXT, value REAL, timestamp REAL
        )
    """)
    conn.commit()
    conn.close()
    return p


@pytest.fixture
def client(cfg_file: Path, db_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import hanipi_dashboard.api.config as cfg_module
    import hanipi_dashboard.db as db_module
    monkeypatch.setattr(cfg_module, "CONFIG_PATH", cfg_file)
    monkeypatch.setattr(cfg_module, "_restart_agent", lambda: None)
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    # Patch _systemctl used by hives router via imported name in config
    monkeypatch.setattr(cfg_module, "_systemctl", lambda *a, **kw: None)

    from hanipi_dashboard.main import app
    return TestClient(app)


# ── GET /api/hives ───────────────────────────────────────────────────────────

def test_list_hives_empty(client: TestClient) -> None:
    r = client.get("/api/hives")
    assert r.status_code == 200
    assert r.json() == []


# ── POST /api/hives ──────────────────────────────────────────────────────────

def test_add_hive_creates_with_id(client: TestClient, cfg_file: Path) -> None:
    r = client.post("/api/hives", json={"name": "Garten", "color": "#10b981"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Garten"
    assert body["color"] == "#10b981"
    assert "id" in body and body["id"]


def test_add_hive_persists_to_config(client: TestClient, cfg_file: Path) -> None:
    client.post("/api/hives", json={"name": "Dach", "color": "#3b82f6"})
    data = json.loads(cfg_file.read_text())
    assert len(data["hives"]) == 1
    assert data["hives"][0]["name"] == "Dach"


def test_add_multiple_hives(client: TestClient) -> None:
    client.post("/api/hives", json={"name": "A"})
    client.post("/api/hives", json={"name": "B"})
    r = client.get("/api/hives")
    assert len(r.json()) == 2


# ── PUT /api/hives/{id} ──────────────────────────────────────────────────────

def test_update_hive_changes_name_and_color(client: TestClient) -> None:
    hive = client.post("/api/hives", json={"name": "Alt", "color": "#aaa"}).json()
    hive_id = hive["id"]

    r = client.put(f"/api/hives/{hive_id}", json={"name": "Neu", "color": "#111"})
    assert r.status_code == 200
    assert r.json()["name"] == "Neu"
    assert r.json()["color"] == "#111"


def test_update_nonexistent_hive_returns_404(client: TestClient) -> None:
    r = client.put("/api/hives/nonexistent", json={"name": "X"})
    assert r.status_code == 404


# ── DELETE /api/hives/{id} ───────────────────────────────────────────────────

def test_delete_hive_removes_it(client: TestClient) -> None:
    hive = client.post("/api/hives", json={"name": "Temp"}).json()
    r = client.delete(f"/api/hives/{hive['id']}")
    assert r.status_code == 200

    remaining = client.get("/api/hives").json()
    assert all(h["id"] != hive["id"] for h in remaining)


def test_delete_hive_clears_sensor_hive_id(client: TestClient, cfg_file: Path) -> None:
    hive = client.post("/api/hives", json={"name": "Test"}).json()
    hive_id = hive["id"]

    # Write a sensor assigned to this hive directly into the config
    data = json.loads(cfg_file.read_text())
    data["sensors"] = [{"type": "hx711", "name": "Waage", "hive_id": hive_id}]
    cfg_file.write_text(json.dumps(data))

    client.delete(f"/api/hives/{hive_id}")

    updated = json.loads(cfg_file.read_text())
    for sensor in updated.get("sensors", []):
        assert "hive_id" not in sensor or sensor["hive_id"] != hive_id


def test_delete_nonexistent_hive_still_returns_ok(client: TestClient) -> None:
    r = client.delete("/api/hives/doesnotexist")
    assert r.status_code == 200
