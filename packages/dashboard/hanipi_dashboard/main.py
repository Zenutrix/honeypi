from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .api import calibrate as calibrate_router
from .api import config as config_router
from .api import data as data_router
from .api import hives as hives_router
from .api import maintenance as maintenance_router
from .api import network as network_router
from .api import thingspeak as thingspeak_router

logger = logging.getLogger(__name__)


async def _cleanup_loop() -> None:
    """Daily DB cleanup task."""
    while True:
        await asyncio.sleep(86400)
        try:
            import json

            from .api.config import CONFIG_PATH

            cfg: dict[str, Any] = {}
            if CONFIG_PATH.exists():
                cfg = json.loads(CONFIG_PATH.read_text())
            db.cleanup_db(
                max_size_mb=cfg.get("db_max_size_mb", 500),
                retention_days=cfg.get("db_retention_days", 90),
            )
            logger.info("DB cleanup completed")
        except Exception as exc:
            logger.error("DB cleanup failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Run cleanup once at startup
    try:
        import json

        from .api.config import CONFIG_PATH

        cfg: dict[str, Any] = {}
        if CONFIG_PATH.exists():
            cfg = json.loads(CONFIG_PATH.read_text())
        db.cleanup_db(
            max_size_mb=cfg.get("db_max_size_mb", 500),
            retention_days=cfg.get("db_retention_days", 90),
        )
    except Exception as exc:
        logger.warning("Startup DB cleanup failed: %s", exc)

    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="HaniPi Dashboard", lifespan=lifespan)

_STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
app.include_router(data_router.router, prefix="/api")
app.include_router(config_router.router, prefix="/api")
app.include_router(network_router.router, prefix="/api")
app.include_router(hives_router.router, prefix="/api")
app.include_router(maintenance_router.router, prefix="/api")
app.include_router(thingspeak_router.router, prefix="/api")
app.include_router(calibrate_router.router, prefix="/api")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(str(_STATIC / "index.html"))


@app.get("/config-ui", include_in_schema=False)
def config_page() -> FileResponse:
    return FileResponse(str(_STATIC / "config.html"))


@app.get("/hives", include_in_schema=False)
def hives_page() -> FileResponse:
    return FileResponse(str(_STATIC / "hives.html"))


@app.get("/hives/{hive_id}", include_in_schema=False)
def hive_detail_page(hive_id: str) -> FileResponse:
    return FileResponse(str(_STATIC / "hive_detail.html"))


@app.get("/network", include_in_schema=False)
def network_page() -> FileResponse:
    return FileResponse(str(_STATIC / "network.html"))


@app.get("/maintenance", include_in_schema=False)
def maintenance_page() -> FileResponse:
    return FileResponse(str(_STATIC / "maintenance.html"))


def main() -> None:
    import uvicorn

    uvicorn.run("hanipi_dashboard.main:app", host="0.0.0.0", port=80, reload=False)
