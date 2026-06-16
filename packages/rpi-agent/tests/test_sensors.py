import time
from unittest.mock import MagicMock, patch

import pytest

from hanipi_agent.sensors.base import BaseSensor, Measurement


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


def test_hx711_reads_weight() -> None:
    mock_gpio = MagicMock()
    mock_gpio.HIGH = 1
    mock_gpio.LOW = 0
    mock_gpio.input.return_value = 0  # constant DOUT -> raw reading of 0 every cycle
    fake_rpi = MagicMock()
    fake_rpi.GPIO = mock_gpio

    with patch.dict("sys.modules", {"RPi": fake_rpi, "RPi.GPIO": mock_gpio}):
        from importlib import reload

        import hanipi_agent.sensors.hx711 as hx711_mod
        reload(hx711_mod)

        s = hx711_mod.HX711Sensor({
            "type": "hx711", "name": "Stock",
            "data_pin": 5, "clock_pin": 6, "reference_unit": 21.0,
        })
        m = s.read()

    assert "weight_kg" in m.values
    assert m.values["weight_kg"] == pytest.approx(0.0)


def test_ds18b20_reads_temperature(tmp_path, mocker: MagicMock) -> None:
    device_dir = tmp_path / "28-000000000000"
    device_dir.mkdir()
    w1_slave = device_dir / "w1_slave"
    w1_slave.write_text(
        "01 01 4b 46 7f ff 0c 10 56 : crc=56 YES\n01 01 4b 46 7f ff 0c 10 56 t=36500\n"
    )

    import hanipi_agent.sensors.ds18b20 as ds18b20_mod
    mocker.patch.object(ds18b20_mod, "_W1_BASE", tmp_path)

    from hanipi_agent.sensors.ds18b20 import DS18B20Sensor
    s = DS18B20Sensor({"type": "ds18b20", "name": "BroodTemp"})
    m = s.read()

    assert "temperature_c" in m.values
    assert m.values["temperature_c"] == pytest.approx(36.5)


def test_bme280_reads_all_values(mocker: MagicMock) -> None:
    mocker.patch("hanipi_agent.sensors.bme280.smbus2")
    mock_bme = mocker.patch("hanipi_agent.sensors.bme280.bme280_module")
    mock_bme.load_calibration_params.return_value = object()
    mock_bme.sample.return_value = MagicMock(
        temperature=22.3, humidity=58.1, pressure=1013.2
    )

    from hanipi_agent.sensors.bme280 import BME280Sensor
    s = BME280Sensor({"type": "bme280", "name": "OutsideWeather"})
    m = s.read()

    assert "temperature_c" in m.values
    assert "humidity_pct" in m.values
    assert "pressure_hpa" in m.values
    assert m.values["temperature_c"] == pytest.approx(22.3)


def test_sensor_factory_creates_bme280(mocker: MagicMock) -> None:
    mocker.patch("hanipi_agent.sensors.bme280.smbus2")
    mocker.patch("hanipi_agent.sensors.bme280.bme280_module")

    from hanipi_agent.sensors import create_sensor
    from hanipi_agent.sensors.bme280 import BME280Sensor
    s = create_sensor({"type": "bme280", "name": "Test"})
    assert isinstance(s, BME280Sensor)


def test_sensor_factory_raises_on_unknown() -> None:
    from hanipi_agent.sensors import create_sensor
    with pytest.raises(ValueError, match="Unbekannter Sensor-Typ"):
        create_sensor({"type": "nonexistent", "name": "X"})
