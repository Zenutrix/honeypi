# HoneyPi Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kompletter Neustart von HoneyPi als Monorepo mit modernem Python-Agent, modularem Exporter-System und lokalem FastAPI-Dashboard.

**Architecture:** `rpi-agent` liest Sensoren, schreibt in SQLite (local-Exporter) und optional in externe Dienste (ThingSpeak, InfluxDB, MQTT). `dashboard` liest aus derselben SQLite-DB und stellt unter `honeypi.local` ein Web-UI bereit. Beide laufen als systemd-Services.

**Tech Stack:** Python 3.11+, uv, Pydantic v2, FastAPI, uvicorn, Chart.js (CDN), SQLite, httpx, influxdb-client, paho-mqtt, pytest, ruff

---

## File Map

```
honeypi/
├── .github/workflows/
│   ├── test.yml
│   └── lint.yml
├── packages/
│   ├── rpi-agent/
│   │   ├── pyproject.toml
│   │   ├── honeypi_agent/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── runner.py
│   │   │   ├── sensors/
│   │   │   │   ├── __init__.py       ← factory
│   │   │   │   ├── base.py
│   │   │   │   ├── dummy.py
│   │   │   │   ├── hx711.py
│   │   │   │   ├── ds18b20.py
│   │   │   │   └── bme280.py
│   │   │   └── exporters/
│   │   │       ├── __init__.py       ← factory
│   │   │       ├── base.py
│   │   │       ├── local.py
│   │   │       ├── thingspeak.py
│   │   │       ├── influxdb.py
│   │   │       └── mqtt.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── test_config.py
│   │   │   ├── test_runner.py
│   │   │   ├── test_sensors.py
│   │   │   └── test_exporters.py
│   │   └── systemd/
│   │       └── honeypi-agent.service
│   └── dashboard/
│       ├── pyproject.toml
│       ├── honeypi_dashboard/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── db.py
│       │   └── api/
│       │       ├── __init__.py
│       │       ├── data.py
│       │       └── config.py
│       ├── static/
│       │   ├── index.html
│       │   ├── config.html
│       │   ├── app.js
│       │   └── style.css
│       ├── tests/
│       │   ├── __init__.py
│       │   └── test_api.py
│       └── systemd/
│           └── honeypi-dashboard.service
└── packages/installer/
    └── install.sh
```

---

## Phase 1: Monorepo Foundation

### Task 1: Git-Repo + Verzeichnisstruktur anlegen

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/__init__.py`
- Create: `packages/rpi-agent/honeypi_agent/sensors/__init__.py`
- Create: `packages/rpi-agent/honeypi_agent/exporters/__init__.py`
- Create: `packages/rpi-agent/tests/__init__.py`
- Create: `packages/dashboard/honeypi_dashboard/__init__.py`
- Create: `packages/dashboard/honeypi_dashboard/api/__init__.py`
- Create: `packages/dashboard/tests/__init__.py`
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Schritt 1: Verzeichnisstruktur anlegen**

```bash
mkdir -p packages/rpi-agent/honeypi_agent/sensors
mkdir -p packages/rpi-agent/honeypi_agent/exporters
mkdir -p packages/rpi-agent/tests
mkdir -p packages/rpi-agent/systemd
mkdir -p packages/dashboard/honeypi_dashboard/api
mkdir -p packages/dashboard/static
mkdir -p packages/dashboard/tests
mkdir -p packages/dashboard/systemd
mkdir -p packages/installer
mkdir -p .github/workflows
```

- [ ] **Schritt 2: `__init__.py` Dateien anlegen**

```bash
touch packages/rpi-agent/honeypi_agent/__init__.py
touch packages/rpi-agent/honeypi_agent/sensors/__init__.py
touch packages/rpi-agent/honeypi_agent/exporters/__init__.py
touch packages/rpi-agent/tests/__init__.py
touch packages/dashboard/honeypi_dashboard/__init__.py
touch packages/dashboard/honeypi_dashboard/api/__init__.py
touch packages/dashboard/tests/__init__.py
```

- [ ] **Schritt 3: `.gitignore` schreiben**

```
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
.ruff_cache/
.mypy_cache/
.pytest_cache/
```

- [ ] **Schritt 4: Git initialisieren und ersten Commit machen**

```bash
git init
git add .
git commit -m "chore: initialize monorepo structure"
```

---

### Task 2: `rpi-agent` pyproject.toml

**Files:**
- Create: `packages/rpi-agent/pyproject.toml`

- [ ] **Schritt 1: `pyproject.toml` schreiben**

```toml
[project]
name = "honeypi-agent"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "httpx>=0.27",
    "influxdb-client>=1.40",
    "paho-mqtt>=2.0",
    "w1thermsensor>=2.0",
]

[project.scripts]
honeypi-agent = "honeypi_agent.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-mock>=3.14",
    "ruff>=0.4",
    "mypy>=1.10",
]

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.mypy]
strict = true
```

- [ ] **Schritt 2: Virtuelle Umgebung anlegen**

```bash
cd packages/rpi-agent
uv venv
uv sync
```

- [ ] **Schritt 3: Committen**

```bash
git add packages/rpi-agent/pyproject.toml
git commit -m "chore: add rpi-agent pyproject.toml"
```

---

### Task 3: `dashboard` pyproject.toml

**Files:**
- Create: `packages/dashboard/pyproject.toml`

- [ ] **Schritt 1: `pyproject.toml` schreiben**

```toml
[project]
name = "honeypi-dashboard"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.30",
]

[project.scripts]
honeypi-dashboard = "honeypi_dashboard.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "httpx>=0.27",
    "ruff>=0.4",
    "mypy>=1.10",
]

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.mypy]
strict = true
```

- [ ] **Schritt 2: Virtuelle Umgebung anlegen**

```bash
cd packages/dashboard
uv venv
uv sync
```

- [ ] **Schritt 3: Committen**

```bash
git add packages/dashboard/pyproject.toml
git commit -m "chore: add dashboard pyproject.toml"
```

---

## Phase 2: rpi-agent — Config & Abstractions

### Task 4: Config-Modell (Pydantic)

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/config.py`
- Create: `packages/rpi-agent/tests/test_config.py`

- [ ] **Schritt 1: Test schreiben**

`packages/rpi-agent/tests/test_config.py`:
```python
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
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
cd packages/rpi-agent
uv run pytest tests/test_config.py -v
```
Erwartet: `ImportError: cannot import name 'load_config'`

- [ ] **Schritt 3: `config.py` implementieren**

`packages/rpi-agent/honeypi_agent/config.py`:
```python
from __future__ import annotations
import json
from pathlib import Path
from pydantic import BaseModel, Field


class HoneyPiConfig(BaseModel):
    interval: int = 300
    sensors: list[dict] = Field(default_factory=list)
    exporters: dict[str, dict] = Field(default_factory=dict)


def load_config(path: Path = Path("/etc/honeypi/honeypi.json")) -> HoneyPiConfig:
    if not path.exists():
        return HoneyPiConfig()
    return HoneyPiConfig.model_validate(json.loads(path.read_text()))
```

