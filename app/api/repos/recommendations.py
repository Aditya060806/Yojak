# app/api/repos/recommendations.py

"""
Recommendations Repository
Handles FAISS search and Neo4j queries for occupation recommendations.
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.ml import ml_engine
from app.core.neo4j import Neo4jClient

logger = logging.getLogger(__name__)


def isco_code_from_uri(uri: str) -> str:
    """'http://data.europa.eu/esco/isco/C2511' -> '2511'."""
    tail = uri.rstrip("/").rsplit("/", 1)[-1]
    return tail[1:] if tail[:1].upper() == "C" else tail


def compute_skill_gap(
    required_skills: List[Dict[str, Any]], user_skill_uris: List[str]
) -> Dict[str, Any]:
    """Split an occupation's required skills into matched / missing for a user."""
    user = set(user_skill_uris)
    required = {s["uri"] for s in required_skills}
    matched = [s for s in required_skills if s["uri"] in user]
    missing = [s for s in required_skills if s["uri"] not in user]
    pct = len(required & user) / len(required) * 100 if required else 0.0
    return {"matched_skills": matched, "missing_skills": missing, "match_percentage": pct}


class RecommendationsRepo:
    """Repository for recommendation queries combining FAISS and Neo4j."""

    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j_client = neo4j_client

    def get_recommendations(
        self,
        skill_uris: List[str],
        occupation_groups: Optional[List[str]] = None,
        schemes: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Rank occupations for a skill set and attach the skill-gap analysis."""
        if not skill_uris:
            return []

        skill_labels = self._get_skill_labels(skill_uris)
        query_embedding = ml_engine.encode([" ".join(skill_labels)])[0]

        # Over-fetch when filtering so the filtered list can still reach `limit`.
        faiss_limit = limit * 5 if (occupation_groups or schemes) else limit
        faiss_results = ml_engine.search(query_embedding, top_k=faiss_limit)
        if not faiss_results:
            return []

        scores = {uri: score for uri, score in faiss_results}
        occupations = self._fetch_occupations_with_skills(
            occupation_uris=list(scores),
            occupation_groups=occupation_groups,
            schemes=schemes,
        )

        enriched = []
        for occ in occupations:
            occ["similarity_score"] = scores.get(occ["uri"], 0.0)
            occ.update(compute_skill_gap(occ.get("required_skills", []), skill_uris))
            enriched.append(occ)

        enriched.sort(key=lambda x: x["similarity_score"], reverse=True)
        return enriched[:limit]

    def _get_skill_labels(self, skill_uris: List[str]) -> List[str]:
        """Skill labels in input order (falls back to the URI if unknown)."""
        results = self.neo4j_client.run_query(
            "MATCH (s:Skill) WHERE s.uri IN $uris RETURN s.uri AS uri, s.preferredLabel AS label",
            {"uris": skill_uris},
        )
        label_map = {rec["uri"]: rec["label"] for rec in results}
        return [label_map.get(uri, uri) for uri in skill_uris]

    def _fetch_occupations_with_skills(
        self,
        occupation_uris: List[str],
        occupation_groups: Optional[List[str]] = None,
        schemes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Occupation details + required skills for FAISS candidates, with filters."""
        query = """
        MATCH (o:Occupation)
        WHERE o.uri IN $occupation_uris
        """
        params: Dict[str, Any] = {"occupation_uris": occupation_uris}

        if occupation_groups:
            # A selected group matches its own occupations and every narrower group.
            # ISCO codes are hierarchical, so a code-prefix match is exact.
            query += """
          AND EXISTS {
              MATCH (o)-[:IN_OCC_GROUP]->(g:OccupationGroup)
              WHERE g.uri IN $occupation_groups
                 OR ANY(code IN $occupation_group_codes WHERE g.code STARTS WITH code)
                 OR EXISTS {
                     MATCH (g)-[:BROADER_THAN_OCC_GROUP*1..5]->(parent:OccupationGroup)
                     WHERE parent.uri IN $occupation_groups
                 }
          }
            """
            params["occupation_groups"] = occupation_groups
            params["occupation_group_codes"] = [isco_code_from_uri(u) for u in occupation_groups]

        if schemes:
            query += """
          AND EXISTS {
              MATCH (o)-[:IN_SCHEME]->(cs:ConceptScheme)
              WHERE cs.uri IN $schemes
          }
            """
            params["schemes"] = schemes

        query += """
        OPTIONAL MATCH (o)-[r:REQUIRES]->(s:Skill)
        WITH o, COLLECT(DISTINCT CASE WHEN s IS NULL THEN NULL ELSE {
                 uri: s.uri,
                 label: s.preferredLabel,
                 relation_type: r.relation,
                 skill_type: s.skillType
             } END) AS required_skills
        OPTIONAL MATCH (o)-[:IN_OCC_GROUP]->(g:OccupationGroup)
        WITH o, required_skills, COLLECT(DISTINCT coalesce(g.label, g.code)) AS groups
        OPTIONAL MATCH (o)-[:IN_SCHEME]->(cs:ConceptScheme)
        RETURN o.uri AS uri,
               o.preferredLabel AS label,
               o.description AS description,
               o.iscoCode AS isco_code,
               required_skills,
               groups,
               COLLECT(DISTINCT coalesce(cs.label, cs.uri)) AS schemes
        """

        occupations = []
        for rec in self.neo4j_client.run_query(query, params):
            occupations.append(
                {
                    "uri": rec["uri"],
                    "label": rec["label"],
                    "description": rec["description"] or None,
                    "isco_code": rec["isco_code"] or None,
                    "required_skills": [s for s in rec["required_skills"] if s and s["uri"]],
                    "groups": [g for g in rec["groups"] if g],
                    "schemes": [s for s in rec["schemes"] if s],
                }
            )
        return occupations
