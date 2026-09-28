#!/bin/bash
#SBATCH --job-name=e3-mechanism
#SBATCH --partition=B300q
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=experiments/e3_mechanism_v1/logs/%x-%j.out
set -euo pipefail
cd /dataset1/zailong/workspace/agent_protocol_dependency_pilot
export PYTHONPATH="$PWD/src"
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
export VLLM_CACHE_ROOT="$PWD/.cache/vllm"
export TRITON_CACHE_DIR="$PWD/.cache/triton"
export TORCHINDUCTOR_CACHE_DIR="$PWD/.cache/torchinductor"
export XDG_CACHE_HOME="$PWD/.cache"
export OMP_NUM_THREADS=8
export VLLM_USE_FLASHINFER_SAMPLER=0
export PILOT_ALLOCATION_START=$(date +%s)
nvidia-smi
srun .venv/bin/python -u experiments/e3_mechanism_v1/run.py run "${1:-smoke}"
