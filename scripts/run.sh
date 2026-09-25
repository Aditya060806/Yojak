#!/usr/bin/env bash
# Yojak task runner for Linux/macOS (no Docker). Same tasks as scripts/run.ps1.
#
#   scripts/run.sh up          # Neo4j + API (:8000) + web (:3000) in the background
#   scripts/run.sh api         # API only, foreground, auto-reload
#   scripts/run.sh web         # production build + next start, foreground
#   scripts/run.sh dev         # next dev, foreground
#   scripts/run.sh data        # download Kaggle + public reference data
#   scripts/run.sh pipeline    # build graph, indexes, models and reports
#   scripts/run.sh eval        # run every evaluation, regenerate EVALUATION.md + README results
#   scripts/run.sh demo        # three personas end to end -> reports/demo_output/
#   scripts/run.sh test        # pytest + ruff + frontend typecheck/lint
#   scripts/run.sh stop        # stop API, web and Neo4j
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "Run scripts/setup.sh first." >&2; exit 1; }
export PYTHONIOENCODING=utf-8 PYTHONWARNINGS=ignore
TASK="${1:-up}"
shift || true

port_open() { (echo > "/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1; }

wait_port() {
  for _ in $(seq 1 "${2:-120}"); do port_open "$1" && return 0; sleep 1; done
  return 1
}

stop_port() {
  local pids
  pids="$(lsof -ti "tcp:$1" -sTCP:LISTEN 2>/dev/null || true)"
  [ -z "$pids" ] || kill $pids 2>/dev/null || true
}

case "$TASK" in
  up)
    "$ROOT/scripts/neo4j.sh" start
    mkdir -p artifacts/logs
    stop_port 8000
    nohup "$PY" -m uvicorn app.api.main:app --port 8000 > artifacts/logs/api.log 2>&1 &
    wait_port 8000 || { echo "API did not start; see artifacts/logs/api.log" >&2; exit 1; }
    echo "API running: http://127.0.0.1:8000/docs"
    (cd app/frontend && { [ -f .next/BUILD_ID ] || npm run build; })
    stop_port 3000
    (cd app/frontend && nohup npm run start > ../../artifacts/logs/web.log 2>&1 &)
    wait_port 3000 || { echo "Web app did not start; see artifacts/logs/web.log" >&2; exit 1; }
    echo "Web running: http://localhost:3000"
    ;;
  api) exec "$PY" -m uvicorn app.api.main:app --port 8000 --reload ;;
  web) cd app/frontend && npm run build && exec npm run start ;;
  dev) cd app/frontend && exec npm run dev ;;
  pipeline)
    "$ROOT/scripts/neo4j.sh" start
    exec "$PY" -m ml_pipeline.run_pipeline "$@"
    ;;
  data) exec "$PY" -m ml_pipeline.acquire "$@" ;;
  eval) exec "$PY" -m ml_pipeline.evaluate_all "$@" ;;
  demo) exec "$PY" scripts/demo.py "$@" ;;
  test)
    "$PY" -m pytest "$@"
    "$PY" -m ruff check app ml_pipeline tests scripts
    cd app/frontend && npx tsc --noEmit && npm run lint
    ;;
  stop)
    stop_port 3000
    stop_port 8000
    "$ROOT/scripts/neo4j.sh" stop
    ;;
  *)
    echo "usage: scripts/run.sh up|api|web|dev|data|pipeline|eval|demo|test|stop" >&2; exit 2
    ;;
esac
