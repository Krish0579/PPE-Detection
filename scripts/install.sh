#!/usr/bin/env bash
# =============================================================================
# SAFE SIGHT AI — site installer (macOS / Linux)
# One command: ./scripts/install.sh  — then: streamlit run app.py
# M3 "site ready" support: venv + locked deps + model check + readiness gate.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

PYBIN="${PYTHON:-python3}"
echo "==> Checking Python..."
if ! "$PYBIN" -c 'import sys; assert (3,10) <= sys.version_info < (3,13)' 2>/dev/null; then
  echo "ERROR: Python 3.10–3.12 required (found: $("$PYBIN" --version 2>&1))."
  exit 1
fi

echo "==> Creating virtualenv (.venv)..."
"$PYBIN" -m venv .venv

echo "==> Installing locked runtime dependencies..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements-lock.txt

if [ ! -f "models/best.pt" ]; then
  echo "ERROR: models/best.pt missing — copy a reviewed checkpoint here first."
  exit 1
fi
echo "==> Model checkpoint present: $(du -h models/best.pt | cut -f1)"

echo "==> Running production readiness gate..."
.venv/bin/python scripts/prod_readiness_check.py

echo ""
echo "INSTALL OK. Launch with:"
echo "  .venv/bin/streamlit run app.py          # browser UI on :8501"
echo "  .venv/bin/python desktop.py             # native desktop app (needs PySide6)"
echo "  ./scripts/run_app.command               # macOS double-click launcher"
