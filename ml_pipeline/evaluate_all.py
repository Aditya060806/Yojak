# ml_pipeline/evaluate_all.py

"""
Run every evaluation, then regenerate reports/EVALUATION.md and the README results block.

    python -m ml_pipeline.evaluate_all                  # everything (about an hour on one GPU)
    python -m ml_pipeline.evaluate_all --quick          # smoke test: small benchmark, fewer instances
    python -m ml_pipeline.evaluate_all --only impact docs

Steps, in order (each writes reports/<name>.json):
  benchmark     link prediction: 6 models x T1/T2/T3 + ablations   -> model_comparison.json
  upskilling    greedy / frequency / exact ILP / budgeted           -> upskilling_eval.json
  multilingual  English vs multilingual linking                     -> multilingual_eval.json
  gold          refresh gold-label metrics in data_quality.json
  impact        Tier-2/3 fresher impact estimate                    -> impact.json
  docs          reports/EVALUATION.md + README results block

Run the steps alone: they use the GPU and all CPU cores, and running two at once
distorts the latency numbers they record.
"""

from __future__ import annotations

import argparse
import sys
import time

STEPS = ("benchmark", "upskilling", "multilingual", "gold", "impact", "docs")


def run_step(step: str, quick: bool) -> int:
    if step == "benchmark":
        from ml_pipeline.graph.evaluate import main as bench

        return bench(["--quick", "--seeds", "1"] if quick else [])
    if step == "upskilling":
        from ml_pipeline.upskilling.evaluate import main as up

        return up(["--instances", "20"] if quick else [])
    if step == "multilingual":
        from ml_pipeline.india.multilingual import main as ml

        return ml()
    if step == "gold":
        from ml_pipeline.india.gold import main as gold

        return gold(["evaluate"])
    if step == "impact":
        from ml_pipeline.impact import main as impact

        return impact()
    if step == "docs":
        from app.core.settings import PROJECT_ROOT, get_settings
        from ml_pipeline.reporting import build_evaluation, load_reports, render_readme

        s = get_settings()
        reports = load_reports(s.reports_dir)
        (s.reports_dir / "EVALUATION.md").write_text(build_evaluation(reports), encoding="utf-8", newline="\n")
        readme = PROJECT_ROOT / "README.md"
        readme.write_text(render_readme(readme.read_text(encoding="utf-8"), reports), encoding="utf-8", newline="\n")
        print("wrote reports/EVALUATION.md and the README results block")
        return 0
    raise ValueError(step)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", choices=STEPS, default=list(STEPS))
    ap.add_argument("--quick", action="store_true", help="smoke test; quick benchmark writes model_comparison_quick.json")
    args = ap.parse_args(argv)
    t_all = time.time()
    failed = []
    for step in STEPS:
        if step not in args.only:
            continue
        print(f"\n######## {step}", flush=True)
        t0 = time.time()
        try:
            code = run_step(step, args.quick)
        except SystemExit as e:  # sub-mains may raise SystemExit with a message
            code = e.code if isinstance(e.code, int) else 1
            if not isinstance(e.code, int):
                print(e.code)
        if code:
            failed.append(step)
        print(f"######## {step}: {'FAILED' if code else 'ok'} in {time.time() - t0:.0f} s", flush=True)
    print(f"\nEvaluation finished in {time.time() - t_all:.0f} s" + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
