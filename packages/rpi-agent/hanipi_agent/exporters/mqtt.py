from __future__ import annotations

import json
from typing import Any

import paho.mqtt.client as mqtt

from ..sensors.base import Measurement
from .base import BaseExporter


class MQTTExporter(BaseExporter):
    def __init__(self, config: dict[str, Any]) -> None:
        self._topic: str = config.get("topic", "hanipi")
        self._client = mqtt.Client()
        self._client.connect(config["broker"], config.get("port", 1883))
        self._client.loop_start()

    def export(self, measurement: Measurement) -> None:
        payload = json.dumps(
            {
                "sensor": measurement.name,
                "timestamp": measurement.timestamp,
                **measurement.values,
            }
        )
        self._client.publish(f"{self._topic}/{measurement.name}", payload)

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
