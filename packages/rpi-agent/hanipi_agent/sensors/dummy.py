from __future__ import annotations
import random
import time
from .base import BaseSensor, Measurement


class DummySensor(BaseSensor):
    def _configure(self, config: dict) -> None:
        self._values: dict[str, float] = config.get("values", {"value": 0.0})
        self._noise: float = config.get("noise", 0.5)

    def read(self) -> Measurement:
        noisy = {k: v + random.uniform(-self._noise, self._noise) for k, v in self._values.items()}
        return Measurement(name=self.name, values=noisy, timestamp=time.time())
