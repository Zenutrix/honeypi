from __future__ import annotations
import datetime
import logging
import struct
import subprocess
from pathlib import Path
from .base import BaseDisplay, DisplayPage

logger = logging.getLogger(__name__)

_FB      = Path("/dev/fb0")
_FB_SIZE = Path("/sys/class/graphics/fb0/virtual_size")
_FB_BPP  = Path("/sys/class/graphics/fb0/bits_per_pixel")

# Farbpalette
BG      = (13,  17,  23)   # sehr dunkles Blau-Schwarz
CARD    = (22,  27,  34)   # Karten-Hintergrund
AMBER   = (245, 158, 11)   # Primärfarbe
WHITE   = (240, 246, 252)
MUTED   = (110, 118, 129)
GREEN   = (63,  185, 80)
RED     = (248, 81,  73)
DIVIDER = (33,  38,  45)

UNIT_MAP = {
    "weight_kg":        "kg",
    "temperature_c":    "°C",
    "humidity_pct":     "%",
    "pressure_hpa":     "hPa",
    "illuminance_lux":  "lx",
    "gas_resistance_ohm": "Ohm",
    "voltage_v":        "V",
}
LABEL_MAP = {
    "weight_kg":        "Gewicht",
    "temperature_c":    "Temperatur",
    "humidity_pct":     "Luftfeuchte",
    "pressure_hpa":     "Luftdruck",
    "illuminance_lux":  "Licht",
    "gas_resistance_ohm": "Gas",
    "voltage_v":        "Spannung",
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


def _to_fb_bytes(img: object, bpp: int) -> bytes:
    from PIL import Image  # type: ignore[import-untyped]
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


def _fonts(sizes: list[int]) -> list:
    from PIL import ImageFont  # type: ignore[import-untyped]
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    out = []
    for size in sizes:
        for path in candidates:
            try:
                out.append(ImageFont.truetype(path, size))
                break
            except OSError:
                continue
        else:
            out.append(ImageFont.load_default())
    return out


def _get_network() -> list[tuple[str, str, bool]]:
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
                 if "." in p and not p.startswith(("127.", "169.254", "10.42."))),
                None,
            )
            connected = state in ("UP", "UNKNOWN") and ip is not None
            if iface.startswith("wlan"):
                try:
                    ssid = subprocess.run(
                        ["iwgetid", iface, "-r"], capture_output=True, text=True, timeout=2
                    ).stdout.strip()
                    label = f"WLAN  {ssid}" if ssid else "WLAN"
                except Exception:
                    label = "WLAN"
                result.append((label, ip or "nicht verbunden", connected))
            elif iface.startswith(("eth", "enp", "end")):
                result.append(("LAN  Kabel", ip or "nicht verbunden", connected))
            elif iface.startswith(("wwan", "ppp", "usb")):
                result.append(("4G  Mobilnetz", ip or "verbunden", connected))
    except Exception:
        pass
    return result or [("Netzwerk", "nicht verbunden", False)]


# ── Display-Klasse ────────────────────────────────────────────────────────────

