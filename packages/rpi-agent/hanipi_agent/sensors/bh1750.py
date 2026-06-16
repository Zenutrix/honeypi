from __future__ import annotations
import time
from typing import Any
from .base import BaseSensor, Measurement

try:
    import smbus2
    _HW_AVAILABLE = True
except ImportError:
    _HW_AVAILABLE = False

_POWER_ON = 0x01
_RESET = 0x07
_CONT_H_RES = 0x10  # continuous high resolution mode (1 lux resolution)


class BH1750Sensor(BaseSensor):
    """BH1750 digital ambient light sensor via I2C."""

    def _configure(self, config: dict[str, Any]) -> None:
        self._port = config.get("i2c_port", 1)
        self._address = config.get("i2c_address", 0x23)  # 0x5C if ADDR pin high

    def read(self) -> Measurement:
        if not _HW_AVAILABLE:
            raise RuntimeError("smbus2 not available")
        with smbus2.SMBus(self._port) as bus:
            bus.write_byte(self._address, _POWER_ON)
            bus.write_byte(self._address, _CONT_H_RES)
            time.sleep(0.18)
            data = bus.read_i2c_block_data(self._address, 0x00, 2)
        raw = (data[0] << 8) | data[1]
        lux = raw / 1.2
        return Measurement(
            name=self.name,
            values={"illuminance_lux": round(lux, 1)},
            timestamp=time.time(),
        )
