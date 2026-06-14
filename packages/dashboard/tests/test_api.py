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
