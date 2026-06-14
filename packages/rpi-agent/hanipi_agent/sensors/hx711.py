from __future__ import annotations
import time
from .base import BaseSensor, Measurement

try:
    from hx711 import HX711  # type: ignore[import-untyped]
except ImportError:
    HX711 = None  # type: ignore[assignment,misc]


class HX711Sensor(BaseSensor):
    def _configure(self, config: dict) -> None:
        if HX711 is None:
            raise RuntimeError("hx711 package not installed")
        self._hx = HX711(dout_pin=config["data_pin"], pd_sck_pin=config["clock_pin"])
        ref = float(config.get("reference_unit", 1.0))
        self._samples: int = config.get("samples", 5)

        # Support multiple hx711 library API variants
        if hasattr(self._hx, "set_scale_ratio"):
            self._hx.set_scale_ratio(ref)
        elif hasattr(self._hx, "set_reference_unit"):
            self._hx.set_reference_unit(ref)
        elif hasattr(self._hx, "set_reference_unit_A"):
            self._hx.set_reference_unit_A(ref)
        # If none available, raw values will be divided by ref manually

        self._manual_ref = ref if not any(
            hasattr(self._hx, m)
            for m in ("set_scale_ratio", "set_reference_unit", "set_reference_unit_A")
        ) else 1.0

    def read(self) -> Measurement:
        if hasattr(self._hx, "get_weight_mean"):
            raw = self._hx.get_weight_mean(self._samples)
        elif hasattr(self._hx, "get_weight"):
            raw = self._hx.get_weight(self._samples)
        else:
            raw = self._hx.read_long() or 0.0

        weight_kg = (raw / self._manual_ref) / 1000
        return Measurement(
            name=self.name,
            values={"weight_kg": weight_kg},
            timestamp=time.time(),
            hive_id=self.hive_id,
        )
