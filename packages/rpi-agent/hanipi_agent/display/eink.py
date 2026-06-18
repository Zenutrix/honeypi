"""Waveshare e-Paper Display Driver (SPI via spidev + lgpio).

Unterstützte Modelle:
  "2.13"  212×104  — Waveshare 2.13" V2/V3
  "2.7"   264×176  — Waveshare 2.7" V2        (PCB-Standard)
  "4.2"   400×300  — Waveshare 4.2"
  "7.5"   800×480  — Waveshare 7.5" V2

Standard-Pins (alle konfigurierbar):
  SPI0 CE0 = GPIO8  (CS)
  DC        = GPIO25
  RST       = GPIO27
  BUSY      = GPIO22
"""

from __future__ import annotations

import datetime
import logging
import time
from typing import TYPE_CHECKING

from .base import BaseDisplay, DisplayPage

if TYPE_CHECKING:
    from PIL import Image, ImageDraw, ImageFont

    FontT = ImageFont.FreeTypeFont | ImageFont.ImageFont

logger = logging.getLogger(__name__)

# ── Display-Größen ─────────────────────────────────────────────────────────────
_MODEL_SIZE: dict[str, tuple[int, int]] = {
    "2.13": (212, 104),
    "2.7":  (264, 176),
    "4.2":  (400, 300),
    "7.5":  (800, 480),
}

# ── Farben (Graustufen, werden am Ende zu 1-bit) ───────────────────────────────
_WHITE = 255
_GREY  = 160
_BLACK = 0

# ── Labels & Einheiten ─────────────────────────────────────────────────────────
UNIT_MAP: dict[str, str] = {
    "weight_kg":          "kg",
    "temperature_c":      "°C",
    "humidity_pct":       "%",
    "pressure_hpa":       "hPa",
    "illuminance_lux":    "lx",
    "gas_resistance_ohm": "kΩ",
    "voltage_v":          "V",
    "solar_voltage_v":    "V",
    "solar_current_a":    "A",
    "solar_power_w":      "W",
    "battery_voltage_v":  "V",
    "battery_current_a":  "A",
    "pi_voltage_v":       "V",
    "pi_current_a":       "A",
    "pi_power_w":         "W",
    "lux":                "lx",
}

