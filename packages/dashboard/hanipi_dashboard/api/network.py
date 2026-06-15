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


@router.get("/network/status")
def network_status() -> dict:
    result: dict = {}

    # WiFi — active connection
    _, wifi_out, _ = _run(["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,DEVICE,SECURITY", "dev", "wifi"])
    for line in wifi_out.splitlines():
        parts = line.split(":")
        if len(parts) >= 4 and parts[0] == "yes":
            device = parts[3]
            _, ip_out, _ = _run(["ip", "-4", "-o", "addr", "show", device])
            ip_m = re.search(r"inet\s+(\S+)", ip_out)
            result["wifi"] = {
                "connected": True,
                "ssid": parts[1],
                "signal": int(parts[2]) if parts[2].isdigit() else 0,
                "device": device,
                "security": parts[4] if len(parts) > 4 else "",
                "ip": ip_m.group(1) if ip_m else None,
            }
            break
    if "wifi" not in result:
        # detect wifi device even when disconnected
        _, dev_out, _ = _run(["nmcli", "-t", "-f", "DEVICE,TYPE", "device", "status"])
        for line in dev_out.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[1] == "wifi":
                result["wifi"] = {"connected": False, "device": parts[0]}
                break
        if "wifi" not in result:
            result["wifi"] = {"connected": False}

    # LAN — first ethernet device
    _, dev_out, _ = _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"])
    for line in dev_out.splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[1] == "ethernet":
            device = parts[0]
            _, ip_out, _ = _run(["ip", "-4", "-o", "addr", "show", device])
            ip_m = re.search(r"inet\s+(\S+)", ip_out)
            _, link_out, _ = _run(["ip", "link", "show", device])
            result["lan"] = {
                "available": True,
                "device": device,
                "state": parts[2],
                "connected": "LOWER_UP" in link_out,
                "ip": ip_m.group(1) if ip_m else None,
            }
            break
    if "lan" not in result:
        result["lan"] = {"available": False}

    return result


def _find_connection(device: str) -> str | None:
    """Return the nmcli connection name associated with a device."""
    _, out, _ = _run(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show"])
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == device:
            return parts[0]
    return None


@router.get("/network/ip/{device}")
def get_ip_config(device: str) -> dict:
    con = _find_connection(device)
    if not con:
        raise HTTPException(status_code=404, detail="Keine Verbindung für dieses Interface")
    _, detail, _ = _run(["nmcli", "-t", "-f",
                          "ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns",
                          "connection", "show", con])
    method_m = re.search(r"ipv4\.method:(.+)", detail)
    addr_m   = re.search(r"ipv4\.addresses:(.+)", detail)
    gw_m     = re.search(r"ipv4\.gateway:(.+)", detail)
    dns_m    = re.search(r"ipv4\.dns:(.+)", detail)
    return {
        "connection": con,
        "mode": "dhcp" if method_m and "auto" in method_m.group(1) else "static",
        "address": addr_m.group(1).strip() if addr_m else "",
        "gateway": gw_m.group(1).strip() if gw_m else "",
        "dns":     dns_m.group(1).strip() if dns_m else "",
    }


class IpConfigRequest(BaseModel):
    mode: str
    address: str = ""
    gateway: str = ""
    dns: str = ""


@router.post("/network/ip/{device}")
def set_ip_config(device: str, req: IpConfigRequest) -> dict:
    con = _find_connection(device)
    if not con:
        raise HTTPException(status_code=404, detail="Keine Verbindung für dieses Interface")
    if req.mode == "dhcp":
        cmd = ["sudo", "nmcli", "connection", "modify", con,
               "ipv4.method", "auto",
               "ipv4.addresses", "", "ipv4.gateway", "", "ipv4.dns", ""]
    else:
        if not req.address:
            raise HTTPException(status_code=400, detail="IP-Adresse fehlt")
        cmd = ["sudo", "nmcli", "connection", "modify", con,
               "ipv4.method", "manual",
               "ipv4.addresses", req.address,
               "ipv4.gateway", req.gateway,
               "ipv4.dns", req.dns]
    rc, _, err = _run(cmd)
    if rc != 0:
        raise HTTPException(status_code=400, detail=f"Fehler: {err.strip()}")
    _run(["sudo", "nmcli", "connection", "up", con], timeout=30)
    return {"status": "ok", "connection": con}


@router.get("/network/wifi/saved")
def wifi_saved() -> list[dict]:
    _, out, _ = _run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"])
    return [
        {"name": line.split(":")[0]}
        for line in out.splitlines()
        if len(line.split(":")) >= 2 and line.split(":")[1] in ("802-11-wireless", "wifi")
    ]


class ForgetRequest(BaseModel):
    name: str


@router.post("/network/wifi/forget")
def wifi_forget(req: ForgetRequest) -> dict:
    rc, _, err = _run(["sudo", "nmcli", "connection", "delete", req.name], timeout=10)
    if rc != 0:
        raise HTTPException(status_code=400, detail=f"Fehler: {err.strip()}")
    return {"status": "deleted"}


@router.post("/network/wifi/reset")
def wifi_reset() -> dict:
    _, out, _ = _run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"])
    deleted = []
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] in ("802-11-wireless", "wifi"):
            _run(["sudo", "nmcli", "connection", "delete", parts[0]], timeout=10)
            deleted.append(parts[0])
    return {"status": "reset", "deleted": deleted}
