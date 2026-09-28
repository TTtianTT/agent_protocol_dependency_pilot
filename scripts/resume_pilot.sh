#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -f configs/freeze.json
sbatch scripts/job.slurm pilot
