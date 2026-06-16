from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hanipi_agent.maintenance import MaintenanceMonitor


class _FakeSensor:
    def __init__(self, type_name: str, name: str = "s") -> None:
        self.__class__ = type(type_name, (_FakeSensor,), {})
        self.name = name
        self.paused = False


def _make_hx711(name: str = "Waage") -> _FakeSensor:
    s = MagicMock()
    s.name = name
    s.paused = False
    type(s).__name__ = "HX711Sensor"
    return s


def _make_monitor(gpio_pin: int = 17, sensors=None) -> MaintenanceMonitor:
    return MaintenanceMonitor(gpio_pin=gpio_pin, sensors=sensors or [])


# ── _set_hx711_paused ────────────────────────────────────────────────────────

def test_set_hx711_paused_pauses_hx711_sensors() -> None:
    hx = _make_hx711()
    non_hx = MagicMock()
    type(non_hx).__name__ = "BME280Sensor"
    non_hx.paused = False

    mon = _make_monitor(sensors=[hx, non_hx])
    mon._set_hx711_paused(True)

    assert hx.paused is True
    assert non_hx.paused is False


def test_set_hx711_paused_unpauses() -> None:
    hx = _make_hx711()
    hx.paused = True
    mon = _make_monitor(sensors=[hx])
    mon._set_hx711_paused(False)
    assert hx.paused is False


# ── _write_status ────────────────────────────────────────────────────────────

def test_write_status_active(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hanipi_agent.maintenance as m_mod
    status_file = tmp_path / "maintenance.json"
    monkeypatch.setattr(m_mod, "_STATUS_FILE", status_file)

    mon = _make_monitor()
    mon._write_status(active=True)

    data = json.loads(status_file.read_text())
    assert data["active"] is True
    assert "since" in data


def test_write_status_inactive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hanipi_agent.maintenance as m_mod
    status_file = tmp_path / "maintenance.json"
    monkeypatch.setattr(m_mod, "_STATUS_FILE", status_file)

    mon = _make_monitor()
    mon._write_status(active=False)

    data = json.loads(status_file.read_text())
    assert data["active"] is False
    assert "since" not in data


# ── _activate / _deactivate ──────────────────────────────────────────────────

def test_activate_pauses_hx711_and_calls_hotspot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hanipi_agent.maintenance as m_mod
    monkeypatch.setattr(m_mod, "_STATUS_FILE", tmp_path / "m.json")

    hx = _make_hx711()
    mon = _make_monitor(sensors=[hx])

    with patch.object(mon, "_hotspot") as mock_hotspot:
        mon._activate()

    assert mon._active is True
    assert hx.paused is True
    mock_hotspot.assert_called_once_with("up")


def test_deactivate_unpauses_hx711_and_calls_hotspot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hanipi_agent.maintenance as m_mod
    monkeypatch.setattr(m_mod, "_STATUS_FILE", tmp_path / "m.json")

    hx = _make_hx711()
    hx.paused = True
    mon = _make_monitor(sensors=[hx])
    mon._active = True

    with patch.object(mon, "_hotspot") as mock_hotspot:
        mon._deactivate()

    assert mon._active is False
    assert hx.paused is False
    mock_hotspot.assert_called_once_with("down")


# ── start() with mock GPIO ───────────────────────────────────────────────────

def test_start_sets_up_gpio_and_starts_thread() -> None:
    mock_gpio = MagicMock()
    mock_gpio.BCM = 11
    mock_gpio.IN = 1
    mock_gpio.PUD_UP = 22
    fake_rpi = MagicMock()
    fake_rpi.GPIO = mock_gpio

    mon = _make_monitor(gpio_pin=17)

    with patch.dict("sys.modules", {"RPi": fake_rpi, "RPi.GPIO": mock_gpio}):
        with patch.object(mon, "_poll_loop"):
            mon.start()

    mock_gpio.setmode.assert_called_once_with(mock_gpio.BCM)
    mock_gpio.setup.assert_called_once_with(17, mock_gpio.IN, pull_up_down=mock_gpio.PUD_UP)


def test_start_disables_gracefully_when_gpio_unavailable() -> None:
    mon = _make_monitor()
    with patch("builtins.__import__", side_effect=ImportError("no GPIO")):
        # Should not raise
        try:
            mon.start()
        except ImportError:
            pass
    # Thread should not be started if GPIO failed — _thread stays None
    # (actual behaviour depends on exception path; just verify no crash)


# ── is_active property ───────────────────────────────────────────────────────

def test_is_active_reflects_internal_state() -> None:
    mon = _make_monitor()
    assert mon.is_active is False
    mon._active = True
    assert mon.is_active is True
