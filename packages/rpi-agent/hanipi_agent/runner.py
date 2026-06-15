from __future__ import annotations
import logging
import time
from typing import Any
from .sensors.base import BaseSensor, Measurement
from .exporters.base import BaseExporter

logger = logging.getLogger(__name__)


class MeasurementRunner:
    def __init__(
        self,
        sensors: list[BaseSensor],
        exporters: list[BaseExporter],
        interval: int = 300,          # legacy, used if measure/export intervals are 0
        measure_interval: int = 0,    # 0 = use interval
        export_interval: int = 0,     # 0 = use interval
        display_renderer: Any | None = None,
        maintenance_monitor: Any | None = None,
    ) -> None:
        self._sensors = sensors
        self._exporters = exporters
        self._interval = interval
        self._measure_interval = measure_interval
        self._export_interval = export_interval
        self._display_renderer = display_renderer
        self._maintenance_monitor = maintenance_monitor
        self._running = False

    def run_once(self, do_export: bool = True) -> dict[str, Measurement]:
        """Read all non-paused sensors, export, and return latest values keyed by sensor name."""
        latest_values: dict[str, Measurement] = {}
        for sensor in self._sensors:
            if sensor.paused:
                continue
            try:
                measurement = sensor.read()
            except Exception as exc:
                logger.error("Sensor %s failed: %s", sensor.name, exc)
                continue
            measurement.hive_id = sensor.hive_id
            latest_values[sensor.name] = measurement
            for exporter in self._exporters:
                if exporter.realtime or do_export:
                    try:
                        exporter.export(measurement)
                    except Exception as exc:
                        logger.error("Exporter %s failed: %s", type(exporter).__name__, exc)

        self._update_temp_compensation(latest_values)
        return latest_values

    def _update_temp_compensation(self, measurements: dict[str, Measurement]) -> None:
        """Pass current temperature to any HX711 sensors that use temp compensation."""
        from .sensors.hx711 import HX711Sensor
        for sensor in self._sensors:
            if not isinstance(sensor, HX711Sensor) or not sensor._tc_enabled:
                continue
            ref_sensor = sensor._tc_sensor
            if not ref_sensor or ref_sensor not in measurements:
                continue
            m = measurements[ref_sensor]
            temp = m.values.get("temperature_c")
            if temp is not None:
                sensor.set_current_temp(float(temp))

    def run(self) -> None:
        self._running = True

        effective_measure = self._measure_interval if self._measure_interval > 0 else self._interval
        effective_export = self._export_interval if self._export_interval > 0 else self._interval
        cycles_per_export = max(1, effective_export // effective_measure)
        cycle = 0

        if self._maintenance_monitor is not None:
            self._maintenance_monitor.start()

        while self._running:
            cycle += 1
            do_export = (cycle % cycles_per_export == 0)

            latest_values = self.run_once(do_export=do_export)

            if self._display_renderer is not None:
                try:
                    self._display_renderer.update(latest_values)
                except Exception as exc:
                    logger.error("Display renderer update failed: %s", exc)

            time.sleep(effective_measure)

    def stop(self) -> None:
        self._running = False
        if self._maintenance_monitor is not None:
            self._maintenance_monitor.stop()
