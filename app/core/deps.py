# app/core/deps.py

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.neo4j import Neo4jClient
from app.core.settings import get_settings

# Global Neo4j client instance (singleton pattern)
_neo4j_client: Neo4jClient | None = None


def get_neo4j_client() -> Neo4jClient:
    """
    FastAPI dependency that returns the shared Neo4j client instance.

    Raises:
        RuntimeError: If the client has not been initialized via init_neo4j_client().
    """
    if _neo4j_client is None:
        raise RuntimeError(
            "Neo4j client not initialized. Call init_neo4j_client() on app startup."
        )
    return _neo4j_client


def init_neo4j_client() -> None:
    """
    Initialize and connect the global Neo4j client.
    Called once during application startup.
    """
    global _neo4j_client
    settings = get_settings()
    _neo4j_client = Neo4jClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )
    _neo4j_client.connect()


def close_neo4j_client() -> None:
    """
    Close the global Neo4j client connection.
    Called once during application shutdown.
    """
    global _neo4j_client
    if _neo4j_client is not None:
        _neo4j_client.close()
        _neo4j_client = None


# Type alias for cleaner dependency injection
Neo4jDep = Annotated[Neo4jClient, Depends(get_neo4j_client)]


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    """
    Demo-grade guard for admin write routes.

    The client sends `X-Admin-Token`. If ADMIN_TOKEN is unset the check is skipped
    in development only; in any other environment an unset token locks writes.
    This is not user authentication, just protection against casual misuse.
    """
    settings = get_settings()
    expected = settings.admin_token
    if not expected:
        if settings.is_development:
            return
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ADMIN_TOKEN is not configured")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid admin token")


AdminDep = Annotated[None, Depends(require_admin)]
