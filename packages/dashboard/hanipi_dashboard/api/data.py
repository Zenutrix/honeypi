from __future__ import annotations

import csv
import io
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from .. import db

router = APIRouter()


@router.get("/data/latest")
def latest(hive_id: str | None = Query(default=None)) -> list[dict[str, Any]]:
    return db.get_latest(hive_id=hive_id)


@router.get("/data/history")
def history(
    sensor: str | None = Query(default=None),
    hours: int = Query(default=24, ge=1, le=8760),
    from_ts: float | None = Query(default=None),
    to_ts: float | None = Query(default=None),
    hive_id: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    if from_ts is not None and to_ts is not None:
        return db.get_measurements_range(
            from_ts=from_ts, to_ts=to_ts, sensor=sensor, hive_id=hive_id
        )
    return db.get_measurements(sensor=sensor, hours=hours, hive_id=hive_id)


@router.get("/data/weight-trend")
def weight_trend(
    hive_id: str | None = Query(default=None),
    target_hour: int = Query(default=6, ge=0, le=23),
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    points = db.get_morning_weights(hive_id=hive_id, target_hour=target_hour, days=days)

    delta_1d: float | None = None
    delta_7d: float | None = None
    honey_7d: float | None = None

    if len(points) >= 2:
        delta_1d = round(points[-1]["weight_kg"] - points[-2]["weight_kg"], 2)

    if len(points) >= 7:
        delta_7d = round(points[-1]["weight_kg"] - points[-7]["weight_kg"], 2)
        # Honey accumulation = sum of positive daily morning-to-morning deltas
        honey_7d = round(
            sum(
                points[i]["weight_kg"] - points[i - 1]["weight_kg"]
                for i in range(1, len(points))
                if points[i]["weight_kg"] - points[i - 1]["weight_kg"] > 0
            ),
            2,
        )

    return {
        "points": points,
        "delta_1d": delta_1d,
        "delta_7d": delta_7d,
        "honey_7d": honey_7d,
    }


@router.get("/data/day-stats")
def day_stats(hive_id: str | None = Query(default=None)) -> list[dict[str, Any]]:
    return db.get_day_stats(hive_id=hive_id)


@router.get("/data/export.csv")
def export_csv(
    hive_id: str | None = Query(default=None),
    hours: int = Query(default=168, ge=1, le=8760),
    from_ts: float | None = Query(default=None),
    to_ts: float | None = Query(default=None),
) -> StreamingResponse:
    if from_ts is not None and to_ts is not None:
        rows = db.get_measurements_range(from_ts=from_ts, to_ts=to_ts, hive_id=hive_id)
    else:
        rows = db.get_measurements(hours=hours, hive_id=hive_id)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["timestamp_iso", "timestamp_unix", "hive_id", "sensor_name", "key", "value"]
    )
    for r in rows:
        ts_iso = datetime.fromtimestamp(r["timestamp"], tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        writer.writerow(
            [
                ts_iso,
                r["timestamp"],
                r.get("hive_id", ""),
                r["sensor_name"],
                r["key"],
                r["value"],
            ]
        )

    buf.seek(0)
    filename = f"hanipi_{int(time.time())}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/db/stats")
def db_stats() -> dict[str, Any]:
    return db.get_db_stats()
