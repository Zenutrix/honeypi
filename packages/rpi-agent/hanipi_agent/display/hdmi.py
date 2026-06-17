from __future__ import annotations

import datetime
import logging
import math
import struct
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from .base import BaseDisplay, DisplayPage

if TYPE_CHECKING:
    from PIL import Image, ImageDraw, ImageFont

    FontT = ImageFont.FreeTypeFont | ImageFont.ImageFont

logger = logging.getLogger(__name__)

_FB = Path("/dev/fb0")
_FB_SIZE = Path("/sys/class/graphics/fb0/virtual_size")
_FB_BPP = Path("/sys/class/graphics/fb0/bits_per_pixel")

# ── Farben – deckungsgleich mit Web-UI (System Dark) ─────────────────────────
BG = (28, 28, 30)  # --bg        #1c1c1e
SURFACE = (44, 44, 46)  # --surface   #2c2c2e
SURF2 = (58, 58, 60)  # --surface-2 #3a3a3c
BORDER = (72, 72, 74)  # --border    #48484a
AMBER = (245, 158, 11)  # --amber     #f59e0b
AMBER_D = (180, 110, 5)  # --amber-dim #d97706
WHITE = (255, 255, 255)  # --text
MUTED = (142, 142, 147)  # --text-muted #8e8e93
FAINT = (72, 72, 74)  # --text-faint #48484a
GREEN = (48, 209, 88)  # --success   #30d158
RED = (255, 69, 58)  # --danger    #ff453a

# ── Typografie-Skala (1024×600-Referenz, via _s() skaliert) ─────────────────
SIZE_DISPLAY = 120  # Hero-Messwert
SIZE_TITLE = 40  # Stockname im Header
SIZE_HEADING = 64  # Sekundäre Kachel-Werte
SIZE_BODY = 26  # Labels, Idle-Datum
SIZE_CAPTION = 20  # Footer, Einheiten, Netzwerk, Header-Uhr
SIZE_BOOT_LOGO = 96  # Boot-Splash-Logo (Sonderfall)
SIZE_IDLE_CLOCK = 140  # Idle-Screen-Uhrzeit (Sonderfall)

# ── Spacing-Skala ─────────────────────────────────────────────────────────
SPACE_XS = 8
SPACE_SM = 16
SPACE_MD = 24
SPACE_LG = 32

