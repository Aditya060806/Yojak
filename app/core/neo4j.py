# app/core/neo4j.py

from __future__ import annotations

from typing import Any

from neo4j import Driver, GraphDatabase


class Neo4jClient:
    """
    Low-level Neo4j driver wrapper.
    Provides `run_query(cypher, params)` for executing Cypher queries.
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        self.uri = uri
        self.user = user
        self.password = password
        self._driver: Driver | None = None

    def connect(self) -> None:
        """Establish the Neo4j driver connection."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )

    def close(self) -> None:
        """Close the Neo4j driver connection."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def run_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query and return results as a list of dicts.

        Args:
            cypher: Cypher query string
            params: Query parameters (optional)

        Returns:
            List of records as dictionaries
        """
        if self._driver is None:
            raise RuntimeError("Neo4j driver not connected. Call .connect() first.")

        params = params or {}

        with self._driver.session() as session:
            result = session.run(cypher, params)
            return [record.data() for record in result]

    def run_write(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a write in a managed transaction. The driver retries transient
        errors (deadlocks, outdated reads) automatically, which plain auto-commit
        `run_query` does not. Not usable with `CALL ... IN TRANSACTIONS`.
        """
        if self._driver is None:
            raise RuntimeError("Neo4j driver not connected. Call .connect() first.")

        def work(tx):
            return [record.data() for record in tx.run(cypher, params or {})]

        with self._driver.session() as session:
            return session.execute_write(work)

    def __enter__(self) -> Neo4jClient:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