- [ ] **Schritt 4: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_config.py -v
```
Erwartet: `3 passed`

- [ ] **Schritt 5: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/config.py packages/rpi-agent/tests/test_config.py
git commit -m "feat(agent): add config model with Pydantic"
```

---

### Task 5: Measurement-Datenklasse + BaseSensor

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/sensors/base.py`

- [ ] **Schritt 1: Test schreiben**

`packages/rpi-agent/tests/test_sensors.py`:
```python
import time
from honeypi_agent.sensors.base import BaseSensor, Measurement


class ConcreteSensor(BaseSensor):
    def read(self) -> Measurement:
        return Measurement(name=self.name, values={"x": 1.0}, timestamp=time.time())


def test_sensor_uses_name_from_config() -> None:
    s = ConcreteSensor({"type": "concrete", "name": "MyHive"})
    assert s.name == "MyHive"


def test_measurement_has_values() -> None:
    s = ConcreteSensor({"type": "concrete", "name": "Test"})
    m = s.read()
    assert "x" in m.values
    assert m.name == "Test"
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
uv run pytest tests/test_sensors.py -v
```

- [ ] **Schritt 3: `sensors/base.py` implementieren**

`packages/rpi-agent/honeypi_agent/sensors/base.py`:
```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Measurement:
    name: str
    values: dict[str, float]
    timestamp: float


class BaseSensor(ABC):
    def __init__(self, config: dict) -> None:
        self.name: str = config.get("name", self.__class__.__name__)
        self._configure(config)

    def _configure(self, config: dict) -> None:
        pass

    @abstractmethod
    def read(self) -> Measurement:
        ...
```

- [ ] **Schritt 4: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_sensors.py -v
```

- [ ] **Schritt 5: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/sensors/base.py packages/rpi-agent/tests/test_sensors.py
git commit -m "feat(agent): add Measurement dataclass and BaseSensor"
```

---

### Task 6: DummySensor

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/sensors/dummy.py`

- [ ] **Schritt 1: Test in `test_sensors.py` ergänzen**

```python
# ans Ende von tests/test_sensors.py anhängen:
from honeypi_agent.sensors.dummy import DummySensor


def test_dummy_sensor_returns_configured_values() -> None:
    s = DummySensor({"type": "dummy", "name": "Fake", "values": {"weight": 42.5, "temp": 21.0}})
    m = s.read()
    assert m.values["weight"] == pytest.approx(42.5, abs=5.0)
    assert "temp" in m.values


def test_dummy_sensor_default_values() -> None:
    s = DummySensor({"type": "dummy", "name": "Default"})
    m = s.read()
    assert "value" in m.values
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
uv run pytest tests/test_sensors.py::test_dummy_sensor_returns_configured_values -v
```

- [ ] **Schritt 3: `sensors/dummy.py` implementieren**

`packages/rpi-agent/honeypi_agent/sensors/dummy.py`:
```python
from __future__ import annotations
import random
import time
from .base import BaseSensor, Measurement


class DummySensor(BaseSensor):
    def _configure(self, config: dict) -> None:
        self._values: dict[str, float] = config.get("values", {"value": 0.0})
        self._noise: float = config.get("noise", 0.5)

    def read(self) -> Measurement:
        noisy = {k: v + random.uniform(-self._noise, self._noise) for k, v in self._values.items()}
        return Measurement(name=self.name, values=noisy, timestamp=time.time())
```

- [ ] **Schritt 4: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_sensors.py -v
```

- [ ] **Schritt 5: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/sensors/dummy.py packages/rpi-agent/tests/test_sensors.py
git commit -m "feat(agent): add DummySensor for testing and simulation"
```

---

### Task 7: BaseExporter

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/exporters/base.py`
- Create: `packages/rpi-agent/tests/test_exporters.py`

- [ ] **Schritt 1: Test schreiben**

`packages/rpi-agent/tests/test_exporters.py`:
```python
import time
from honeypi_agent.exporters.base import BaseExporter
from honeypi_agent.sensors.base import Measurement


class ConcreteExporter(BaseExporter):
    def __init__(self) -> None:
        self.exported: list[Measurement] = []

    def export(self, measurement: Measurement) -> None:
        self.exported.append(measurement)


def test_exporter_receives_measurement() -> None:
    exp = ConcreteExporter()
    m = Measurement(name="Test", values={"weight": 10.0}, timestamp=time.time())
    exp.export(m)
    assert len(exp.exported) == 1
    assert exp.exported[0].name == "Test"
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
uv run pytest tests/test_exporters.py -v
```

- [ ] **Schritt 3: `exporters/base.py` implementieren**

`packages/rpi-agent/honeypi_agent/exporters/base.py`:
```python
from __future__ import annotations
from abc import ABC, abstractmethod
from ..sensors.base import Measurement


class BaseExporter(ABC):
    @abstractmethod
    def export(self, measurement: Measurement) -> None:
        ...

    def close(self) -> None:
        pass
```

- [ ] **Schritt 4: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_exporters.py -v
```

- [ ] **Schritt 5: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/exporters/base.py packages/rpi-agent/tests/test_exporters.py
git commit -m "feat(agent): add BaseExporter abstract class"
```

---

## Phase 3: rpi-agent — Sensoren

### Task 8: HX711-Sensor (Gewicht)

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/sensors/hx711.py`

- [ ] **Schritt 1: Test in `test_sensors.py` ergänzen**

```python
# ans Ende von tests/test_sensors.py anhängen:
import pytest
from unittest.mock import MagicMock, patch


def test_hx711_reads_weight(mocker: MagicMock) -> None:
    mock_hx = mocker.patch("honeypi_agent.sensors.hx711.HX711")
    mock_instance = mock_hx.return_value
    mock_instance.get_weight_mean.return_value = 15340.0

    from honeypi_agent.sensors.hx711 import HX711Sensor
    s = HX711Sensor({"type": "hx711", "name": "Stock", "data_pin": 5, "clock_pin": 6, "reference_unit": 21.0})
    m = s.read()

    assert "weight_kg" in m.values
    assert m.values["weight_kg"] == pytest.approx(15340.0 / 1000, abs=0.1)
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
uv run pytest tests/test_sensors.py::test_hx711_reads_weight -v
```

- [ ] **Schritt 3: `sensors/hx711.py` implementieren**

`packages/rpi-agent/honeypi_agent/sensors/hx711.py`:
```python
from __future__ import annotations
import time
from .base import BaseSensor, Measurement

try:
    from hx711 import HX711  # type: ignore[import-untyped]
except ImportError:
    HX711 = None  # type: ignore[assignment,misc]


class HX711Sensor(BaseSensor):
    def _configure(self, config: dict) -> None:
        if HX711 is None:
            raise RuntimeError("hx711 package not installed")
        self._hx = HX711(dout_pin=config["data_pin"], pd_sck_pin=config["clock_pin"])
        self._hx.set_scale_ratio(config.get("reference_unit", 1.0))
        self._samples: int = config.get("samples", 5)

    def read(self) -> Measurement:
        raw = self._hx.get_weight_mean(self._samples)
        return Measurement(
            name=self.name,
            values={"weight_kg": raw / 1000},
            timestamp=time.time(),
        )
```

