from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

import hanipi_dashboard.db as db_module


def _make_db(path: Path, rows: list[tuple]) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_name TEXT, key TEXT, value REAL, timestamp REAL, hive_id TEXT
        )
    """)
    conn.executemany(
        "INSERT INTO measurements (sensor_name, key, value, timestamp, hive_id) "
        "VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()


def _count(path: Path) -> int:
    conn = sqlite3.connect(str(path))
    n = conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
    conn.close()
    return n


# ── get_sensor_keys ──────────────────────────────────────────────────────────


def test_get_sensor_keys_returns_dotted_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "data.db"
    now = time.time()
    _make_db(
        db,
        [
            ("Waage", "weight_kg", 42.0, now, None),
            ("Waage", "temperature_c", 35.0, now, None),
            ("Aussen", "humidity_pct", 60.0, now, None),
        ],
    )
    monkeypatch.setattr(db_module, "DB_PATH", db)

    keys = db_module.get_sensor_keys()
    assert "Waage.weight_kg" in keys
    assert "Waage.temperature_c" in keys
    assert "Aussen.humidity_pct" in keys


def test_get_sensor_keys_deduplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "data.db"
    now = time.time()
    _make_db(
        db,
        [
            ("Waage", "weight_kg", 42.0, now - 10, None),
            ("Waage", "weight_kg", 43.0, now, None),
        ],
    )
    monkeypatch.setattr(db_module, "DB_PATH", db)

    keys = db_module.get_sensor_keys()
    assert keys.count("Waage.weight_kg") == 1


# ── cleanup_db: retention ────────────────────────────────────────────────────


def test_cleanup_db_retention_deletes_old_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "data.db"
    now = time.time()
    old = now - 100 * 86400  # 100 days ago
    _make_db(
        db,
        [
            ("S", "v", 1.0, old, None),
            ("S", "v", 2.0, old, None),
            ("S", "v", 3.0, now, None),
        ],
    )
    monkeypatch.setattr(db_module, "DB_PATH", db)

    db_module.cleanup_db(retention_days=30)

    assert _count(db) == 1  # only the recent row survives


def test_cleanup_db_retention_zero_keeps_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "data.db"
    now = time.time()
    old = now - 200 * 86400
    _make_db(
        db,
        [
            ("S", "v", 1.0, old, None),
            ("S", "v", 2.0, now, None),
        ],
    )
    monkeypatch.setattr(db_module, "DB_PATH", db)

    db_module.cleanup_db(retention_days=0)

    assert _count(db) == 2


# ── cleanup_db: size limit ───────────────────────────────────────────────────


def test_cleanup_db_size_deletes_oldest_10pct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "data.db"
    now = time.time()
    rows = [("S", "v", float(i), now - (100 - i), None) for i in range(100)]
    _make_db(db, rows)
    monkeypatch.setattr(db_module, "DB_PATH", db)

    # Pass max_size_mb=0 so size check doesn't trigger, but test the logic directly
    # by patching os.path.getsize to simulate an over-limit DB
    import os

    original_getsize = os.path.getsize

    call_count = [0]

    def mock_getsize(path):
        call_count[0] += 1
        if call_count[0] == 1:
            return 600 * 1024 * 1024  # 600 MB — over limit
        return original_getsize(path)

    monkeypatch.setattr(os.path, "getsize", mock_getsize)

    db_module.cleanup_db(max_size_mb=500)

    remaining = _count(db)
    assert remaining == 90  # 10% of 100 deleted


# ── cleanup_db: noop when file missing ───────────────────────────────────────


def test_cleanup_db_noop_when_no_db_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "missing.db")
    db_module.cleanup_db(retention_days=30, max_size_mb=100)  # Should not raise


# ── get_db_stats ─────────────────────────────────────────────────────────────


def test_get_db_stats_returns_expected_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "data.db"
    now = time.time()
    _make_db(
        db,
        [
            ("S", "v", 1.0, now - 100, None),
            ("S", "v", 2.0, now, None),
        ],
    )
    monkeypatch.setattr(db_module, "DB_PATH", db)

    stats = db_module.get_db_stats()
    assert stats["row_count"] == 2
    assert stats["size_mb"] >= 0
    assert stats["oldest_entry"] == pytest.approx(now - 100, abs=1)
    assert stats["newest_entry"] == pytest.approx(now, abs=1)


# ── hive_id filter in get_latest ─────────────────────────────────────────────


def test_get_latest_filters_by_hive_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "data.db"
    now = time.time()
    _make_db(
        db,
        [
            ("Waage", "weight_kg", 42.0, now, "hive-a"),
            ("Aussen", "temperature_c", 30.0, now, "hive-b"),
        ],
    )
    monkeypatch.setattr(db_module, "DB_PATH", db)

    rows = db_module.get_latest(hive_id="hive-a")
    assert len(rows) == 1
    assert rows[0]["sensor_name"] == "Waage"


# ── _ensure_hive_id_column: idempotent migration ─────────────────────────────


def test_ensure_hive_id_column_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "migrate.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE measurements "
        "(id INTEGER, sensor_name TEXT, key TEXT, value REAL, timestamp REAL)"
    )
    conn.commit()

    db_module._ensure_hive_id_column(conn)
    db_module._ensure_hive_id_column(conn)  # Second call must not raise

    cols = {
        row[1] for row in conn.execute("PRAGMA table_info(measurements)").fetchall()
    }
    assert "hive_id" in cols
    conn.close()
