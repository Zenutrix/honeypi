from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


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
