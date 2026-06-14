import sqlite3
import time
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient


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
    now = time.time()
    conn.executemany(
        "INSERT INTO measurements (sensor_name, key, value, timestamp) VALUES (?, ?, ?, ?)",
        [
            ("Hive1", "weight_kg", 45.2, now - 10),
            ("Hive1", "temperature_c", 34.1, now - 10),
        ],
    )
    conn.commit()
    conn.close()
    return p


@pytest.fixture
def client(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import honeypi_dashboard.db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    from honeypi_dashboard.main import app
    return TestClient(app)


def test_get_latest_returns_values(client: TestClient) -> None:
    resp = client.get("/api/data/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    keys = {row["key"] for row in data}
    assert "weight_kg" in keys


def test_get_history_returns_rows(client: TestClient) -> None:
    resp = client.get("/api/data/history?hours=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_config_returns_json(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import honeypi_dashboard.api.config as cfg_module
    cfg_file = tmp_path / "honeypi.json"
    cfg_file.write_text(json.dumps({"interval": 300, "sensors": [], "exporters": {}}))
    monkeypatch.setattr(cfg_module, "CONFIG_PATH", cfg_file)
    resp = client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json()["interval"] == 300


def test_post_config_writes_file(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import honeypi_dashboard.api.config as cfg_module
    cfg_file = tmp_path / "honeypi.json"
    cfg_file.write_text("{}")
    monkeypatch.setattr(cfg_module, "CONFIG_PATH", cfg_file)
    monkeypatch.setattr(cfg_module, "_restart_agent", lambda: None)
    resp = client.post("/api/config", json={"interval": 120, "sensors": [], "exporters": {}})
    assert resp.status_code == 200
    assert json.loads(cfg_file.read_text())["interval"] == 120
