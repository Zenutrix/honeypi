from __future__ import annotations
import json
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter()
CONFIG_PATH = Path("/etc/honeypi/honeypi.json")


def _restart_agent() -> None:
    subprocess.run(["systemctl", "restart", "honeypi-agent"], check=True)


@router.get("/config")
def get_config() -> dict:
    if not CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="Config file not found")
    return json.loads(CONFIG_PATH.read_text())


@router.post("/config")
def update_config(config: dict) -> dict:
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    _restart_agent()
    return {"status": "ok"}


@router.post("/control/{action}")
def control(action: str) -> dict:
    if action not in {"start", "stop", "restart"}:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action!r}")
    subprocess.run(["systemctl", action, "honeypi-agent"], check=True)
    return {"status": "ok"}
