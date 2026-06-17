from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()
CONFIG_PATH = Path("/etc/hanipi/hanipi.json")

# Bekannte I²C-Geräte: Adresse → Name für die UI
_KNOWN_I2C: dict[int, str] = {
    0x23: "BH1750 — Licht (ADDR→GND)",
    0x40: "INA3221 — Solar/Batterie (A0/A1→GND)",
    0x41: "INA3221 (A0→VCC) / INA226 Batterie",
    0x48: "ADS1115 (ADDR→GND)",
    0x49: "ADS1115 (ADDR→VCC)",
    0x4A: "ADS1115 (ADDR→SDA)",
    0x4B: "ADS1115 (ADDR→SCL)",
    0x5C: "BH1750 — Licht (ADDR→3.3V)",
    0x68: "RTC DS3231 / DS1307",
    0x76: "BME280 / BME680 (SDO→GND)",
    0x77: "BME280 / BME680 (SDO→3.3V)",
}


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


@router.get("/scan/i2c")
def scan_i2c(bus: int = 1) -> list[dict[str, Any]]:
    """Scannt den I²C-Bus und gibt gefundene Geräte mit Namen zurück."""
    found: list[dict[str, Any]] = []
    try:
        import smbus2

        b = smbus2.SMBus(bus)
        for addr in range(0x03, 0x78):
            try:
                b.read_byte(addr)
                hex_addr = f"0x{addr:02x}"
                name = _KNOWN_I2C.get(addr, f"Unbekanntes Gerät @ {hex_addr}")
                found.append({"address": addr, "hex": hex_addr, "name": name})
            except OSError:
                pass
        b.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"I²C-Scan fehlgeschlagen: {exc}")
    return found


@router.get("/scan/1wire")
def scan_1wire() -> list[dict[str, str]]:
    """Scannt den 1-Wire-Bus und gibt gefundene DS18B20-Sensoren zurück."""
    w1_root = Path("/sys/bus/w1/devices")
    devices = []
    if w1_root.exists():
        for d in sorted(w1_root.glob("28-*")):
            devices.append({"id": d.name, "label": f"DS18B20 — {d.name}"})
    return devices
