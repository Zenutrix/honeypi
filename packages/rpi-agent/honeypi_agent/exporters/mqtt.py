from __future__ import annotations
import json
import paho.mqtt.client as mqtt  # type: ignore[import-untyped]
from .base import BaseExporter
from ..sensors.base import Measurement


class MQTTExporter(BaseExporter):
    def __init__(self, config: dict) -> None:
        self._topic: str = config.get("topic", "honeypi")
        self._client = mqtt.Client()
        self._client.connect(config["broker"], config.get("port", 1883))
        self._client.loop_start()

    def export(self, measurement: Measurement) -> None:
        payload = json.dumps({"sensor": measurement.name, "timestamp": measurement.timestamp, **measurement.values})
        self._client.publish(f"{self._topic}/{measurement.name}", payload)

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
