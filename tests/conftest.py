"""
Shared pytest fixtures.

Most tests run without a database: `FakeNeo4j` returns scripted rows and records
every Cypher query so tests can assert on what was sent. Tests that need a live
Neo4j are marked `neo4j` and only run when NEO4J_TEST_URI is set, so the suite
can never touch the development graph by accident.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

# Must be set before app modules read settings.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ["WARM_UP_MODELS"] = "false"
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

FIXTURES = Path(__file__).parent / "fixtures"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeNeo4j:
    """Stand-in for app.core.neo4j.Neo4jClient."""

    def __init__(self) -> None:
        self.queries: list[tuple[str, dict[str, Any]]] = []
        self._rules: list[tuple[re.Pattern[str], Callable[[dict], list[dict]] | list[dict]]] = []

    def on(self, pattern: str, rows: Callable[[dict], list[dict]] | list[dict]) -> FakeNeo4j:
        """Return `rows` for any query matching `pattern` (regex, DOTALL)."""
        self._rules.append((re.compile(pattern, re.S), rows))
        return self

    def run_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        params = params or {}
        self.queries.append((cypher, params))
        for pattern, rows in self._rules:
            if pattern.search(cypher):
                return rows(params) if callable(rows) else rows
        return []

    def connect(self) -> None:  # pragma: no cover - parity with the real client
        pass

    def close(self) -> None:  # pragma: no cover
        pass

    def last_query(self, contains: str) -> tuple[str, dict[str, Any]]:
        for cypher, params in reversed(self.queries):
            if contains in cypher:
                return cypher, params
        raise AssertionError(f"No query containing {contains!r} was sent")


@pytest.fixture
def fake_neo4j() -> FakeNeo4j:
    return FakeNeo4j()


@pytest.fixture
def client(fake_neo4j: FakeNeo4j, monkeypatch: pytest.MonkeyPatch):
    """FastAPI TestClient wired to FakeNeo4j (no real database)."""
    from fastapi.testclient import TestClient

    import app.api.main as main
    from app.core import deps

    monkeypatch.setattr(main, "init_neo4j_client", lambda: None)
    monkeypatch.setattr(main, "close_neo4j_client", lambda: None)
    main.app.dependency_overrides[deps.get_neo4j_client] = lambda: fake_neo4j
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("NEO4J_TEST_URI"):
        return
    skip = pytest.mark.skip(reason="NEO4J_TEST_URI not set (live-database test)")
    for item in items:
        if "neo4j" in item.keywords:
            item.add_marker(skip)