- [ ] **Schritt 4: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_sensors.py -v
```

- [ ] **Schritt 5: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/sensors/hx711.py packages/rpi-agent/tests/test_sensors.py
git commit -m "feat(agent): add HX711 weight sensor"
```

---

### Task 9: DS18B20-Sensor (Temperatur)

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/sensors/ds18b20.py`

- [ ] **Schritt 1: Test in `test_sensors.py` ergänzen**

```python
def test_ds18b20_reads_temperature(mocker: MagicMock) -> None:
    mock_sensor_cls = mocker.patch("honeypi_agent.sensors.ds18b20.W1ThermSensor")
    mock_instance = mock_sensor_cls.return_value
    mock_instance.get_temperature.return_value = 36.5

    from honeypi_agent.sensors.ds18b20 import DS18B20Sensor
    s = DS18B20Sensor({"type": "ds18b20", "name": "BroodTemp"})
    m = s.read()

    assert "temperature_c" in m.values
    assert m.values["temperature_c"] == pytest.approx(36.5)
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
uv run pytest tests/test_sensors.py::test_ds18b20_reads_temperature -v
```

- [ ] **Schritt 3: `sensors/ds18b20.py` implementieren**

`packages/rpi-agent/honeypi_agent/sensors/ds18b20.py`:
```python
from __future__ import annotations
import time
from .base import BaseSensor, Measurement

try:
    from w1thermsensor import W1ThermSensor  # type: ignore[import-untyped]
except ImportError:
    W1ThermSensor = None  # type: ignore[assignment,misc]


class DS18B20Sensor(BaseSensor):
    def _configure(self, config: dict) -> None:
        if W1ThermSensor is None:
            raise RuntimeError("w1thermsensor package not installed")
        self._sensor = W1ThermSensor()

    def read(self) -> Measurement:
        temp = self._sensor.get_temperature()
        return Measurement(
            name=self.name,
            values={"temperature_c": temp},
            timestamp=time.time(),
        )
```

- [ ] **Schritt 4: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_sensors.py -v
```

- [ ] **Schritt 5: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/sensors/ds18b20.py packages/rpi-agent/tests/test_sensors.py
git commit -m "feat(agent): add DS18B20 temperature sensor"
```

---

### Task 10: BME280-Sensor (Temp/Feuchte/Druck)

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/sensors/bme280.py`

- [ ] **Schritt 1: Test in `test_sensors.py` ergänzen**

```python
def test_bme280_reads_all_values(mocker: MagicMock) -> None:
    mock_smbus = mocker.patch("honeypi_agent.sensors.bme280.smbus2")
    mock_bme = mocker.patch("honeypi_agent.sensors.bme280.bme280_module")
    mock_bme.sample.return_value = MagicMock(temperature=22.3, humidity=58.1, pressure=1013.2)

    from honeypi_agent.sensors.bme280 import BME280Sensor
    s = BME280Sensor({"type": "bme280", "name": "OutsideWeather"})
    m = s.read()

    assert "temperature_c" in m.values
    assert "humidity_pct" in m.values
    assert "pressure_hpa" in m.values
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
uv run pytest tests/test_sensors.py::test_bme280_reads_all_values -v
```

- [ ] **Schritt 3: `sensors/bme280.py` implementieren**

`packages/rpi-agent/honeypi_agent/sensors/bme280.py`:
```python
from __future__ import annotations
import time
from .base import BaseSensor, Measurement

try:
    import smbus2  # type: ignore[import-untyped]
    import bme280 as bme280_module  # type: ignore[import-untyped]
except ImportError:
    smbus2 = None  # type: ignore[assignment]
    bme280_module = None  # type: ignore[assignment]


class BME280Sensor(BaseSensor):
    def _configure(self, config: dict) -> None:
        if smbus2 is None or bme280_module is None:
            raise RuntimeError("smbus2 or RPi.bme280 package not installed")
        port = config.get("i2c_port", 1)
        self._address = config.get("i2c_address", 0x76)
        self._bus = smbus2.SMBus(port)
        self._calibration = bme280_module.load_calibration_params(self._bus, self._address)

    def read(self) -> Measurement:
        data = bme280_module.sample(self._bus, self._address, self._calibration)
        return Measurement(
            name=self.name,
            values={
                "temperature_c": data.temperature,
                "humidity_pct": data.humidity,
                "pressure_hpa": data.pressure,
            },
            timestamp=time.time(),
        )
```

- [ ] **Schritt 4: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_sensors.py -v
```

- [ ] **Schritt 5: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/sensors/bme280.py packages/rpi-agent/tests/test_sensors.py
git commit -m "feat(agent): add BME280 temperature/humidity/pressure sensor"
```

---

## Phase 4: rpi-agent — Exporter

### Task 11: Local SQLite Exporter

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/exporters/local.py`

- [ ] **Schritt 1: Test in `test_exporters.py` ergänzen**

```python
import time
from pathlib import Path
from honeypi_agent.exporters.local import LocalExporter
from honeypi_agent.sensors.base import Measurement


