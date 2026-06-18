from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class HiveConfig(BaseModel):
    id: str
    name: str
    color: str = "#f59e0b"


class MaintenanceSwitchConfig(BaseModel):
    enabled: bool = False
    gpio_pin: int = 17
    hotspot_password: str = "hanipi123"


class DisplayConfig(BaseModel):
    enabled: bool = False
    type: str = "none"  # "none" | "hdmi" | "tft" | "eink"
    tft_device: str = "/dev/fb1"
    brightness: int = 80
    rotation: int = 0  # 0 | 90 | 180 | 270
    page_interval: int = 8
    # E-Ink spezifisch
    eink_model: str = "2.7"       # "2.13" | "2.7" | "4.2" | "7.5"
    eink_spi_bus: int = 0
    eink_spi_cs: int = 0          # 0=GPIO8, 1=GPIO7
    eink_dc_pin: int = 25
    eink_rst_pin: int = 27
    eink_busy_pin: int = 22
    button_gpio: int = 18      # 0 = deaktiviert


class HaniPiConfig(BaseModel):
    # Keep old field for backward compat
    interval: int = 300
    # New separate intervals (if set, override interval)
    measure_interval: int = 0  # 0 = use interval
    export_interval: int = 0  # 0 = use interval
    # Limits
    db_max_size_mb: int = 500
    db_retention_days: int = 90
    # New feature configs
    hives: list[HiveConfig] = Field(default_factory=list)
    maintenance_switch: MaintenanceSwitchConfig = Field(
        default_factory=MaintenanceSwitchConfig
    )
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    # Existing
    sensors: list[dict[str, Any]] = Field(default_factory=list)
    exporters: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @property
    def effective_measure_interval(self) -> int:
        return self.measure_interval if self.measure_interval > 0 else self.interval

    @property
    def effective_export_interval(self) -> int:
        return self.export_interval if self.export_interval > 0 else self.interval


def load_config(path: Path = Path("/etc/hanipi/hanipi.json")) -> HaniPiConfig:
    if not path.exists():
        return HaniPiConfig()
    return HaniPiConfig.model_validate(json.loads(path.read_text()))
