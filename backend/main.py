"""FastAPI application entry point.

    uvicorn main:app --reload        (run from backend/)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.routes import agent, auth, clinical, dashboard, operations
from core.config import settings
from core.deps import ALL_ROLES, require_roles
from core.logging import get_logger, setup_logging
from database.session import get_db, init_db
from models import SystemState, User
from services.hospital_state import get_now
from services.nvidia_llm import model_name

setup_logging()
log = get_logger("api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    log.info("API ready (reviewer_mode=%s, max_revisions=%s)", settings.reviewer_mode, settings.max_revisions)
    yield


app = FastAPI(
    title="Hospital Workflow Agent API",
    version="1.0.0",
    description="Multi-agent decision support for hospital operations: scheduling, beds, staffing and "
                "emergency response. Synthetic data only; not a clinical tool.",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for module in (auth, dashboard, clinical, operations, agent):
    app.include_router(module.router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["health"], summary="Liveness, database and LLM status")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001
        database = "unavailable"
    return {"status": "ok", "database": database, "llm_model": model_name()}


@app.get("/clock", tags=["health"], summary="Hospital clock and active scenario (all roles)")
def clock(db: Session = Depends(get_db), _: User = Depends(require_roles(*ALL_ROLES))) -> dict:
    now = get_now(db)
    scenario = db.get(SystemState, "active_scenario")
    return {"now": now.isoformat(), "date": now.date().isoformat(),
            "active_scenario": scenario.value if scenario else None}
