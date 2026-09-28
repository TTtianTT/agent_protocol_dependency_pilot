#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src"
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
.venv/bin/python -m protocol_pilot.reporting
.venv/bin/python scripts/supplement_report.py
.venv/bin/python scripts/finalize_report.py
.venv/bin/python scripts/audit_completed.py
