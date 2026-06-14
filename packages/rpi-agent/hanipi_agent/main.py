from __future__ import annotations
import logging
import signal
import sys
from pathlib import Path
from .config import load_config
from .sensors import create_sensor
from .exporters import create_exporters
from .runner import MeasurementRunner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    cfg = load_config(Path("/etc/hanipi/hanipi.json"))
    sensors = []
    for s_cfg in cfg.sensors:
        try:
            sensors.append(create_sensor(s_cfg))
        except Exception as exc:
            logger.error(
                "Sensor '%s' (%s) konnte nicht initialisiert werden: %s",
                s_cfg.get("name", "?"), s_cfg.get("type", "?"), exc,
            )
    exporters = create_exporters(cfg.exporters)

    if not sensors:
        logger.warning("No sensors configured — check /etc/hanipi/hanipi.json")

    maintenance_monitor = None
    if cfg.maintenance_switch.enabled:
        try:
            from .maintenance import MaintenanceMonitor
            maintenance_monitor = MaintenanceMonitor(
                gpio_pin=cfg.maintenance_switch.gpio_pin,
                sensors=sensors,
            )
        except Exception as exc:
            logger.warning("Could not initialize MaintenanceMonitor: %s", exc)

    display_renderer = None
    if cfg.display.enabled and cfg.display.type != "none":
        try:
            from .display.renderer import DisplayRenderer
            if cfg.display.type == "hdmi":
                from .display.hdmi import HDMIDisplay
                display_obj: object = HDMIDisplay(rotation=cfg.display.rotation)
            else:
                from .display.tft import TFTDisplay
                display_obj = TFTDisplay(
                    device=cfg.display.tft_device, rotation=cfg.display.rotation
                )
            hives_dicts = [h.model_dump() for h in cfg.hives]
            display_renderer = DisplayRenderer(
                display=display_obj,  # type: ignore[arg-type]
                hives=hives_dicts,
                page_interval=cfg.display.page_interval,
            )
            display_renderer.start()
        except Exception as exc:
            logger.warning("Could not initialize display: %s", exc)

    runner = MeasurementRunner(
        sensors=sensors,
        exporters=exporters,
        interval=cfg.interval,
        measure_interval=cfg.effective_measure_interval,
        export_interval=cfg.effective_export_interval,
        display_renderer=display_renderer,
        maintenance_monitor=maintenance_monitor,
    )

    def _shutdown(sig: int, frame: object) -> None:
        logger.info("Shutting down...")
        runner.stop()
        if display_renderer is not None:
            display_renderer.stop()
        for exp in exporters:
            exp.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info(
        "HaniPi Agent started. Measure: %ds, Export: %ds, Sensors: %d, Exporters: %d",
        cfg.effective_measure_interval,
        cfg.effective_export_interval,
        len(sensors),
        len(exporters),
    )
    runner.run()


if __name__ == "__main__":
    main()
