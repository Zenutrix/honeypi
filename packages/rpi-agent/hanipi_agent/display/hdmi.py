from __future__ import annotations
import datetime
import logging
import math
import struct
import subprocess
from pathlib import Path
from .base import BaseDisplay, DisplayPage

logger = logging.getLogger(__name__)

_FB      = Path("/dev/fb0")
_FB_SIZE = Path("/sys/class/graphics/fb0/virtual_size")
_FB_BPP  = Path("/sys/class/graphics/fb0/bits_per_pixel")

# ── Farben – deckungsgleich mit Web-UI (System Dark) ─────────────────────────
BG      = (28,  28,  30)    # --bg        #1c1c1e
SURFACE = (44,  44,  46)    # --surface   #2c2c2e
SURF2   = (58,  58,  60)    # --surface-2 #3a3a3c
BORDER  = (72,  72,  74)    # --border    #48484a
AMBER   = (245, 158, 11)    # --amber     #f59e0b
AMBER_D = (180, 110,  5)    # --amber-dim #d97706
WHITE   = (255, 255, 255)   # --text
MUTED   = (142, 142, 147)   # --text-muted #8e8e93
FAINT   = (72,  72,  74)    # --text-faint #48484a
GREEN   = (48,  209, 88)    # --success   #30d158
RED     = (255, 69,  58)    # --danger    #ff453a

UNIT_MAP = {
    "weight_kg": "kg",  "temperature_c": "°C",  "humidity_pct": "%",
    "pressure_hpa": "hPa", "illuminance_lux": "lx",
    "gas_resistance_ohm": "Ω", "voltage_v": "V",
}
LABEL_MAP = {
    "weight_kg": "Gewicht",    "temperature_c": "Temperatur",
    "humidity_pct": "Feuchte", "pressure_hpa": "Luftdruck",
    "illuminance_lux": "Licht","gas_resistance_ohm": "Gas",
    "voltage_v": "Spannung",
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _detect_fb() -> tuple[int, int, int]:
    try:
        w, h = _FB_SIZE.read_text().strip().split(",")
        bpp  = int(_FB_BPP.read_text().strip())
        return int(w), int(h), bpp
    except Exception:
        return 1024, 600, 16


def _to_bytes(img: object, bpp: int) -> bytes:
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
    bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    reg  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    out  = []
    for i, size in enumerate(sizes):
        path = bold if i % 2 == 0 else reg
        for p in (path, bold, reg):
            try:
                out.append(ImageFont.truetype(p, size))
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
            ["ip", "-br", "addr"], capture_output=True, text=True, timeout=3,
        ).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            iface, state = parts[0], parts[1]
            if iface.startswith(("lo", "HaniPi", "docker")):
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
                        ["iwgetid", iface, "-r"],
                        capture_output=True, text=True, timeout=2,
                    ).stdout.strip()
                except Exception:
                    ssid = ""
                result.append((f"WLAN  {ssid}" if ssid else "WLAN", ip or "—", connected))
            elif iface.startswith(("eth", "enp", "end")):
                result.append(("LAN", ip or "—", connected))
            elif iface.startswith(("wwan", "ppp", "usb")):
                result.append(("4G", ip or "verbunden", connected))
    except Exception:
        pass
    return result or [("Netzwerk", "nicht verbunden", False)]


def _pill(d: object, x0: int, y0: int, x1: int, y1: int,
          fill: tuple, radius: int) -> None:
    """Gefülltes Rechteck mit runden Ecken."""
    d.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)  # type: ignore


