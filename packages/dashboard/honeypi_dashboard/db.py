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
