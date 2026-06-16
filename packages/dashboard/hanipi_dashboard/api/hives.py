from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import config as cfg_module

router = APIRouter()


def _read_cfg() -> dict[str, Any]:
    if not cfg_module.CONFIG_PATH.exists():
        return {}
    data: dict[str, Any] = json.loads(cfg_module.CONFIG_PATH.read_text())
    return data


def _write_cfg(cfg: dict[str, Any]) -> None:
    cfg_module.CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    cfg_module._systemctl("restart")


class HiveBody(BaseModel):
    name: str
    color: str = "#f59e0b"


@router.get("/hives")
def list_hives() -> list[dict[str, Any]]:
    cfg = _read_cfg()
    hives: list[dict[str, Any]] = cfg.get("hives", [])
    return hives


@router.post("/hives")
def add_hive(body: HiveBody) -> dict[str, Any]:
    cfg = _read_cfg()
    hive = {"id": str(uuid.uuid4()), "name": body.name, "color": body.color}
    cfg.setdefault("hives", []).append(hive)
    _write_cfg(cfg)
    return hive


@router.put("/hives/{hive_id}")
def update_hive(hive_id: str, body: HiveBody) -> dict[str, Any]:
    cfg = _read_cfg()
    hives: list[dict[str, Any]] = cfg.get("hives", [])
    for h in hives:
        if h["id"] == hive_id:
            h["name"] = body.name
            h["color"] = body.color
            _write_cfg(cfg)
            return h
    raise HTTPException(status_code=404, detail="Hive not found")


@router.delete("/hives/{hive_id}")
def delete_hive(hive_id: str) -> dict[str, Any]:
    cfg = _read_cfg()
    hives: list[dict[str, Any]] = cfg.get("hives", [])
    cfg["hives"] = [h for h in hives if h["id"] != hive_id]
    # Clear hive_id from sensors
    for sensor in cfg.get("sensors", []):
        if sensor.get("hive_id") == hive_id:
            sensor.pop("hive_id", None)
    _write_cfg(cfg)
    return {"status": "deleted"}
