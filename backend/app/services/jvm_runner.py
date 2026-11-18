"""Compile and run Java or Scala programs against the local Spark installation.

Unlike PySpark cells, every run is an independent JVM process started with
``spark-submit``. Nothing is shared between runs: each program builds its own
SparkSession. The embedded Derby Hive metastore is locked by the backend
session, so runs use an in-memory catalog instead. Delta and Iceberg tables
remain reachable by path (``delta.`path``` and ``local_iceberg`` tables on
disk) but tables registered only in the backend metastore are not visible.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import get_settings
from .cancellation import CancelToken, cancellation_registry
from .spark_setup import SparkSetupError, resolve_spark_home

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("java", "scala")
MAX_OUTPUT_CHARS = 200_000
DEFAULT_TIMEOUT_SECONDS = 600


class JvmRunError(RuntimeError):
    """The runner itself could not start (missing JDK, Spark, or bad input)."""


class JvmRunCancelled(JvmRunError):
    """The user cancelled the compile or run."""


_SUBMIT_NOISE = (
    "WARNING: Using incubator",
    "Ivy Default Cache",
    "The jars for the packages",
    ":: ",
    "\tfound ",
    "\tconfs:",
    "\tcom.",
    "\torg.",
    "\tio.",
    "\tjavax.",
    "\t|",
    "\t:: ",
    "\t---",
    "\t0 artifacts",
    "\tfound",
    "\tconfs",
)


def _strip_submit_noise(text: str) -> str:
    kept = [
        line
        for line in text.splitlines()
        if not line.startswith(_SUBMIT_NOISE)
        and not line.endswith("added as a dependency")
    ]
    return "\n".join(kept) + ("\n" if kept else "")


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n… output truncated …"


def _tool(name: str) -> str:
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / "bin" / (name + (".exe" if os.name == "nt" else ""))
        if candidate.exists():
            return str(candidate)
    found = shutil.which(name)
    if not found:
        raise JvmRunError(f"'{name}' was not found. Install a JDK 17+ and set JAVA_HOME.")
    return found


def _spark_paths() -> Dict[str, Path]:
    try:
        home = Path(resolve_spark_home()["path"])
    except SparkSetupError as exc:
        raise JvmRunError(str(exc)) from exc
    jars = home / "jars"
    submit = home / "bin" / ("spark-submit.cmd" if os.name == "nt" else "spark-submit")
    if not jars.is_dir() or not submit.exists():
        raise JvmRunError(f"Spark installation at {home} has no jars or spark-submit.")
    return {"home": home, "jars": jars, "submit": submit}


def _spark_conf(settings: Any) -> List[str]:
    """Spark settings mirroring the backend session, minus the Derby metastore."""

    pairs = {
        "spark.sql.catalogImplementation": "in-memory",
        "spark.sql.warehouse.dir": settings.delta_warehouse_dir.as_uri(),
        "spark.sql.session.timeZone": "UTC",
        "spark.sql.defaultCatalog": "spark_catalog",
        "spark.sql.shuffle.partitions": "8",
        "spark.sql.extensions": ",".join(
            (
                "io.delta.sql.DeltaSparkSessionExtension",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
            )
        ),
        "spark.sql.catalog.spark_catalog": "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        "spark.sql.catalog.local_iceberg": "org.apache.iceberg.spark.SparkCatalog",
        "spark.sql.catalog.local_iceberg.type": "hadoop",
        "spark.sql.catalog.local_iceberg.warehouse": settings.iceberg_warehouse_dir.as_uri(),
        "spark.ui.enabled": "false",
        "spark.driver.host": "127.0.0.1",
        "spark.driver.bindAddress": "127.0.0.1",
        "spark.local.dir": str(settings.spark_local_dir),
        "spark.driver.memory": settings.spark_driver_memory,
    }
    args: List[str] = []
    for key, value in pairs.items():
        args += ["--conf", f"{key}={value}"]
    return args


def _write_jar(classes_dir: Path, jar_path: Path) -> None:
    with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as jar:
        for file in classes_dir.rglob("*"):
            if file.is_file():
                jar.write(file, file.relative_to(classes_dir).as_posix())


def _kill_process(process: subprocess.Popen[str]) -> None:
    """Kill a process tree (spark-submit.cmd spawns java on Windows)."""

    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
            )
        else:
            process.kill()
    except Exception:  # pragma: no cover - best effort cancellation
        try:
            process.kill()
        except Exception:
            pass


def _run(
    cmd: List[str],
    cwd: Path,
    timeout: int,
    env: Optional[Dict[str, str]] = None,
    token: Optional[CancelToken] = None,
) -> Dict[str, Any]:
    started = time.perf_counter()
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    def kill() -> None:
        _kill_process(process)

    if token is not None:
        token.add_callback(kill)

    deadline = time.monotonic() + timeout
    cancelled = False
    timed_out = False
    stdout = ""
    stderr = ""
    try:
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                if token is not None and token.cancelled:
                    cancelled = True
                    kill()
                    stdout, stderr = process.communicate()
                    break
                if time.monotonic() >= deadline:
                    timed_out = True
                    kill()
                    stdout, stderr = process.communicate()
                    break
        if token is not None and token.cancelled:
            cancelled = True
    finally:
        if token is not None:
            token.remove_callback(kill)

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    if cancelled:
        return {
            "exit_code": None,
            "stdout": _truncate(stdout or ""),
            "stderr": "Run cancelled by user.",
            "timed_out": False,
            "cancelled": True,
            "duration_ms": duration_ms,
        }
    if timed_out:
        return {
            "exit_code": None,
            "stdout": _truncate(stdout or ""),
            "stderr": f"Process exceeded the {timeout}s timeout and was killed.",
            "timed_out": True,
            "cancelled": False,
            "duration_ms": duration_ms,
        }
    return {
        "exit_code": process.returncode,
        "stdout": _truncate(stdout or ""),
        "stderr": _truncate(stderr or ""),
        "timed_out": False,
        "cancelled": False,
        "duration_ms": duration_ms,
    }


def run_jvm_program(
    language: str,
    source: str,
    timeout_seconds: Optional[int] = None,
    target: Optional[str] = None,
) -> Dict[str, Any]:
    """Compile ``source`` (class/object ``Main``) and run it with spark-submit."""

    if language not in SUPPORTED_LANGUAGES:
        raise JvmRunError(f"Unsupported language '{language}'.")
    if not source.strip():
        raise JvmRunError("The program is empty.")

    settings = get_settings()
    settings.ensure_directories()
    timeout = timeout_seconds or DEFAULT_TIMEOUT_SECONDS
    started = time.perf_counter()
    token = cancellation_registry.begin(target) if target else None

    try:
        paths = _spark_paths()
        jars = sorted(str(p) for p in paths["jars"].glob("*.jar"))
        jar_classpath = str(paths["jars"] / "*")

        work = Path(
            tempfile.mkdtemp(prefix="jvm-run-", dir=str(settings.spark_local_dir))
        )
        try:
            source_file = work / (
                "Main.java" if language == "java" else "Main.scala"
            )
            source_file.write_text(source.lstrip("\ufeff"), encoding="utf-8")
            classes = work / "classes"
            classes.mkdir()

            # Compile.
            if language == "java":
                compile_cmd = [
                    _tool("javac"),
                    "-d",
                    str(classes),
                    "-cp",
                    jar_classpath,
                    str(source_file),
                ]
            else:
                args_file = work / "scalac-args.txt"
                args_file.write_text(
                    "\n".join(
                        [
                            "-usejavacp",
                            "-classpath",
                            os.pathsep.join(jars),
                            "-d",
                            str(classes),
                            str(source_file),
                        ]
                    ),
                    encoding="utf-8",
                )
                compile_cmd = [
                    _tool("java"),
                    "-cp",
                    jar_classpath,
                    "scala.tools.nsc.Main",
                    f"@{args_file}",
                ]

            compiled = _run(compile_cmd, work, timeout, token=token)
            if compiled.get("cancelled"):
                raise JvmRunCancelled("Run cancelled by user.")
            compile_output = (compiled["stdout"] + compiled["stderr"]).strip()
            if compiled["timed_out"] or compiled["exit_code"] != 0:
                return {
                    "language": language,
                    "compile_ok": False,
                    "compile_output": compile_output or "Compilation failed.",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": compiled["exit_code"],
                    "execution_time_ms": round(
                        (time.perf_counter() - started) * 1000, 2
                    ),
                }

            # Package and submit.
            jar_path = work / "app.jar"
            _write_jar(classes, jar_path)

            submit_cmd = [
                str(paths["submit"]),
                "--master",
                settings.spark_master,
                "--name",
                f"{settings.spark_app_name}-{language}",
                "--class",
                "Main",
                "--driver-memory",
                settings.spark_driver_memory,
                "--packages",
                settings.spark_packages,
            ]
            if settings.spark_jars:
                submit_cmd += ["--jars", settings.spark_jars]
            submit_cmd += _spark_conf(settings)
            submit_cmd.append(str(jar_path))

            env = dict(os.environ)
            env["SPARK_HOME"] = str(paths["home"])
            ran = _run(submit_cmd, work, timeout, env=env, token=token)
            if ran.get("cancelled"):
                raise JvmRunCancelled("Run cancelled by user.")
            ran["stderr"] = _strip_submit_noise(ran["stderr"])
            logger.info(
                "Ran %s program: exit=%s duration=%.0fms",
                language,
                ran["exit_code"],
                ran["duration_ms"],
            )
            return {
                "language": language,
                "compile_ok": True,
                "compile_output": compile_output,
                "stdout": ran["stdout"],
                "stderr": ran["stderr"],
                "exit_code": ran["exit_code"],
                "execution_time_ms": round(
                    (time.perf_counter() - started) * 1000, 2
                ),
            }
        finally:
            shutil.rmtree(work, ignore_errors=True)
    finally:
        if token is not None:
            cancellation_registry.finish(token)