def test_local_exporter_stores_measurement(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    exp = LocalExporter({"enabled": True, "db_path": db})
    m = Measurement(name="Hive1", values={"weight_kg": 45.2, "temperature_c": 34.1}, timestamp=time.time())
    exp.export(m)
    exp.close()

    import sqlite3
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT sensor_name, key, value FROM measurements").fetchall()
    conn.close()

    assert len(rows) == 2
    keys = {r[1] for r in rows}
    assert "weight_kg" in keys
    assert "temperature_c" in keys
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
uv run pytest tests/test_exporters.py::test_local_exporter_stores_measurement -v
```

- [ ] **Schritt 3: `exporters/local.py` implementieren**

`packages/rpi-agent/honeypi_agent/exporters/local.py`:
```python
from __future__ import annotations
import sqlite3
from pathlib import Path
from .base import BaseExporter
from ..sensors.base import Measurement

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS measurements (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_name TEXT NOT NULL,
    key       TEXT NOT NULL,
    value     REAL NOT NULL,
    timestamp REAL NOT NULL
)
"""


class LocalExporter(BaseExporter):
    def __init__(self, config: dict) -> None:
        db_path = Path(config.get("db_path", "/var/lib/honeypi/data.db"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    def export(self, measurement: Measurement) -> None:
        rows = [
            (measurement.name, key, value, measurement.timestamp)
            for key, value in measurement.values.items()
        ]
        self._conn.executemany(
            "INSERT INTO measurements (sensor_name, key, value, timestamp) VALUES (?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Schritt 4: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_exporters.py -v
```

- [ ] **Schritt 5: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/exporters/local.py packages/rpi-agent/tests/test_exporters.py
git commit -m "feat(agent): add LocalExporter writing to SQLite"
```

---

### Task 12: ThingSpeak Exporter

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/exporters/thingspeak.py`

- [ ] **Schritt 1: Test in `test_exporters.py` ergänzen**

```python
import time
from unittest.mock import MagicMock, patch
from honeypi_agent.exporters.thingspeak import ThingSpeakExporter
from honeypi_agent.sensors.base import Measurement


def test_thingspeak_sends_mapped_fields() -> None:
    cfg = {
        "enabled": True,
        "api_key": "TESTKEY123",
        "field_mapping": {"weight_kg": "field1", "temperature_c": "field2"},
    }
    m = Measurement(name="Hive1", values={"weight_kg": 45.2, "temperature_c": 34.1}, timestamp=time.time())

    with patch("honeypi_agent.exporters.thingspeak.httpx.get") as mock_get:
        exp = ThingSpeakExporter(cfg)
        exp.export(m)
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        params = kwargs["params"]
        assert params["api_key"] == "TESTKEY123"
        assert params["field1"] == pytest.approx(45.2)
        assert params["field2"] == pytest.approx(34.1)
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
uv run pytest tests/test_exporters.py::test_thingspeak_sends_mapped_fields -v
```

- [ ] **Schritt 3: `exporters/thingspeak.py` implementieren**

`packages/rpi-agent/honeypi_agent/exporters/thingspeak.py`:
```python
from __future__ import annotations
import logging
import httpx
from .base import BaseExporter
from ..sensors.base import Measurement

logger = logging.getLogger(__name__)
_URL = "https://api.thingspeak.com/update"


class ThingSpeakExporter(BaseExporter):
    def __init__(self, config: dict) -> None:
        self._api_key: str = config["api_key"]
        self._field_mapping: dict[str, str] = config.get("field_mapping", {})

    def export(self, measurement: Measurement) -> None:
        params: dict[str, object] = {"api_key": self._api_key}
        for key, value in measurement.values.items():
            field = self._field_mapping.get(key)
            if field:
                params[field] = value
        if len(params) < 2:
            logger.warning("ThingSpeak: no fields mapped for sensor %s", measurement.name)
            return
        httpx.get(_URL, params=params, timeout=10)
```

- [ ] **Schritt 4: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_exporters.py -v
```

- [ ] **Schritt 5: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/exporters/thingspeak.py packages/rpi-agent/tests/test_exporters.py
git commit -m "feat(agent): add ThingSpeak exporter"
```

---

### Task 13: InfluxDB Exporter

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/exporters/influxdb.py`

- [ ] **Schritt 1: Test in `test_exporters.py` ergänzen**

```python
def test_influxdb_writes_point(mocker: MagicMock) -> None:
    import time
    mock_client_cls = mocker.patch("honeypi_agent.exporters.influxdb.InfluxDBClient")
    mock_client = mock_client_cls.return_value
    mock_write_api = mock_client.write_api.return_value

    from honeypi_agent.exporters.influxdb import InfluxDBExporter
    cfg = {"enabled": True, "url": "http://localhost:8086", "token": "tok", "org": "myorg", "bucket": "honeypi"}
    exp = InfluxDBExporter(cfg)
    m = Measurement(name="Hive1", values={"weight_kg": 45.2}, timestamp=time.time())
    exp.export(m)

    mock_write_api.write.assert_called_once()
    call_kwargs = mock_write_api.write.call_args.kwargs
    assert call_kwargs["bucket"] == "honeypi"
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
uv run pytest tests/test_exporters.py::test_influxdb_writes_point -v
```

- [ ] **Schritt 3: `exporters/influxdb.py` implementieren**

`packages/rpi-agent/honeypi_agent/exporters/influxdb.py`:
```python
from __future__ import annotations
from influxdb_client import InfluxDBClient, Point  # type: ignore[import-untyped]
from influxdb_client.client.write_api import SYNCHRONOUS  # type: ignore[import-untyped]
from .base import BaseExporter
from ..sensors.base import Measurement


class InfluxDBExporter(BaseExporter):
    def __init__(self, config: dict) -> None:
        self._client = InfluxDBClient(url=config["url"], token=config["token"], org=config["org"])
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
        self._bucket: str = config["bucket"]
        self._org: str = config["org"]

    def export(self, measurement: Measurement) -> None:
        point = Point(measurement.name)
        for key, value in measurement.values.items():
            point = point.field(key, value)
        self._write_api.write(bucket=self._bucket, org=self._org, record=point)

    def close(self) -> None:
        self._client.close()
```

- [ ] **Schritt 4: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_exporters.py -v
```

- [ ] **Schritt 5: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/exporters/influxdb.py packages/rpi-agent/tests/test_exporters.py
git commit -m "feat(agent): add InfluxDB v2 exporter"
```

---

### Task 14: MQTT Exporter

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/exporters/mqtt.py`

- [ ] **Schritt 1: Test in `test_exporters.py` ergänzen**

```python
def test_mqtt_publishes_json(mocker: MagicMock) -> None:
    import json, time
    mock_mqtt = mocker.patch("honeypi_agent.exporters.mqtt.mqtt")
    mock_client = mock_mqtt.Client.return_value

    from honeypi_agent.exporters.mqtt import MQTTExporter
    cfg = {"enabled": True, "broker": "localhost", "port": 1883, "topic": "honeypi"}
    exp = MQTTExporter(cfg)
    m = Measurement(name="Hive1", values={"weight_kg": 45.2}, timestamp=1234567890.0)
    exp.export(m)

    mock_client.publish.assert_called_once()
    topic, payload = mock_client.publish.call_args.args
    assert topic == "honeypi/Hive1"
    data = json.loads(payload)
    assert data["weight_kg"] == pytest.approx(45.2)
    assert data["sensor"] == "Hive1"
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
uv run pytest tests/test_exporters.py::test_mqtt_publishes_json -v
```

- [ ] **Schritt 3: `exporters/mqtt.py` implementieren**

`packages/rpi-agent/honeypi_agent/exporters/mqtt.py`:
```python
from __future__ import annotations
import json
import paho.mqtt.client as mqtt  # type: ignore[import-untyped]
from .base import BaseExporter
from ..sensors.base import Measurement


class MQTTExporter(BaseExporter):
    def __init__(self, config: dict) -> None:
        self._topic: str = config.get("topic", "honeypi")
        self._client = mqtt.Client()
        self._client.connect(config["broker"], config.get("port", 1883))
        self._client.loop_start()

    def export(self, measurement: Measurement) -> None:
        payload = json.dumps({"sensor": measurement.name, "timestamp": measurement.timestamp, **measurement.values})
        self._client.publish(f"{self._topic}/{measurement.name}", payload)

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
```

- [ ] **Schritt 4: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_exporters.py -v
```

- [ ] **Schritt 5: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/exporters/mqtt.py packages/rpi-agent/tests/test_exporters.py
git commit -m "feat(agent): add MQTT exporter"
```

---

### Task 15: Sensor- und Exporter-Factories

**Files:**
- Modify: `packages/rpi-agent/honeypi_agent/sensors/__init__.py`
- Modify: `packages/rpi-agent/honeypi_agent/exporters/__init__.py`

- [ ] **Schritt 1: Test in `test_sensors.py` ergänzen**

```python
def test_sensor_factory_creates_dummy() -> None:
    from honeypi_agent.sensors import create_sensor
    s = create_sensor({"type": "dummy", "name": "Test"})
    from honeypi_agent.sensors.dummy import DummySensor
    assert isinstance(s, DummySensor)


def test_sensor_factory_raises_on_unknown() -> None:
    from honeypi_agent.sensors import create_sensor
    with pytest.raises(ValueError, match="Unknown sensor type"):
        create_sensor({"type": "nonexistent", "name": "X"})
```

- [ ] **Schritt 2: Test in `test_exporters.py` ergänzen**

```python
def test_exporter_factory_creates_local(tmp_path: Path) -> None:
    from honeypi_agent.exporters import create_exporters
    cfg = {"local": {"enabled": True, "db_path": str(tmp_path / "db.sqlite")}}
    exporters = create_exporters(cfg)
    from honeypi_agent.exporters.local import LocalExporter
    assert len(exporters) == 1
    assert isinstance(exporters[0], LocalExporter)
    exporters[0].close()


def test_exporter_factory_skips_disabled() -> None:
    from honeypi_agent.exporters import create_exporters
    cfg = {"thingspeak": {"enabled": False, "api_key": ""}}
    exporters = create_exporters(cfg)
    assert exporters == []
```

- [ ] **Schritt 3: Tests laufen lassen — erwartet FAIL**

```bash
uv run pytest tests/ -v
```

- [ ] **Schritt 4: `sensors/__init__.py` implementieren**

`packages/rpi-agent/honeypi_agent/sensors/__init__.py`:
```python
from __future__ import annotations
from .base import BaseSensor
from .dummy import DummySensor
from .hx711 import HX711Sensor
from .ds18b20 import DS18B20Sensor
from .bme280 import BME280Sensor

_REGISTRY: dict[str, type[BaseSensor]] = {
    "dummy": DummySensor,
    "hx711": HX711Sensor,
    "ds18b20": DS18B20Sensor,
    "bme280": BME280Sensor,
}


def create_sensor(config: dict) -> BaseSensor:
    sensor_type = config["type"]
    if sensor_type not in _REGISTRY:
        raise ValueError(f"Unknown sensor type: {sensor_type!r}")
    return _REGISTRY[sensor_type](config)
```

- [ ] **Schritt 5: `exporters/__init__.py` implementieren**

`packages/rpi-agent/honeypi_agent/exporters/__init__.py`:
```python
from __future__ import annotations
from .base import BaseExporter
from .local import LocalExporter
from .thingspeak import ThingSpeakExporter
from .influxdb import InfluxDBExporter
from .mqtt import MQTTExporter

_REGISTRY: dict[str, type[BaseExporter]] = {
    "local": LocalExporter,
    "thingspeak": ThingSpeakExporter,
    "influxdb": InfluxDBExporter,
    "mqtt": MQTTExporter,
}


def create_exporters(config: dict[str, dict]) -> list[BaseExporter]:
    return [
        _REGISTRY[name](cfg)
        for name, cfg in config.items()
        if cfg.get("enabled", False) and name in _REGISTRY
    ]
```

- [ ] **Schritt 6: Alle Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/ -v
```

- [ ] **Schritt 7: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/sensors/__init__.py packages/rpi-agent/honeypi_agent/exporters/__init__.py packages/rpi-agent/tests/
git commit -m "feat(agent): add sensor and exporter factories"
```

---

## Phase 5: rpi-agent — Runner & Entry Point

### Task 16: MeasurementRunner

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/runner.py`

- [ ] **Schritt 1: Test in `test_runner.py` schreiben**

`packages/rpi-agent/tests/test_runner.py`:
```python
import time
from unittest.mock import MagicMock
from honeypi_agent.runner import MeasurementRunner
from honeypi_agent.sensors.base import Measurement
from honeypi_agent.sensors.dummy import DummySensor
from honeypi_agent.exporters.base import BaseExporter


class CapturingExporter(BaseExporter):
    def __init__(self) -> None:
        self.received: list[Measurement] = []

    def export(self, measurement: Measurement) -> None:
        self.received.append(measurement)


def test_run_once_calls_all_exporters() -> None:
    sensor = DummySensor({"type": "dummy", "name": "Test", "values": {"weight_kg": 10.0}})
    exp1 = CapturingExporter()
    exp2 = CapturingExporter()
    runner = MeasurementRunner(sensors=[sensor], exporters=[exp1, exp2], interval=60)
    runner.run_once()
    assert len(exp1.received) == 1
    assert len(exp2.received) == 1


def test_run_once_continues_after_sensor_error() -> None:
    bad_sensor = MagicMock()
    bad_sensor.name = "Bad"
    bad_sensor.read.side_effect = RuntimeError("hardware error")
    good_sensor = DummySensor({"type": "dummy", "name": "Good"})
    exp = CapturingExporter()
    runner = MeasurementRunner(sensors=[bad_sensor, good_sensor], exporters=[exp], interval=60)
    runner.run_once()
    assert len(exp.received) == 1
    assert exp.received[0].name == "Good"


def test_run_once_continues_after_exporter_error() -> None:
    sensor = DummySensor({"type": "dummy", "name": "Test"})
    bad_exp = MagicMock()
    bad_exp.export.side_effect = RuntimeError("network error")
    good_exp = CapturingExporter()
    runner = MeasurementRunner(sensors=[sensor], exporters=[bad_exp, good_exp], interval=60)
    runner.run_once()
    assert len(good_exp.received) == 1
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
uv run pytest tests/test_runner.py -v
```

- [ ] **Schritt 3: `runner.py` implementieren**

`packages/rpi-agent/honeypi_agent/runner.py`:
```python
from __future__ import annotations
import logging
import time
from .sensors.base import BaseSensor
from .exporters.base import BaseExporter

logger = logging.getLogger(__name__)


class MeasurementRunner:
    def __init__(self, sensors: list[BaseSensor], exporters: list[BaseExporter], interval: int) -> None:
        self._sensors = sensors
        self._exporters = exporters
        self._interval = interval
        self._running = False

    def run_once(self) -> None:
        for sensor in self._sensors:
            try:
                measurement = sensor.read()
            except Exception as exc:
                logger.error("Sensor %s failed: %s", sensor.name, exc)
                continue
            for exporter in self._exporters:
                try:
                    exporter.export(measurement)
                except Exception as exc:
                    logger.error("Exporter %s failed: %s", type(exporter).__name__, exc)

    def run(self) -> None:
        self._running = True
        while self._running:
            self.run_once()
            time.sleep(self._interval)

    def stop(self) -> None:
        self._running = False
```

- [ ] **Schritt 4: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/ -v
```

- [ ] **Schritt 5: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/runner.py packages/rpi-agent/tests/test_runner.py
git commit -m "feat(agent): add MeasurementRunner with error isolation"
```

---

### Task 17: main.py + systemd Service

**Files:**
- Create: `packages/rpi-agent/honeypi_agent/main.py`
- Create: `packages/rpi-agent/systemd/honeypi-agent.service`

- [ ] **Schritt 1: `main.py` schreiben**

`packages/rpi-agent/honeypi_agent/main.py`:
```python
from __future__ import annotations
import logging
import signal
import sys
from pathlib import Path
from .config import load_config
from .sensors import create_sensor
from .exporters import create_exporters
from .runner import MeasurementRunner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    cfg = load_config(Path("/etc/honeypi/honeypi.json"))
    sensors = [create_sensor(s) for s in cfg.sensors]
    exporters = create_exporters(cfg.exporters)

    if not sensors:
        logger.warning("No sensors configured — check /etc/honeypi/honeypi.json")

    runner = MeasurementRunner(sensors=sensors, exporters=exporters, interval=cfg.interval)

    def _shutdown(sig: int, frame: object) -> None:
        logger.info("Shutting down...")
        runner.stop()
        for exp in exporters:
            exp.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("HoneyPi Agent started. Interval: %ds, Sensors: %d, Exporters: %d",
                cfg.interval, len(sensors), len(exporters))
    runner.run()


if __name__ == "__main__":
    main()
```

- [ ] **Schritt 2: systemd Service-Datei schreiben**

`packages/rpi-agent/systemd/honeypi-agent.service`:
```ini
[Unit]
Description=HoneyPi Sensor Agent
After=network.target

[Service]
Type=simple
User=honeypi
WorkingDirectory=/opt/honeypi
ExecStart=/opt/honeypi/venv/bin/python -m honeypi_agent
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Schritt 3: Committen**

```bash
git add packages/rpi-agent/honeypi_agent/main.py packages/rpi-agent/systemd/
git commit -m "feat(agent): add main entry point and systemd service"
```

---

## Phase 6: Dashboard

### Task 18: DB-Reader + FastAPI App Skeleton

**Files:**
- Create: `packages/dashboard/honeypi_dashboard/db.py`
- Create: `packages/dashboard/honeypi_dashboard/main.py`

- [ ] **Schritt 1: Test schreiben**

`packages/dashboard/tests/test_api.py`:
```python
import sqlite3
import time
import pytest
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "data.db"
    conn = sqlite3.connect(str(p))
    conn.execute("""
        CREATE TABLE measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_name TEXT, key TEXT, value REAL, timestamp REAL
        )
    """)
    now = time.time()
    conn.executemany(
        "INSERT INTO measurements (sensor_name, key, value, timestamp) VALUES (?, ?, ?, ?)",
        [
            ("Hive1", "weight_kg", 45.2, now - 10),
            ("Hive1", "temperature_c", 34.1, now - 10),
        ],
    )
    conn.commit()
    conn.close()
    return p


@pytest.fixture
def client(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import honeypi_dashboard.db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    from honeypi_dashboard.main import app
    return TestClient(app)


def test_get_latest_returns_values(client: TestClient) -> None:
    resp = client.get("/api/data/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    keys = {row["key"] for row in data}
    assert "weight_kg" in keys


def test_get_history_returns_rows(client: TestClient) -> None:
    resp = client.get("/api/data/history?hours=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 2
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
cd packages/dashboard
uv run pytest tests/test_api.py -v
```

- [ ] **Schritt 3: `db.py` implementieren**

`packages/dashboard/honeypi_dashboard/db.py`:
```python
from __future__ import annotations
import sqlite3
import time
from pathlib import Path

DB_PATH = Path("/var/lib/honeypi/data.db")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def get_latest() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT sensor_name, key, value, MAX(timestamp) as timestamp "
            "FROM measurements GROUP BY sensor_name, key"
        ).fetchall()
    return [dict(r) for r in rows]


def get_measurements(sensor: str | None = None, hours: int = 24) -> list[dict]:
    since = time.time() - hours * 3600
    sql = "SELECT sensor_name, key, value, timestamp FROM measurements WHERE timestamp > ?"
    params: list[object] = [since]
    if sensor:
        sql += " AND sensor_name = ?"
        params.append(sensor)
    sql += " ORDER BY timestamp ASC"
    with _conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Schritt 4: `main.py` implementieren**

`packages/dashboard/honeypi_dashboard/main.py`:
```python
from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .api import data as data_router, config as config_router

app = FastAPI(title="HoneyPi Dashboard")

_STATIC = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
app.include_router(data_router.router, prefix="/api")
app.include_router(config_router.router, prefix="/api")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(str(_STATIC / "index.html"))


@app.get("/config-ui", include_in_schema=False)
def config_page() -> FileResponse:
    return FileResponse(str(_STATIC / "config.html"))


def main() -> None:
    import uvicorn
    uvicorn.run("honeypi_dashboard.main:app", host="0.0.0.0", port=80, reload=False)
```

- [ ] **Schritt 5: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_api.py -v
```

- [ ] **Schritt 6: Committen**

```bash
git add packages/dashboard/honeypi_dashboard/db.py packages/dashboard/honeypi_dashboard/main.py packages/dashboard/tests/test_api.py
git commit -m "feat(dashboard): add FastAPI app skeleton and SQLite DB reader"
```

---

### Task 19: Data API Endpoints

**Files:**
- Create: `packages/dashboard/honeypi_dashboard/api/data.py`

- [ ] **Schritt 1: `api/data.py` implementieren**

`packages/dashboard/honeypi_dashboard/api/data.py`:
```python
from __future__ import annotations
from fastapi import APIRouter, Query
from .. import db

router = APIRouter()


@router.get("/data/latest")
def latest() -> list[dict]:
    return db.get_latest()


@router.get("/data/history")
def history(
    sensor: str | None = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
) -> list[dict]:
    return db.get_measurements(sensor=sensor, hours=hours)
```

- [ ] **Schritt 2: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_api.py -v
```

- [ ] **Schritt 3: Committen**

```bash
git add packages/dashboard/honeypi_dashboard/api/data.py
git commit -m "feat(dashboard): add /api/data endpoints"
```

---

### Task 20: Config API Endpoints

**Files:**
- Create: `packages/dashboard/honeypi_dashboard/api/config.py`

- [ ] **Schritt 1: Test in `test_api.py` ergänzen**

```python
import json


def test_get_config_returns_json(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import honeypi_dashboard.api.config as cfg_module
    cfg_file = tmp_path / "honeypi.json"
    cfg_file.write_text(json.dumps({"interval": 300, "sensors": [], "exporters": {}}))
    monkeypatch.setattr(cfg_module, "CONFIG_PATH", cfg_file)
    resp = client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json()["interval"] == 300


def test_post_config_writes_file(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import honeypi_dashboard.api.config as cfg_module
    cfg_file = tmp_path / "honeypi.json"
    cfg_file.write_text("{}")
    monkeypatch.setattr(cfg_module, "CONFIG_PATH", cfg_file)
    monkeypatch.setattr(cfg_module, "_restart_agent", lambda: None)
    resp = client.post("/api/config", json={"interval": 120, "sensors": [], "exporters": {}})
    assert resp.status_code == 200
    assert json.loads(cfg_file.read_text())["interval"] == 120
```

- [ ] **Schritt 2: Test laufen lassen — erwartet FAIL**

```bash
uv run pytest tests/test_api.py -v
```

- [ ] **Schritt 3: `api/config.py` implementieren**

`packages/dashboard/honeypi_dashboard/api/config.py`:
```python
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
```

- [ ] **Schritt 4: Tests laufen lassen — erwartet PASS**

```bash
uv run pytest tests/test_api.py -v
```

- [ ] **Schritt 5: Committen**

```bash
git add packages/dashboard/honeypi_dashboard/api/config.py packages/dashboard/tests/test_api.py
git commit -m "feat(dashboard): add /api/config and /api/control endpoints"
```

---

### Task 21: systemd Service + Dashboard Frontend

**Files:**
- Create: `packages/dashboard/systemd/honeypi-dashboard.service`
- Create: `packages/dashboard/static/style.css`
- Create: `packages/dashboard/static/index.html`
- Create: `packages/dashboard/static/config.html`
- Create: `packages/dashboard/static/app.js`

- [ ] **Schritt 1: systemd Service schreiben**

`packages/dashboard/systemd/honeypi-dashboard.service`:
```ini
[Unit]
Description=HoneyPi Dashboard
After=network.target

[Service]
Type=simple
User=honeypi
ExecStart=/opt/honeypi/venv/bin/uvicorn honeypi_dashboard.main:app --host 0.0.0.0 --port 80
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Schritt 2: `style.css` schreiben**

`packages/dashboard/static/style.css`:
```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #f5f5f0; color: #1a1a1a; }
header { background: #f5a623; color: white; padding: 1rem 1.5rem; display: flex; justify-content: space-between; align-items: center; }
header h1 { font-size: 1.25rem; font-weight: 700; }
nav a { color: white; text-decoration: none; margin-left: 1.5rem; font-size: 0.9rem; opacity: 0.9; }
nav a:hover { opacity: 1; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1rem; padding: 1.5rem; }
.card { background: white; border-radius: 12px; padding: 1.25rem; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
.card .label { font-size: 0.75rem; color: #666; text-transform: uppercase; letter-spacing: 0.05em; }
.card .value { font-size: 2rem; font-weight: 700; margin-top: 0.25rem; color: #f5a623; }
.card .unit { font-size: 0.85rem; color: #888; }
.card .sensor { font-size: 0.75rem; color: #aaa; margin-top: 0.5rem; }
.chart-section { padding: 0 1.5rem 1.5rem; }
.chart-section h2 { font-size: 1rem; margin-bottom: 0.75rem; color: #444; }
canvas { background: white; border-radius: 12px; padding: 1rem; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
form .field { margin-bottom: 1rem; }
form label { display: block; font-size: 0.85rem; color: #444; margin-bottom: 0.25rem; }
form input, form select { width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 6px; font-size: 0.95rem; }
form button { background: #f5a623; color: white; border: none; padding: 0.6rem 1.5rem; border-radius: 6px; cursor: pointer; font-size: 0.95rem; }
form button:hover { background: #e0951f; }
.container { max-width: 900px; margin: 0 auto; padding: 1.5rem; }
```

- [ ] **Schritt 3: `index.html` schreiben**

`packages/dashboard/static/index.html`:
```html
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HoneyPi Dashboard</title>
  <link rel="stylesheet" href="/static/style.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
</head>
<body>
  <header>
    <h1>🍯 HoneyPi</h1>
    <nav>
      <a href="/">Dashboard</a>
      <a href="/config-ui">Einstellungen</a>
    </nav>
  </header>
  <div id="cards" class="cards"></div>
  <div class="chart-section">
    <h2>Verlauf (24h)</h2>
    <canvas id="chart" height="80"></canvas>
  </div>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Schritt 4: `config.html` schreiben**

`packages/dashboard/static/config.html`:
```html
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HoneyPi Einstellungen</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header>
    <h1>🍯 HoneyPi</h1>
    <nav>
      <a href="/">Dashboard</a>
      <a href="/config-ui">Einstellungen</a>
    </nav>
  </header>
  <div class="container">
    <h2 style="margin-bottom:1rem">Konfiguration</h2>
    <form id="cfg-form">
      <div class="field">
        <label>Messintervall (Sekunden)</label>
        <input type="number" id="interval" min="30" max="3600">
      </div>
      <h3 style="margin:1rem 0 0.5rem">Exporters</h3>
      <div class="field">
        <label><input type="checkbox" id="ts-enabled"> ThingSpeak aktiviert</label>
        <input type="text" id="ts-key" placeholder="API Key" style="margin-top:0.5rem">
      </div>
      <div class="field">
        <label><input type="checkbox" id="idb-enabled"> InfluxDB aktiviert</label>
        <input type="text" id="idb-url" placeholder="URL (z.B. http://server:8086)" style="margin-top:0.5rem">
        <input type="text" id="idb-token" placeholder="Token" style="margin-top:0.25rem">
        <input type="text" id="idb-org" placeholder="Organisation" style="margin-top:0.25rem">
        <input type="text" id="idb-bucket" placeholder="Bucket" style="margin-top:0.25rem">
      </div>
      <div class="field">
        <label><input type="checkbox" id="mqtt-enabled"> MQTT aktiviert</label>
        <input type="text" id="mqtt-broker" placeholder="Broker IP/Hostname" style="margin-top:0.5rem">
        <input type="text" id="mqtt-topic" placeholder="Topic (z.B. honeypi)" style="margin-top:0.25rem">
      </div>
      <button type="submit">Speichern & Neustart</button>
    </form>
    <div style="margin-top:2rem">
      <h3 style="margin-bottom:0.5rem">Agent-Steuerung</h3>
      <button onclick="control('start')">Start</button>
      <button onclick="control('stop')" style="margin-left:0.5rem;background:#888">Stop</button>
      <button onclick="control('restart')" style="margin-left:0.5rem;background:#e07b00">Neustart</button>
    </div>
    <p id="status" style="margin-top:1rem;color:#666"></p>
  </div>
  <script>
    async function loadConfig() {
      const cfg = await fetch('/api/config').then(r => r.json());
      document.getElementById('interval').value = cfg.interval ?? 300;
      const exp = cfg.exporters ?? {};
      document.getElementById('ts-enabled').checked = exp.thingspeak?.enabled ?? false;
      document.getElementById('ts-key').value = exp.thingspeak?.api_key ?? '';
      document.getElementById('idb-enabled').checked = exp.influxdb?.enabled ?? false;
      document.getElementById('idb-url').value = exp.influxdb?.url ?? '';
      document.getElementById('idb-token').value = exp.influxdb?.token ?? '';
      document.getElementById('idb-org').value = exp.influxdb?.org ?? '';
      document.getElementById('idb-bucket').value = exp.influxdb?.bucket ?? 'honeypi';
      document.getElementById('mqtt-enabled').checked = exp.mqtt?.enabled ?? false;
      document.getElementById('mqtt-broker').value = exp.mqtt?.broker ?? '';
      document.getElementById('mqtt-topic').value = exp.mqtt?.topic ?? 'honeypi';
    }

    document.getElementById('cfg-form').addEventListener('submit', async e => {
      e.preventDefault();
      const cfg = {
        interval: parseInt(document.getElementById('interval').value),
        sensors: [],
        exporters: {
          local: { enabled: true },
          thingspeak: { enabled: document.getElementById('ts-enabled').checked, api_key: document.getElementById('ts-key').value },
          influxdb: { enabled: document.getElementById('idb-enabled').checked, url: document.getElementById('idb-url').value, token: document.getElementById('idb-token').value, org: document.getElementById('idb-org').value, bucket: document.getElementById('idb-bucket').value },
          mqtt: { enabled: document.getElementById('mqtt-enabled').checked, broker: document.getElementById('mqtt-broker').value, topic: document.getElementById('mqtt-topic').value },
        }
      };
      await fetch('/api/config', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(cfg) });
      document.getElementById('status').textContent = 'Gespeichert und Agent neugestartet.';
    });

    async function control(action) {
      await fetch(`/api/control/${action}`, { method: 'POST' });
      document.getElementById('status').textContent = `Agent ${action} ausgeführt.`;
    }

    loadConfig();
  </script>
</body>
</html>
```

- [ ] **Schritt 5: `app.js` schreiben**

`packages/dashboard/static/app.js`:
```javascript
const COLORS = ['#f5a623','#4a90d9','#7ed321','#9b59b6','#e74c3c','#1abc9c'];

async function loadLatest() {
  const data = await fetch('/api/data/latest').then(r => r.json());
  const cards = document.getElementById('cards');
  cards.innerHTML = '';
  data.forEach(row => {
    const div = document.createElement('div');
    div.className = 'card';
    const val = parseFloat(row.value).toFixed(2);
    div.innerHTML = `
      <div class="label">${row.key.replace(/_/g,' ')}</div>
      <div class="value">${val}</div>
      <div class="sensor">${row.sensor_name}</div>
    `;
    cards.appendChild(div);
  });
}

async function loadChart() {
  const data = await fetch('/api/data/history?hours=24').then(r => r.json());
  const byKey = {};
  data.forEach(row => {
    const k = `${row.sensor_name}/${row.key}`;
    if (!byKey[k]) byKey[k] = { labels: [], values: [] };
    byKey[k].labels.push(new Date(row.timestamp * 1000).toLocaleTimeString());
    byKey[k].values.push(row.value);
  });

  const keys = Object.keys(byKey);
  new Chart(document.getElementById('chart'), {
    type: 'line',
    data: {
      labels: byKey[keys[0]]?.labels ?? [],
      datasets: keys.map((k, i) => ({
        label: k.replace('/', ' – '),
        data: byKey[k].values,
        borderColor: COLORS[i % COLORS.length],
        tension: 0.3,
        pointRadius: 0,
      })),
    },
    options: {
      responsive: true,
      plugins: { legend: { position: 'bottom' } },
      scales: { y: { beginAtZero: false } },
    },
  });
}

loadLatest();
loadChart();
setInterval(loadLatest, 30000);
```

- [ ] **Schritt 6: Committen**

```bash
git add packages/dashboard/
git commit -m "feat(dashboard): add frontend HTML/CSS/JS with Chart.js"
```

---

## Phase 7: Installer

### Task 22: install.sh

**Files:**
- Create: `packages/installer/install.sh`

- [ ] **Schritt 1: `install.sh` schreiben**

`packages/installer/install.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/Zenutrix/honeypi"
INSTALL_DIR="/opt/honeypi"
DATA_DIR="/var/lib/honeypi"
CFG_DIR="/etc/honeypi"

echo "==> HoneyPi Installer"
echo "==> Updating system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq git python3 python3-pip avahi-daemon

echo "==> Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "==> Cloning repository..."
if [ -d "$INSTALL_DIR" ]; then
  cd "$INSTALL_DIR" && sudo git pull
else
  sudo git clone "$REPO" "$INSTALL_DIR"
fi

echo "==> Creating honeypi user..."
id -u honeypi &>/dev/null || sudo useradd --system --no-create-home honeypi

echo "==> Setting up Python environment..."
cd "$INSTALL_DIR"
sudo uv venv /opt/honeypi/venv
sudo uv pip install --python /opt/honeypi/venv/bin/python \
  packages/rpi-agent packages/dashboard

echo "==> Creating directories..."
sudo mkdir -p "$DATA_DIR" "$CFG_DIR"
sudo chown honeypi:honeypi "$DATA_DIR"

echo "==> Writing default config..."
if [ ! -f "$CFG_DIR/honeypi.json" ]; then
  sudo tee "$CFG_DIR/honeypi.json" > /dev/null <<'HONEYPI_JSON'
{
  "interval": 300,
  "sensors": [
    {"type": "dummy", "name": "Demo", "values": {"weight_kg": 10.0, "temperature_c": 20.0}}
  ],
  "exporters": {
    "local": {"enabled": true, "db_path": "/var/lib/honeypi/data.db"}
  }
}
HONEYPI_JSON
fi

echo "==> Installing systemd services..."
sudo cp "$INSTALL_DIR/packages/rpi-agent/systemd/honeypi-agent.service" /etc/systemd/system/
sudo cp "$INSTALL_DIR/packages/dashboard/systemd/honeypi-dashboard.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now honeypi-agent honeypi-dashboard

echo ""
echo "✓ HoneyPi installed successfully!"
echo "  Dashboard: http://honeypi.local"
echo "  Config:    $CFG_DIR/honeypi.json"
echo "  Logs:      journalctl -u honeypi-agent -f"
```

- [ ] **Schritt 2: Ausführbar machen und committen**

```bash
chmod +x packages/installer/install.sh
git add packages/installer/install.sh
git commit -m "feat(installer): add one-command install script"
```

---

## Phase 8: CI/CD

### Task 23: GitHub Actions

**Files:**
- Create: `.github/workflows/test.yml`
- Create: `.github/workflows/lint.yml`

- [ ] **Schritt 1: `test.yml` schreiben**

`.github/workflows/test.yml`:
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Run rpi-agent tests
        working-directory: packages/rpi-agent
        run: |
          uv sync
          uv run pytest tests/ -v

  test-dashboard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Run dashboard tests
        working-directory: packages/dashboard
        run: |
          uv sync
          uv run pytest tests/ -v
```

- [ ] **Schritt 2: `lint.yml` schreiben**

`.github/workflows/lint.yml`:
```yaml
name: Lint

on: [push, pull_request]

jobs:
  ruff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Lint rpi-agent
        working-directory: packages/rpi-agent
        run: |
          uv sync
          uv run ruff check honeypi_agent/
      - name: Lint dashboard
        working-directory: packages/dashboard
        run: |
          uv sync
          uv run ruff check honeypi_dashboard/
```

- [ ] **Schritt 3: Committen**

```bash
git add .github/
git commit -m "ci: add GitHub Actions for tests and linting"
```

---

## Abschlussprüfung

- [ ] Alle Tests laufen lokal durch:
  ```bash
  cd packages/rpi-agent && uv run pytest tests/ -v
  cd packages/dashboard && uv run pytest tests/ -v
  ```
- [ ] Ruff meldet keine Fehler:
  ```bash
  cd packages/rpi-agent && uv run ruff check honeypi_agent/
  cd packages/dashboard && uv run ruff check honeypi_dashboard/
  ```
- [ ] GitHub repo als Fork von `Honey-Pi` auf `https://github.com/Zenutrix/honeypi` erstellt
- [ ] Push zu GitHub: `git remote add origin https://github.com/Zenutrix/honeypi.git && git push -u origin main`
- [ ] CI/CD auf GitHub grün
