from __future__ import annotations
import json
from pathlib import Path
from pydantic import BaseModel, Field


class HaniPiConfig(BaseModel):
    interval: int = 300
    sensors: list[dict] = Field(default_factory=list)
    exporters: dict[str, dict] = Field(default_factory=dict)


def load_config(path: Path = Path("/etc/hanipi/hanipi.json")) -> HaniPiConfig:
    if not path.exists():
        return HaniPiConfig()
    return HaniPiConfig.model_validate(json.loads(path.read_text()))
