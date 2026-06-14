from __future__ import annotations
import logging
import threading
import time
from typing import TYPE_CHECKING
from .base import BaseDisplay, DisplayPage

if TYPE_CHECKING:
    from ..sensors.base import Measurement

logger = logging.getLogger(__name__)


class DisplayRenderer:
    """Cycles through hive pages on a background thread."""

    def __init__(
        self,
        display: BaseDisplay,
        hives: list[dict[str, str]],
        page_interval: int = 8,
    ) -> None:
        self._display = display
        self._hives = {h["id"]: h for h in hives}
        self._page_interval = page_interval
        self._latest: dict[str, Measurement] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._page_index = 0

    def update(self, latest: dict[str, Measurement]) -> None:
        with self._lock:
            self._latest.update(latest)

    def start(self) -> None:
        self._display.start()
        self._show_splash()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="display-renderer"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._display.stop()

    def _show_splash(self) -> None:
        """Zeigt sofort beim Start eine Warteseite — überschreibt den Linux-Boot-Log."""
        splash = DisplayPage(
            hive_name="HaniPi",
            timestamp=time.time(),
            values={},
            hive_color="#f59e0b",
        )
        try:
            self._display.show_splash(splash)
        except AttributeError:
            # Display unterstützt kein show_splash — normale Seite zeigen
            self._display.show_page(splash)
        except Exception as exc:
            logger.warning("Splash konnte nicht angezeigt werden: %s", exc)

    def _build_pages(self) -> list[DisplayPage]:
        with self._lock:
            latest = dict(self._latest)

        by_hive: dict[str | None, dict[str, float]] = {}
        timestamps: dict[str | None, float] = {}
        for m in latest.values():
            hid = m.hive_id
            if hid not in by_hive:
                by_hive[hid] = {}
                timestamps[hid] = m.timestamp
            by_hive[hid].update(m.values)
            timestamps[hid] = max(timestamps[hid], m.timestamp)

        pages: list[DisplayPage] = []
        for hid, values in by_hive.items():
            if hid and hid in self._hives:
                hive = self._hives[hid]
                name = hive.get("name", hid)
                color = hive.get("color", "#f59e0b")
            else:
                name = "Umgebung" if hid is None else hid
                color = "#f59e0b"

            batt = values.pop("voltage_v", None)
            pages.append(DisplayPage(
                hive_name=name,
                timestamp=timestamps.get(hid, time.time()),
                values=values,
                hive_color=color,
                battery_voltage=batt,
            ))
        return pages

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            pages = self._build_pages()
            if pages:
                page = pages[self._page_index % len(pages)]
                try:
                    self._display.show_page(page)
                except Exception as exc:
                    logger.error("Display show_page error: %s", exc)
                self._page_index += 1
            self._stop_event.wait(timeout=float(self._page_interval))
