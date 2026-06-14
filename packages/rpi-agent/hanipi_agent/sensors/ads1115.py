from __future__ import annotations
import time
from .base import BaseSensor, Measurement

try:
    import smbus2  # type: ignore[import-untyped]
    _HW_AVAILABLE = True
except ImportError:
    _HW_AVAILABLE = False

# PGA (gain) settings: gain_key -> (PGA bits, V/LSB)
_GAIN_TABLE: dict[str, tuple[int, float]] = {
    "2/3": (0b000, 6.144 / 32767),
    "1":   (0b001, 4.096 / 32767),
    "2":   (0b010, 2.048 / 32767),
    "4":   (0b011, 1.024 / 32767),
    "8":   (0b100, 0.512 / 32767),
    "16":  (0b101, 0.256 / 32767),
}

_REG_CONVERSION = 0x00
_REG_CONFIG = 0x01


class ADS1115Sensor(BaseSensor):
    """ADS1115 16-bit ADC via I2C — single-ended channel reading with optional voltage divider.

    Typical use: battery voltage monitoring via resistor divider on one channel.
    Config:
      channel: 0-3 (default 0)
      gain: "2/3"|"1"|"2"|"4"|"8"|"16" (default "1" = ±4.096V)
      voltage_divider: float multiplier to recover actual voltage (e.g. 5.7 for 100k/20k divider)
    """

    def _configure(self, config: dict) -> None:
        self._port = config.get("i2c_port", 1)
        self._address = config.get("i2c_address", 0x48)
        self._channel = int(config.get("channel", 0))
        gain_key = str(config.get("gain", "1"))
        self._pga_bits, self._lsb_v = _GAIN_TABLE.get(gain_key, _GAIN_TABLE["1"])
        self._divider = float(config.get("voltage_divider", 1.0))

    def _build_config(self) -> int:
        # MUX for single-ended: channel+4 (channels 0-3 → MUX 4-7)
        mux = (self._channel + 4) & 0x07
        config = (
            (1 << 15)             # OS: start single conversion
            | (mux << 12)         # MUX
            | (self._pga_bits << 9)  # PGA
            | (1 << 8)            # MODE: single shot
            | (0b100 << 5)        # DR: 128 SPS
            | 0b11                # COMP_QUE: disable comparator
        )
        return config

    def read(self) -> Measurement:
        if not _HW_AVAILABLE:
            raise RuntimeError("smbus2 not available")
        cfg = self._build_config()
        cfg_bytes = [(cfg >> 8) & 0xFF, cfg & 0xFF]
        with smbus2.SMBus(self._port) as bus:
            bus.write_i2c_block_data(self._address, _REG_CONFIG, cfg_bytes)
            time.sleep(0.01)  # wait for conversion (~8ms at 128 SPS)
            raw_bytes = bus.read_i2c_block_data(self._address, _REG_CONVERSION, 2)
        raw = (raw_bytes[0] << 8) | raw_bytes[1]
        # two's complement for negative values
        if raw > 32767:
            raw -= 65536
        voltage = raw * self._lsb_v * self._divider
        return Measurement(
            name=self.name,
            values={"voltage_v": round(voltage, 3)},
            timestamp=time.time(),
        )
