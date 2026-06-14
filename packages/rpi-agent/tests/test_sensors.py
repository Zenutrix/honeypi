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


def test_hx711_reads_weight(mocker: MagicMock) -> None:
    mock_hx = mocker.patch("honeypi_agent.sensors.hx711.HX711")
    mock_instance = mock_hx.return_value
    mock_instance.get_weight_mean.return_value = 15340.0

    from honeypi_agent.sensors.hx711 import HX711Sensor
    s = HX711Sensor({"type": "hx711", "name": "Stock", "data_pin": 5, "clock_pin": 6, "reference_unit": 21.0})
    m = s.read()

    assert "weight_kg" in m.values
    assert m.values["weight_kg"] == pytest.approx(15340.0 / 1000, abs=0.1)


def test_ds18b20_reads_temperature(mocker: MagicMock) -> None:
    mock_sensor_cls = mocker.patch("honeypi_agent.sensors.ds18b20.W1ThermSensor")
    mock_instance = mock_sensor_cls.return_value
    mock_instance.get_temperature.return_value = 36.5

    from honeypi_agent.sensors.ds18b20 import DS18B20Sensor
    s = DS18B20Sensor({"type": "ds18b20", "name": "BroodTemp"})
    m = s.read()

    assert "temperature_c" in m.values
    assert m.values["temperature_c"] == pytest.approx(36.5)


def test_bme280_reads_all_values(mocker: MagicMock) -> None:
    mock_smbus = mocker.patch("honeypi_agent.sensors.bme280.smbus2")
    mock_bme = mocker.patch("honeypi_agent.sensors.bme280.bme280_module")
    mock_bme.load_calibration_params.return_value = object()
    mock_bme.sample.return_value = MagicMock(temperature=22.3, humidity=58.1, pressure=1013.2)

    from honeypi_agent.sensors.bme280 import BME280Sensor
    s = BME280Sensor({"type": "bme280", "name": "OutsideWeather"})
    m = s.read()

    assert "temperature_c" in m.values
    assert "humidity_pct" in m.values
    assert "pressure_hpa" in m.values
    assert m.values["temperature_c"] == pytest.approx(22.3)
