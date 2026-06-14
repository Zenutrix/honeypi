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
    sensors = [create_sensor(s) for s in cfg.sensors]
    exporters = create_exporters(cfg.exporters)

    if not sensors:
        logger.warning("No sensors configured — check /etc/hanipi/hanipi.json")

    runner = MeasurementRunner(sensors=sensors, exporters=exporters, interval=cfg.interval)

    def _shutdown(sig: int, frame: object) -> None:
        logger.info("Shutting down...")
        runner.stop()
        for exp in exporters:
            exp.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("HaniPi Agent started. Interval: %ds, Sensors: %d, Exporters: %d",
                cfg.interval, len(sensors), len(exporters))
    runner.run()


if __name__ == "__main__":
    main()
