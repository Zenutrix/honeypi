from __future__ import annotations
import re
import subprocess
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


def _run(cmd: list[str], timeout: int = 15) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return -1, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"


@router.get("/network/modem")
def modem_status() -> dict:
    rc, out, err = _run(["mmcli", "-L"])
    if rc != 0:
        return {"available": False, "reason": "Kein ModemManager oder kein Stick gefunden"}

    match = re.search(r"/Modem/(\d+)", out)
    if not match:
        return {"available": False, "reason": "Kein Stick erkannt"}

    modem_id = match.group(1)
    _, detail, _ = _run(["mmcli", "-m", modem_id])

    state_m = re.search(r"state:\s+'?(\w[\w-]*)'?", detail)
    signal_m = re.search(r"signal quality:\s+'?(\d+)%", detail)
    model_m = re.search(r"model:\s+'?(.+?)'?\n", detail)

    _, nm_out, _ = _run(["nmcli", "-t", "-f", "NAME,TYPE,STATE", "connection", "show", "--active"])
    connected = any("hanipi-4g" in line and "activated" in line for line in nm_out.splitlines())

    # Current APN if connection exists
    _, apn_out, _ = _run(["nmcli", "-t", "-f", "gsm.apn", "connection", "show", "hanipi-4g"])
    apn = ""
    apn_m = re.search(r"gsm\.apn:(.+)", apn_out)
    if apn_m:
        apn = apn_m.group(1).strip()

    return {
        "available": True,
        "modem_id": modem_id,
        "model": model_m.group(1).strip() if model_m else "Unbekannter Stick",
        "state": state_m.group(1) if state_m else "unknown",
        "signal": int(signal_m.group(1)) if signal_m else None,
        "connected": connected,
        "apn": apn,
    }


class ConnectRequest(BaseModel):
    apn: str
    username: str = ""
    password: str = ""


@router.post("/network/connect")
def connect(req: ConnectRequest) -> dict:
    if not req.apn:
        raise HTTPException(status_code=400, detail="APN fehlt")

    CON = "hanipi-4g"
    _run(["sudo", "nmcli", "connection", "delete", CON])

    cmd = ["sudo", "nmcli", "connection", "add",
           "type", "gsm", "con-name", CON, "ifname", "*",
           "gsm.apn", req.apn, "connection.autoconnect", "yes"]
    if req.username:
        cmd += ["gsm.username", req.username]
    if req.password:
        cmd += ["gsm.password", req.password]

    rc, _, err = _run(cmd, timeout=20)
    if rc != 0:
        raise HTTPException(status_code=400, detail=f"Verbindung erstellen fehlgeschlagen: {err.strip()}")

    rc2, _, err2 = _run(["sudo", "nmcli", "connection", "up", CON], timeout=60)
    if rc2 != 0:
        raise HTTPException(status_code=400, detail=f"Verbinden fehlgeschlagen: {err2.strip()}")

    return {"status": "connected"}


@router.post("/network/disconnect")
def disconnect() -> dict:
    _run(["sudo", "nmcli", "connection", "down", "hanipi-4g"])
    return {"status": "disconnected"}


@router.get("/network/wifi/scan")
def wifi_scan() -> list[dict]:
    _, out, _ = _run(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"], timeout=20)
    results: list[dict] = []
    seen: set[str] = set()
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 2:
            ssid = parts[0].strip()
            if ssid and ssid not in seen:
                seen.add(ssid)
                signal = int(parts[1]) if parts[1].isdigit() else 0
                security = parts[2].strip() if len(parts) > 2 else ""
                results.append({"ssid": ssid, "signal": signal, "security": security})
    results.sort(key=lambda x: x["signal"], reverse=True)
    return results


class WifiConnectRequest(BaseModel):
    ssid: str
    password: str = ""


@router.post("/network/wifi/connect")
def wifi_connect(req: WifiConnectRequest) -> dict:
    if not req.ssid:
        raise HTTPException(status_code=400, detail="SSID fehlt")
    if req.password:
        cmd = ["sudo", "nmcli", "device", "wifi", "connect", req.ssid, "password", req.password]
    else:
        cmd = ["sudo", "nmcli", "device", "wifi", "connect", req.ssid]
    rc, out, err = _run(cmd, timeout=30)
    if rc != 0:
        raise HTTPException(status_code=400, detail=f"WLAN-Verbindung fehlgeschlagen: {err.strip()}")
    return {"status": "connected", "ssid": req.ssid}
