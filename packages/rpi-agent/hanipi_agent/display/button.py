"""Taster-Monitor für E-Ink Navigation (GPIO, lgpio, Hintergrund-Thread).

Kurzer Druck (<2s)  → on_short_press()  — nächste Seite
Langer Druck (≥2s)  → on_long_press()   — Idle-Screen
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

_DEBOUNCE_S   = 0.05   # 50 ms Entprellung
_LONG_PRESS_S = 2.0    # ab 2 s = langer Druck
_POLL_S       = 0.02   # 20 ms Poll-Intervall


class ButtonMonitor:
    """Überwacht einen Taster (NO, Pull-Up) auf GPIO und löst Callbacks aus."""

    def __init__(
        self,
        gpio_pin: int = 18,
        on_short_press: Callable[[], None] | None = None,
        on_long_press:  Callable[[], None] | None = None,
    ) -> None:
        self._pin       = gpio_pin
        self._on_short  = on_short_press
        self._on_long   = on_long_press
        self._stop      = threading.Event()
        self._thread: threading.Thread | None = None
        self._h: int | None = None

    def start(self) -> None:
        try:
            import lgpio
            self._h = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_input(self._h, self._pin, lgpio.SET_PULL_UP)
            self._thread = threading.Thread(
                target=self._loop, daemon=True, name="button-monitor"
            )
            self._thread.start()
            logger.info("ButtonMonitor gestartet — GPIO%d", self._pin)
        except Exception as exc:
            logger.error("ButtonMonitor konnte nicht gestartet werden: %s", exc)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self._h is not None:
            try:
                import lgpio
                lgpio.gpiochip_close(self._h)
            except Exception:
                pass
        self._h = None

    def _loop(self) -> None:
        import lgpio

        prev        = 1          # Pull-Up → HIGH wenn nicht gedrückt
        press_start: float | None = None

        while not self._stop.wait(_POLL_S):
            if self._h is None:
                break
            try:
                curr = lgpio.gpio_read(self._h, self._pin)
            except Exception as exc:
                logger.warning("ButtonMonitor read-Fehler: %s", exc)
                break

            # Fallende Flanke — Druck beginnt
            if prev == 1 and curr == 0:
                time.sleep(_DEBOUNCE_S)
                press_start = time.monotonic()

            # Steigende Flanke — Druck endet
            elif prev == 0 and curr == 1:
                if press_start is not None:
                    duration = time.monotonic() - press_start
                    if duration >= _LONG_PRESS_S:
                        logger.debug("Langer Druck (%.1f s)", duration)
                        if self._on_long:
                            try:
                                self._on_long()
                            except Exception as exc:
                                logger.error("on_long_press Fehler: %s", exc)
                    elif duration >= _DEBOUNCE_S:
                        logger.debug("Kurzer Druck (%.2f s)", duration)
                        if self._on_short:
                            try:
                                self._on_short()
                            except Exception as exc:
                                logger.error("on_short_press Fehler: %s", exc)
                    press_start = None
                time.sleep(_DEBOUNCE_S)

            prev = curr
