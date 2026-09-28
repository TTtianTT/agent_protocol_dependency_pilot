#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export PYTHONPATH=src
export MPLCONFIGDIR=.cache/matplotlib
.venv/bin/python experiments/e3_mechanism_v1/run.py analyze
.venv/bin/python experiments/e3_mechanism_v1/stratify.py
.venv/bin/python experiments/e3_mechanism_v1/interpret.py
