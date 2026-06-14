from __future__ import annotations
import datetime
import logging
import struct
from pathlib import Path
from .base import BaseDisplay, DisplayPage

logger = logging.getLogger(__name__)

_FB = Path("/dev/fb0")
_FB_VSIZE = Path("/sys/class/graphics/fb0/virtual_size")
_FB_BPP = Path("/sys/class/graphics/fb0/bits_per_pixel")

BG = (26, 26, 46)
WHITE = (255, 255, 255)
GREY = (120, 113, 108)

UNIT_MAP: dict[str, str] = {
    "weight_kg": "kg", "temperature_c": "°C", "humidity_pct": "%",
    "pressure_hpa": "hPa", "illuminance_lux": "lx",
    "gas_resistance_ohm": "Ω", "voltage_v": "V",
}
LABEL_MAP: dict[str, str] = {
    "weight_kg": "Gewicht", "temperature_c": "Temperatur",
    "humidity_pct": "Luftfeuchte", "pressure_hpa": "Luftdruck",
    "illuminance_lux": "Licht", "gas_resistance_ohm": "Gas", "voltage_v": "Spannung",
}


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _detect_fb() -> tuple[int, int, int]:
    """Returns (width, height, bits_per_pixel) of /dev/fb0."""
    try:
        w, h = _FB_VSIZE.read_text().strip().split(",")
        bpp = int(_FB_BPP.read_text().strip())
        return int(w), int(h), bpp
    except Exception:
        return 1920, 1080, 32


def _img_to_fb_bytes(img: object, bpp: int) -> bytes:
    """Convert PIL Image to raw framebuffer bytes (RGB565 or XRGB8888)."""
    try:
        from PIL import Image  # type: ignore[import-untyped]
        assert isinstance(img, Image.Image)
        if bpp == 16:
            # RGB565 little-endian
            pixels = img.convert("RGB").getdata()
            buf = bytearray(len(pixels) * 2)
            for i, (r, g, b) in enumerate(pixels):
                val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                struct.pack_into("<H", buf, i * 2, val)
            return bytes(buf)
        else:
            # 32-bit XRGB8888 (framebuffer expects BGRA on most RPi configs)
            rgba = img.convert("RGBA")
            r, g, b, a = rgba.split()
            bgra = type(rgba).merge("RGBA", (b, g, r, a))
            return bgra.tobytes()
    except Exception as exc:
        logger.error("_img_to_fb_bytes failed: %s", exc)
        return b""


class HDMIDisplay(BaseDisplay):
    """HDMI display via PIL direct framebuffer write to /dev/fb0."""

    def __init__(self, rotation: int = 0) -> None:
        self._rotation = rotation
        self._available = False
        self._w = 1920
        self._h = 1080
        self._bpp = 32

    def start(self) -> None:
        try:
            from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-untyped]  # noqa: F401
        except ImportError:
            logger.warning("HDMIDisplay: Pillow nicht installiert (pip install Pillow)")
            return

        if not _FB.exists():
            logger.warning("HDMIDisplay: /dev/fb0 nicht gefunden")
            return

        self._w, self._h, self._bpp = _detect_fb()
        self._available = True
        logger.info("HDMIDisplay bereit: %dx%d %d-bit (%s)", self._w, self._h, self._bpp, _FB)

    def show_page(self, page: DisplayPage) -> None:
        if not self._available:
            return
        try:
            self._render(page)
        except Exception as exc:
            logger.error("HDMIDisplay render error: %s", exc)

    def _render(self, page: DisplayPage) -> None:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-untyped]

        img = Image.new("RGB", (self._w, self._h), BG)
        draw = ImageDraw.Draw(img)

        # Load fonts — try truetype, fall back to default
        try:
            font_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            font_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
            font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        except OSError:
            font_lg = font_md = font_sm = ImageFont.load_default()

        accent = _hex_to_rgb(page.hive_color)

        # Header bar
        draw.rectangle([0, 0, self._w, 80], fill=accent)
        draw.text((24, 14), page.hive_name, fill=WHITE, font=font_lg)

        # Timestamp
        ts = datetime.datetime.fromtimestamp(page.timestamp).strftime("%d.%m.%Y %H:%M")
        draw.text((24, 90), ts, fill=GREY, font=font_sm)

        # Sensor values grid
        items = [(k, v) for k, v in page.values.items() if k != "voltage_v"]
        cols = 3
        cell_w = self._w // cols
        cell_h = max(90, (self._h - 160) // max(1, (len(items) + cols - 1) // cols))
        for i, (key, val) in enumerate(items[:6]):
            row, col = divmod(i, cols)
            x = col * cell_w + 24
            y = 125 + row * cell_h
            draw.text((x, y), LABEL_MAP.get(key, key), fill=GREY, font=font_sm)
            unit = UNIT_MAP.get(key, "")
            draw.text((x, y + 28), f"{val:.1f} {unit}", fill=WHITE, font=font_md)

        # Footer
        draw.rectangle([0, self._h - 40, self._w, self._h], fill=(30, 30, 50))
        status_color = (34, 197, 94) if page.connected else (239, 68, 68)
        status_text = "Online" if page.connected else "Offline"
        draw.text((24, self._h - 30), status_text, fill=status_color, font=font_sm)
        if page.battery_voltage is not None:
            draw.text(
                (self._w - 220, self._h - 30),
                f"Akku: {page.battery_voltage:.1f}V", fill=WHITE, font=font_sm,
            )

        if self._rotation:
            img = img.rotate(self._rotation, expand=True)

        raw = _img_to_fb_bytes(img, self._bpp)
        if raw:
            _FB.write_bytes(raw)
