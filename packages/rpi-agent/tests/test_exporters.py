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
