"""Verify private artifacts and measure the three route handlers on this machine."""
from __future__ import annotations

import json
import os
import time

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.sas import router

from .data import PRIVATE, write_json


def main():
    manifest = json.loads((PRIVATE / "manifest.json").read_text())
    checks = {}
    for name in manifest["audit"]:
        frame = pd.read_parquet(PRIVATE / f"{name}.parquet")
        assert frame.groupby("group_id").split.nunique().max() == 1
        assert frame.row_key.is_unique
        assert len(frame) == manifest["audit"][name]["prepared_rows"]
        checks[name] = {"rows": len(frame), "group_overlap": False, "unique_keys": True}
    os.environ["YOJAK_SAS_LOCAL"] = "1"
    app = FastAPI()
    app.include_router(router)
    timings, scenarios = {}, []
    with TestClient(app) as client:
        for endpoint in ["match", "plan", "pay-range"]:
            print("Verifying", endpoint, flush=True)
            samples = []
            payload = {"role_family": "Data analyst", "experience": 2, "skills": ["python", "sql", "excel"]}
            for _ in range(21):
                start = time.perf_counter()
                response = client.post(f"/sas/{endpoint}", json=payload)
                samples.append(time.perf_counter() - start)
                assert response.status_code == 200, response.text
                assert response.json()["source_version"] == manifest["source_version"]
            timings[endpoint] = {"first_seconds": samples[0], "warm_p50_seconds": float(np.median(samples[1:])),
                                 "warm_p95_seconds": float(np.quantile(samples[1:], .95)), "warm_samples": 20}
        for family in ["Data analyst", "Data scientist", "Business analyst", "Data engineer"]:
            for complete in [False, True]:
                print("Scenario", family, "complete_only", complete, flush=True)
                payload = {"role_family": family, "experience": 3, "skills": ["python", "sql"], "complete_only": complete}
                response = client.post("/sas/plan", json=payload)
                assert response.status_code == 200
                result = response.json()
                if result["optimized"]:
                    assert result["optimized"]["coverage"] >= result["frequency"]["coverage"]
                scenarios.append({"profile": payload, "result": result})
        empty = client.post("/sas/match", json={"experience": 40}).json()
        assert empty["support"] == 0 and empty["matches"] == []
    write_json(PRIVATE / "verification.json", {"data_checks": checks, "route_timings": timings,
                                              "timing_scope": "In-process TestClient, local machine; excludes HTTP network and frontend",
                                              "source_version": manifest["source_version"], "scenarios": scenarios})
    print(json.dumps({"checks": checks, "timings": timings}, indent=2))


if __name__ == "__main__":
    main()
