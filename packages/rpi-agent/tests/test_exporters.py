import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from hanipi_agent.exporters.base import BaseExporter
from hanipi_agent.sensors.base import Measurement


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


from hanipi_agent.exporters.local import LocalExporter


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


from hanipi_agent.exporters.thingspeak import ThingSpeakExporter


def test_thingspeak_sends_mapped_fields() -> None:
    cfg = {
        "enabled": True,
        "api_key": "TESTKEY123",
        "field_mapping": {"weight_kg": "field1", "temperature_c": "field2"},
    }
    m = Measurement(name="Hive1", values={"weight_kg": 45.2, "temperature_c": 34.1}, timestamp=time.time())

    with patch("hanipi_agent.exporters.thingspeak.httpx.get") as mock_get:
        exp = ThingSpeakExporter(cfg)
        exp.export(m)
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        params = kwargs["params"]
        assert params["api_key"] == "TESTKEY123"
        assert params["field1"] == pytest.approx(45.2)
        assert params["field2"] == pytest.approx(34.1)


from hanipi_agent.exporters.influxdb import InfluxDBExporter


def test_influxdb_writes_point(mocker: MagicMock) -> None:
    mock_client_cls = mocker.patch("hanipi_agent.exporters.influxdb.InfluxDBClient")
    mock_client = mock_client_cls.return_value
    mock_write_api = mock_client.write_api.return_value

    cfg = {"enabled": True, "url": "http://localhost:8086", "token": "tok", "org": "myorg", "bucket": "hanipi"}
    exp = InfluxDBExporter(cfg)
    m = Measurement(name="Hive1", values={"weight_kg": 45.2}, timestamp=time.time())
    exp.export(m)

    mock_write_api.write.assert_called_once()
    call_kwargs = mock_write_api.write.call_args.kwargs
    assert call_kwargs["bucket"] == "hanipi"


from hanipi_agent.exporters.mqtt import MQTTExporter


def test_mqtt_publishes_json(mocker: MagicMock) -> None:
    import json
    mock_mqtt = mocker.patch("hanipi_agent.exporters.mqtt.mqtt")
    mock_client = mock_mqtt.Client.return_value

    cfg = {"enabled": True, "broker": "localhost", "port": 1883, "topic": "hanipi"}
    exp = MQTTExporter(cfg)
    m = Measurement(name="Hive1", values={"weight_kg": 45.2}, timestamp=1234567890.0)
    exp.export(m)

    mock_client.publish.assert_called_once()
    topic, payload = mock_client.publish.call_args.args
    assert topic == "hanipi/Hive1"
    data = json.loads(payload)
    assert data["weight_kg"] == pytest.approx(45.2)
    assert data["sensor"] == "Hive1"


def test_exporter_factory_creates_local(tmp_path: Path) -> None:
    from hanipi_agent.exporters import create_exporters
    cfg = {"local": {"enabled": True, "db_path": str(tmp_path / "db.sqlite")}}
    exporters = create_exporters(cfg)
    from hanipi_agent.exporters.local import LocalExporter
    assert len(exporters) == 1
    assert isinstance(exporters[0], LocalExporter)
    exporters[0].close()


def test_exporter_factory_skips_disabled() -> None:
    from hanipi_agent.exporters import create_exporters
    cfg = {"thingspeak": {"enabled": False, "api_key": ""}}
    exporters = create_exporters(cfg)
    assert exporters == []
