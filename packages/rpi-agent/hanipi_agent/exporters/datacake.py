from __future__ import annotations

import logging
from typing import Any

import httpx

from ..sensors.base import Measurement
from .base import BaseExporter

logger = logging.getLogger(__name__)
_URL = "https://api.datacake.co/v1/device/measurements/"


class DatacakeExporter(BaseExporter):
    def __init__(self, config: dict[str, Any]) -> None:
        self._token: str = config["token"]
        self._serial: str = config["serial_number"]
        self._field_mapping: dict[str, str] = config.get("field_mapping", {})

    def export(self, measurement: Measurement) -> None:
        fields = []
        for key, value in measurement.values.items():
            full_key = f"{measurement.name}.{key}"
            field_name = self._field_mapping.get(full_key) or self._field_mapping.get(
                key
            )
            if field_name:
                fields.append({"field": field_name, "value": value})

        if not fields:
            logger.warning(
                "Datacake: keine Felder gemappt für Sensor %s", measurement.name
            )
            return

        payload = {"serial_number": self._serial, "fields": fields}
        headers = {"Authorization": f"Token {self._token}"}
        httpx.post(_URL, json=payload, headers=headers, timeout=10)