class HDMIDisplay(BaseDisplay):
    """HDMI via PIL → /dev/fb0 (kein pygame noetig)."""

    def __init__(self, rotation: int = 0) -> None:
        self._rotation = rotation
        self._available = False
        self._w, self._h, self._bpp = 1024, 600, 16

    def _scale(self, size: int) -> int:
        """Skaliert Fontgröße proportional zur Auflösung (Basis 1024×600)."""
        return max(10, int(size * min(self._w / 1024, self._h / 600)))

    def start(self) -> None:
        try:
            from PIL import Image  # type: ignore[import-untyped]  # noqa: F401
        except ImportError:
            logger.warning("HDMIDisplay: Pillow fehlt  →  pip install Pillow")
            return
        if not _FB.exists():
            logger.warning("HDMIDisplay: /dev/fb0 nicht gefunden")
            return
        self._w, self._h, self._bpp = _detect_fb()
        self._available = True
        logger.info("HDMIDisplay %dx%d %dbit", self._w, self._h, self._bpp)
        self._hide_cursor()

    def stop(self) -> None:
        pass

    def _hide_cursor(self) -> None:
        """Blinkcursor auf dem Linux-Framebuffer ausblenden."""
        # Methode 1: sysfs (funktioniert wenn fbcon geladen)
        try:
            Path("/sys/class/graphics/fbcon/cursor_blink").write_text("0")
        except Exception:
            pass
        # Methode 2: ANSI-Escape an tty1 schreiben
        for tty in ("/dev/tty1", "/dev/tty0"):
            try:
                with open(tty, "wb") as f:
                    f.write(b"\033[?25l")   # Cursor verstecken
                    f.write(b"\033[?17;0;0c")  # Cursor-Blink deaktivieren
                break
            except Exception:
                pass

    # ── Boot-Splash ───────────────────────────────────────────────────────────

    def show_boot_splash(self) -> None:
        if not self._available:
            return
        try:
            from PIL import Image, ImageDraw  # type: ignore[import-untyped]
            W, H = self._w, self._h
            img = Image.new("RGB", (W, H), BG)
            d = ImageDraw.Draw(img)

            f_huge, f_lg, f_md, f_sm = _fonts([
                self._scale(96), self._scale(38),
                self._scale(26), self._scale(18),
            ])
            cx = W // 2

            # Amber-Balken oben (10px)
            d.rectangle([0, 0, W, 10], fill=AMBER)
            # Amber-Balken unten (10px)
            d.rectangle([0, H - 10, W, H], fill=AMBER)

            # Grosses Logo
            d.text((cx, H // 2 - 80), "HaniPi",
                   fill=AMBER, font=f_huge, anchor="mm")

            # Trennlinie
            d.rectangle([cx - 200, H // 2 - 10, cx + 200, H // 2 - 7], fill=AMBER)

            # Untertitel
            d.text((cx, H // 2 + 28), "Bienenstock-Monitoring",
                   fill=WHITE, font=f_lg, anchor="mm")
            d.text((cx, H // 2 + 70), "by Thomas Schöpf",
                   fill=MUTED, font=f_md, anchor="mm")
            d.text((cx, H // 2 + 100), "hanipi.hanimat.at",
                   fill=(60, 70, 90), font=f_sm, anchor="mm")

            # Startet
            d.text((cx, H - 28), "Startet …",
                   fill=(50, 60, 75), font=f_sm, anchor="mm")

            self._flush(img)
        except Exception as exc:
            logger.warning("Boot-Splash Fehler: %s", exc)

    # ── Idle-Screen (kein Messert) ────────────────────────────────────────────

    def show_splash(self, page: DisplayPage) -> None:
        if not self._available:
            return
        try:
            from PIL import Image, ImageDraw  # type: ignore[import-untyped]
            W, H = self._w, self._h
            img = Image.new("RGB", (W, H), BG)
            d = ImageDraw.Draw(img)

            f_clock, f_date, f_head, f_net_lbl, f_net_val, f_hint = _fonts([
                self._scale(120), self._scale(32), self._scale(22),
                self._scale(28),  self._scale(22), self._scale(18),
            ])

            mid = W // 2

            # ── LINKE HÄLFTE: Uhrzeit ────────────────────────────────────────
            now = datetime.datetime.now()

            # Amber-Linie links
            d.rectangle([0, 0, 5, H], fill=AMBER)

            # Grosse Uhrzeit
            d.text((mid // 2, H // 2 - 30),
                   now.strftime("%H:%M"),
                   fill=WHITE, font=f_clock, anchor="mm")

            # Datum
            d.text((mid // 2, H // 2 + 72),
                   now.strftime("%d.%m.%Y"),
                   fill=MUTED, font=f_date, anchor="mm")

            # Wartetext unten links
            d.text((mid // 2, H - 30),
                   "Warte auf Sensordaten …",
                   fill=(55, 65, 80), font=f_hint, anchor="mm")

            # ── TRENNLINIE ────────────────────────────────────────────────────
            d.rectangle([mid - 1, 30, mid + 1, H - 30], fill=DIVIDER)

            # ── RECHTE HÄLFTE: Netzwerk ───────────────────────────────────────
            rx = mid + 32
            d.text((rx, 28), "Verbindung", fill=MUTED, font=f_head)

            net = _get_network()
            y = 78
            for label, value, ok in net:
                dot_color = GREEN if ok else RED
                # Grosser farbiger Punkt
                d.ellipse([rx, y + 5, rx + 16, y + 21], fill=dot_color)
                d.text((rx + 28, y), label, fill=WHITE, font=f_net_lbl)
                d.text((rx + 28, y + 32), value,
                       fill=GREEN if ok else MUTED, font=f_net_val)
                y += 90

            self._flush(img)
        except Exception as exc:
            logger.warning("Idle-Screen Fehler: %s", exc)

    # ── Daten-Seite (Messwerte) ───────────────────────────────────────────────

    def show_page(self, page: DisplayPage) -> None:
        if not self._available:
            return
        try:
            self._render_data(page)
        except Exception as exc:
            logger.error("Datenseite Fehler: %s", exc)

    def _render_data(self, page: DisplayPage) -> None:
        from PIL import Image, ImageDraw  # type: ignore[import-untyped]
        W, H = self._w, self._h
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)

        accent = _hex_to_rgb(page.hive_color)
        f_name, f_val, f_unit, f_lbl, f_foot = _fonts([
            self._scale(48), self._scale(72), self._scale(28),
            self._scale(22), self._scale(18),
        ])

        HEADER_H = 80
        FOOTER_H = 36
        BODY_TOP  = HEADER_H
        BODY_H    = H - HEADER_H - FOOTER_H

        # ── Header ──────────────────────────────────────────────────────────
        d.rectangle([0, 0, W, HEADER_H], fill=accent)
        # Kleiner dunkler Overlay für bessere Lesbarkeit
        d.rectangle([0, 0, W, HEADER_H], fill=(*accent, 220))  # type: ignore
        d.text((24, HEADER_H // 2), page.hive_name,
               fill=WHITE, font=f_name, anchor="lm")

        # Uhrzeit rechts im Header
        now = datetime.datetime.now().strftime("%H:%M")
        d.text((W - 20, HEADER_H // 2), now,
               fill=(255, 255, 255), font=f_unit, anchor="rm")

        # ── Sensor-Kacheln ───────────────────────────────────────────────────
        items = [(k, v) for k, v in page.values.items()]

        if not items:
            d.text((W // 2, BODY_TOP + BODY_H // 2),
                   "Keine Messwerte",
                   fill=MUTED, font=f_unit, anchor="mm")
        else:
            n = len(items)
            if n <= 2:
                cols, rows = n, 1
            elif n <= 3:
                cols, rows = 3, 1
            elif n <= 4:
                cols, rows = 2, 2
            else:
                cols, rows = 3, 2

            tile_w = W // cols
            tile_h = BODY_H // rows
            PAD = 10

            for i, (key, val) in enumerate(items[: cols * rows]):
                row, col = divmod(i, cols)
                tx = col * tile_w
                ty = BODY_TOP + row * tile_h

                # Kachelrahmen
                d.rounded_rectangle(
                    [tx + PAD, ty + PAD, tx + tile_w - PAD, ty + tile_h - PAD],
                    radius=12, fill=CARD,
                )
                # Accent-Linie oben auf Kachel
                d.rounded_rectangle(
                    [tx + PAD, ty + PAD, tx + tile_w - PAD, ty + PAD + 4],
                    radius=2, fill=accent,
                )

                cx_tile = tx + tile_w // 2
                cy_tile = ty + tile_h // 2

                label = LABEL_MAP.get(key, key)
                unit  = UNIT_MAP.get(key, "")

                # Label (klein, oben)
                d.text((cx_tile, cy_tile - 32), label,
                       fill=MUTED, font=f_lbl, anchor="mm")
                # Wert (gross, mitte)
                d.text((cx_tile, cy_tile + 14), f"{val:.1f}",
                       fill=WHITE, font=f_val, anchor="mm")
                # Einheit (rechts neben Wert, klein)
                bbox = f_val.getbbox(f"{val:.1f}")  # type: ignore[attr-defined]
                val_w = (bbox[2] - bbox[0]) if bbox else 60
                d.text((cx_tile + val_w // 2 + 6, cy_tile + 20), unit,
                       fill=MUTED, font=f_unit, anchor="lm")

        # ── Footer ───────────────────────────────────────────────────────────
        fy = H - FOOTER_H
        d.rectangle([0, fy, W, H], fill=CARD)

        # Netzwerk links
        net = _get_network()
        net_text = "  ·  ".join(
            f"{lbl.split()[0]}: {val}" for lbl, val, ok in net if ok
        ) or "kein Netzwerk"
        d.text((16, fy + FOOTER_H // 2), net_text,
               fill=MUTED, font=f_foot, anchor="lm")

        # Datum mittig
        ds = datetime.datetime.fromtimestamp(page.timestamp).strftime("%d.%m.%Y  %H:%M")
        d.text((W // 2, fy + FOOTER_H // 2), ds,
               fill=MUTED, font=f_foot, anchor="mm")

        # Akku rechts
        if page.battery_voltage is not None:
            bc = GREEN if page.battery_voltage > 3.6 else RED
            d.text((W - 16, fy + FOOTER_H // 2),
                   f"Akku  {page.battery_voltage:.1f}V",
                   fill=bc, font=f_foot, anchor="rm")

        self._flush(img)

    # ── intern ────────────────────────────────────────────────────────────────

    def _flush(self, img: object) -> None:
        from PIL import Image  # type: ignore[import-untyped]
        assert isinstance(img, Image.Image)
        if self._rotation:
            img = img.rotate(self._rotation, expand=True)
        raw = _to_fb_bytes(img, self._bpp)
        if raw:
            _FB.write_bytes(raw)
