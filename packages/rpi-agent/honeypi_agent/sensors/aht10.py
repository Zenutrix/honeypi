from __future__ import annotations
import time
from .base import BaseSensor, Measurement

try:
    import smbus2  # type: ignore[import-untyped]
    from smbus2 import i2c_msg
    _HW_AVAILABLE = True
except ImportError:
    _HW_AVAILABLE = False

_INIT_CMD = [0xE1, 0x08, 0x00]
_MEAS_CMD = [0xAC, 0x33, 0x00]


class AHT10Sensor(BaseSensor):
    """AHT10 temperature/humidity sensor via I2C (also compatible with AHT20)."""

    def _configure(self, config: dict) -> None:
        self._port = config.get("i2c_port", 1)
        self._address = config.get("i2c_address", 0x38)
        if _HW_AVAILABLE:
            with smbus2.SMBus(self._port) as bus:
                init = i2c_msg.write(self._address, _INIT_CMD)
                bus.i2c_rdwr(init)
            time.sleep(0.02)

    def read(self) -> Measurement:
        if not _HW_AVAILABLE:
            raise RuntimeError("smbus2 not available")
        with smbus2.SMBus(self._port) as bus:
            trigger = i2c_msg.write(self._address, _MEAS_CMD)
            bus.i2c_rdwr(trigger)
            time.sleep(0.1)
            read = i2c_msg.read(self._address, 6)
            bus.i2c_rdwr(read)
        data = list(read)
        if data[0] & 0x80:
            raise RuntimeError("AHT10 busy — retry next cycle")
        hum_raw = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4)) & 0xFFFFF
        temp_raw = ((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5]
        humidity = (hum_raw / 1048576.0) * 100.0
        temperature = (temp_raw / 1048576.0) * 200.0 - 50.0
        return Measurement(
            name=self.name,
            values={
                "temperature_c": round(temperature, 2),
                "humidity_pct": round(min(max(humidity, 0.0), 100.0), 2),
            },
            timestamp=time.time(),
        )
