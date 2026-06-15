from __future__ import annotations
import time
import logging
from .base import BaseSensor, Measurement

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO  # type: ignore[import-untyped]
    _GPIO_AVAILABLE = True
except ImportError:
    _GPIO_AVAILABLE = False


class HX711Sensor(BaseSensor):
    """HX711 Wägezelle — liest direkt über RPi.GPIO, keine externe hx711-Library nötig."""

    def _configure(self, config: dict) -> None:
        if not _GPIO_AVAILABLE:
            raise RuntimeError("RPi.GPIO nicht installiert")
        self._data_pin: int = config["data_pin"]
        self._clock_pin: int = config["clock_pin"]
        self._ref_unit: float = float(config.get("reference_unit", 1.0))
        self._samples: int = int(config.get("samples", 5))
        self._offset: float = 0.0

        # Temperature compensation
        tc = config.get("temp_compensation", {})
        self._tc_enabled: bool = bool(tc.get("enabled", False))
        self._tc_sensor: str = str(tc.get("sensor", ""))
        self._tc_ref_c: float = float(tc.get("ref_c", 20.0))
        self._tc_coeff: float = float(tc.get("coeff_kg_per_c", 0.0))
        self._current_temp_c: float | None = None

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self._data_pin, GPIO.IN)
        GPIO.setup(self._clock_pin, GPIO.OUT)
        GPIO.output(self._clock_pin, False)

        time.sleep(0.5)
        self._offset = self._read_raw_mean(10)
        logger.info(
            "HX711 '%s' tare offset: %.0f  ref_unit=%.4f  temp_comp=%s",
            self.name, self._offset, self._ref_unit,
            f"on (ref={self._tc_ref_c}°C coeff={self._tc_coeff})" if self._tc_enabled else "off",
        )

    def set_current_temp(self, temp_c: float) -> None:
        self._current_temp_c = temp_c

    def _read_raw(self) -> int:
        deadline = time.monotonic() + 0.5
        while GPIO.input(self._data_pin) == GPIO.HIGH:
            if time.monotonic() > deadline:
                raise RuntimeError("HX711 antwortet nicht (DOUT bleibt HIGH)")
            time.sleep(0.001)

        data = 0
        for _ in range(24):
            GPIO.output(self._clock_pin, GPIO.HIGH)
            data = (data << 1) | GPIO.input(self._data_pin)
            GPIO.output(self._clock_pin, GPIO.LOW)

        # Gain 128, Kanal A: 1 extra Puls
        GPIO.output(self._clock_pin, GPIO.HIGH)
        GPIO.output(self._clock_pin, GPIO.LOW)

        if data & 0x800000:
            data -= 0x1000000
        return data

    def _read_raw_mean(self, n: int) -> float:
        readings = [self._read_raw() for _ in range(n)]
        return sum(readings) / len(readings)

    def read(self) -> Measurement:
        raw = self._read_raw_mean(self._samples)
        weight_kg = (raw - self._offset) / self._ref_unit / 1000

        if (
            self._tc_enabled
            and self._tc_coeff != 0.0
            and self._current_temp_c is not None
        ):
            delta_t = self._current_temp_c - self._tc_ref_c
            weight_kg -= delta_t * self._tc_coeff
            logger.debug(
                "HX711 '%s' temp comp: T=%.1f ref=%.1f Δ=%.2f correction=%.4f kg",
                self.name, self._current_temp_c, self._tc_ref_c, delta_t,
                delta_t * self._tc_coeff,
            )

        return Measurement(
            name=self.name,
            values={"weight_kg": round(weight_kg, 3)},
            timestamp=time.time(),
            hive_id=self.hive_id,
        )
