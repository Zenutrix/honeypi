from __future__ import annotations
import json
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

CMD_FILE = Path("/var/lib/hanipi/cal_cmd.json")
RESULT_FILE = Path("/var/lib/hanipi/cal_result.json")
CONFIG_PATH = Path("/etc/hanipi/hanipi.json")


class CalibrationServer:
    """Polls for calibration commands from the dashboard and executes them on HX711 sensors."""

    def __init__(self, sensors: list) -> None:
        self._sensors = sensors
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="calibration")
        self._thread.start()
        logger.info("CalibrationServer started")

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        while self._running:
            if CMD_FILE.exists():
                try:
                    text = CMD_FILE.read_text()
                    CMD_FILE.unlink(missing_ok=True)
                    cmd = json.loads(text)
                    result = self._execute(cmd)
                    RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False))
                    logger.info("Calibration result: %s", result)
                except Exception as exc:
                    logger.error("Calibration error: %s", exc)
                    try:
                        RESULT_FILE.write_text(
                            json.dumps({"status": "error", "error": str(exc)})
                        )
                    except Exception:
                        pass
            time.sleep(2)

    def _execute(self, cmd: dict) -> dict:
        action = cmd.get("action")
        sensor_name = cmd.get("sensor_name")

        sensor = self._find_hx711(sensor_name)
        if sensor is None:
            return {"status": "error", "error": "Kein HX711-Sensor gefunden"}

        if action == "tare":
            raw = sensor._read_raw_mean(20)
            sensor._offset = raw
            return {
                "status": "ok",
                "action": "tare",
                "offset": round(raw, 2),
                "sensor": sensor.name,
            }

        if action == "measure":
            weight_g = float(cmd.get("weight_g", 0))
            if weight_g <= 0:
                return {"status": "error", "error": "Ungültiges Referenzgewicht"}
            raw = sensor._read_raw_mean(20)
            ref_unit = (raw - sensor._offset) / weight_g
            sensor._ref_unit = ref_unit
            self._persist_ref_unit(sensor.name, round(ref_unit, 4))
            return {
                "status": "ok",
                "action": "measure",
                "raw": round(raw, 2),
                "offset": round(sensor._offset, 2),
                "ref_unit": round(ref_unit, 4),
                "sensor": sensor.name,
            }

        return {"status": "error", "error": f"Unbekannte Aktion: {action}"}

    def _find_hx711(self, sensor_name: str | None):
        for s in self._sensors:
            if s.__class__.__name__ == "HX711Sensor":
                if sensor_name is None or s.name == sensor_name:
                    return s
        return None

    def _persist_ref_unit(self, sensor_name: str, ref_unit: float) -> None:
        if not CONFIG_PATH.exists():
            return
        try:
            cfg = json.loads(CONFIG_PATH.read_text())
            for s in cfg.get("sensors", []):
                if s.get("name") == sensor_name and s.get("type") == "hx711":
                    s["reference_unit"] = ref_unit
                    break
            CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        except Exception as exc:
            logger.warning("Could not persist reference_unit: %s", exc)
