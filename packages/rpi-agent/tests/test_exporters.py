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
