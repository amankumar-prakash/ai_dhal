#!/usr/bin/env bash
# Wrap a native supervisord service command with CPU/memory guards.
#
# Usage: run_with_limits.sh <command> [args...]
#
# All limits are read from the environment; 0/unset means "leave the OS
# default". Thread caps must be exported before the Python process imports
# Torch/NumPy, which is exactly what this wrapper does.
set -euo pipefail

# --- CPU thread caps for Torch / OpenMP / BLAS (LLMLingua is the main hog) ---
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-2}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-2}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-2}"

# --- Address-space (virtual memory) cap, in KB (0 = unlimited) ---
LIMIT_AS_KB="${LIMIT_AS_KB:-0}"
if [[ "${LIMIT_AS_KB}" =~ ^[0-9]+$ && "${LIMIT_AS_KB}" -gt 0 ]]; then
  ulimit -v "${LIMIT_AS_KB}" || echo "run_with_limits: ulimit -v ${LIMIT_AS_KB} rejected" >&2
fi

# --- Max user processes/threads (0 = leave default) ---
LIMIT_NPROC="${LIMIT_NPROC:-0}"
if [[ "${LIMIT_NPROC}" =~ ^[0-9]+$ && "${LIMIT_NPROC}" -gt 0 ]]; then
  ulimit -u "${LIMIT_NPROC}" || echo "run_with_limits: ulimit -u ${LIMIT_NPROC} rejected" >&2
fi

# --- Scheduling priority (higher niceness = lower CPU priority) ---
LIMIT_NICE="${LIMIT_NICE:-10}"

if command -v ionice >/dev/null 2>&1; then
  exec nice -n "${LIMIT_NICE}" ionice -c3 "$@"
fi
exec nice -n "${LIMIT_NICE}" "$@"
