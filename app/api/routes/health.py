# app/api/routes/health.py

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import Neo4jDep
from app.core.settings import APP_NAME, APP_VERSION, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(neo4j: Neo4jDep) -> dict:
    """
    Readiness endpoint: config presence, live Neo4j connectivity and ML artifacts.
    Never returns secrets.
    """
    settings = get_settings()

    try:
        neo4j.run_query("RETURN 1 AS ok")
        neo4j_ok, neo4j_error = True, None
    except Exception as e:  # noqa: BLE001 - report, don't raise
        neo4j_ok, neo4j_error = False, type(e).__name__

    return {
        "status": "ok" if neo4j_ok else "degraded",
        "app": APP_NAME,
        "version": APP_VERSION,
        "environment": settings.environment,
        "neo4j": {
            "connected": neo4j_ok,
            "error": neo4j_error,
            "uri_configured": bool(settings.neo4j_uri),
            "password_configured": bool(settings.neo4j_password),
        },
        "faiss": {
            "index_present": settings.faiss_index_path.exists(),
            "metadata_present": settings.occupation_metadata_path.exists(),
        },
    }
