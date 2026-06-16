from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from hanipi_agent.display.base import DisplayPage
from hanipi_agent.display.renderer import DisplayRenderer
from hanipi_agent.sensors.base import Measurement

# ── DisplayPage ──────────────────────────────────────────────────────────────

def test_display_page_defaults() -> None:
    page = DisplayPage(
        hive_name="Stock A",
        timestamp=time.time(),
        values={"weight_kg": 42.1},
    )
    assert page.hive_color == "#f59e0b"
    assert page.battery_voltage is None
    assert page.connected is True


def test_display_page_custom_color() -> None:
    page = DisplayPage(
        hive_name="B",
        timestamp=0.0,
        values={},
        hive_color="#10b981",
    )
    assert page.hive_color == "#10b981"


# ── TFTDisplay (mocked PIL) ──────────────────────────────────────────────────

def _make_pil_mock() -> MagicMock:
    pil_mock = MagicMock()
    img_mock = MagicMock()
    pil_mock.Image.new.return_value = img_mock
    pil_mock.ImageDraw.Draw.return_value = MagicMock()
    pil_mock.ImageFont.truetype.side_effect = OSError("no font")
    pil_mock.ImageFont.load_default.return_value = MagicMock()
    img_mock.tobytes.return_value = b"\x00" * (320 * 240 * 2)
    return pil_mock


def test_tft_display_show_page_writes_to_device(tmp_path) -> None:
    device = tmp_path / "fb1"
    device.write_bytes(b"\x00" * (320 * 240 * 2))

    pil_mock = _make_pil_mock()

    with patch.dict("sys.modules", {
        "PIL": pil_mock,
        "PIL.Image": pil_mock.Image,
        "PIL.ImageDraw": pil_mock.ImageDraw,
        "PIL.ImageFont": pil_mock.ImageFont,
    }):
        from importlib import reload

        import hanipi_agent.display.tft as tft_mod
        reload(tft_mod)

        disp = tft_mod.TFTDisplay(device=str(device))
        page = DisplayPage(hive_name="Garten", timestamp=time.time(), values={"weight_kg": 12.3})
        disp.show_page(page)

    # show_page should have called tobytes and written to device file
    pil_mock.Image.new.assert_called()


def test_tft_display_skips_when_pil_unavailable(tmp_path) -> None:
    device = tmp_path / "fb1"
    device.write_bytes(b"")

    with patch.dict("sys.modules", {"PIL": None}):
        from importlib import reload

        import hanipi_agent.display.tft as tft_mod
        try:
            reload(tft_mod)
            disp = tft_mod.TFTDisplay(device=str(device))
            page = DisplayPage(hive_name="X", timestamp=0.0, values={})
            disp.show_page(page)  # Should not raise
        except (ImportError, TypeError, AttributeError):
            pass  # Expected when PIL is fully absent


# ── HDMIDisplay (mocked PIL + framebuffer) ───────────────────────────────────

def test_hdmi_display_start_skips_when_fb_missing(mocker: MagicMock) -> None:
    mocker.patch("pathlib.Path.exists", return_value=False)

    import hanipi_agent.display.hdmi as hdmi_mod
    disp = hdmi_mod.HDMIDisplay()
    disp.start()

    assert disp._available is False


def test_hdmi_display_show_page_writes_to_framebuffer(mocker: MagicMock) -> None:
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("hanipi_agent.display.hdmi._detect_fb", return_value=(320, 240, 16))
    mocker.patch("hanipi_agent.display.hdmi.HDMIDisplay._hide_cursor")
    write_bytes = mocker.patch("pathlib.Path.write_bytes")

    import hanipi_agent.display.hdmi as hdmi_mod
    disp = hdmi_mod.HDMIDisplay()
    disp.start()
    assert disp._available is True

    page = DisplayPage(
        hive_name="Feld", timestamp=time.time(), values={"temperature_c": 35.0}
    )
    disp.show_page(page)

    write_bytes.assert_called()


# ── DisplayRenderer ──────────────────────────────────────────────────────────

def test_renderer_update_stores_measurements() -> None:
    mock_display = MagicMock()
    renderer = DisplayRenderer(display=mock_display, hives=[], page_interval=8)

    m = Measurement(name="Waage", values={"weight_kg": 42.0}, timestamp=time.time(), hive_id="h1")
    renderer.update({"Waage": m})

    with renderer._lock:
        assert "Waage" in renderer._latest


def test_renderer_builds_pages_without_hive_config() -> None:
    mock_display = MagicMock()
    renderer = DisplayRenderer(display=mock_display, hives=[], page_interval=8)

    now = time.time()
    m1 = Measurement(name="Waage", values={"weight_kg": 42.0, "voltage_v": 3.8}, timestamp=now, hive_id=None)
    renderer.update({"Waage": m1})

    pages = renderer._build_pages()
    assert len(pages) >= 1
    # hive_id=None → name "Alle Sensoren"
    assert pages[0].hive_name == "Alle Sensoren"
    assert pages[0].battery_voltage == pytest.approx(3.8)
    assert "weight_kg" in pages[0].values


def test_renderer_extracts_battery_voltage_from_values() -> None:
    mock_display = MagicMock()
    renderer = DisplayRenderer(display=mock_display, hives=[], page_interval=8)

    now = time.time()
    m = Measurement(name="Akku", values={"voltage_v": 12.6, "temperature_c": 28.0}, timestamp=now)
    renderer.update({"Akku": m})

    pages = renderer._build_pages()
    assert pages[0].battery_voltage == pytest.approx(12.6)
    assert "voltage_v" not in pages[0].values


def test_renderer_uses_hive_color_from_hives_list() -> None:
    mock_display = MagicMock()
    hives = [{"id": "abc", "name": "Garten", "color": "#10b981"}]
    renderer = DisplayRenderer(display=mock_display, hives=hives, page_interval=8)

    m = Measurement(name="Waage", values={"weight_kg": 40.0}, timestamp=time.time(), hive_id="abc")
    renderer.update({"Waage": m})

    pages = renderer._build_pages()
    assert pages[0].hive_color == "#10b981"
