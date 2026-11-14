"""Run private SAS analytics: python -m ml_pipeline.sas.run --stage all."""
from __future__ import annotations

import argparse
from pathlib import Path

from .data import DEFAULT_SOURCE, PRIVATE, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--stage", choices=["all", "prepare", "train", "analyze", "explain", "benchmark", "calibration-audit", "sensitivity", "package"], default="all")
    parser.add_argument("--cpu", action="store_true", help="Explicit baseline-only mode; no GPU claim")
    args = parser.parse_args()
    # Output is intentionally fixed outside public snapshots.
    if args.stage in {"all", "prepare"}:
        manifest = prepare(args.source, PRIVATE)
        print("Prepared source version", manifest["source_version"])
    if args.stage in {"all", "train"}:
        from .model import train
        report = train(PRIVATE, gpu=not args.cpu)
        print("Champion", report["champion"], "test", report["test"])
    if args.stage in {"all", "analyze"}:
        from .research import analyze
        analyze(PRIVATE)
        print("Aggregate research complete")
    if args.stage == "explain":
        import pandas as pd

        from .data import write_json
        from .explanation import ordinal_analysis
        report = ordinal_analysis(pd.read_parquet(PRIVATE / "analytics.parquet"))
        write_json(PRIVATE / "salary_explanation.json", report)
        print("Salary explanation", report["primary_model"], report["assumption_status"])
    if args.stage in {"all", "calibration-audit"}:
        from .calibration_audit import audit
        print("Calibration audit", audit(PRIVATE)["overall"])
    if args.stage in {"all", "benchmark"}:
        from .planner_benchmark import benchmark
        report = benchmark(PRIVATE)
        print("Planner benchmark", report["summary"])
    # Explicit opt-in: this post-hoc experiment must not affect model selection.
    if args.stage == "sensitivity":
        from .sensitivity import run_sensitivity
        report = run_sensitivity(PRIVATE, gpu=not args.cpu)
        print("Token sensitivity", report["paired_mean_band_error"])
    if args.stage in {"all", "package"}:
        from .package import package
        package(PRIVATE)
        print("Private exchange bundle and submission readiness refreshed; reviewed documents preserved")


if __name__ == "__main__":
    main()
