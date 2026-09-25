# app/api/repos/notes.py

"""
Notes Repository
Handles Neo4j queries for notes management.
"""

import logging
from typing import Any, Dict, Optional

from app.core.neo4j import Neo4jClient

logger = logging.getLogger(__name__)


class NotesRepo:
    """Repository for notes queries."""

    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j_client = neo4j_client

    def search_notes(
        self,
        occupation_uri: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> Dict[str, Any]:
        """
        Search notes with optional filtering.

        Args:
            occupation_uri: Optional occupation URI to filter by
            limit: Maximum number of results
            skip: Number of results to skip (pagination)

        Returns:
            Dict with total count and list of notes
        """
        query = """
        MATCH (o:Occupation)-[hn:HAS_NOTE]->(n:Note)
        """

        params = {"limit": limit, "skip": skip}

        if occupation_uri:
            query += "WHERE o.uri = $occupationUri\n"
            params["occupationUri"] = occupation_uri

        query += """
        WITH o, n, hn
        ORDER BY COALESCE(n.updatedAt, n.createdAt) DESC

        WITH COLLECT({
            occupationUri: o.uri,
            occupationLabel: o.preferredLabel,
            noteId: n.id,
            text: n.text,
            createdAt: toString(n.createdAt),
            updatedAt: toString(coalesce(n.updatedAt, n.createdAt))
        }) AS all_notes

        RETURN SIZE(all_notes) AS total,
               all_notes[$skip..$skip + $limit] AS notes
        """

        results = self.neo4j_client.run_query(query, params)

        if not results:
            return {"total": 0, "notes": []}

        result = results[0]
        return {
            "total": result["total"],
            "notes": result["notes"]
        }

    def upsert_note(
        self,
        occupation_uri: str,
        note_id: str,
        text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create or update a note for an occupation.

        Args:
            occupation_uri: Occupation URI
            note_id: Note identifier
            text: Note text content

        Returns:
            Note details or None if occupation not found
        """
        # A note belongs to exactly one occupation: if the note already exists
        # under a different occupation it is moved, not linked twice.
        query = """
        MATCH (o:Occupation {uri: $occupationUri})

        MERGE (n:Note {id: $noteId})
        ON CREATE SET
            n.text = $text,
            n.createdAt = datetime(),
            n.updatedAt = datetime()
        ON MATCH SET
            n.text = $text,
            n.updatedAt = datetime()

        WITH o, n
        OPTIONAL MATCH (other:Occupation)-[old:HAS_NOTE]->(n)
        WHERE other.uri <> o.uri
        DELETE old

        WITH DISTINCT o, n
        MERGE (o)-[hn:HAS_NOTE]->(n)
        ON CREATE SET hn.createdAt = datetime()

        RETURN
            o.uri AS occupationUri,
            o.preferredLabel AS occupationLabel,
            n.id AS noteId,
            n.text AS text,
            toString(n.createdAt) AS createdAt,
            toString(coalesce(n.updatedAt, n.createdAt)) AS updatedAt
        """

        params = {
            "occupationUri": occupation_uri,
            "noteId": note_id,
            "text": text
        }

        results = self.neo4j_client.run_query(query, params)

        if not results:
            return None

        return dict(results[0])



    def delete_note(
        self,
        occupation_uri: str,
        note_id: str
    ) -> bool:
        """
        Delete a note from an occupation.

        If the note is only linked to this occupation, the Note node is also deleted.
        If the note is linked to other occupations, only the HAS_NOTE relationship is deleted.

        Args:
            occupation_uri: Occupation URI
            note_id: Note identifier

        Returns:
            True if deleted, False if not found
        """
        query = """
        MATCH (o:Occupation {uri: $occupationUri})-[hn:HAS_NOTE]->(n:Note {id: $noteId})
        DELETE hn
        WITH n
        // Remove the Note node once nothing references it any more.
        OPTIONAL MATCH (n)<-[remaining:HAS_NOTE]-()
        WITH n, count(remaining) AS remainingLinks
        FOREACH (_ IN CASE WHEN remainingLinks = 0 THEN [1] ELSE [] END | DELETE n)
        RETURN 1 AS deleted
        """

        params = {
            "occupationUri": occupation_uri,
            "noteId": note_id
        }

        # Errors propagate so the service reports a 500 instead of a false 404.
        results = self.neo4j_client.run_query(query, params)
        return bool(results)
