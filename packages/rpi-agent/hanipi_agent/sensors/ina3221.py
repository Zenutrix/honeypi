from __future__ import annotations

import logging
import time
from typing import Any

from .base import BaseSensor, Measurement

logger = logging.getLogger(__name__)

try:
    import smbus2
    _SMBUS2_OK = True
except ImportError:
    smbus2 = None  # type: ignore[assignment]
    _SMBUS2_OK = False

# INA3221 Register-Adressen
_REG_CONFIG  = 0x00
_REG_CH1_SHV = 0x01  # Shunt-Spannung Kanal 1
_REG_CH1_BV  = 0x02  # Bus-Spannung Kanal 1
_REG_CH2_SHV = 0x03
_REG_CH2_BV  = 0x04
_REG_CH3_SHV = 0x05
_REG_CH3_BV  = 0x06

# Config: alle 3 Kanäle aktiv, 1024 Mittelwerte, 1.1ms Wandlungszeit
_CONFIG_DEFAULT = 0x7127

_CH_REGS = [
    (_REG_CH1_SHV, _REG_CH1_BV),
    (_REG_CH2_SHV, _REG_CH2_BV),
    (_REG_CH3_SHV, _REG_CH3_BV),
]


class INA3221Sensor(BaseSensor):
    """INA3221 3-Kanal Leistungsmessung (Solar, Batterie, Pi-Ausgang) via I²C.

    Kanal-Belegung (Standard-Anschlussplan):
      CH1 → Solar-Eingang:  solar_voltage_v, solar_current_a, solar_power_w
      CH2 → Batterie:       battery_voltage_v, battery_current_a
                             (positiv = lädt, negativ = entlädt)
      CH3 → Pi 5V-Ausgang:  pi_voltage_v, pi_current_a, pi_power_w
    """

    def _configure(self, config: dict[str, Any]) -> None:
        if not _SMBUS2_OK:
            raise RuntimeError("smbus2 nicht installiert — 'pip install smbus2'")
        port = int(config.get("i2c_port", 1))
        addr_raw = config.get("i2c_address", 0x40)
        self._addr = int(addr_raw, 16) if isinstance(addr_raw, str) else int(addr_raw)
        self._bus = smbus2.SMBus(port)
        self._shunt_ohms = float(config.get("shunt_ohms", 0.1))
        self._ch_enabled = [
            bool(config.get("ch1_enabled", True)),
            bool(config.get("ch2_enabled", True)),
            bool(config.get("ch3_enabled", False)),
        ]
        self._ch_names = [
            str(config.get("ch1_name", "solar")),
            str(config.get("ch2_name", "battery")),
            str(config.get("ch3_name", "pi")),
        ]
        self._write16(_REG_CONFIG, _CONFIG_DEFAULT)
        logger.info(
            "INA3221 @ 0x%02x  CH1=%s CH2=%s CH3=%s  shunt=%.3fΩ",
            self._addr,
            self._ch_names[0] if self._ch_enabled[0] else "—",
            self._ch_names[1] if self._ch_enabled[1] else "—",
            self._ch_names[2] if self._ch_enabled[2] else "—",
            self._shunt_ohms,
        )

    def _write16(self, reg: int, val: int) -> None:
        self._bus.write_i2c_block_data(
            self._addr, reg, [(val >> 8) & 0xFF, val & 0xFF]
        )

    def _read16_signed(self, reg: int) -> int:
        d = self._bus.read_i2c_block_data(self._addr, reg, 2)
        raw = (d[0] << 8) | d[1]
        return raw - 65536 if raw & 0x8000 else raw

    def _read_channel(self, shv_reg: int, bv_reg: int) -> tuple[float, float]:
        # Shunt-Spannung: Bits 15:3, LSB = 40 µV
        shv_raw = self._read16_signed(shv_reg) >> 3
        shv_uv = shv_raw * 40  # µV
        # Bus-Spannung: Bits 15:3, LSB = 8 mV
        bv_raw = self._read16_signed(bv_reg) >> 3
        bus_v = bv_raw * 0.008  # V
        current_a = (shv_uv / 1_000_000.0) / self._shunt_ohms
        return round(bus_v, 3), round(current_a, 4)

    def read(self) -> Measurement:
        values: dict[str, float] = {}
        for idx, (enabled, name) in enumerate(zip(self._ch_enabled, self._ch_names)):
            if not enabled:
                continue
            shv_reg, bv_reg = _CH_REGS[idx]
            v, i = self._read_channel(shv_reg, bv_reg)
            values[f"{name}_voltage_v"] = v
            values[f"{name}_current_a"] = i
            # Batterie-Kanal: kein power_w (Vorzeichen ist die Info)
            if idx != 1:
                values[f"{name}_power_w"] = round(v * abs(i), 4)
        return Measurement(
            name=self.name,
            values=values,
            hive_id=self.hive_id,
            timestamp=time.time(),
        )
