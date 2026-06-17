# HaniPi HDMI Display — Dashboard-Upgrade: Trend, Balken, Farbkodierung

**Datum:** 2026-06-17  
**Status:** Genehmigt  
**Betrifft:** `packages/rpi-agent/hanipi_agent/display/hdmi.py`, `display/renderer.py`, `sensors/ads1115.py`, `sensors/__init__.py`

---

## Ziel

Das bestehende Dark-Theme-Display (1024×600, PIL/Framebuffer) wird zum echten Dashboard aufgewertet:
- Trendpfeil pro Wert (↑ steigend / → stabil / ↓ fallend)
- Fortschrittsbalken für Sensoren mit sinnvollem Normalbereich
- Farbkodierung: grün / amber / rot je nach Bereichsstatus
- ADS1115-Sensor komplett entfernen

Layout und Typografie-Skala bleiben unverändert (Hero + max. 2 Kacheln, Schriftgrößen aus 2026-06-16-Spec).

---

## Datenbasis: Trend & Normalbereiche

### Trend-Tracking

`DisplayRenderer` speichert nach jedem Render die zuletzt gezeigten Werte pro `(hive_id, sensor_key)` in einem Dict `_prev_values`.

Trendberechnung beim nächsten Render:
- Differenz > +0,5 % vom Vorgänger → `"up"` (↑)
- Differenz < -0,5 % → `"down"` (↓)
- sonst → `"stable"` (→)

Wird als `trends: dict[str, str]` im `DisplayPage`-Dataclass mitgeführt.

### Normalbereiche (für Balken + Farbkodierung)

| Sensor | Grün | Amber | Rot | Balken-Range |
|---|---|---|---|---|
| `temperature_c` | 15–40 °C | 10–15 / 40–45 °C | <10 / >45 °C | 0–60 °C |
| `humidity_pct` | 40–80 % | 30–40 / 80–90 % | <30 / >90 % | 0–100 % |
| `illuminance_lux` | — | — | — | 0–100 000 lx (relativ) |
| `pressure_hpa` | 990–1030 hPa | rest | — | 950–1050 hPa |
| `gas_resistance_ohm` | — | — | — | 0–500 000 Ω (relativ, hoch=gut) |
| `voltage_v` | >3,7 V | 3,5–3,7 V | <3,5 V | 3,0–4,2 V |
| `weight_kg` | kein fixer Bereich | → kein Balken | | |

Farben: Grün `#30d158`, Amber `#f59e0b`, Rot `#ff453a`.

---

## Visuelle Änderungen

### Hero-Karte

- Wert (120 px, `WHITE`) bleibt zentriert
- Trendpfeil rechts neben dem Wert: `↑` grün / `↓` rot / `→` MUTED, Größe `_s(36)`
- Fortschrittsbalken (Höhe `_s(8)`, Breite ~70 % der Karte) unterhalb des Werts:
  - Hintergrund `SURF2`, Füllfarbe = Status-Farbe
  - Bei `weight_kg`: kein Balken

### Kachel

- Wert (64 px) bleibt, Trendpfeil (`_s(24)`) direkt rechts daneben, vertikal mittig
- Schmaler Balken (`_s(5)` hoch) am unteren Innenrand der Kachel (innerhalb `_pill_outline`)
- Bei `weight_kg`: kein Balken

### Gewicht (Sonderregel Trendfarbe)

- ↑ = grün (Gewicht steigt → gut für Tracht)
- ↓ stark (>1 %) = rot (Gewicht fällt schnell)
- sonst = MUTED

### Idle-Screen & Boot-Splash

Keine Änderung — kein Trendpfeil, kein Balken dort.

---

## Neue Hilfsfunktionen in `hdmi.py`

```
_value_status(key, val) -> str          # "good" | "warn" | "bad" | "neutral"
_status_color(status) -> RGB            # gibt GREEN / AMBER / RED / MUTED zurück
_bar_range(key) -> tuple[float,float] | None   # (min, max) oder None = kein Balken
_draw_trend(d, trend, cx, cy, size, key, val)  # zeichnet ↑↓→ in passender Farbe
_draw_bar(d, key, val, x0, y0, x1, y1)        # zeichnet Fortschrittsbalken
```

---

## DisplayPage — Erweiterung

```python
@dataclass
class DisplayPage:
    ...
    trends: dict[str, str] = field(default_factory=dict)  # key -> "up"|"down"|"stable"
```

---

## DisplayRenderer — Änderungen

- `_prev_values: dict[tuple[str|None, str], float]` — gespeicherte Vorwerte
- `_build_pages()` berechnet Trends und befüllt `page.trends`
- `_prev_values` wird am Ende von `_build_pages()` mit den aktuellen Werten überschrieben (bevor die Pages zurückgegeben werden). Damit enthält `_prev_values` beim nächsten Aufruf die zuletzt gezeigten Werte.

---

## ADS1115-Entfernung

- `packages/rpi-agent/hanipi_agent/sensors/ads1115.py` — Datei löschen
- `sensors/__init__.py` — Import + Registrierung entfernen
- Keine Änderung an Config-Schema nötig (unbekannte Sensor-Typen werden ohnehin ignoriert)

---

## Nicht betroffen

- TFT-Display, Web-Dashboard, Exporter, MQTT, Config-Format
- `_fonts()`, `_to_bytes()`, `_flush()`, `_detect_fb()`, `_get_network()`, `_s()`
- Bestehende Spacing-Skala und Farbpalette
