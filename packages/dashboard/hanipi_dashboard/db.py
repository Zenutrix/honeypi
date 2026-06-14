from __future__ import annotations
import os
import sqlite3
import time
from pathlib import Path

DB_PATH = Path("/var/lib/hanipi/data.db")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def get_latest(hive_id: str | None = None) -> list[dict]:
    sql = (
        "SELECT sensor_name, key, value, hive_id, MAX(timestamp) as timestamp "
        "FROM measurements"
    )
    params: list[object] = []
    if hive_id is not None:
        sql += " WHERE hive_id = ?"
        params.append(hive_id)
    sql += " GROUP BY sensor_name, key"
    with _conn() as conn:
        _ensure_hive_id_column(conn)
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_measurements(
    sensor: str | None = None,
    hours: int = 24,
    hive_id: str | None = None,
) -> list[dict]:
    since = time.time() - hours * 3600
    sql = "SELECT sensor_name, key, value, timestamp, hive_id FROM measurements WHERE timestamp > ?"
    params: list[object] = [since]
    if sensor:
        sql += " AND sensor_name = ?"
        params.append(sensor)
    if hive_id is not None:
        sql += " AND hive_id = ?"
        params.append(hive_id)
    sql += " ORDER BY timestamp ASC"
    with _conn() as conn:
        _ensure_hive_id_column(conn)
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_db_stats() -> dict:
    size_mb = 0.0
    if DB_PATH.exists():
        size_mb = round(os.path.getsize(DB_PATH) / (1024 * 1024), 3)
    with _conn() as conn:
        _ensure_hive_id_column(conn)
        row_count = conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
        oldest = conn.execute("SELECT MIN(timestamp) FROM measurements").fetchone()[0]
        newest = conn.execute("SELECT MAX(timestamp) FROM measurements").fetchone()[0]
    return {
        "size_mb": size_mb,
        "row_count": row_count,
        "oldest_entry": oldest,
        "newest_entry": newest,
    }


def get_sensor_keys() -> list[str]:
    """Return all sensor_name.key combinations present in DB (for ThingSpeak mapping UI)."""
    with _conn() as conn:
        _ensure_hive_id_column(conn)
        rows = conn.execute(
            "SELECT DISTINCT sensor_name, key FROM measurements ORDER BY sensor_name, key"
        ).fetchall()
    return [f"{r[0]}.{r[1]}" for r in rows]


def cleanup_db(max_size_mb: int = 0, retention_days: int = 0) -> None:
    """Delete old rows to stay within size/retention limits, then VACUUM."""
    if not DB_PATH.exists():
        return
    with _conn() as conn:
        _ensure_hive_id_column(conn)

        if retention_days > 0:
            cutoff = time.time() - retention_days * 86400
            conn.execute("DELETE FROM measurements WHERE timestamp < ?", (cutoff,))
            conn.commit()

        if max_size_mb > 0:
            size_bytes = os.path.getsize(DB_PATH)
            limit_bytes = max_size_mb * 1024 * 1024
            if size_bytes > limit_bytes:
                total = conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
                delete_count = max(1, total // 10)
                conn.execute(
                    "DELETE FROM measurements WHERE rowid IN "
                    "(SELECT rowid FROM measurements ORDER BY timestamp ASC LIMIT ?)",
                    (delete_count,),
                )
                conn.commit()

        conn.execute("VACUUM")


def _ensure_hive_id_column(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(measurements)").fetchall()}
    if "hive_id" not in cols:
        conn.execute("ALTER TABLE measurements ADD COLUMN hive_id TEXT")
        conn.commit()
