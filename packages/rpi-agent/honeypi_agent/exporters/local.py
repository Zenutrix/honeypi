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
