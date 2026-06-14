from __future__ import annotations
import sqlite3
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def db_with_data(tmp_path: Path) -> Path:
    p = tmp_path / "data.db"
    conn = sqlite3.connect(str(p))
    conn.execute("""
        CREATE TABLE measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_name TEXT, key TEXT, value REAL, timestamp REAL, hive_id TEXT
        )
    """)
    now = time.time()
    conn.executemany(
        "INSERT INTO measurements (sensor_name, key, value, timestamp, hive_id) VALUES (?,?,?,?,?)",
        [
            ("Waage", "weight_kg", 42.0, now, None),
            ("Waage", "temperature_c", 35.0, now, None),
            ("Aussen", "humidity_pct", 60.0, now, None),
            ("Aussen", "pressure_hpa", 1013.0, now, None),
        ],
    )
    conn.commit()
    conn.close()
    return p


@pytest.fixture
def client(db_with_data: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import hanipi_dashboard.db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_with_data)
    from hanipi_dashboard.main import app
    return TestClient(app)


def test_thingspeak_keys_returns_dotted_list(client: TestClient) -> None:
    r = client.get("/api/thingspeak/keys")
    assert r.status_code == 200
    keys = r.json()
    assert "Waage.weight_kg" in keys
    assert "Waage.temperature_c" in keys
    assert "Aussen.humidity_pct" in keys
    assert "Aussen.pressure_hpa" in keys


def test_thingspeak_keys_sorted(client: TestClient) -> None:
    r = client.get("/api/thingspeak/keys")
    keys = r.json()
    assert keys == sorted(keys)


def test_thingspeak_keys_empty_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty_db = tmp_path / "empty.db"
    conn = sqlite3.connect(str(empty_db))
    conn.execute("""
        CREATE TABLE measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_name TEXT, key TEXT, value REAL, timestamp REAL
        )
    """)
    conn.commit()
    conn.close()

    import hanipi_dashboard.db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", empty_db)

    from hanipi_dashboard.main import app
    from fastapi.testclient import TestClient as TC
    c = TC(app)
    r = c.get("/api/thingspeak/keys")
    assert r.status_code == 200
    assert r.json() == []


# ── ThingSpeakExporter: sensor_name.key mapping ──────────────────────────────

def test_thingspeak_exporter_sensor_dot_key_mapping() -> None:
    import time as t
    from unittest.mock import patch
    from hanipi_agent.exporters.thingspeak import ThingSpeakExporter
    from hanipi_agent.sensors.base import Measurement
    import pytest as _pytest

    cfg = {
        "enabled": True,
        "api_key": "KEY",
        "field_mapping": {
            "Waage.weight_kg": "field1",
            "Aussen.temperature_c": "field2",
        },
    }
    exp = ThingSpeakExporter(cfg)

    with patch("hanipi_agent.exporters.thingspeak.httpx.get") as mock_get:
        m = Measurement(name="Waage", values={"weight_kg": 45.0}, timestamp=t.time())
        exp.export(m)
        params = mock_get.call_args.kwargs["params"]
        assert params["field1"] == _pytest.approx(45.0)
        assert "field2" not in params


def test_thingspeak_exporter_fallback_to_key_only() -> None:
    import time as t
    from unittest.mock import patch
    from hanipi_agent.exporters.thingspeak import ThingSpeakExporter
    from hanipi_agent.sensors.base import Measurement
    import pytest as _pytest

    cfg = {
        "enabled": True,
        "api_key": "KEY",
        "field_mapping": {"weight_kg": "field1"},  # old-style key without sensor prefix
    }
    exp = ThingSpeakExporter(cfg)

    with patch("hanipi_agent.exporters.thingspeak.httpx.get") as mock_get:
        m = Measurement(name="AnyName", values={"weight_kg": 42.0}, timestamp=t.time())
        exp.export(m)
        params = mock_get.call_args.kwargs["params"]
        assert params["field1"] == _pytest.approx(42.0)


def test_thingspeak_exporter_skips_unmapped_fields() -> None:
    import time as t
    from unittest.mock import patch
    from hanipi_agent.exporters.thingspeak import ThingSpeakExporter
    from hanipi_agent.sensors.base import Measurement

    cfg = {
        "enabled": True,
        "api_key": "KEY",
        "field_mapping": {"Waage.weight_kg": "field1"},
    }
    exp = ThingSpeakExporter(cfg)

    with patch("hanipi_agent.exporters.thingspeak.httpx.get") as mock_get:
        # Sensor with no mapped fields
        m = Measurement(name="Aussen", values={"temperature_c": 30.0}, timestamp=t.time())
        exp.export(m)
        mock_get.assert_not_called()
