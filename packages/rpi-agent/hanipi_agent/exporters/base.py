from __future__ import annotations
from abc import ABC, abstractmethod
from ..sensors.base import Measurement


class BaseExporter(ABC):
    @abstractmethod
    def export(self, measurement: Measurement) -> None:
        ...

    def close(self) -> None:
        pass
