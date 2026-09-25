#!/usr/bin/env bash
# Project-local Neo4j Community for Linux/macOS (no Docker, no system install).
#
#   scripts/neo4j.sh install   # download + configure into tools/neo4j (needs Java 17+)
#   scripts/neo4j.sh start     # start in the background, wait until Bolt is up
#   scripts/neo4j.sh stop
#   scripts/neo4j.sh status
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="5.26.31"
TOOLS="$ROOT/tools"
HOME4J="$TOOLS/neo4j"
ENV_FILE="$ROOT/.env"

env_value() {
  [ -f "$ENV_FILE" ] || return 0
  grep -E "^\s*$1\s*=" "$ENV_FILE" | head -n1 | cut -d= -f2- | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//'
}

port_open() { (echo > "/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1; }

sha256() {
  if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

case "${1:-status}" in
  install)
    if [ -x "$HOME4J/bin/neo4j" ]; then echo "Neo4j already installed at $HOME4J"; exit 0; fi
    command -v java >/dev/null || { echo "Java 17+ is required (e.g. Eclipse Temurin 17)." >&2; exit 1; }
    mkdir -p "$TOOLS"
    url="https://dist.neo4j.org/neo4j-community-$VERSION-unix.tar.gz"
    echo "Downloading $url"
    curl -fsSL -o "$TOOLS/neo4j.tar.gz" "$url"
    expected="$(curl -fsSL "$url.sha256" | cut -c1-64 | tr 'A-F' 'a-f')"
    actual="$(sha256 "$TOOLS/neo4j.tar.gz")"
    [ "$actual" = "$expected" ] || { echo "Checksum mismatch for neo4j.tar.gz" >&2; exit 1; }
    tar -xzf "$TOOLS/neo4j.tar.gz" -C "$TOOLS"
    mv "$TOOLS/neo4j-community-$VERSION" "$HOME4J"
    printf '\nserver.memory.heap.initial_size=1g\nserver.memory.heap.max_size=2g\nserver.memory.pagecache.size=1g\n' \
      >> "$HOME4J/conf/neo4j.conf"
    pw="$(env_value NEO4J_PASSWORD)"
    if [ -z "$pw" ] || [ "$pw" = "change-me" ]; then
      echo "Set NEO4J_PASSWORD in .env first (scripts/setup.sh does this)." >&2; exit 1
    fi
    "$HOME4J/bin/neo4j-admin" dbms set-initial-password "$pw" >/dev/null
    echo "Neo4j $VERSION installed. Password taken from .env."
    ;;
  start)
    if port_open 7687; then echo "Neo4j already running (bolt://127.0.0.1:7687)"; exit 0; fi
    [ -x "$HOME4J/bin/neo4j" ] || { echo "Neo4j not installed. Run: scripts/neo4j.sh install" >&2; exit 1; }
    "$HOME4J/bin/neo4j" start >/dev/null
    for _ in $(seq 1 60); do port_open 7687 && break; sleep 2; done
    port_open 7687 || { echo "Neo4j did not start; see $HOME4J/logs" >&2; exit 1; }
    echo "Neo4j running: bolt://127.0.0.1:7687  browser: http://127.0.0.1:7474"
    ;;
  stop)
    if [ -x "$HOME4J/bin/neo4j" ]; then "$HOME4J/bin/neo4j" stop || true; else echo "Neo4j is not installed"; fi
    ;;
  status)
    if port_open 7687; then echo "running"; else echo "stopped"; fi
    ;;
  *)
    echo "usage: scripts/neo4j.sh install|start|stop|status" >&2; exit 2
    ;;
esac
