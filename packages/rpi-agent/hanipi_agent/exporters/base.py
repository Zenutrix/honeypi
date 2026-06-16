from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..sensors.base import Measurement


class BaseExporter(ABC):
    realtime: bool = (
        False  # if True, called on every measure cycle; if False, only on export cycle
    )

    def __init__(self, config: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def export(self, measurement: Measurement) -> None: ...

    def close(self) -> None:
        pass
