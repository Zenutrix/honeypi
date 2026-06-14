from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .api import data as data_router
from .api import config as config_router
from .api import network as network_router

app = FastAPI(title="HoneyPi Dashboard")

_STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
app.include_router(data_router.router, prefix="/api")
app.include_router(config_router.router, prefix="/api")
app.include_router(network_router.router, prefix="/api")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(str(_STATIC / "index.html"))


@app.get("/config-ui", include_in_schema=False)
def config_page() -> FileResponse:
    return FileResponse(str(_STATIC / "config.html"))


def main() -> None:
    import uvicorn
    uvicorn.run("honeypi_dashboard.main:app", host="0.0.0.0", port=80, reload=False)
