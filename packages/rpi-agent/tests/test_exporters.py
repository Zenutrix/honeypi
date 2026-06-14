import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from honeypi_agent.exporters.base import BaseExporter
from honeypi_agent.sensors.base import Measurement


class ConcreteExporter(BaseExporter):
    def __init__(self) -> None:
        self.exported: list[Measurement] = []

    def export(self, measurement: Measurement) -> None:
        self.exported.append(measurement)


def test_exporter_receives_measurement() -> None:
    exp = ConcreteExporter()
    m = Measurement(name="Test", values={"weight": 10.0}, timestamp=time.time())
    exp.export(m)
    assert len(exp.exported) == 1
    assert exp.exported[0].name == "Test"


from honeypi_agent.exporters.local import LocalExporter


def test_local_exporter_stores_measurement(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    exp = LocalExporter({"enabled": True, "db_path": db})
    m = Measurement(name="Hive1", values={"weight_kg": 45.2, "temperature_c": 34.1}, timestamp=time.time())
    exp.export(m)
    exp.close()

    import sqlite3
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT sensor_name, key, value FROM measurements").fetchall()
    conn.close()

    assert len(rows) == 2
    keys = {r[1] for r in rows}
    assert "weight_kg" in keys
    assert "temperature_c" in keys


from honeypi_agent.exporters.thingspeak import ThingSpeakExporter


def test_thingspeak_sends_mapped_fields() -> None:
    cfg = {
        "enabled": True,
        "api_key": "TESTKEY123",
        "field_mapping": {"weight_kg": "field1", "temperature_c": "field2"},
    }
    m = Measurement(name="Hive1", values={"weight_kg": 45.2, "temperature_c": 34.1}, timestamp=time.time())

    with patch("honeypi_agent.exporters.thingspeak.httpx.get") as mock_get:
        exp = ThingSpeakExporter(cfg)
        exp.export(m)
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        params = kwargs["params"]
        assert params["api_key"] == "TESTKEY123"
        assert params["field1"] == pytest.approx(45.2)
        assert params["field2"] == pytest.approx(34.1)


from honeypi_agent.exporters.influxdb import InfluxDBExporter


def test_influxdb_writes_point(mocker: MagicMock) -> None:
    mock_client_cls = mocker.patch("honeypi_agent.exporters.influxdb.InfluxDBClient")
    mock_client = mock_client_cls.return_value
    mock_write_api = mock_client.write_api.return_value

    cfg = {"enabled": True, "url": "http://localhost:8086", "token": "tok", "org": "myorg", "bucket": "honeypi"}
    exp = InfluxDBExporter(cfg)
    m = Measurement(name="Hive1", values={"weight_kg": 45.2}, timestamp=time.time())
    exp.export(m)

    mock_write_api.write.assert_called_once()
    call_kwargs = mock_write_api.write.call_args.kwargs
    assert call_kwargs["bucket"] == "honeypi"
