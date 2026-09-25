"""Impact estimate -> reports/impact.json. Thin wrapper around ml_pipeline.impact (see its docstring)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml_pipeline.impact import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
