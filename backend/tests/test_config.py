from __future__ import annotations

import os
import sys

from app.config import ensure_pyspark_python


def test_defaults_to_backend_interpreter(monkeypatch) -> None:
    monkeypatch.delenv("PYSPARK_PYTHON", raising=False)
    monkeypatch.delenv("PYSPARK_DRIVER_PYTHON", raising=False)

    result = ensure_pyspark_python()

    assert result == sys.executable
    assert os.environ["PYSPARK_PYTHON"] == sys.executable
    assert os.environ["PYSPARK_DRIVER_PYTHON"] == sys.executable


def test_keeps_working_python(monkeypatch) -> None:
    monkeypatch.setenv("PYSPARK_PYTHON", sys.executable)

    assert ensure_pyspark_python() == sys.executable


def test_replaces_missing_python(monkeypatch) -> None:
    # Reproduces the Windows failure mode: PySpark's default ``python3`` is not
    # an executable on this machine, so the backend must fall back to itself.
    monkeypatch.setenv("PYSPARK_PYTHON", "python3-does-not-exist-xyz")

    assert ensure_pyspark_python() == sys.executable


def test_keeps_explicit_driver_python(monkeypatch) -> None:
    monkeypatch.delenv("PYSPARK_PYTHON", raising=False)
    monkeypatch.setenv("PYSPARK_DRIVER_PYTHON", "ipython")

    ensure_pyspark_python()

    assert os.environ["PYSPARK_DRIVER_PYTHON"] == "ipython"
