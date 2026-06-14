import time
from unittest.mock import MagicMock
from honeypi_agent.runner import MeasurementRunner
from honeypi_agent.sensors.base import Measurement
from honeypi_agent.sensors.dummy import DummySensor
from honeypi_agent.exporters.base import BaseExporter


class CapturingExporter(BaseExporter):
    def __init__(self) -> None:
        self.received: list[Measurement] = []

    def export(self, measurement: Measurement) -> None:
        self.received.append(measurement)


def test_run_once_calls_all_exporters() -> None:
    sensor = DummySensor({"type": "dummy", "name": "Test", "values": {"weight_kg": 10.0}})
    exp1 = CapturingExporter()
    exp2 = CapturingExporter()
    runner = MeasurementRunner(sensors=[sensor], exporters=[exp1, exp2], interval=60)
    runner.run_once()
    assert len(exp1.received) == 1
    assert len(exp2.received) == 1


def test_run_once_continues_after_sensor_error() -> None:
    bad_sensor = MagicMock()
    bad_sensor.name = "Bad"
    bad_sensor.read.side_effect = RuntimeError("hardware error")
    good_sensor = DummySensor({"type": "dummy", "name": "Good"})
    exp = CapturingExporter()
    runner = MeasurementRunner(sensors=[bad_sensor, good_sensor], exporters=[exp], interval=60)
    runner.run_once()
    assert len(exp.received) == 1
    assert exp.received[0].name == "Good"


def test_run_once_continues_after_exporter_error() -> None:
    sensor = DummySensor({"type": "dummy", "name": "Test"})
    bad_exp = MagicMock()
    bad_exp.export.side_effect = RuntimeError("network error")
    good_exp = CapturingExporter()
    runner = MeasurementRunner(sensors=[sensor], exporters=[bad_exp, good_exp], interval=60)
    runner.run_once()
    assert len(good_exp.received) == 1
