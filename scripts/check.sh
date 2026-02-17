#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHONPATH=src python3 -m unittest discover -s tests -v

if command -v ruff >/dev/null 2>&1; then
  ruff check src tests examples
else
  echo "[warn] ruff not installed; skipping lint"
fi

if command -v mypy >/dev/null 2>&1; then
  mypy src/qrt_platform
else
  echo "[warn] mypy not installed; skipping type-check"
fi
