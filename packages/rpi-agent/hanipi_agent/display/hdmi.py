from __future__ import annotations
import datetime
import logging
from .base import BaseDisplay, DisplayPage

logger = logging.getLogger(__name__)

BG_COLOR = (26, 26, 46)
WHITE = (255, 255, 255)
GREY = (120, 113, 108)

UNIT_MAP: dict[str, str] = {
    "weight_kg": "kg",
    "temperature_c": "°C",
    "humidity_pct": "%",
    "pressure_hpa": "hPa",
    "illuminance_lux": "lx",
    "gas_resistance_ohm": "Ω",
    "voltage_v": "V",
}
LABEL_MAP: dict[str, str] = {
    "weight_kg": "Gewicht",
    "temperature_c": "Temperatur",
    "humidity_pct": "Luftfeuchte",
    "pressure_hpa": "Luftdruck",
    "illuminance_lux": "Licht",
    "gas_resistance_ohm": "Gas",
    "voltage_v": "Spannung",
}


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


class HDMIDisplay(BaseDisplay):
    def __init__(self, rotation: int = 0) -> None:
        self._rotation = rotation
        self._screen: object = None
        self._pg: object = None
        self._available = False

    def start(self) -> None:
        try:
            import pygame  # type: ignore[import-untyped]
            self._pg = pygame
            pygame.init()
            pygame.mouse.set_visible(False)
            self._screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            pygame.display.set_caption("HaniPi")
            self._available = True
            logger.info("HDMIDisplay initialized")
        except Exception as exc:
            logger.warning("HDMIDisplay: pygame not available (%s)", exc)

    def stop(self) -> None:
        if self._pg is not None and self._available:
            try:
                import pygame  # type: ignore[import-untyped]
                pygame.quit()
            except Exception:
                pass

    def show_page(self, page: DisplayPage) -> None:
        if not self._available or self._screen is None:
            return
        try:
            self._render(page)
        except Exception as exc:
            logger.error("HDMIDisplay render error: %s", exc)

    def _render(self, page: DisplayPage) -> None:
        import pygame  # type: ignore[import-untyped]
        screen = self._screen
        assert screen is not None
        W, H = screen.get_size()  # type: ignore[attr-defined]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

        screen.fill(BG_COLOR)  # type: ignore[attr-defined]

        accent = _hex_to_rgb(page.hive_color)
        pygame.draw.rect(screen, accent, (0, 0, W, 60))  # type: ignore[arg-type]

        font_lg = pygame.font.SysFont("dejavusans", 36, bold=True)
        font_md = pygame.font.SysFont("dejavusans", 26)
        font_sm = pygame.font.SysFont("dejavusans", 18)

        screen.blit(font_lg.render(page.hive_name, True, WHITE), (20, 12))  # type: ignore[attr-defined]

        ts = datetime.datetime.fromtimestamp(page.timestamp).strftime("%d.%m.%Y %H:%M")
        screen.blit(font_sm.render(ts, True, GREY), (20, 68))  # type: ignore[attr-defined]

        items = [(k, v) for k, v in page.values.items() if k != "voltage_v"]
        cols = 3
        cell_w = W // cols
        cell_h = max(70, (H - 130) // max(1, (len(items) + cols - 1) // cols))
        for i, (key, val) in enumerate(items[:6]):
            row, col = divmod(i, cols)
            x, y = col * cell_w + 20, 95 + row * cell_h
            screen.blit(font_sm.render(LABEL_MAP.get(key, key), True, GREY), (x, y))  # type: ignore[attr-defined]
            unit = UNIT_MAP.get(key, "")
            screen.blit(font_md.render(f"{val:.1f} {unit}", True, WHITE), (x, y + 22))  # type: ignore[attr-defined]

        pygame.draw.rect(screen, (30, 30, 50), (0, H - 30, W, 30))  # type: ignore[arg-type]
        status = "Online" if page.connected else "Offline"
        color: tuple[int, int, int] = (34, 197, 94) if page.connected else (239, 68, 68)
        screen.blit(font_sm.render(status, True, color), (20, H - 24))  # type: ignore[attr-defined]
        if page.battery_voltage is not None:
            screen.blit(  # type: ignore[attr-defined]
                font_sm.render(f"Akku: {page.battery_voltage:.1f}V", True, WHITE),
                (W - 180, H - 24),
            )

        pygame.display.flip()
