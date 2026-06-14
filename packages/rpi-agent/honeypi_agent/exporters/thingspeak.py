from __future__ import annotations
import logging
import httpx
from .base import BaseExporter
from ..sensors.base import Measurement

logger = logging.getLogger(__name__)
_URL = "https://api.thingspeak.com/update"


class ThingSpeakExporter(BaseExporter):
    def __init__(self, config: dict) -> None:
        self._api_key: str = config["api_key"]
        self._field_mapping: dict[str, str] = config.get("field_mapping", {})

    def export(self, measurement: Measurement) -> None:
        params: dict[str, object] = {"api_key": self._api_key}
        for key, value in measurement.values.items():
            field = self._field_mapping.get(key)
            if field:
                params[field] = value
        if len(params) < 2:
            logger.warning("ThingSpeak: no fields mapped for sensor %s", measurement.name)
            return
        httpx.get(_URL, params=params, timeout=10)
