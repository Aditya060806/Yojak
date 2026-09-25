#!/usr/bin/env bash
# One-time local setup for Yojak on Linux/macOS (no Docker).
#
# Creates .venv, installs Python and frontend dependencies, writes .env with a random
# Neo4j password, and installs a project-local Neo4j.
#
#   scripts/setup.sh              # torch: CUDA wheel if nvidia-smi exists, else CPU
#   scripts/setup.sh --torch cpu  # cpu | cuda | skip (keep whatever torch is importable)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TORCH="auto"
if [ "${1:-}" = "--torch" ]; then TORCH="${2:-auto}"; fi

# 1) .env with a random Neo4j password
if [ ! -f .env ]; then
  pw="$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 24)"
  sed -e "s/^NEO4J_PASSWORD=.*/NEO4J_PASSWORD=$pw/" .env.example > .env
  echo "Created .env"
fi

# 2) Python venv
PY_BOOT="$(command -v python3.11 || command -v python3)"
[ -d .venv ] || "$PY_BOOT" -m venv .venv
PY="$ROOT/.venv/bin/python"
"$PY" -m pip install --upgrade pip -q
if [ "$TORCH" = "auto" ]; then
  if command -v nvidia-smi >/dev/null; then TORCH="cuda"; else TORCH="cpu"; fi
fi
case "$TORCH" in
  cuda) "$PY" -m pip install -q torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121 ;;
  cpu)  "$PY" -m pip install -q torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu ;;
  skip) ;;
  *) echo "unknown --torch value: $TORCH" >&2; exit 2 ;;
esac
"$PY" -m pip install -q -r requirements-dev.txt
echo "Python dependencies installed"

# 3) Frontend
(
  cd app/frontend
  npm ci --no-audit --no-fund
  [ -f .env.local ] || echo "NEXT_PUBLIC_API_URL=http://127.0.0.1:8000" > .env.local
)
echo "Frontend dependencies installed"

# 4) Data folders + Neo4j
mkdir -p data/raw/esco data/raw/naukri data/raw/external data/processed artifacts
"$ROOT/scripts/neo4j.sh" install

cat <<'MSG'

Setup done. Next:
  1. Put the ESCO v1.2 English CSVs in data/raw/esco (manual download from esco.ec.europa.eu)
  2. scripts/run.sh data       # Kaggle + public reference data (needs ~/.kaggle/kaggle.json)
  3. scripts/run.sh pipeline   # build graph, indexes, models and reports
  4. scripts/run.sh up         # Neo4j + API + web on http://localhost:3000
MSG
