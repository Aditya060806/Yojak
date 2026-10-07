"""
Fill the README's results block from reports/*.json.

    python scripts/render_readme.py           # rewrite README.md in place
    python scripts/render_readme.py --check   # exit 1 if README.md is out of date (CI)
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_pipeline.reporting import load_reports, render_readme  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    path = ROOT / "README.md"
    current = path.read_text(encoding="utf-8")
    fresh = render_readme(current, load_reports(ROOT / "reports"))
    if args.check:
        if fresh != current:
            print("README.md results block is out of date: run python scripts/render_readme.py")
            return 1
        print("README.md is up to date with reports/*.json")
        return 0
    if fresh != current:
        path.write_text(fresh, encoding="utf-8", newline="\n")
    print("README.md generated blocks updated" if fresh != current else "README.md already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
