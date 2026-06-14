from __future__ import annotations
import datetime
import logging
import struct
import subprocess
from pathlib import Path
from .base import BaseDisplay, DisplayPage

logger = logging.getLogger(__name__)

_FB = Path("/dev/fb0")
_FB_VSIZE = Path("/sys/class/graphics/fb0/virtual_size")
_FB_BPP = Path("/sys/class/graphics/fb0/bits_per_pixel")

# Farben
BG      = (18, 18, 32)
SURFACE = (30, 30, 50)
WHITE   = (255, 255, 255)
GREY    = (120, 113, 108)
AMBER   = (245, 158, 11)
GREEN   = (34, 197, 94)
RED     = (239, 68, 68)

UNIT_MAP: dict[str, str] = {
    "weight_kg": "kg", "temperature_c": "C", "humidity_pct": "%",
    "pressure_hpa": "hPa", "illuminance_lux": "lx",
    "gas_resistance_ohm": "Ohm", "voltage_v": "V",
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
    try:
        w, h = _FB_VSIZE.read_text().strip().split(",")
        bpp = int(_FB_BPP.read_text().strip())
        return int(w), int(h), bpp
    except Exception:
        return 1920, 1080, 32


def _img_to_fb(img: object, bpp: int) -> bytes:
    try:
        from PIL import Image  # type: ignore[import-untyped]
        assert isinstance(img, Image.Image)
        if bpp == 16:
            pixels = list(img.convert("RGB").getdata())
            buf = bytearray(len(pixels) * 2)
            for i, (r, g, b) in enumerate(pixels):
                val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                struct.pack_into("<H", buf, i * 2, val)
            return bytes(buf)
        else:
            rgba = img.convert("RGBA")
            r, g, b, a = rgba.split()
            bgra = type(rgba).merge("RGBA", (b, g, r, a))
            return bgra.tobytes()
    except Exception as exc:
        logger.error("FB convert error: %s", exc)
        return b""


def _get_network_status() -> list[tuple[str, str, bool]]:
    """Gibt Liste von (Label, IP/Status, verbunden) zurück."""
    result = []
    try:
        out = subprocess.run(
            ["ip", "-br", "addr"], capture_output=True, text=True, timeout=3
        ).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            iface, state = parts[0], parts[1]
            if iface.startswith("lo") or iface.startswith("HaniPi"):
                continue

            ip = next(
                (p.split("/")[0] for p in parts[2:]
                 if "." in p
                 and not p.startswith("127.")
                 and not p.startswith("169.254")
                 and not p.startswith("10.42.")),
                None,
            )

            connected = state in ("UP", "UNKNOWN") and ip is not None

            if iface.startswith("wlan"):
                try:
                    ssid = subprocess.run(
                        ["iwgetid", iface, "-r"],
                        capture_output=True, text=True, timeout=2,
                    ).stdout.strip()
                    label = f"WLAN  {ssid}" if ssid else "WLAN"
                except Exception:
                    label = "WLAN"
                result.append((label, ip or "nicht verbunden", connected))

            elif iface.startswith(("eth", "enp", "end")):
                result.append(("LAN  (Kabel)", ip or "nicht verbunden", connected))

            elif iface.startswith(("wwan", "ppp", "usb")):
                result.append(("4G  Mobilnetz", ip or "verbunden", connected))

    except Exception as exc:
        logger.debug("Network scan error: %s", exc)

    if not result:
        result.append(("Netzwerk", "nicht verbunden", False))
    return result


def _load_fonts(sizes: list[int]) -> list[object]:
    from PIL import ImageFont  # type: ignore[import-untyped]
    fonts: list[object] = []
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for size in sizes:
        loaded = False
        for path in paths:
            try:
                fonts.append(ImageFont.truetype(path, size))
                loaded = True
                break
            except OSError:
                continue
        if not loaded:
            fonts.append(ImageFont.load_default())
    return fonts


class HDMIDisplay(BaseDisplay):
    """HDMI-Display via PIL direktes Framebuffer-Schreiben nach /dev/fb0."""

    def __init__(self, rotation: int = 0) -> None:
        self._rotation = rotation
        self._available = False
        self._w = 1024
        self._h = 600
        self._bpp = 16

    def start(self) -> None:
        try:
            from PIL import Image  # type: ignore[import-untyped]  # noqa: F401
        except ImportError:
            logger.warning("HDMIDisplay: Pillow nicht installiert")
            return
        if not _FB.exists():
            logger.warning("HDMIDisplay: /dev/fb0 nicht gefunden")
            return
        self._w, self._h, self._bpp = _detect_fb()
        self._available = True
        logger.info("HDMIDisplay bereit: %dx%d %d-bit (%s)", self._w, self._h, self._bpp, _FB)

    def stop(self) -> None:
        pass

    def show_boot_splash(self) -> None:
        """Kurzer Startbildschirm mit Branding — wird einmalig beim Start angezeigt."""
        if not self._available:
            return
        try:
            from PIL import Image, ImageDraw  # type: ignore[import-untyped]
            font_xl, font_lg, font_md, font_sm = _load_fonts([72, 40, 26, 18])

            img = Image.new("RGB", (self._w, self._h), BG)
            draw = ImageDraw.Draw(img)
            W, H = self._w, self._h
            cx = W // 2

            # Amber-Streifen oben und unten
            draw.rectangle([0, 0, W, 8], fill=AMBER)
            draw.rectangle([0, H - 8, W, H], fill=AMBER)

            # Hintergrund-Kreis
            r = min(W, H) // 5
            draw.ellipse([cx - r, H // 2 - r - 60, cx + r, H // 2 + r - 60],
                         fill=(35, 32, 20))

            # Honig-Symbol
            draw.text((cx, H // 2 - 60), "HaniPi",
                      fill=AMBER, font=font_xl, anchor="mm")

            # Trennlinie
            lw = W // 3
            draw.rectangle([cx - lw // 2, H // 2 + 20, cx + lw // 2, H // 2 + 23],
                           fill=AMBER)

            # Untertexte
            draw.text((cx, H // 2 + 55), "Bienenstock-Monitoring",
                      fill=WHITE, font=font_md, anchor="mm")
            draw.text((cx, H // 2 + 90), "by Thomas Schopf",
                      fill=GREY, font=font_sm, anchor="mm")
            draw.text((cx, H // 2 + 115), "hanipi.hanimat.at",
                      fill=(100, 100, 130), font=font_sm, anchor="mm")

            # Startet...
            draw.text((cx, H - 30), "Startet ...",
                      fill=(70, 70, 90), font=font_sm, anchor="mm")

            self._write(img)
        except Exception as exc:
            logger.warning("Boot splash error: %s", exc)

    def show_splash(self, page: DisplayPage) -> None:
        """Idle-Screen: Logo + Uhrzeit + Netzwerk-Status."""
        if not self._available:
            return
        try:
            from PIL import Image, ImageDraw  # type: ignore[import-untyped]
            font_xl, font_lg, font_md, font_sm = _load_fonts([56, 36, 26, 18])

            img = Image.new("RGB", (self._w, self._h), BG)
            draw = ImageDraw.Draw(img)

            W, H = self._w, self._h

            # Linke Seite — Logo + Titel
            left_w = W // 2

            # Amber-Akzentlinie links
            draw.rectangle([0, 0, 4, H], fill=AMBER)

            # Titel
            draw.text((left_w // 2, H // 2 - 80), "HaniPi",
                      fill=WHITE, font=font_xl, anchor="mm")
            draw.text((left_w // 2, H // 2 - 20),
                      "Bienenstock-Monitoring",
                      fill=GREY, font=font_md, anchor="mm")

            # Uhrzeit gross
            now = datetime.datetime.now()
            draw.text((left_w // 2, H // 2 + 50),
                      now.strftime("%H:%M"),
                      fill=AMBER, font=font_xl, anchor="mm")
            draw.text((left_w // 2, H // 2 + 110),
                      now.strftime("%d.%m.%Y"),
                      fill=GREY, font=font_sm, anchor="mm")

            # Wartetext
            draw.text((left_w // 2, H - 40),
                      "Warte auf Sensordaten ...",
                      fill=(70, 70, 90), font=font_sm, anchor="mm")

            # Trennlinie
            draw.rectangle([left_w - 1, 20, left_w + 1, H - 20], fill=(45, 45, 65))

            # Rechte Seite — Netzwerk
            rx = left_w + 20
            draw.text((rx, 30), "Verbindung", fill=GREY, font=font_sm)

            network = _get_network_status()
            y = 80
            for label, value, ok in network:
                color = GREEN if ok else RED
                # Status-Punkt
                draw.ellipse([rx, y + 4, rx + 12, y + 16], fill=color)
                draw.text((rx + 22, y), label, fill=WHITE, font=font_md)
                draw.text((rx + 22, y + 28), value, fill=GREY, font=font_sm)
                y += 80

            self._write(img)
        except Exception as exc:
            logger.warning("Splash render error: %s", exc)

    def show_page(self, page: DisplayPage) -> None:
        if not self._available:
            return
        try:
            self._render(page)
        except Exception as exc:
            logger.error("HDMIDisplay render error: %s", exc)

    def _render(self, page: DisplayPage) -> None:
        from PIL import Image, ImageDraw  # type: ignore[import-untyped]
        font_lg, font_md, font_sm, font_xs = _load_fonts([36, 28, 20, 16])

        img = Image.new("RGB", (self._w, self._h), BG)
        draw = ImageDraw.Draw(img)
        W, H = self._w, self._h

        accent = _hex_to_rgb(page.hive_color)

        # Header
        draw.rectangle([0, 0, W, 70], fill=accent)
        draw.text((20, 12), page.hive_name, fill=WHITE, font=font_lg)

        ts = datetime.datetime.fromtimestamp(page.timestamp).strftime("%d.%m.%Y  %H:%M")
        draw.text((W - 20, 42), ts, fill=(255, 255, 255, 180), font=font_xs, anchor="rm")

        # Sensor-Werte als Kacheln
        items = [(k, v) for k, v in page.values.items()]
        if not items:
            draw.text((W // 2, H // 2), "Keine Daten", fill=GREY, font=font_md, anchor="mm")
        else:
            cols = 3 if len(items) > 2 else len(items)
            rows = (len(items) + cols - 1) // cols
            tile_w = W // cols
            tile_h = (H - 100) // rows

            for i, (key, val) in enumerate(items[:cols * rows]):
                row, col = divmod(i, cols)
                x = col * tile_w
                y = 80 + row * tile_h

                # Kachelrahmen
                draw.rectangle([x + 8, y + 6, x + tile_w - 8, y + tile_h - 6],
                                fill=SURFACE)

                label = LABEL_MAP.get(key, key)
                unit = UNIT_MAP.get(key, "")
                draw.text((x + tile_w // 2, y + tile_h // 2 - 20),
                          label, fill=GREY, font=font_xs, anchor="mm")
                draw.text((x + tile_w // 2, y + tile_h // 2 + 14),
                          f"{val:.1f} {unit}", fill=WHITE, font=font_md, anchor="mm")

        # Footer
        draw.rectangle([0, H - 32, W, H], fill=SURFACE)

        net = _get_network_status()
        net_text = "  |  ".join(
            f"{lbl}: {val}" for lbl, val, ok in net if ok
        ) or "Kein Netzwerk"
        draw.text((20, H - 24), net_text, fill=GREY, font=font_xs)

        now = datetime.datetime.now().strftime("%H:%M")
        draw.text((W - 20, H - 24), now, fill=GREY, font=font_xs, anchor="rm")

        if page.battery_voltage is not None:
            batt_color = GREEN if page.battery_voltage > 3.6 else RED
            draw.text((W // 2, H - 24),
                      f"Akku  {page.battery_voltage:.1f}V",
                      fill=batt_color, font=font_xs, anchor="mm")

        self._write(img)

    def _write(self, img: object) -> None:
        from PIL import Image  # type: ignore[import-untyped]
        assert isinstance(img, Image.Image)
        if self._rotation:
            img = img.rotate(self._rotation, expand=True)
        raw = _img_to_fb(img, self._bpp)
        if raw:
            _FB.write_bytes(raw)
