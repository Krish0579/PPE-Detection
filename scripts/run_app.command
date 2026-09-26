#!/bin/bash
# =============================================================================
# SAFE SIGHT — double-click launcher for macOS
# =============================================================================
# Double-clicking this file runs the app inside Terminal.app, which means
# macOS camera permission can be granted to Terminal and OpenCV hardware
# capture will work (a server launched by another host app cannot get it).
#
# One-time setup if the live feed shows "SIMULATED":
#   System Settings → Privacy & Security → Camera → enable Terminal,
#   then quit this window and double-click this file again.
# =============================================================================
set -e
cd "$(dirname "$0")/.."

echo "=============================================="
echo " SAFE SIGHT — starting on http://localhost:8501"
echo "=============================================="
echo "If the live feed reports 'SIMULATED · DEMO FEED':"
echo "  1. System Settings → Privacy & Security → Camera → enable Terminal"
echo "  2. Close this window and double-click run_app.command again"
echo "  (or run:  tccutil reset Camera  in Terminal, then Start Camera)"
echo ""

exec .venv/bin/streamlit run app.py --server.headless false --server.port 8501
