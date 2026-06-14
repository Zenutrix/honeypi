from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class DisplayPage:
    hive_name: str
    timestamp: float
    values: dict[str, float]
    hive_color: str = "#f59e0b"
    battery_voltage: float | None = None
    connected: bool = True


class BaseDisplay(ABC):
    @abstractmethod
    def show_page(self, page: DisplayPage) -> None: ...

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
