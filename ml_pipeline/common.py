# ml_pipeline/common.py

"""
Shared helpers for pipelines: provenance, report writing, hashing, logging.

Every number that reaches the README, UI or slides is written by `write_report`,
which stamps it with provenance (git commit, input file hashes, seed, script,
UTC time) so any figure can be traced back to the exact code and data.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

import numpy as np

from app.core.settings import PROJECT_ROOT, get_settings

REPORT_SCHEMA_VERSION = 1


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def git_commit() -> dict[str, Any]:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
            ).stdout.strip()
        except Exception:  # noqa: BLE001 - git missing is not fatal
            return ""

    return {
        "commit": run("rev-parse", "HEAD") or None,
        "branch": run("rev-parse", "--abbrev-ref", "HEAD") or None,
        "dirty": bool(run("status", "--porcelain")),
    }


def provenance(script: str, inputs: Iterable[Path] = (), seed: int | None = None, **extra: Any) -> dict:
    files = []
    for p in inputs:
        p = Path(p)
        if p.exists() and p.is_file():
            files.append(
                {
                    "path": str(p.relative_to(PROJECT_ROOT)) if p.is_relative_to(PROJECT_ROOT) else str(p),
                    "sha256": sha256_file(p),
                    "bytes": p.stat().st_size,
                }
            )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "script": script,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "git": git_commit(),
        "python": sys.version.split()[0],
        "seed": seed,
        "inputs": files,
        **extra,
    }


def _to_jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return _to_jsonable(obj.tolist())
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (dt.date, dt.datetime)):
        return obj.isoformat()
    return obj


def write_report(name: str, body: dict, prov: dict) -> Path:
    """Write reports/<name>.json with a provenance block. Returns the path."""
    out_dir = get_settings().reports_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.json"
    payload = {"report": name, "provenance": prov, **body}
    path.write_text(json.dumps(_to_jsonable(payload), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_report(name: str) -> dict | None:
    path = get_settings().reports_dir / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson score interval for a proportion (None when n == 0)."""
    if n == 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


@contextmanager
def stage(name: str, timings: dict[str, float] | None = None) -> Iterator[None]:
    """Print a stage banner and record its wall time."""
    print(f"\n[{name}]", flush=True)
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    if timings is not None:
        timings[name] = round(elapsed, 2)
    print(f"[{name}] done in {elapsed:.1f} s", flush=True)
