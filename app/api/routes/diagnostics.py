# app/api/routes/diagnostics.py

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.routing import APIRoute

from app.api.schemas.diagnostics import (
    EndpointInfo,
    EndpointMetric,
    EndpointsResponse,
    MetricsResponse,
    NodeCountResponse,
    NodesByLabelResponse,
    RelCountResponse,
    RelsByTypeResponse,
)
from app.api.services.diagnostics import DiagnosticsService
from app.core.deps import Neo4jDep
from app.core.metrics_middleware import latency_store

router = APIRouter(prefix="/admin/diagnostics", tags=["diagnostics"])


@router.get("/nodes-by-label", response_model=NodesByLabelResponse)
def get_nodes_by_label(neo4j: Neo4jDep) -> NodesByLabelResponse:
    """
    Returns node counts grouped by label.

    Queries Neo4j to count all nodes grouped by their primary label.
    """
    service = DiagnosticsService(neo4j)
    node_counts = service.get_node_counts_by_label()

    return NodesByLabelResponse(
        labels=[
            NodeCountResponse(label=nc.label, count=nc.count)
            for nc in node_counts
        ]
    )


@router.get("/rels-by-type", response_model=RelsByTypeResponse)
def get_rels_by_type(neo4j: Neo4jDep) -> RelsByTypeResponse:
    """
    Returns relationship counts grouped by type.

    Queries Neo4j to count all relationships grouped by their type.
    """
    service = DiagnosticsService(neo4j)
    rel_counts = service.get_relationship_counts_by_type()

    return RelsByTypeResponse(
        types=[
            RelCountResponse(type=rc.type, count=rc.count)
            for rc in rel_counts
        ]
    )


@router.get("/endpoints", response_model=EndpointsResponse)
def get_endpoints(request: Request) -> EndpointsResponse:
    """Every API route registered on this app (introspected, not hard-coded)."""
    endpoints: list[EndpointInfo] = []
    for route in request.app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            endpoints.append(
                EndpointInfo(
                    method=method,
                    path=route.path,
                    name=route.name,
                    tags=[str(t) for t in (route.tags or [])],
                )
            )
    endpoints.sort(key=lambda e: (e.tags[0] if e.tags else "", e.path, e.method))
    return EndpointsResponse(endpoints=endpoints)


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics() -> MetricsResponse:
    """Per-route latency (avg, p50, p95, min, max) over a rolling window."""
    return MetricsResponse(metrics=[EndpointMetric(**m) for m in latency_store.snapshot()])
