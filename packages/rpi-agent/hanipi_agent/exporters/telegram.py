from __future__ import annotations

import datetime
import json
import logging
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..sensors.base import Measurement
from .base import BaseExporter

logger = logging.getLogger(__name__)

_STATE_FILE = Path("/var/lib/hanipi/telegram_last_sent.txt")

_LABELS = {
    "weight_kg": "Gewicht",
    "temperature_c": "Temperatur",
    "humidity_pct": "Feuchte",
    "pressure_hpa": "Luftdruck",
    "illuminance_lux": "Licht",
    "gas_resistance_ohm": "Gas",
    "voltage_v": "Spannung",
}
_UNITS = {
    "weight_kg": "kg",
    "temperature_c": "°C",
    "humidity_pct": "%",
    "pressure_hpa": "hPa",
    "illuminance_lux": "lx",
    "gas_resistance_ohm": "Ω",
    "voltage_v": "V",
}
_ICONS = {
    "weight_kg": "⚖️",
    "temperature_c": "🌡",
    "humidity_pct": "💧",
    "pressure_hpa": "🔵",
    "illuminance_lux": "☀️",
    "voltage_v": "🔋",
    "gas_resistance_ohm": "💨",
}
_KEY_ORDER = [
    "weight_kg",
    "temperature_c",
    "humidity_pct",
    "pressure_hpa",
    "voltage_v",
    "illuminance_lux",
    "gas_resistance_ohm",
]

_WEEKDAYS = [
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
]
_MONTHS = [
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]


class TelegramExporter(BaseExporter):
    realtime: bool = False

    def __init__(self, config: dict[str, Any]) -> None:
        self._bot_token = config.get("bot_token", "").strip()
        self._chat_id = str(config.get("chat_id", "")).strip()
        self._send_time = config.get("send_time", "08:00")
        self._hives: dict[str, str] = {
            h["id"]: h["name"] for h in config.get("_hives", [])
        }
        # hive_id → {key: value}
        self._latest: dict[str, dict[str, float]] = defaultdict(dict)

    def export(self, measurement: Measurement) -> None:
        hive_id = measurement.hive_id or "__none__"
        for key, value in measurement.values.items():
            self._latest[hive_id][key] = float(value)

        if self._should_send():
            try:
                self._send_report()
                self._mark_sent()
            except Exception as exc:
                logger.error("Telegram: Senden fehlgeschlagen: %s", exc)

    def _should_send(self) -> bool:
        if not self._bot_token or not self._chat_id:
            return False
        if not self._latest:
            return False
        now = datetime.datetime.now()
        try:
            h, m = [int(x) for x in self._send_time.split(":")]
        except Exception:
            return False
        if now.hour < h or (now.hour == h and now.minute < m):
            return False
        today = now.strftime("%Y-%m-%d")
        try:
            if _STATE_FILE.read_text().strip() == today:
                return False
        except FileNotFoundError:
            pass
        return True

    def _mark_sent(self) -> None:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(datetime.date.today().isoformat())

    def _send_report(self) -> None:
        now = datetime.datetime.now()
        date_str = (
            f"{_WEEKDAYS[now.weekday()]}, {now.day}. "
            f"{_MONTHS[now.month - 1]} {now.year}"
        )

        lines = [
            "🐝 *HaniPi Tagesbericht*",
            f"📅 {date_str} · {now.strftime('%H:%M')}",
            "",
        ]

        for hive_id, values in self._latest.items():
            name = self._hives.get(
                hive_id, "Sensoren" if hive_id == "__none__" else hive_id
            )
            lines.append(f"📍 *{name}*")

            for key in sorted(
                values, key=lambda k: _KEY_ORDER.index(k) if k in _KEY_ORDER else 99
            ):
                val = values[key]
                icon = _ICONS.get(key, "•")
                label = _LABELS.get(key, key)
                unit = _UNITS.get(key, "")
                lines.append(f"{icon} {label}: *{val:.1f} {unit}*")
            lines.append("")

        text = "\n".join(lines).rstrip()
        payload = json.dumps(
            {
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }
        ).encode()

        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        if not result.get("ok"):
            raise RuntimeError(f"Telegram API: {result}")
        logger.info("Telegram Tagesbericht gesendet.")
