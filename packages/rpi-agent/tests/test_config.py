import json
import pytest
from pathlib import Path
from honeypi_agent.config import load_config, HoneyPiConfig


def test_load_minimal_config(tmp_path: Path) -> None:
    cfg_file = tmp_path / "honeypi.json"
    cfg_file.write_text(json.dumps({"interval": 60, "sensors": [], "exporters": {}}))
    cfg = load_config(cfg_file)
    assert cfg.interval == 60
    assert cfg.sensors == []


def test_load_config_with_local_exporter(tmp_path: Path) -> None:
    data = {
        "interval": 300,
        "sensors": [{"type": "dummy", "name": "TestSensor"}],
        "exporters": {"local": {"enabled": True, "db_path": "/tmp/test.db"}},
    }
    cfg_file = tmp_path / "honeypi.json"
    cfg_file.write_text(json.dumps(data))
    cfg = load_config(cfg_file)
    assert cfg.exporters["local"]["enabled"] is True


def test_config_defaults(tmp_path: Path) -> None:
    cfg_file = tmp_path / "honeypi.json"
    cfg_file.write_text("{}")
    cfg = load_config(cfg_file)
    assert cfg.interval == 300
    assert cfg.exporters == {}