UNIT_MAP = {
    "weight_kg": "kg",
    "temperature_c": "°C",
    "humidity_pct": "%",
    "pressure_hpa": "hPa",
    "illuminance_lux": "lx",
    "gas_resistance_ohm": "Ω",
    "voltage_v": "V",
}
LABEL_MAP = {
    "weight_kg": "Gewicht",
    "temperature_c": "Temperatur",
    "humidity_pct": "Feuchte",
    "pressure_hpa": "Luftdruck",
    "illuminance_lux": "Licht",
    "gas_resistance_ohm": "Gas",
    "voltage_v": "Spannung",
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _detect_fb() -> tuple[int, int, int]:
    try:
        w, h = _FB_SIZE.read_text().strip().split(",")
        bpp = int(_FB_BPP.read_text().strip())
        return int(w), int(h), bpp
    except Exception:
        return 1024, 600, 16


def _to_bytes(img: Image.Image, bpp: int) -> bytes:
    from PIL import Image

    assert isinstance(img, Image.Image)
    try:
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
            return Image.merge("RGBA", (b, g, r, a)).tobytes()
    except Exception as exc:
        logger.error("FB convert: %s", exc)
        return b""


def _fonts(sizes: list[int]) -> list[FontT]:
    from PIL import ImageFont

    bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    reg = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    out: list[FontT] = []
    for i, size in enumerate(sizes):
        path = bold if i % 2 == 0 else reg
        for p in (path, bold, reg):
            try:
                out.append(ImageFont.truetype(p, size))
                break
            except OSError:
                continue
        else:
            logger.warning(
                "DejaVu-Schriftart nicht gefunden (%s) — Anzeige nutzt PIL-"
                "Mini-Fallback-Font, der jede Groessenangabe ignoriert. "
                "Fix: sudo apt-get install fonts-dejavu-core",
                bold,
            )
            out.append(ImageFont.load_default())
    return out


def _get_network() -> list[tuple[str, str, bool]]:
    result = []
    try:
        out = subprocess.run(
            ["ip", "-br", "addr"],
            capture_output=True,
            text=True,
            timeout=3,
        ).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            iface, state = parts[0], parts[1]
            if iface.startswith(("lo", "HaniPi", "docker")):
                continue
            ip = next(
                (
                    p.split("/")[0]
                    for p in parts[2:]
                    if "." in p and not p.startswith(("127.", "169.254", "10.42."))
                ),
                None,
            )
            connected = state in ("UP", "UNKNOWN") and ip is not None
            if iface.startswith("wlan"):
                try:
                    ssid = subprocess.run(
                        ["iwgetid", iface, "-r"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    ).stdout.strip()
                except Exception:
                    ssid = ""
                result.append(
                    (f"WLAN  {ssid}" if ssid else "WLAN", ip or "—", connected)
                )
            elif iface.startswith(("eth", "enp", "end")):
                result.append(("LAN", ip or "—", connected))
            elif iface.startswith(("wwan", "ppp", "usb")):
                result.append(("4G", ip or "verbunden", connected))
    except Exception:
        pass
    return result or [("Netzwerk", "nicht verbunden", False)]


def _pill_outline(
    d: ImageDraw.ImageDraw,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    radius: int,
) -> None:
    d.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline)


def _draw_icon(
    d: ImageDraw.ImageDraw,
    key: str,
    cx: int,
    cy: int,
    size: int,
    color: tuple[int, int, int],
) -> None:
    """Zeichnet ein einfaches Icon für den Messwert-Typ, zentriert auf (cx, cy)."""
    r = max(3, size // 2)
    w = max(2, size // 10)
    if key == "weight_kg":
        d.line([cx, cy - r, cx, cy], fill=color, width=w)
        d.line([cx - r, cy, cx + r, cy], fill=color, width=w)
        cr = max(2, r // 3)
        d.ellipse([cx - r - cr, cy, cx - r + cr, cy + 2 * cr], outline=color, width=w)
        d.ellipse([cx + r - cr, cy, cx + r + cr, cy + 2 * cr], outline=color, width=w)
    elif key == "temperature_c":
        bulb_r = max(3, int(r * 0.55))
        stem_w = max(2, int(r * 0.5))
        d.rounded_rectangle(
            [cx - stem_w // 2, cy - r, cx + stem_w // 2, cy + bulb_r],
            radius=stem_w // 2,
            outline=color,
            width=w,
        )
        d.ellipse(
            [
                cx - bulb_r,
                cy + bulb_r - 2 * bulb_r // 3,
                cx + bulb_r,
                cy + bulb_r + 2 * bulb_r // 3,
            ],
            fill=color,
        )
    elif key == "humidity_pct":
        d.polygon(
            [
                (cx, cy - r),
                (cx + int(r * 0.7), cy + int(r * 0.4)),
                (cx, cy + r),
                (cx - int(r * 0.7), cy + int(r * 0.4)),
            ],
            fill=color,
        )
    elif key == "pressure_hpa":
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=w)
        d.line([cx, cy, cx + int(r * 0.6), cy - int(r * 0.5)], fill=color, width=w)
        d.ellipse([cx - w, cy - w, cx + w, cy + w], fill=color)
    elif key == "illuminance_lux":
        cr = max(2, int(r * 0.5))
        d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=color)
        for i in range(8):
            ang = math.pi * 2 * i / 8
            x0 = cx + int(math.cos(ang) * cr * 1.6)
            y0 = cy + int(math.sin(ang) * cr * 1.6)
            x1 = cx + int(math.cos(ang) * r)
            y1 = cy + int(math.sin(ang) * r)
            d.line([x0, y0, x1, y1], fill=color, width=w)
    elif key == "gas_resistance_ohm":
        cr = max(2, int(r * 0.5))
        d.ellipse(
            [cx - r, cy - cr // 2, cx - r + 2 * cr, cy - cr // 2 + 2 * cr], fill=color
        )
        d.ellipse([cx - cr, cy - cr, cx - cr + 2 * cr, cy - cr + 2 * cr], fill=color)
        d.ellipse([cx, cy - cr // 2, cx + 2 * cr, cy - cr // 2 + 2 * cr], fill=color)
    elif key == "voltage_v":
        d.polygon(
            [
                (cx + int(r * 0.2), cy - r),
                (cx - int(r * 0.5), cy + int(r * 0.1)),
                (cx, cy + int(r * 0.1)),
                (cx - int(r * 0.2), cy + r),
                (cx + int(r * 0.5), cy - int(r * 0.1)),
                (cx, cy - int(r * 0.1)),
            ],
            fill=color,
        )
    else:
        cr = max(3, int(r * 0.6))
        d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=color)


# ── Normalbereiche & Statusfarben ────────────────────────────────────────────

_BAR_RANGES: dict[str, tuple[float, float]] = {
    "temperature_c": (0.0, 60.0),
    "humidity_pct": (0.0, 100.0),
    "illuminance_lux": (0.0, 100_000.0),
    "pressure_hpa": (950.0, 1050.0),
    "gas_resistance_ohm": (0.0, 500_000.0),
    "voltage_v": (3.0, 4.2),
}


def _bar_range(key: str) -> tuple[float, float] | None:
    return _BAR_RANGES.get(key)


def _value_status(key: str, val: float) -> str:
    if key == "temperature_c":
        if 15 <= val <= 40:
            return "good"
        if 10 <= val <= 45:
            return "warn"
        return "bad"
    if key == "humidity_pct":
        if 40 <= val <= 80:
            return "good"
        if 30 <= val <= 90:
            return "warn"
        return "bad"
    if key == "voltage_v":
        if val > 3.7:
            return "good"
        if val >= 3.5:
            return "warn"
        return "bad"
    if key == "pressure_hpa":
        if 990 <= val <= 1030:
            return "good"
        return "warn"
    return "neutral"


def _status_color(status: str) -> tuple[int, int, int]:
    return {"good": GREEN, "warn": AMBER, "bad": RED}.get(status, MUTED)


def _draw_trend(
    d: ImageDraw.ImageDraw,
    trend: str,
    x: int,
    y: int,
    size: int,
    key: str,
    val: float,
) -> None:
    if trend == "up":
        color = GREEN if key != "weight_kg" else GREEN
    elif trend == "down":
        status = _value_status(key, val)
        color = RED if status == "bad" or key == "weight_kg" else AMBER
    else:
        color = MUTED

    h = size
    w = max(2, size // 3)
    if trend == "up":
        d.polygon([(x, y - h // 2), (x - w, y + h // 2), (x + w, y + h // 2)], fill=color)
    elif trend == "down":
        d.polygon([(x, y + h // 2), (x - w, y - h // 2), (x + w, y - h // 2)], fill=color)
    else:
        d.line([x - w, y, x + w, y], fill=color, width=max(2, size // 6))


def _draw_bar(
    d: ImageDraw.ImageDraw,
    key: str,
    val: float,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> None:
    rng = _bar_range(key)
    if rng is None:
        return
    lo, hi = rng
    frac = max(0.0, min(1.0, (val - lo) / (hi - lo)))
    status = _value_status(key, val)
    fill_color = _status_color(status)
    r = (y1 - y0) // 2
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=SURF2)
    fill_w = int((x1 - x0) * frac)
    if fill_w > r * 2:
        d.rounded_rectangle([x0, y0, x0 + fill_w, y1], radius=r, fill=fill_color)
    elif fill_w > 0:
        d.ellipse([x0, y0, x0 + r * 2, y1], fill=fill_color)


# ── Display ───────────────────────────────────────────────────────────────────


class HDMIDisplay(BaseDisplay):
    def __init__(self, rotation: int = 0) -> None:
        self._rotation = rotation
        self._available = False
        self._w, self._h, self._bpp = 1024, 600, 16

    def _s(self, n: int) -> int:
        return max(4, int(n * min(self._w / 1024, self._h / 600)))

    def start(self) -> None:
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            logger.warning("Pillow nicht installiert")
            return
        if not _FB.exists():
            logger.warning("/dev/fb0 nicht gefunden")
            return
        self._w, self._h, self._bpp = _detect_fb()
        self._available = True
        logger.info("HDMIDisplay %dx%d %dbit", self._w, self._h, self._bpp)
        self._hide_cursor()

    def stop(self) -> None:
        pass

    def _hide_cursor(self) -> None:
        try:
            Path("/sys/class/graphics/fbcon/cursor_blink").write_text("0")
        except Exception:
            pass
        for tty in ("/dev/tty1", "/dev/tty0"):
            try:
                with open(tty, "wb") as f:
                    f.write(b"\033[?25l\033[?17;0;0c")
                break
            except Exception:
                pass

    def _flush(self, img: Image.Image) -> None:
        from PIL import Image

        assert isinstance(img, Image.Image)
        if self._rotation:
            img = img.rotate(self._rotation, expand=True)
        raw = _to_bytes(img, self._bpp)
        if raw:
            _FB.write_bytes(raw)

    def _new(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (self._w, self._h), BG)
        return img, ImageDraw.Draw(img)

    # ── Boot-Splash ───────────────────────────────────────────────────────────

    def show_boot_splash(self) -> None:
        if not self._available:
            return
        try:
            img, d = self._new()
            W, H = self._w, self._h

            f_logo, f_sub, f_hint, f_small = _fonts(
                [
                    self._s(SIZE_BOOT_LOGO),
                    self._s(SIZE_BODY),
                    self._s(SIZE_CAPTION),
                    self._s(SIZE_CAPTION),
                ]
            )

            cx = W // 2
            cy = H // 2 - self._s(20)

            # Amber-Akzentlinie oben
            d.rectangle([0, 0, W, self._s(4)], fill=AMBER)

            # Logo "HaniPi" — "Hani" weiß, "Pi" amber
            try:
                hani_w = int(f_logo.getlength("Hani"))
                pi_w = int(f_logo.getlength("Pi"))
                total = hani_w + pi_w
                lx = cx - total // 2
                d.text(
                    (lx, cy - self._s(50)), "Hani", fill=WHITE, font=f_logo, anchor="lt"
                )
                d.text(
                    (lx + hani_w, cy - self._s(50)),
                    "Pi",
                    fill=AMBER,
                    font=f_logo,
                    anchor="lt",
                )
            except Exception:
                d.text(
                    (cx, cy - self._s(50)),
                    "HaniPi",
                    fill=AMBER,
                    font=f_logo,
                    anchor="mt",
                )

            # Dünne Trennlinie unter Logo
            lw = self._s(220)
            d.rectangle(
                [cx - lw, cy + self._s(56), cx + lw, cy + self._s(58)], fill=BORDER
            )

            d.text(
                (cx, cy + self._s(80)),
                "Bienenstock-Monitoring",
                fill=WHITE,
                font=f_sub,
                anchor="mm",
            )
            d.text(
                (cx, cy + self._s(112)),
                "by Thomas Schöpf",
                fill=MUTED,
                font=f_hint,
                anchor="mm",
            )

            # Ladebalken-Dots
            dot_y = H - self._s(38)
            for i, dot_x in enumerate([cx - self._s(18), cx, cx + self._s(18)]):
                col = AMBER if i == 1 else SURF2
                r = self._s(5) if i == 1 else self._s(4)
                d.ellipse([dot_x - r, dot_y - r, dot_x + r, dot_y + r], fill=col)

            d.text(
                (cx, H - self._s(16)),
                "System startet …",
                fill=FAINT,
                font=f_small,
                anchor="mm",
            )

            self._flush(img)
        except Exception as exc:
            logger.warning("Boot-Splash: %s", exc)

    # ── Idle-Screen (keine Daten) ─────────────────────────────────────────────

    def show_splash(self, page: DisplayPage) -> None:
        if not self._available:
            return
        try:
            img, d = self._new()
            W, H = self._w, self._h

            f_clock, f_date, f_net, f_hint = _fonts(
                [
                    self._s(SIZE_IDLE_CLOCK),
                    self._s(SIZE_BODY),
                    self._s(SIZE_CAPTION),
                    self._s(SIZE_CAPTION),
                ]
            )

            now = datetime.datetime.now()
            cx = W // 2

            # Amber-Akzentlinie oben
            d.rectangle([0, 0, W, self._s(4)], fill=AMBER)

            # Uhrzeit — zentriert, leicht über Mitte
            d.text(
                (cx, H // 2 - self._s(30)),
                now.strftime("%H:%M"),
                fill=WHITE,
                font=f_clock,
                anchor="mm",
            )

            # Datum
            d.text(
                (cx, H // 2 + self._s(90)),
                now.strftime("%A, %d. %B %Y"),
                fill=MUTED,
                font=f_date,
                anchor="mm",
            )

            # Dünne Trennlinie
            d.rectangle(
                [
                    cx - self._s(180),
                    H // 2 + self._s(118),
                    cx + self._s(180),
                    H // 2 + self._s(119),
                ],
                fill=BORDER,
            )

            # Netzwerk-Info
            net = _get_network()
            ny = H // 2 + self._s(142)
            for label, ip, ok in net[:2]:
                dot_c = GREEN if ok else RED
                dot_x = cx - self._s(130)
                d.ellipse(
                    [
                        dot_x - self._s(5),
                        ny - self._s(5),
                        dot_x + self._s(5),
                        ny + self._s(5),
                    ],
                    fill=dot_c,
                )
                d.text(
                    (dot_x + self._s(14), ny),
                    f"{label}  {ip}",
                    fill=MUTED if ok else FAINT,
                    font=f_net,
                    anchor="lm",
                )
                ny += self._s(30)

            # Wartetext
            d.text(
                (cx, H - self._s(22)),
                "Warte auf Sensordaten …",
                fill=FAINT,
                font=f_hint,
                anchor="mm",
            )
            self._flush(img)
        except Exception as exc:
            logger.warning("Idle-Screen: %s", exc)

    # ── Datenseite ────────────────────────────────────────────────────────────

    def show_page(self, page: DisplayPage) -> None:
        if not self._available:
            return
        try:
            self._render_data(page)
        except Exception as exc:
            logger.error("Datenseite: %s", exc)

    def _render_data(self, page: DisplayPage) -> None:
        trends = page.trends
        img, d = self._new()
        W, H = self._w, self._h

        accent = _hex_to_rgb(page.hive_color)

        ACCENT_H = self._s(4)
        HEADER_H = self._s(80)
        FOOTER_H = self._s(56)
        PAD = self._s(SPACE_MD)

        body_top = ACCENT_H + HEADER_H
        body_h = H - body_top - FOOTER_H

        f_hive, f_clock, f_lbl, f_hero_val, f_tile_val, f_unit = _fonts(
            [
                self._s(SIZE_TITLE),
                self._s(SIZE_CAPTION),
                self._s(SIZE_BODY),
                self._s(SIZE_DISPLAY),
                self._s(SIZE_HEADING),
                self._s(SIZE_CAPTION),
            ]
        )

        # ── Akzent-Linie oben (Hive-Farbe) ───────────────────────────────────
        d.rectangle([0, 0, W, ACCENT_H], fill=accent)

        # ── Header ────────────────────────────────────────────────────────────
        d.rectangle([0, ACCENT_H, W, ACCENT_H + HEADER_H], fill=SURFACE)

        d.text(
            (self._s(SPACE_LG), ACCENT_H + HEADER_H // 2),
            page.hive_name,
            fill=WHITE,
            font=f_hive,
            anchor="lm",
        )

        status_color = GREEN if page.connected else RED
        sr = self._s(6)
        sx = W - self._s(SPACE_LG) - self._s(120)
        sy = ACCENT_H + HEADER_H // 2
        d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=status_color)
        d.text(
            (W - self._s(SPACE_LG), sy),
            datetime.datetime.now().strftime("%H:%M"),
            fill=MUTED,
            font=f_clock,
            anchor="rm",
        )

        # Trennlinie Header/Body
        d.rectangle([0, ACCENT_H + HEADER_H, W, ACCENT_H + HEADER_H + 1], fill=BORDER)

        # ── Footer ────────────────────────────────────────────────────────────
        fy = H - FOOTER_H
        d.rectangle([0, fy, W, H], fill=SURFACE)
        d.rectangle([0, fy, W, fy + 1], fill=BORDER)

        net = _get_network()
        net_txt = (
            "  ·  ".join(f"{lbl}: {ip}" for lbl, ip, ok in net if ok) or "kein Netzwerk"
        )
        d.text(
            (self._s(SPACE_SM), fy + FOOTER_H // 2),
            net_txt,
            fill=MUTED,
            font=f_unit,
            anchor="lm",
        )

        ts = datetime.datetime.fromtimestamp(page.timestamp).strftime("%d.%m.%Y  %H:%M")
        d.text(
            (W - self._s(SPACE_SM), fy + FOOTER_H // 2),
            ts,
            fill=FAINT,
            font=f_unit,
            anchor="rm",
        )

        # ── Body: maximal 3 Messwerte (Dichte-Regel) ─────────────────────────
        items = list(page.values.items())
        if not items:
            d.text(
                (W // 2, body_top + body_h // 2),
                "Keine Messwerte",
                fill=MUTED,
                font=f_hive,
                anchor="mm",
            )
            self._flush(img)
            return

        fonts = (f_lbl, f_hero_val, f_tile_val, f_unit)

        if len(items) == 1:
            self._draw_hero(
                d, items[0], accent, PAD, body_top + PAD, W - PAD, fy - PAD, fonts,
                trend=trends.get(items[0][0], "stable"),
            )
        elif len(items) == 2:
            avail_w = W - PAD * 3
            hero_w = int(avail_w * 0.58)
            self._draw_hero(
                d, items[0], accent, PAD, body_top + PAD, PAD + hero_w, fy - PAD, fonts,
                trend=trends.get(items[0][0], "stable"),
            )
            self._draw_tile(
                d, items[1], accent, PAD * 2 + hero_w, body_top + PAD, W - PAD, fy - PAD, fonts,
                trend=trends.get(items[1][0], "stable"),
            )
        else:
            avail_w = W - PAD * 3
            hero_w = int(avail_w * 0.58)
            self._draw_hero(
                d, items[0], accent, PAD, body_top + PAD, PAD + hero_w, fy - PAD, fonts,
                trend=trends.get(items[0][0], "stable"),
            )
            tile_x0 = PAD * 2 + hero_w
            tile_h = (body_h - PAD * 3) // 2
            self._draw_tile(
                d, items[1], accent, tile_x0, body_top + PAD, W - PAD, body_top + PAD + tile_h, fonts,
                trend=trends.get(items[1][0], "stable"),
            )
            self._draw_tile(
                d, items[2], accent, tile_x0, body_top + PAD * 2 + tile_h, W - PAD, fy - PAD, fonts,
                trend=trends.get(items[2][0], "stable"),
            )

        self._flush(img)

    def _draw_label_row(
        self,
        d: ImageDraw.ImageDraw,
        key: str,
        cx: int,
        y: int,
        icon_size: int,
        f_lbl: FontT,
    ) -> None:
        """Icon + Label, als Gruppe horizontal zentriert auf cx."""
        label = LABEL_MAP.get(key, key).upper()
        try:
            label_w = int(f_lbl.getlength(label))
        except Exception:
            label_w = len(label) * icon_size

        gap = max(4, icon_size // 3)
        total_w = icon_size + gap + label_w
        start_x = cx - total_w // 2

        _draw_icon(d, key, start_x + icon_size // 2, y, icon_size, MUTED)
        d.text(
            (start_x + icon_size + gap, y), label, fill=MUTED, font=f_lbl, anchor="lm"
        )

    def _draw_hero(
        self,
        d: ImageDraw.ImageDraw,
        item: tuple[str, float],
        accent: tuple[int, int, int],
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        fonts: tuple[FontT, FontT, FontT, FontT],
        trend: str = "stable",
    ) -> None:
        key, val = item
        f_lbl, f_hero_val, _f_tile_val, f_unit = fonts
        unit = UNIT_MAP.get(key, "")
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2

        _pill_outline(d, x0, y0, x1, y1, SURFACE, BORDER, self._s(14))
        d.rounded_rectangle(
            [x0 + 1, y0 + 1, x1 - 1, y0 + self._s(3)], radius=self._s(14), fill=accent
        )

        self._draw_label_row(d, key, cx, cy - self._s(72), self._s(28), f_lbl)

        val_str = f"{val:.1f}" if isinstance(val, float) else str(val)
        d.text(
            (cx, cy + self._s(10)), val_str, fill=WHITE, font=f_hero_val, anchor="mm"
        )

        try:
            val_w = int(f_hero_val.getlength(val_str))
        except Exception:
            val_w = self._s(140)

        unit_x = cx + val_w // 2 + self._s(SPACE_SM)
        d.text(
            (unit_x, cy + self._s(24)),
            unit,
            fill=accent,
            font=f_unit,
            anchor="lm",
        )

        trend_size = self._s(36)
        trend_x = unit_x + self._s(SPACE_MD)
        _draw_trend(d, trend, trend_x, cy + self._s(10), trend_size, key, val)

        bar_h = self._s(8)
        bar_w = int((x1 - x0) * 0.68)
        bar_x0 = cx - bar_w // 2
        bar_y0 = cy + self._s(52)
        _draw_bar(d, key, val, bar_x0, bar_y0, bar_x0 + bar_w, bar_y0 + bar_h)

    def _draw_tile(
        self,
        d: ImageDraw.ImageDraw,
        item: tuple[str, float],
        accent: tuple[int, int, int],
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        fonts: tuple[FontT, FontT, FontT, FontT],
        trend: str = "stable",
    ) -> None:
        key, val = item
        f_lbl, _f_hero_val, f_tile_val, f_unit = fonts
        unit = UNIT_MAP.get(key, "")
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2

        _pill_outline(d, x0, y0, x1, y1, SURFACE, BORDER, self._s(12))
        d.rounded_rectangle(
            [x0 + 1, y0 + 1, x1 - 1, y0 + self._s(3)], radius=self._s(12), fill=accent
        )

        self._draw_label_row(d, key, cx, cy - self._s(40), self._s(20), f_lbl)

        val_str = f"{val:.1f}" if isinstance(val, float) else str(val)
        d.text(
            (cx, cy + self._s(12)), val_str, fill=WHITE, font=f_tile_val, anchor="mm"
        )

        try:
            val_w = int(f_tile_val.getlength(val_str))
        except Exception:
            val_w = self._s(70)

        unit_x = cx + val_w // 2 + self._s(SPACE_XS)
        d.text(
            (unit_x, cy + self._s(20)),
            unit,
            fill=accent,
            font=f_unit,
            anchor="lm",
        )

        trend_size = self._s(24)
        trend_x = unit_x + self._s(SPACE_SM)
        _draw_trend(d, trend, trend_x, cy + self._s(12), trend_size, key, val)

        bar_h = self._s(5)
        pad = self._s(SPACE_SM)
        bar_y1 = y1 - pad
        _draw_bar(d, key, val, x0 + pad, bar_y1 - bar_h, x1 - pad, bar_y1)
