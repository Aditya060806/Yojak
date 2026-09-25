# app/api/main.py

"""
Yojak API
FastAPI app with a Neo4j lifecycle, latency metrics and router auto-discovery.
"""

from __future__ import annotations

import importlib
import logging
import threading
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.deps import close_neo4j_client, init_neo4j_client
from app.core.metrics_middleware import LatencyMiddleware
from app.core.settings import APP_NAME, APP_VERSION, get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _warm_up_models() -> None:
    """Load the embedding model and FAISS index off the request path."""
    from app.core.ml import ml_engine

    ml_engine.is_ready()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_neo4j_client()
    if settings.warm_up_models:
        threading.Thread(target=_warm_up_models, name="model-warmup", daemon=True).start()
    try:
        yield
    finally:
        close_neo4j_client()


app = FastAPI(
    title=f"{APP_NAME} API",
    version=APP_VERSION,
    description=(
        "Talent and workforce intelligence for India: skill linking, job matching, "
        "optimal upskilling plans, salary ranges and workforce demand, built on "
        "ESCO and Indian job-posting data."
    ),
    lifespan=lifespan,
)

app.add_middleware(LatencyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the full error server-side; never leak internals to the client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def _try_include(module_path: str) -> bool:
    """
    Import `module_path` and include its `router`.
    Returns False only if that module itself does not exist.
    """
    try:
        mod = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        if e.name == module_path:
            return False
        raise  # a missing dependency inside an existing module is a real error

    router: Optional[APIRouter] = getattr(mod, "router", None)
    if router is None:
        raise RuntimeError(f"{module_path} exists but does not export `router`")
    app.include_router(router)
    return True


ROUTE_MODULES = [
    "app.api.routes.health",
    "app.api.routes.diagnostics",
    "app.api.routes.catalog",
    "app.api.routes.occupations",
    "app.api.routes.skills",
    "app.api.routes.notes",
    "app.api.routes.recommendations",
    # Yojak modules (added phase by phase)
    "app.api.routes.reports",
    "app.api.routes.extract",
    "app.api.routes.jobs",
    "app.api.routes.student",
    "app.api.routes.recruiter",
    "app.api.routes.institution",
    "app.api.routes.workforce",
    "app.api.routes.salary",
    "app.api.routes.labelling",
    "app.api.routes.graph",
]

for _module in ROUTE_MODULES:
    _try_include(_module)
