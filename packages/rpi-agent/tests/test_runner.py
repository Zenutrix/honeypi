import time
from unittest.mock import MagicMock

from hanipi_agent.exporters.base import BaseExporter
from hanipi_agent.runner import MeasurementRunner
from hanipi_agent.sensors.base import BaseSensor, Measurement


class CapturingExporter(BaseExporter):
    def __init__(self) -> None:
        self.received: list[Measurement] = []

    def export(self, measurement: Measurement) -> None:
        self.received.append(measurement)


class FakeSensor(BaseSensor):
    """Test double standing in for a real sensor — returns a fixed measurement."""

    def _configure(self, config: dict) -> None:
        self._values = config.get("values", {"value": 1.0})

    def read(self) -> Measurement:
        return Measurement(
            name=self.name, values=dict(self._values), timestamp=time.time()
        )


def test_run_once_calls_all_exporters() -> None:
    sensor = FakeSensor({"type": "fake", "name": "Test", "values": {"weight_kg": 10.0}})
    exp1 = CapturingExporter()
    exp2 = CapturingExporter()
    runner = MeasurementRunner(sensors=[sensor], exporters=[exp1, exp2], interval=60)
    runner.run_once()
    assert len(exp1.received) == 1
    assert len(exp2.received) == 1


def test_run_once_continues_after_sensor_error() -> None:
    bad_sensor = MagicMock()
    bad_sensor.name = "Bad"
    bad_sensor.paused = False
    bad_sensor.read.side_effect = RuntimeError("hardware error")
    good_sensor = FakeSensor({"type": "fake", "name": "Good"})
    exp = CapturingExporter()
    runner = MeasurementRunner(
        sensors=[bad_sensor, good_sensor], exporters=[exp], interval=60
    )
    runner.run_once()
    assert len(exp.received) == 1
    assert exp.received[0].name == "Good"


def test_run_once_continues_after_exporter_error() -> None:
    sensor = FakeSensor({"type": "fake", "name": "Test"})
    bad_exp = MagicMock()
    bad_exp.export.side_effect = RuntimeError("network error")
    good_exp = CapturingExporter()
    runner = MeasurementRunner(
        sensors=[sensor], exporters=[bad_exp, good_exp], interval=60
    )
    runner.run_once()
    assert len(good_exp.received) == 1
