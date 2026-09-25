"""
Generate reports/EVALUATION.md from reports/*.json.

    python scripts/build_evaluation.py           # write reports/EVALUATION.md
    python scripts/build_evaluation.py --check   # exit 1 if it is out of date (CI)
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_pipeline.reporting import build_evaluation, load_reports  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    path = ROOT / "reports" / "EVALUATION.md"
    fresh = build_evaluation(load_reports(ROOT / "reports"))
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if args.check:
        if fresh != current:
            print("reports/EVALUATION.md is out of date: run python scripts/build_evaluation.py")
            return 1
        print("reports/EVALUATION.md is up to date")
        return 0
    path.write_text(fresh, encoding="utf-8", newline="\n")
    print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
