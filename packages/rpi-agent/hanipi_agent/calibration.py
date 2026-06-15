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
            result: dict = {
                "status": "ok",
                "action": "tare",
                "offset": round(raw, 2),
                "sensor": sensor.name,
            }
            # Auto-capture reference temperature if temp compensation is configured
            if sensor._tc_enabled and sensor._tc_sensor:
                temp_c = self._read_temp(sensor._tc_sensor)
                if temp_c is not None:
                    sensor._tc_ref_c = temp_c
                    self._persist_temp_ref(sensor.name, temp_c)
                    result["ref_temp_c"] = round(temp_c, 2)
            return result

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

        if action == "read":
            raw = sensor._read_raw_mean(sensor._samples)
            weight_kg = round((raw - sensor._offset) / sensor._ref_unit / 1000, 3)
            result = {
                "status": "ok",
                "action": "read",
                "weight_kg": weight_kg,
                "sensor": sensor.name,
            }
            if sensor._tc_enabled and sensor._tc_sensor:
                temp_c = self._read_temp(sensor._tc_sensor)
                if temp_c is not None:
                    result["current_temp_c"] = round(temp_c, 2)
            return result

        if action == "set_temp_ref":
            if not sensor._tc_sensor:
                return {"status": "error", "error": "Kein Temperatursensor konfiguriert"}
            temp_c = self._read_temp(sensor._tc_sensor)
            if temp_c is None:
                return {"status": "error", "error": f"Sensor '{sensor._tc_sensor}' hat keine Temperaturmessung"}
            sensor._tc_ref_c = temp_c
            self._persist_temp_ref(sensor.name, temp_c)
            return {
                "status": "ok",
                "action": "set_temp_ref",
                "ref_temp_c": round(temp_c, 2),
                "sensor": sensor.name,
            }

        return {"status": "error", "error": f"Unbekannte Aktion: {action}"}

    def _read_temp(self, sensor_name: str) -> float | None:
        for s in self._sensors:
            if s.name == sensor_name:
                try:
                    m = s.read()
                    return m.values.get("temperature_c")
                except Exception as exc:
                    logger.warning("Could not read temp from '%s': %s", sensor_name, exc)
                    return None
        return None

    def _persist_temp_ref(self, sensor_name: str, temp_c: float) -> None:
        if not CONFIG_PATH.exists():
            return
        try:
            from datetime import datetime, timezone
            cfg = json.loads(CONFIG_PATH.read_text())
            for s in cfg.get("sensors", []):
                if s.get("name") == sensor_name and s.get("type") == "hx711":
                    tc = s.setdefault("temp_compensation", {})
                    tc["ref_c"] = round(temp_c, 2)
                    tc["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    break
            CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        except Exception as exc:
            logger.warning("Could not persist temp ref: %s", exc)

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
