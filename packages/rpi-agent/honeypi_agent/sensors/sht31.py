from __future__ import annotations
import time
from .base import BaseSensor, Measurement

try:
    import smbus2  # type: ignore[import-untyped]
    from smbus2 import i2c_msg
    _HW_AVAILABLE = True
except ImportError:
    _HW_AVAILABLE = False


class SHT31Sensor(BaseSensor):
    """SHT31 (and SHT25) high-precision temperature/humidity sensor via I2C."""

    _MEAS_CMD = [0x24, 0x00]  # single shot, high repeatability, no clock stretch

    def _configure(self, config: dict) -> None:
        self._port = config.get("i2c_port", 1)
        self._address = config.get("i2c_address", 0x44)

    def read(self) -> Measurement:
        if not _HW_AVAILABLE:
            raise RuntimeError("smbus2 not available")
        with smbus2.SMBus(self._port) as bus:
            write = i2c_msg.write(self._address, self._MEAS_CMD)
            bus.i2c_rdwr(write)
            time.sleep(0.02)
            read = i2c_msg.read(self._address, 6)
            bus.i2c_rdwr(read)
        data = list(read)
        temp_raw = (data[0] << 8) | data[1]
        hum_raw = (data[3] << 8) | data[4]
        temperature = -45.0 + 175.0 * temp_raw / 65535.0
        humidity = 100.0 * hum_raw / 65535.0
        return Measurement(
            name=self.name,
            values={
                "temperature_c": round(temperature, 2),
                "humidity_pct": round(min(max(humidity, 0.0), 100.0), 2),
            },
            timestamp=time.time(),
        )
