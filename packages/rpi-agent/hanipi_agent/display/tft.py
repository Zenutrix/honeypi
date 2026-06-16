from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

from .base import BaseDisplay, DisplayPage

if TYPE_CHECKING:
    from PIL import ImageFont

logger = logging.getLogger(__name__)

WIDTH = 320
HEIGHT = 240
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


class TFTDisplay(BaseDisplay):
    def __init__(self, device: str = "/dev/fb1", rotation: int = 0) -> None:
        self._device = device
        self._rotation = rotation
        self._available = False
        try:
            from PIL import Image, ImageDraw, ImageFont

            self._Image = Image
            self._ImageDraw = ImageDraw
            self._ImageFont = ImageFont
            self._available = True
        except ImportError:
            logger.warning("TFTDisplay: Pillow not available — display disabled")

    def show_page(self, page: DisplayPage) -> None:
        if not self._available:
            return
        try:
            self._render(page)
        except Exception as exc:
            logger.error("TFTDisplay render error: %s", exc)

    def _render(self, page: DisplayPage) -> None:
        img = self._Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = self._ImageDraw.Draw(img)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_large: ImageFont.FreeTypeFont | ImageFont.ImageFont
        font_med: ImageFont.FreeTypeFont | ImageFont.ImageFont
        font_small: ImageFont.FreeTypeFont | ImageFont.ImageFont
        try:
            font_large = self._ImageFont.truetype(font_path, 26)
            font_med = self._ImageFont.truetype(font_path, 18)
            font_small = self._ImageFont.truetype(font_path, 12)
        except Exception:
            font_large = font_med = font_small = self._ImageFont.load_default()

        accent = _hex_to_rgb(page.hive_color)
        draw.rectangle([0, 0, WIDTH, 38], fill=accent)
        draw.text((8, 7), page.hive_name, font=font_large, fill=WHITE)

        ts = datetime.datetime.fromtimestamp(page.timestamp).strftime("%d.%m.%Y %H:%M")
        draw.text((8, 44), ts, font=font_small, fill=GREY)

        items = [(k, v) for k, v in page.values.items() if k != "voltage_v"]
        for i, (key, val) in enumerate(items[:6]):
            row, col = divmod(i, 2)
            x = col * (WIDTH // 2) + 8
            y = 60 + row * 52
            draw.text((x, y), LABEL_MAP.get(key, key), font=font_small, fill=GREY)
            unit = UNIT_MAP.get(key, "")
            draw.text((x, y + 14), f"{val:.1f} {unit}", font=font_med, fill=WHITE)

        draw.rectangle([0, HEIGHT - 18, WIDTH, HEIGHT], fill=(30, 30, 50))
        status = "Online" if page.connected else "Offline"
        color = (34, 197, 94) if page.connected else (239, 68, 68)
        draw.text((8, HEIGHT - 15), status, font=font_small, fill=color)
        if page.battery_voltage is not None:
            draw.text(
                (WIDTH - 90, HEIGHT - 15),
                f"Akku: {page.battery_voltage:.1f}V",
                font=font_small,
                fill=WHITE,
            )

        if self._rotation:
            img = img.rotate(self._rotation, expand=True)

        try:
            raw = img.tobytes()
            with open(self._device, "wb") as fb:
                fb.write(raw)
        except Exception as exc:
            logger.warning("TFT framebuffer write error: %s", exc)
