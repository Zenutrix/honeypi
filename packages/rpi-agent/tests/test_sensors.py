import time
import pytest
from unittest.mock import MagicMock, patch
from honeypi_agent.sensors.base import BaseSensor, Measurement


class ConcreteSensor(BaseSensor):
    def read(self) -> Measurement:
        return Measurement(name=self.name, values={"x": 1.0}, timestamp=time.time())


def test_sensor_uses_name_from_config() -> None:
    s = ConcreteSensor({"type": "concrete", "name": "MyHive"})
    assert s.name == "MyHive"


def test_measurement_has_values() -> None:
    s = ConcreteSensor({"type": "concrete", "name": "Test"})
    m = s.read()
    assert "x" in m.values
    assert m.name == "Test"