def _pill_outline(d: object, x0: int, y0: int, x1: int, y1: int,
                  fill: tuple, outline: tuple, radius: int) -> None:
    d.rounded_rectangle([x0, y0, x1, y1], radius=radius,
                        fill=fill, outline=outline)  # type: ignore


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
            from PIL import Image  # type: ignore[import-untyped]  # noqa: F401
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

    def _flush(self, img: object) -> None:
        from PIL import Image  # type: ignore[import-untyped]
        assert isinstance(img, Image.Image)
        if self._rotation:
            img = img.rotate(self._rotation, expand=True)
        raw = _to_bytes(img, self._bpp)
        if raw:
            _FB.write_bytes(raw)

    def _new(self) -> tuple:
        from PIL import Image, ImageDraw  # type: ignore[import-untyped]
        img = Image.new("RGB", (self._w, self._h), BG)
        return img, ImageDraw.Draw(img)

    # ── Boot-Splash ───────────────────────────────────────────────────────────

    def show_boot_splash(self) -> None:
        if not self._available:
            return
        try:
            img, d = self._new()
            W, H = self._w, self._h

            f_logo, f_sub, f_hint, f_small = _fonts([
                self._s(88), self._s(28), self._s(20), self._s(16),
            ])

            cx = W // 2
            cy = H // 2 - self._s(20)

            # Amber-Akzentlinie oben
            d.rectangle([0, 0, W, self._s(4)], fill=AMBER)

            # Logo "HaniPi" — "Hani" weiß, "Pi" amber
            try:
                hani_w = int(f_logo.getlength("Hani"))  # type: ignore
                pi_w   = int(f_logo.getlength("Pi"))
                total  = hani_w + pi_w
                lx = cx - total // 2
                d.text((lx, cy - self._s(50)), "Hani",
                       fill=WHITE, font=f_logo, anchor="lt")
                d.text((lx + hani_w, cy - self._s(50)), "Pi",
                       fill=AMBER, font=f_logo, anchor="lt")
            except Exception:
                d.text((cx, cy - self._s(50)), "HaniPi",
                       fill=AMBER, font=f_logo, anchor="mt")

            # Dünne Trennlinie unter Logo
            lw = self._s(220)
            d.rectangle([cx - lw, cy + self._s(46), cx + lw, cy + self._s(48)],
                        fill=BORDER)

            d.text((cx, cy + self._s(66)), "Bienenstock-Monitoring",
                   fill=WHITE, font=f_sub, anchor="mm")
            d.text((cx, cy + self._s(98)), "by Thomas Schöpf",
                   fill=MUTED, font=f_hint, anchor="mm")

            # Ladebalken-Dots
            dot_y = H - self._s(38)
            for i, dot_x in enumerate([cx - self._s(18), cx, cx + self._s(18)]):
                col = AMBER if i == 1 else SURF2
                r = self._s(5) if i == 1 else self._s(4)
                d.ellipse([dot_x - r, dot_y - r, dot_x + r, dot_y + r], fill=col)

            d.text((cx, H - self._s(16)), "System startet …",
                   fill=FAINT, font=f_small, anchor="mm")

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

            f_clock, f_date, f_label, f_net, f_hint = _fonts([
                self._s(108), self._s(30), self._s(22), self._s(18), self._s(16),
            ])

            now = datetime.datetime.now()
            cx  = W // 2

            # Amber-Akzentlinie oben
            d.rectangle([0, 0, W, self._s(4)], fill=AMBER)

            # Uhrzeit — zentriert, leicht über Mitte
            d.text((cx, H // 2 - self._s(30)),
                   now.strftime("%H:%M"),
                   fill=WHITE, font=f_clock, anchor="mm")

            # Datum
            d.text((cx, H // 2 + self._s(72)),
                   now.strftime("%A, %d. %B %Y"),
                   fill=MUTED, font=f_date, anchor="mm")

            # Dünne Trennlinie
            d.rectangle([cx - self._s(180), H // 2 + self._s(95),
                         cx + self._s(180), H // 2 + self._s(96)], fill=BORDER)

            # Netzwerk-Info
            net = _get_network()
            ny  = H // 2 + self._s(118)
            for label, ip, ok in net[:2]:
                dot_c = GREEN if ok else RED
                dot_x = cx - self._s(130)
                d.ellipse([dot_x - self._s(5), ny - self._s(5),
                           dot_x + self._s(5), ny + self._s(5)], fill=dot_c)
                d.text((dot_x + self._s(14), ny),
                       f"{label}  {ip}", fill=MUTED if ok else FAINT,
                       font=f_net, anchor="lm")
                ny += self._s(28)

            # Wartetext
            d.text((cx, H - self._s(22)), "Warte auf Sensordaten …",
                   fill=FAINT, font=f_hint, anchor="mm")

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
        img, d = self._new()
        W, H = self._w, self._h

        accent = _hex_to_rgb(page.hive_color)

        ACCENT_H = self._s(4)
        HEADER_H = self._s(56)
        FOOTER_H = self._s(40)
        PAD      = self._s(10)

        body_top = ACCENT_H + HEADER_H
        body_h   = H - body_top - FOOTER_H

        f_hive, f_clock, f_hero_lbl, f_hero_val, f_hero_unit, \
            f_tile_lbl, f_tile_val, f_tile_unit, f_foot = _fonts([
            self._s(28), self._s(22), self._s(20), self._s(72), self._s(28),
            self._s(18), self._s(40), self._s(18), self._s(16),
        ])

        # ── Akzent-Linie oben (Hive-Farbe) ───────────────────────────────────
        d.rectangle([0, 0, W, ACCENT_H], fill=accent)

        # ── Header ────────────────────────────────────────────────────────────
        d.rectangle([0, ACCENT_H, W, ACCENT_H + HEADER_H], fill=SURFACE)

        d.text((self._s(20), ACCENT_H + HEADER_H // 2),
               page.hive_name, fill=WHITE, font=f_hive, anchor="lm")

        d.text((W - self._s(20), ACCENT_H + HEADER_H // 2),
               datetime.datetime.now().strftime("%H:%M"),
               fill=MUTED, font=f_clock, anchor="rm")

        # Trennlinie Header/Body
        d.rectangle([0, ACCENT_H + HEADER_H, W, ACCENT_H + HEADER_H + 1],
                    fill=BORDER)

        # ── Footer ────────────────────────────────────────────────────────────
        fy = H - FOOTER_H
        d.rectangle([0, fy, W, H], fill=SURFACE)
        d.rectangle([0, fy, W, fy + 1], fill=BORDER)

        net = _get_network()
        net_txt = "  ·  ".join(
            f"{lbl}: {ip}" for lbl, ip, ok in net if ok
        ) or "kein Netzwerk"
        d.text((self._s(16), fy + FOOTER_H // 2),
               net_txt, fill=MUTED, font=f_foot, anchor="lm")

        ts = datetime.datetime.fromtimestamp(page.timestamp).strftime("%d.%m.%Y  %H:%M")
        d.text((W - self._s(16), fy + FOOTER_H // 2),
               ts, fill=FAINT, font=f_foot, anchor="rm")

        # ── Body: Kacheln ─────────────────────────────────────────────────────
        items = list(page.values.items())
        if not items:
            d.text((W // 2, body_top + body_h // 2),
                   "Keine Messwerte", fill=MUTED, font=f_hive, anchor="mm")
            self._flush(img)
            return

        if len(items) == 1:
            self._draw_hero(d, items[0], accent,
                            PAD, body_top + PAD, W - PAD, fy - PAD,
                            f_hero_lbl, f_hero_val, f_hero_unit)
        elif len(items) <= 4:
            # Alle gleich groß, 2 Spalten
            cols = 2
            rows = math.ceil(len(items) / cols)
            tw = (W - PAD * (cols + 1)) // cols
            th = (body_h - PAD * (rows + 1)) // rows
            for idx, item in enumerate(items):
                row, col = divmod(idx, cols)
                tx = PAD + col * (tw + PAD)
                ty = body_top + PAD + row * (th + PAD)
                self._draw_tile(d, item, accent,
                                tx, ty, tx + tw, ty + th,
                                f_tile_lbl, f_tile_val, f_tile_unit)
        else:
            # Hero oben (erste/wichtigste Messung), Grid unten
            hero_h = int(body_h * 0.42)
            grid_top = body_top + hero_h + PAD

            self._draw_hero(d, items[0], accent,
                            PAD, body_top + PAD,
                            W - PAD, body_top + hero_h,
                            f_hero_lbl, f_hero_val, f_hero_unit)

            rest = items[1:]
            cols = min(len(rest), 4)
            grid_h = fy - grid_top - PAD
            tw = (W - PAD * (cols + 1)) // cols
            for idx, item in enumerate(rest[:cols]):
                tx = PAD + idx * (tw + PAD)
                self._draw_tile(d, item, accent,
                                tx, grid_top, tx + tw, grid_top + grid_h,
                                f_tile_lbl, f_tile_val, f_tile_unit)

        self._flush(img)

    def _draw_hero(self, d: object, item: tuple, accent: tuple,
                   x0: int, y0: int, x1: int, y1: int,
                   f_lbl: object, f_val: object, f_unit: object) -> None:
        key, val = item
        lbl  = LABEL_MAP.get(key, key)
        unit = UNIT_MAP.get(key, "")
        cx   = (x0 + x1) // 2
        cy   = (y0 + y1) // 2

        _pill_outline(d, x0, y0, x1, y1, SURFACE, BORDER, self._s(14))
        # Amber-Akzentlinie oben auf Karte
        d.rounded_rectangle([x0 + 1, y0 + 1, x1 - 1, y0 + self._s(3)],
                            radius=self._s(14), fill=accent)  # type: ignore

        d.text((cx, cy - self._s(34)), lbl.upper(),
               fill=MUTED, font=f_lbl, anchor="mm")

        val_str = f"{val:.1f}" if isinstance(val, float) else str(val)
        d.text((cx, cy + self._s(14)), val_str,
               fill=WHITE, font=f_val, anchor="mm")

        try:
            val_w = int(f_val.getlength(val_str))  # type: ignore
        except Exception:
            val_w = self._s(80)
        d.text((cx + val_w // 2 + self._s(6), cy + self._s(18)),
               unit, fill=accent, font=f_unit, anchor="lm")

    def _draw_tile(self, d: object, item: tuple, accent: tuple,
                   x0: int, y0: int, x1: int, y1: int,
                   f_lbl: object, f_val: object, f_unit: object) -> None:
        key, val = item
        lbl  = LABEL_MAP.get(key, key)
        unit = UNIT_MAP.get(key, "")
        cx   = (x0 + x1) // 2
        cy   = (y0 + y1) // 2

        _pill_outline(d, x0, y0, x1, y1, SURFACE, BORDER, self._s(12))
        d.rounded_rectangle([x0 + 1, y0 + 1, x1 - 1, y0 + self._s(3)],
                            radius=self._s(12), fill=accent)  # type: ignore

        d.text((cx, cy - self._s(20)), lbl.upper(),
               fill=MUTED, font=f_lbl, anchor="mm")

        val_str = f"{val:.1f}" if isinstance(val, float) else str(val)
        d.text((cx, cy + self._s(8)), val_str,
               fill=WHITE, font=f_val, anchor="mm")

        try:
            val_w = int(f_val.getlength(val_str))  # type: ignore
        except Exception:
            val_w = self._s(50)
        d.text((cx + val_w // 2 + self._s(4), cy + self._s(12)),
               unit, fill=accent, font=f_unit, anchor="lm")
