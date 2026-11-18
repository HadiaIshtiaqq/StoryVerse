"""STORYVERSE backend entrypoint.

Run locally:   uvicorn app.main:app --reload
Simulator:     http://localhost:8000/sim/      API docs: http://localhost:8000/docs
"""

import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import discovery
from app.api import auth, diplomacy, economy, kingdoms, military, worlds, ws
from app.config import settings
from app.database import init_db
from app.errors import GameError


class _RedactTokens(logging.Filter):
    """Browsers and Unity's ClientWebSocket can't set headers on a WebSocket, so the session token travels in the
    URL (?token=...). Uvicorn's access log would otherwise write every player's token to disk."""
    _pattern = re.compile(r"(token=)[^&\s\"']+")

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            record.args = tuple(self._pattern.sub(r"\1[redacted]", a) if isinstance(a, str) else a for a in record.args)
        record.msg = self._pattern.sub(r"\1[redacted]", str(record.msg))
        return True


for _name in ("uvicorn.access", "uvicorn.error"):
    logging.getLogger(_name).addFilter(_RedactTokens())


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    discovery.start()          # headsets re-find the server when the laptop's IP changes
    yield


app = FastAPI(title="STORYVERSE: Rise of Kingdoms API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def always_fresh_simulator(request: Request, call_next):
    """Without Cache-Control, browsers kept serving an old copy of the simulator after updates (old page + new
    script = broken login). `no-cache` makes the browser revalidate every time; unchanged files still come back as
    a cheap 304 thanks to the ETag."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/sim"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.exception_handler(GameError)
async def game_error_handler(_: Request, exc: GameError):
    return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message, **exc.details}})


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:])
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error",
                                                            "message": f"{field}: {first.get('msg', 'invalid input')}",
                                                            "fields": [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]}})


for module in (auth, worlds, kingdoms, economy, diplomacy, military, ws):
    app.include_router(module.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


_SIM = Path(__file__).parent / "static" / "sim"
if _SIM.exists():
    app.mount("/sim", StaticFiles(directory=_SIM, html=True), name="sim")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/sim/")
