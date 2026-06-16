from __future__ import annotations

from fastapi import APIRouter

from .. import db

router = APIRouter()


@router.get("/thingspeak/keys")
def thingspeak_keys() -> list[str]:
    """Return all sensor_name.key combinations from DB for ThingSpeak field mapping."""
    return db.get_sensor_keys()
