from __future__ import annotations

import shutil

import pytest

from app.services import jvm_runner


def test_unsupported_language_is_rejected() -> None:
    with pytest.raises(jvm_runner.JvmRunError):
        jvm_runner.run_jvm_program("python", "print(1)")


def test_empty_program_is_rejected() -> None:
    with pytest.raises(jvm_runner.JvmRunError):
        jvm_runner.run_jvm_program("java", "   ")


@pytest.mark.skipif(shutil.which("javac") is None, reason="JDK not installed")
def test_java_compile_error_is_reported_without_running() -> None:
    result = jvm_runner.run_jvm_program(
        "java",
        "public class Main { public static void main(String[] a) { int x = ; } }",
        timeout_seconds=120,
    )

    assert result["compile_ok"] is False
    assert "error" in result["compile_output"].lower()
    assert result["stdout"] == ""
    assert result["exit_code"] != 0
