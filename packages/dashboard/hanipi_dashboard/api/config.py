from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()
CONFIG_PATH = Path("/etc/hanipi/hanipi.json")


def _systemctl(action: str) -> None:
    subprocess.run(
        ["sudo", "systemctl", action, "hanipi-agent"], capture_output=True, timeout=10
    )


@router.get("/status")
def agent_status() -> dict[str, Any]:
    r = subprocess.run(
        ["systemctl", "is-active", "hanipi-agent"], capture_output=True, text=True
    )
    active = r.stdout.strip() == "active"
    return {"active": active, "status": r.stdout.strip()}


@router.get("/config")
def get_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="Config nicht gefunden")
    data: dict[str, Any] = json.loads(CONFIG_PATH.read_text())
    return data


@router.post("/config")
def update_config(config: dict[str, Any]) -> dict[str, Any]:
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    _systemctl("restart")
    return {"status": "ok"}


@router.post("/control/{action}")
def control(action: str) -> dict[str, Any]:
    if action not in {"start", "stop", "restart"}:
        raise HTTPException(status_code=400, detail=f"Ungültige Aktion: {action!r}")
    _systemctl(action)
    return {"status": "ok"}
