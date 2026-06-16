from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
_STATUS_FILE = Path("/var/lib/hanipi/maintenance.json")
_HOTSPOT_CON = "HaniPi-Wartung"


@router.get("/maintenance/status")
def maintenance_status() -> dict[str, Any]:
    if not _STATUS_FILE.exists():
        return {"active": False}
    try:
        data: dict[str, Any] = json.loads(_STATUS_FILE.read_text())
        return data
    except Exception:
        return {"active": False}


class HotspotAction(BaseModel):
    action: str  # "up" or "down"


@router.post("/maintenance/hotspot")
def hotspot(body: HotspotAction) -> dict[str, Any]:
    if body.action not in {"up", "down"}:
        raise HTTPException(status_code=400, detail="action must be 'up' or 'down'")
    r = subprocess.run(
        ["sudo", "nmcli", "connection", body.action, _HOTSPOT_CON],
        capture_output=True,
        text=True,
        timeout=20,
    )
    return {"status": "ok", "action": body.action, "output": r.stdout.strip()}