LABEL_MAP: dict[str, str] = {
    "weight_kg":          "Gewicht",
    "temperature_c":      "Temp.",
    "humidity_pct":       "Feuchte",
    "pressure_hpa":       "Luftdr.",
    "illuminance_lux":    "Licht",
    "gas_resistance_ohm": "Gas",
    "voltage_v":          "Spanng.",
    "solar_voltage_v":    "Solar U",
    "solar_current_a":    "Solar I",
    "solar_power_w":      "Solar P",
    "battery_voltage_v":  "Akku U",
    "battery_current_a":  "Akku I",
    "pi_voltage_v":       "Pi U",
    "pi_current_a":       "Pi I",
    "pi_power_w":         "Pi P",
    "lux":                "Licht",
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _img_to_buf(img: "Image.Image") -> bytes:
    """Konvertiert PIL-Bild zu Waveshare-Bitpuffer (bit=1 → weiß, bit=0 → schwarz, MSB first).

    Jede Zeile wird auf ganze Bytes aufgefüllt.
    """
    bw = img.convert("1")
    w, h = bw.size
    row_bytes = (w + 7) // 8
    buf = bytearray(b"\xff" * (row_bytes * h))  # Initialisierung: weiß
    for y in range(h):
        for x in range(w):
            if not bw.getpixel((x, y)):  # schwarzes Pixel
                buf[y * row_bytes + x // 8] &= ~(0x80 >> (x % 8))
    return bytes(buf)


def _font(size: int, bold: bool = False) -> "FontT":
    from PIL import ImageFont

    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


# ── Hardware-Abstraction-Layer (spidev + lgpio) ───────────────────────────────

class _HAL:
    def __init__(
        self,
        spi_bus: int = 0,
        spi_cs: int = 0,
        dc_pin: int = 25,
        rst_pin: int = 27,
        busy_pin: int = 22,
        busy_high: bool = True,
    ) -> None:
        self._dc   = dc_pin
        self._rst  = rst_pin
        self._busy = busy_pin
        self._busy_active = 1 if busy_high else 0

        import spidev
        self._spi = spidev.SpiDev()
        self._spi.open(spi_bus, spi_cs)
        self._spi.max_speed_hz = 4_000_000
        self._spi.mode = 0b00

        import lgpio
        self._g = lgpio
        self._h = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(self._h, dc_pin,  0)
        lgpio.gpio_claim_output(self._h, rst_pin, 1)
        lgpio.gpio_claim_input(self._h,  busy_pin)

    def reset(self) -> None:
        g, h = self._g, self._h
        g.gpio_write(h, self._rst, 1); time.sleep(0.02)
        g.gpio_write(h, self._rst, 0); time.sleep(0.002)
        g.gpio_write(h, self._rst, 1); time.sleep(0.02)

    def cmd(self, b: int) -> None:
        self._g.gpio_write(self._h, self._dc, 0)
        self._spi.writebytes([b])

    def dat(self, data: bytes | list[int]) -> None:
        self._g.gpio_write(self._h, self._dc, 1)
        if isinstance(data, (bytes, bytearray)):
            self._spi.writebytes2(data)
        else:
            self._spi.writebytes(list(data))

    def wait(self, timeout: float = 40.0) -> None:
        t0 = time.monotonic()
        while self._g.gpio_read(self._h, self._busy) == self._busy_active:
            if time.monotonic() - t0 > timeout:
                logger.warning("E-Ink BUSY-Timeout nach %.0f s", timeout)
                return
            time.sleep(0.01)

    def close(self) -> None:
        try:
            self._g.gpiochip_close(self._h)
        except Exception:
            pass
        try:
            self._spi.close()
        except Exception:
            pass


# ── Modell-spezifische Protokolle ─────────────────────────────────────────────

def _init_std(hal: _HAL) -> None:
    """Init für 2.13" V2, 2.7" V2 (LUT aus OTP, kein expliziter Resolution-Befehl)."""
    hal.reset()
    hal.wait()
    hal.cmd(0x04)      # Power On
    hal.wait()
    hal.cmd(0x00)      # PSR: LUT-OTP, KW, Booster an
    hal.dat([0x1F])
    hal.cmd(0x50)      # CDI: VCOM
    hal.dat([0x97])


def _init_42(hal: _HAL) -> None:
    """Init für Waveshare 4.2" (mit expliziter Auflösung 400×300)."""
    hal.reset()
    hal.cmd(0x04)      # Power On
    hal.wait()
    hal.cmd(0x00)      # PSR: LUT-OTP, KW
    hal.dat([0x1F])
    hal.cmd(0x61)      # TRES: 400×300
    hal.dat([0x01, 0x90, 0x01, 0x2C])
    hal.cmd(0x50)      # CDI
    hal.dat([0x97])


def _init_75v2(hal: _HAL) -> None:
    """Init für Waveshare 7.5" V2 (800×480)."""
    hal.reset()
    hal.cmd(0x01)      # POWER SETTING
    hal.dat([0x07, 0x07, 0x3F, 0x3F])
    hal.cmd(0x04)      # Power On
    time.sleep(0.1)
    hal.wait()
    hal.cmd(0x00)      # PSR
    hal.dat([0x1F])
    hal.cmd(0x61)      # TRES: 800×480
    hal.dat([0x03, 0x20, 0x01, 0xE0])
    hal.cmd(0x15)
    hal.dat([0x00])
    hal.cmd(0x50)      # CDI
    hal.dat([0x10, 0x07])
    hal.cmd(0x60)      # TCON
    hal.dat([0x22])


def _disp_27v2(hal: _HAL, buf: bytes) -> None:
    """2.13" / 2.7" V2: DTM1=buf, DTM2=~buf → Full-Refresh."""
    inv = bytes(b ^ 0xFF for b in buf)
    hal.cmd(0x10); hal.dat(buf)
    hal.cmd(0x13); hal.dat(inv)
    hal.cmd(0x12); time.sleep(0.1); hal.wait(timeout=40)


def _disp_42(hal: _HAL, buf: bytes) -> None:
    """4.2": DTM1=weiß, DTM2=buf."""
    hal.cmd(0x10); hal.dat(bytes([0xFF] * len(buf)))
    hal.cmd(0x13); hal.dat(buf)
    hal.cmd(0x12); time.sleep(0.1); hal.wait(timeout=30)


def _disp_75v2(hal: _HAL, buf: bytes) -> None:
    """7.5" V2: nur DTM2."""
    hal.cmd(0x13); hal.dat(buf)
    hal.cmd(0x12); time.sleep(0.1); hal.wait(timeout=60)


def _sleep_std(hal: _HAL) -> None:
    hal.cmd(0x02); hal.wait()
    hal.cmd(0x07); hal.dat([0xA5])


# (init_fn, disp_fn, sleep_fn)
_PROTOCOLS: dict[str, tuple] = {
    "2.13": (_init_std,  _disp_27v2, _sleep_std),
    "2.7":  (_init_std,  _disp_27v2, _sleep_std),
    "4.2":  (_init_42,   _disp_42,   _sleep_std),
    "7.5":  (_init_75v2, _disp_75v2, _sleep_std),
}


# ── EInkDisplay ───────────────────────────────────────────────────────────────

class EInkDisplay(BaseDisplay):
    """Waveshare e-Paper Display (SPI, PIL-Rendering, B&W).

    Adapter zu DisplayRenderer — implementiert show_boot_splash(),
    show_splash() und show_page().
    """

    def __init__(
        self,
        model: str = "2.7",
        spi_bus: int = 0,
        spi_cs: int = 0,
        dc_pin: int = 25,
        rst_pin: int = 27,
        busy_pin: int = 22,
        rotation: int = 0,
    ) -> None:
        self._model    = model
        self._rotation = rotation
        self._w, self._h = _MODEL_SIZE.get(model, (264, 176))
        self._available = False
        self._hal: _HAL | None = None
        proto = _PROTOCOLS.get(model, _PROTOCOLS["2.7"])
        self._init_fn, self._disp_fn, self._sleep_fn = proto

        self._spi_bus = spi_bus
        self._spi_cs  = spi_cs
        self._dc_pin  = dc_pin
        self._rst_pin = rst_pin
        self._busy_pin = busy_pin

    # ── Skalierung (Referenz: 2.7" 264×176) ───────────────────────────────────
    def _s(self, n: int) -> int:
        return max(3, int(n * min(self._w / 264, self._h / 176)))

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            logger.warning("EInkDisplay: Pillow nicht installiert — Display deaktiviert")
            return
        try:
            self._hal = _HAL(
                spi_bus=self._spi_bus,
                spi_cs=self._spi_cs,
                dc_pin=self._dc_pin,
                rst_pin=self._rst_pin,
                busy_pin=self._busy_pin,
            )
            self._init_fn(self._hal)
            self._available = True
            logger.info(
                "EInkDisplay %s %dx%d gestartet  SPI%d.%d  DC=%d  RST=%d  BUSY=%d",
                self._model, self._w, self._h,
                self._spi_bus, self._spi_cs,
                self._dc_pin, self._rst_pin, self._busy_pin,
            )
        except Exception as exc:
            logger.error("EInkDisplay init fehlgeschlagen: %s", exc)

    def stop(self) -> None:
        if self._hal:
            try:
                self._sleep_fn(self._hal)
            except Exception:
                pass
            self._hal.close()
            self._hal = None
        self._available = False

    # ── Öffentliche Render-Methoden ────────────────────────────────────────────

    def show_boot_splash(self) -> None:
        if not self._available:
            return
        try:
            self._send(self._render_boot())
        except Exception as exc:
            logger.warning("EInk Boot-Splash: %s", exc)

    def show_splash(self, page: DisplayPage) -> None:
        if not self._available:
            return
        try:
            self._send(self._render_idle())
        except Exception as exc:
            logger.warning("EInk Idle-Screen: %s", exc)

    def show_page(self, page: DisplayPage) -> None:
        if not self._available:
            return
        try:
            self._send(self._render_page(page))
        except Exception as exc:
            logger.error("EInk show_page: %s", exc)

    # ── Interner Pipeline: PIL-Bild → Puffer → Display ────────────────────────

    def _send(self, img: "Image.Image") -> None:
        from PIL import Image

        assert self._hal is not None
        if self._rotation:
            img = img.rotate(self._rotation, expand=True)
        if img.size != (self._w, self._h):
            img = img.resize((self._w, self._h), Image.LANCZOS)
        self._disp_fn(self._hal, _img_to_buf(img))

    def _new(self) -> "tuple[Image.Image, ImageDraw.ImageDraw]":
        from PIL import Image, ImageDraw

        img = Image.new("L", (self._w, self._h), _WHITE)
        return img, ImageDraw.Draw(img)

    # ── Boot-Splash ───────────────────────────────────────────────────────────

    def _render_boot(self) -> "Image.Image":
        img, d = self._new()
        W, H = self._w, self._h
        cx, cy = W // 2, H // 2

        f_big = _font(self._s(28), bold=True)
        f_sm  = _font(self._s(12))

        d.rectangle([2, 2, W - 3, H - 3], outline=_BLACK, width=2)
        d.text((cx, cy - self._s(18)), "HaniPi", fill=_BLACK, font=f_big, anchor="mm")
        d.line(
            [cx - self._s(44), cy + self._s(6), cx + self._s(44), cy + self._s(6)],
            fill=_BLACK, width=1,
        )
        d.text((cx, cy + self._s(18)), "Bienenstock-Monitoring", fill=_GREY, font=f_sm, anchor="mm")
        d.text((cx, H - self._s(14)), "System startet …", fill=_GREY, font=f_sm, anchor="mm")
        return img

    # ── Idle-Screen ───────────────────────────────────────────────────────────

    def _render_idle(self) -> "Image.Image":
        img, d = self._new()
        W, H = self._w, self._h
        cx = W // 2
        now = datetime.datetime.now()

        f_clk  = _font(self._s(40), bold=True)
        f_date = _font(self._s(12))

        d.rectangle([2, 2, W - 3, H - 3], outline=_BLACK, width=2)
        d.text(
            (cx, H // 2 - self._s(12)),
            now.strftime("%H:%M"),
            fill=_BLACK, font=f_clk, anchor="mm",
        )
        d.text(
            (cx, H // 2 + self._s(30)),
            now.strftime("%d. %B %Y"),
            fill=_GREY, font=f_date, anchor="mm",
        )
        d.text(
            (cx, H - self._s(14)),
            "Warte auf Sensordaten …",
            fill=_GREY, font=f_date, anchor="mm",
        )
        return img

    # ── Daten-Seite ───────────────────────────────────────────────────────────

    def _render_page(self, page: DisplayPage) -> "Image.Image":
        img, d = self._new()
        W, H = self._w, self._h

        PAD      = self._s(5)
        HDR_H    = self._s(26)
        FTR_H    = self._s(14)

        f_hive = _font(self._s(14), bold=True)
        f_time = _font(self._s(11))
        f_lbl  = _font(self._s(10))
        f_val  = _font(self._s(20), bold=True)
        f_unit = _font(self._s(10))
        f_ts   = _font(self._s(9))

        # Header: schwarzer Balken, weißer Text
        d.rectangle([0, 0, W, HDR_H], fill=_BLACK)
        d.text(
            (PAD + self._s(3), HDR_H // 2),
            page.hive_name,
            fill=_WHITE, font=f_hive, anchor="lm",
        )
        d.text(
            (W - PAD - self._s(3), HDR_H // 2),
            datetime.datetime.now().strftime("%H:%M"),
            fill=_WHITE, font=f_time, anchor="rm",
        )

        # Body
        body_top = HDR_H + 1
        body_h   = H - body_top - FTR_H - 1
        items    = list(page.values.items())
        trends   = page.trends

        if items:
            self._draw_grid(d, items, trends, body_top, body_h, W, PAD, f_lbl, f_val, f_unit)
        else:
            d.text(
                (W // 2, body_top + body_h // 2),
                "Keine Daten",
                fill=_GREY, font=f_lbl, anchor="mm",
            )

        # Footer: Zeitstempel
        ts = datetime.datetime.fromtimestamp(page.timestamp).strftime("%d.%m.%y  %H:%M")
        d.line([0, H - FTR_H, W, H - FTR_H], fill=_BLACK, width=1)
        d.text(
            (PAD, H - FTR_H // 2),
            ts,
            fill=_GREY, font=f_ts, anchor="lm",
        )

        return img

    # ── Wert-Gitter ───────────────────────────────────────────────────────────

    def _draw_grid(
        self,
        d: "ImageDraw.ImageDraw",
        items: list[tuple[str, float]],
        trends: dict[str, str],
        y0: int,
        body_h: int,
        W: int,
        PAD: int,
        f_lbl: "FontT",
        f_val: "FontT",
        f_unit: "FontT",
    ) -> None:
        n = len(items)
        cols = 1 if n == 1 else (3 if n >= 5 and self._w >= 400 else 2)
        rows = (n + cols - 1) // cols

        cw = (W - PAD * (cols + 1)) // cols
        ch = (body_h - PAD * (rows + 1)) // rows

        for idx, (key, val) in enumerate(items):
            row, col = divmod(idx, cols)
            x0 = PAD + col * (cw + PAD)
            yt = y0 + PAD + row * (ch + PAD)
            cx = x0 + cw // 2
            cy = yt + ch // 2

            # Zell-Rahmen
            d.rectangle([x0, yt, x0 + cw, yt + ch], outline=_BLACK, width=1)

            # Label
            label = LABEL_MAP.get(key, key).upper()
            d.text((cx, yt + self._s(8)), label, fill=_GREY, font=f_lbl, anchor="mm")

            # Wert + Einheit
            unit = UNIT_MAP.get(key, "")
            if key == "gas_resistance_ohm":
                val_str = f"{val / 1000:.1f}"
            elif abs(val) >= 100:
                val_str = f"{val:.0f}"
            else:
                val_str = f"{val:.1f}"

            try:
                vw = int(f_val.getlength(val_str))
            except Exception:
                vw = self._s(40)

            d.text(
                (cx - self._s(4), cy + self._s(4)),
                val_str,
                fill=_BLACK, font=f_val, anchor="rm",
            )
            d.text(
                (cx - self._s(2), cy + self._s(8)),
                unit,
                fill=_GREY, font=f_unit, anchor="lm",
            )

            # Trend-Pfeil
            trend = trends.get(key, "stable")
            ax = x0 + cw - self._s(10)
            ay = yt + self._s(10)
            self._draw_arrow(d, trend, ax, ay, self._s(5))

    def _draw_arrow(
        self,
        d: "ImageDraw.ImageDraw",
        trend: str,
        x: int,
        y: int,
        r: int,
    ) -> None:
        if trend == "up":
            d.polygon([(x, y - r), (x - r, y + r), (x + r, y + r)], fill=_BLACK)
        elif trend == "down":
            d.polygon([(x, y + r), (x - r, y - r), (x + r, y - r)], fill=_BLACK)
        else:
            d.line([x - r, y, x + r, y], fill=_GREY, width=max(1, r // 2))
