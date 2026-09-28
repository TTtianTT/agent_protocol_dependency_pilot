#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
sbatch scripts/job.slurm smoke
