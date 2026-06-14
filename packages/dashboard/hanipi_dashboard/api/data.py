from __future__ import annotations
from fastapi import APIRouter, Query
from .. import db

router = APIRouter()


@router.get("/data/latest")
def latest() -> list[dict]:
    return db.get_latest()


@router.get("/data/history")
def history(
    sensor: str | None = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
) -> list[dict]:
    return db.get_measurements(sensor=sensor, hours=hours)
