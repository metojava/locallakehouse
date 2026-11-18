#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

# Spark's Python workers should use the same interpreter and packages as the
# backend rather than whatever `python3` happens to resolve to on PATH.
export PYSPARK_PYTHON="$PWD/.venv/bin/python"
export PYSPARK_DRIVER_PYTHON="$PYSPARK_PYTHON"

# Install the optional notebook kernels (IJava, almond) before the backend
# starts. A failure must not keep the backend from running: kernels can also
# be installed later from the notebook toolbar.
if [ "${NO_KERNELS:-0}" != "1" ]; then
  echo "Installing missing notebook kernels (Java, Scala)..."
  echo "The first Scala install downloads almond and can take several minutes."
  .venv/bin/python install_kernels.py || \
    echo "Warning: notebook kernel installation failed. Install kernels later from the notebook toolbar." >&2
fi

exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}" --reload
