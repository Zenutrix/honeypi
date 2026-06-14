from __future__ import annotations
import logging
import time
from .sensors.base import BaseSensor
from .exporters.base import BaseExporter

logger = logging.getLogger(__name__)


class MeasurementRunner:
    def __init__(self, sensors: list[BaseSensor], exporters: list[BaseExporter], interval: int) -> None:
        self._sensors = sensors
        self._exporters = exporters
        self._interval = interval
        self._running = False

    def run_once(self) -> None:
        for sensor in self._sensors:
            try:
                measurement = sensor.read()
            except Exception as exc:
                logger.error("Sensor %s failed: %s", sensor.name, exc)
                continue
            for exporter in self._exporters:
                try:
                    exporter.export(measurement)
                except Exception as exc:
                    logger.error("Exporter %s failed: %s", type(exporter).__name__, exc)

    def run(self) -> None:
        self._running = True
        while self._running:
            self.run_once()
            time.sleep(self._interval)

    def stop(self) -> None:
        self._running = False
