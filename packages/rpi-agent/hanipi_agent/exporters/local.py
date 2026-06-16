from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..sensors.base import Measurement
from .base import BaseExporter

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS measurements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_name TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       REAL NOT NULL,
    timestamp   REAL NOT NULL,
    hive_id     TEXT
)
"""


class LocalExporter(BaseExporter):
    realtime: bool = True

    def __init__(self, config: dict[str, Any]) -> None:
        db_path = Path(config.get("db_path", "/var/lib/hanipi/data.db"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()
        # Idempotent migration: add hive_id column if missing
        cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(measurements)").fetchall()
        }
        if "hive_id" not in cols:
            self._conn.execute("ALTER TABLE measurements ADD COLUMN hive_id TEXT")
            self._conn.commit()

    def export(self, measurement: Measurement) -> None:
        rows = [
            (measurement.name, key, value, measurement.timestamp, measurement.hive_id)
            for key, value in measurement.values.items()
        ]
        self._conn.executemany(
            "INSERT INTO measurements (sensor_name, key, value, timestamp, hive_id) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
