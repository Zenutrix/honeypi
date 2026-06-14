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


from honeypi_agent.sensors.dummy import DummySensor


def test_dummy_sensor_returns_configured_values() -> None:
    s = DummySensor({"type": "dummy", "name": "Fake", "values": {"weight": 42.5, "temp": 21.0}})
    m = s.read()
    assert m.values["weight"] == pytest.approx(42.5, abs=5.0)
    assert "temp" in m.values


def test_dummy_sensor_default_values() -> None:
    s = DummySensor({"type": "dummy", "name": "Default"})
    m = s.read()
    assert "value" in m.values
