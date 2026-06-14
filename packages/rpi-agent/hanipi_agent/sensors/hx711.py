from __future__ import annotations
import time
from .base import BaseSensor, Measurement

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

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self._data_pin, GPIO.IN)
        GPIO.setup(self._clock_pin, GPIO.OUT)
        GPIO.output(self._clock_pin, False)

        # Kurze Wartezeit nach Init, dann taren
        time.sleep(0.5)
        self._offset = self._read_raw_mean(10)

    def _read_raw(self) -> int:
        # Warten bis DOUT LOW (Daten bereit), max. 500ms
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

        # 24-Bit Two's Complement
        if data & 0x800000:
            data -= 0x1000000

        return data

    def _read_raw_mean(self, n: int) -> float:
        readings = [self._read_raw() for _ in range(n)]
        return sum(readings) / len(readings)

    def read(self) -> Measurement:
        raw = self._read_raw_mean(self._samples)
        weight_kg = round((raw - self._offset) / self._ref_unit / 1000, 3)
        return Measurement(
            name=self.name,
            values={"weight_kg": weight_kg},
            timestamp=time.time(),
            hive_id=self.hive_id,
        )
