from __future__ import annotations
import json
from pathlib import Path
from fastapi import APIRouter, Query

router = APIRouter()

CMD_FILE = Path("/var/lib/hanipi/cal_cmd.json")
RESULT_FILE = Path("/var/lib/hanipi/cal_result.json")


@router.post("/calibrate/tare")
def calibrate_tare(sensor_name: str | None = Query(default=None)) -> dict:
    cmd: dict = {"action": "tare"}
    if sensor_name:
        cmd["sensor_name"] = sensor_name
    RESULT_FILE.unlink(missing_ok=True)
    CMD_FILE.write_text(json.dumps(cmd))
    return {"status": "pending"}


@router.post("/calibrate/measure")
def calibrate_measure(
    weight_g: float = Query(..., gt=0),
    sensor_name: str | None = Query(default=None),
) -> dict:
    cmd: dict = {"action": "measure", "weight_g": weight_g}
    if sensor_name:
        cmd["sensor_name"] = sensor_name
    RESULT_FILE.unlink(missing_ok=True)
    CMD_FILE.write_text(json.dumps(cmd))
    return {"status": "pending"}


@router.get("/calibrate/result")
def calibrate_result() -> dict:
    if CMD_FILE.exists():
        return {"status": "pending"}
    if RESULT_FILE.exists():
        return json.loads(RESULT_FILE.read_text())
    return {"status": "idle"}


@router.post("/calibrate/set-temp-ref")
def calibrate_set_temp_ref(sensor_name: str | None = Query(default=None)) -> dict:
    cmd: dict = {"action": "set_temp_ref"}
    if sensor_name:
        cmd["sensor_name"] = sensor_name
    RESULT_FILE.unlink(missing_ok=True)
    CMD_FILE.write_text(json.dumps(cmd))
    return {"status": "pending"}


@router.post("/calibrate/read")
def calibrate_read(sensor_name: str | None = Query(default=None)) -> dict:
    cmd: dict = {"action": "read"}
    if sensor_name:
        cmd["sensor_name"] = sensor_name
    RESULT_FILE.unlink(missing_ok=True)
    CMD_FILE.write_text(json.dumps(cmd))
    return {"status": "pending"}


@router.delete("/calibrate/result")
def calibrate_clear() -> dict:
    RESULT_FILE.unlink(missing_ok=True)
    return {"status": "cleared"}
