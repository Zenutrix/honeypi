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
        self._hx.set_scale_ratio(config.get("reference_unit", 1.0))
        self._samples: int = config.get("samples", 5)

    def read(self) -> Measurement:
        raw = self._hx.get_weight_mean(self._samples)
        return Measurement(
            name=self.name,
            values={"weight_kg": raw / 1000},
            timestamp=time.time(),
        )
