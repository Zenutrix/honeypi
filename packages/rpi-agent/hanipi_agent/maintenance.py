from __future__ import annotations
import json
import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sensors.base import BaseSensor

logger = logging.getLogger(__name__)
_STATUS_FILE = Path("/var/lib/hanipi/maintenance.json")
_HOTSPOT_CON = "HaniPi-Wartung"
_POLL_INTERVAL = 0.5


class MaintenanceMonitor:
    def __init__(self, gpio_pin: int, sensors: list[BaseSensor]) -> None:
        self._gpio_pin = gpio_pin
        self._sensors = sensors
        self._active = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._gpio: object = None

    def start(self) -> None:
        try:
            import RPi.GPIO as GPIO  # type: ignore[import-untyped]
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self._gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self._gpio = GPIO
        except Exception as exc:
            logger.warning("MaintenanceMonitor: GPIO not available (%s) — disabled", exc)
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="maintenance-monitor"
        )
        self._thread.start()
        logger.info("MaintenanceMonitor started on GPIO%d", self._gpio_pin)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        try:
            if self._gpio is not None:
                import RPi.GPIO as GPIO
                GPIO.cleanup(self._gpio_pin)
        except Exception:
            pass

    def _poll_loop(self) -> None:
        import RPi.GPIO as GPIO
        while not self._stop_event.is_set():
            try:
                pin_low = GPIO.input(self._gpio_pin) == GPIO.LOW
                if pin_low and not self._active:
                    self._activate()
                elif not pin_low and self._active:
                    self._deactivate()
            except Exception as exc:
                logger.error("MaintenanceMonitor poll error: %s", exc)
            self._stop_event.wait(timeout=_POLL_INTERVAL)

    def _activate(self) -> None:
        logger.info("Maintenance mode ACTIVATED")
        self._active = True
        self._set_hx711_paused(True)
        self._write_status(active=True)
        self._hotspot("up")

    def _deactivate(self) -> None:
        logger.info("Maintenance mode DEACTIVATED")
        self._active = False
        self._set_hx711_paused(False)
        self._write_status(active=False)
        self._hotspot("down")

    def _set_hx711_paused(self, paused: bool) -> None:
        for sensor in self._sensors:
            if type(sensor).__name__ == "HX711Sensor":
                sensor.paused = paused
                logger.debug("Sensor %s paused=%s", sensor.name, paused)

    def _hotspot(self, action: str) -> None:
        try:
            subprocess.run(
                ["sudo", "nmcli", "connection", action, _HOTSPOT_CON],
                capture_output=True,
                timeout=15,
            )
        except Exception as exc:
            logger.warning("Hotspot %s failed: %s", action, exc)

    def _write_status(self, active: bool) -> None:
        try:
            _STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data: dict[str, object] = {"active": active}
            if active:
                data["since"] = time.time()
            _STATUS_FILE.write_text(json.dumps(data))
        except Exception as exc:
            logger.warning("Could not write maintenance status: %s", exc)

    @property
    def is_active(self) -> bool:
        return self._active
