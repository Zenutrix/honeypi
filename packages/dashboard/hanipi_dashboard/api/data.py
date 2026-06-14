from __future__ import annotations
from fastapi import APIRouter, Query
from .. import db

router = APIRouter()


@router.get("/data/latest")
def latest(hive_id: str | None = Query(default=None)) -> list[dict]:
    return db.get_latest(hive_id=hive_id)


@router.get("/data/history")
def history(
    sensor: str | None = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
    hive_id: str | None = Query(default=None),
) -> list[dict]:
    return db.get_measurements(sensor=sensor, hours=hours, hive_id=hive_id)


@router.get("/db/stats")
def db_stats() -> dict:
    return db.get_db_stats()
