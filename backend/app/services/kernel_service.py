"""Jupyter kernels for non-Python notebooks (for example the IJava Java kernel).

The built-in ``python3`` entry keeps using the in-process PySpark engine. Any
other kernel is started through ``jupyter_client``. One kernel process is kept
per notebook and language, so variables persist between cells like Jupyter.
"""

from __future__ import annotations

import atexit
import glob
import gzip
import json
import logging
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from jupyter_client.kernelspec import KernelSpecManager
from jupyter_client.manager import KernelManager
from jupyter_core.paths import jupyter_data_dir

from ..config import get_settings
from .cancellation import cancellation_registry
from .jvm_runner import _tool
from .spark_setup import SparkSetupError, resolve_spark_home

logger = logging.getLogger(__name__)

BUILTIN_KERNEL = "python3"
BUILTIN_DISPLAY = "Python 3 (PySpark built-in)"
SQL_KERNEL = "sql"
SQL_DISPLAY = "SQL (Spark SQL built-in)"
JAVA_KERNEL = "java"
IJAVA_VERSION = "1.3.0"
IJAVA_URL = (
    "https://github.com/SpencerPark/IJava/releases/download/"
    f"v{IJAVA_VERSION}/ijava-{IJAVA_VERSION}.zip"
)
SCALA_KERNEL = "scala"
ALMOND_APP = "almond"
ALMOND_INSTALL_TIMEOUT = 1_800
COURSIER_LAUNCHERS = {
    "win32": "https://github.com/coursier/launchers/raw/master/cs-x86_64-pc-win32.zip",
    "linux": "https://github.com/coursier/launchers/raw/master/cs-x86_64-pc-linux.gz",
    "darwin": "https://github.com/coursier/launchers/raw/master/cs-x86_64-apple-darwin.gz",
}
COURSIER_ARM64_LAUNCHERS = {
    "linux": "https://github.com/coursier/launchers/raw/master/cs-aarch64-pc-linux.gz",
    "darwin": "https://github.com/coursier/launchers/raw/master/cs-aarch64-apple-darwin.gz",
}
MAX_OUTPUT_CHARS = 200_000
KERNEL_START_TIMEOUT = 180


class KernelError(RuntimeError):
    """A kernel is missing, failed to start, or cannot run the cell."""


class KernelCancelledError(KernelError):
    """The user interrupted the running cell."""


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _clean(text: str) -> str:
    """Remove terminal color codes and normalise Windows line endings."""

    return _ANSI_ESCAPE.sub("", text).replace("\r\n", "\n")


def is_sql_kernel(kernel_name: Optional[str]) -> bool:
    """Whether a notebook kernel should execute cells as Spark SQL."""

    return bool(kernel_name) and kernel_name.strip().lower() == SQL_KERNEL


def is_builtin(kernel_name: Optional[str]) -> bool:
    return (
        not kernel_name
        or kernel_name in (BUILTIN_KERNEL, "pyspark", SQL_KERNEL)
    )


def _candidate_kernel_dirs() -> List[str]:
    """Kernel folders that are not on Jupyter's default search path.

    Kernels installed into a separate Python (for example Python 3.12's
    ``share/jupyter/kernels``) are found by scanning the usual install roots.
    """

    dirs: List[str] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        pattern = os.path.join(
            local, "Programs", "Python", "Python*", "share", "jupyter", "kernels"
        )
        dirs.extend(sorted(glob.glob(pattern), reverse=True))
    return [d for d in dirs if os.path.isdir(d)]


def _spec_manager() -> KernelSpecManager:
    manager = KernelSpecManager()
    for extra in _candidate_kernel_dirs():
        if extra not in manager.kernel_dirs:
            manager.kernel_dirs.append(extra)
    return manager


def list_kernels() -> Dict[str, Any]:
    """Kernels that a notebook can be bound to (non-Python kernels + built-in)."""

    kernels: List[Dict[str, Any]] = [
        {
            "name": BUILTIN_KERNEL,
            "display_name": BUILTIN_DISPLAY,
            "language": "python",
            "builtin": True,
        },
        {
            "name": SQL_KERNEL,
            "display_name": SQL_DISPLAY,
            "language": "sql",
            "builtin": True,
        },
    ]
    try:
        specs = _spec_manager().get_all_specs()
    except Exception as exc:  # pragma: no cover - broken kernel folders
        logger.warning("Could not enumerate Jupyter kernels: %s", exc)
        specs = {}

    for name, info in sorted(specs.items()):
        spec = info.get("spec", {})
        language = (spec.get("language") or "").lower()
        if name in (BUILTIN_KERNEL, SQL_KERNEL) or language in ("", "python"):
            continue
        kernels.append(
            {
                "name": name,
                "display_name": spec.get("display_name") or name,
                "language": language,
                "builtin": False,
            }
        )

    return {
        "kernels": kernels,
        "java_installed": any(k["language"] == "java" for k in kernels),
        "scala_installed": any(k["language"] == "scala" for k in kernels),
    }


def _user_kernels_dir() -> Path:
    return Path(jupyter_data_dir()) / "kernels"


def _spark_jars_classpath() -> Optional[str]:
    """Classpath glob for the Spark jars the backend already uses.

    IJava resolves simple globs itself and always expects forward slashes, so
    ``<spark home>/jars/*`` puts every Spark/Scala dependency on the kernel's
    compilation and runtime classpath. Without it, cells fail with
    ``package org.apache.spark.sql does not exist``.
    """

    try:
        home = Path(resolve_spark_home()["path"])
    except SparkSetupError as exc:
        logger.warning("Java kernel: Spark is unavailable: %s", exc)
        return None
    jars = home / "jars"
    if not jars.is_dir():
        logger.warning("Java kernel: no jars folder in %s", home)
        return None
    return jars.as_posix() + "/*"


def _spark_kernel_env() -> Dict[str, str]:
    """Environment that gives IJava cells access to the bundled Spark jars."""

    classpath = _spark_jars_classpath()
    if not classpath:
        return {}
    return {"IJAVA_CLASSPATH": classpath}


def install_java_kernel() -> Dict[str, Any]:
    """Download IJava, extract it, and register a ``java`` kernel for this user."""

    if any(k["language"] == "java" for k in list_kernels()["kernels"]):
        return {"installed": False, "already_installed": True, "message": "A Java kernel is already installed."}

    _tool("java")  # the kernel needs a JDK/JRE on PATH or JAVA_HOME

    settings = get_settings()
    settings.ensure_directories()
    workdir = Path(tempfile.mkdtemp(prefix="ijava-", dir=str(settings.spark_local_dir)))
    try:
        archive = workdir / "ijava.zip"
        try:
            with urllib.request.urlopen(IJAVA_URL, timeout=120) as response, archive.open("wb") as out:
                shutil.copyfileobj(response, out)
        except Exception as exc:
            raise KernelError(f"Could not download the IJava kernel from {IJAVA_URL}: {exc}") from exc

        target = _user_kernels_dir() / JAVA_KERNEL
        target.mkdir(parents=True, exist_ok=True)
        jar_name = None
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.namelist():
                if member.endswith(".jar") and os.path.basename(member).startswith("ijava"):
                    data = bundle.read(member)
                    jar_name = os.path.basename(member)
                    (target / jar_name).write_bytes(data)
                    break
        if jar_name is None:
            raise KernelError("The IJava archive did not contain the kernel jar.")

        spec = {
            "argv": [
                "java",
                "--add-exports=java.base/sun.nio.ch=ALL-UNNAMED",
                "--add-opens=java.base/java.lang=ALL-UNNAMED",
                "-jar",
                str(target / jar_name),
                "{connection_file}",
            ],
            "display_name": f"Java (IJava {IJAVA_VERSION})",
            "language": "java",
            "interrupt_mode": "message",
            "env": _spark_kernel_env(),
        }
        (target / "kernel.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
        logger.info("Installed Java kernel into %s", target)
        return {
            "installed": True,
            "already_installed": False,
            "message": f"Installed the Java kernel in {target}.",
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _coursier_launcher_url() -> str:
    machine = platform.machine().lower()
    arm64 = machine in ("arm64", "aarch64")
    if arm64 and sys.platform in COURSIER_ARM64_LAUNCHERS:
        return COURSIER_ARM64_LAUNCHERS[sys.platform]
    return COURSIER_LAUNCHERS.get(sys.platform, "")


def _coursier_executable(workdir: Path) -> Path:
    """Find coursier, downloading its launcher when it is not on PATH."""

    for name in ("cs", "cs.exe", "coursier", "coursier.exe"):
        found = shutil.which(name)
        if found:
            return Path(found)

    url = _coursier_launcher_url()
    if not url:
        raise KernelError(
            "Could not find coursier ('cs') on PATH and no launcher is available "
            f"for this platform ({sys.platform}). Install coursier, then retry."
        )

    archive = workdir / ("cs-launcher.zip" if url.endswith(".zip") else "cs-launcher.gz")
    target = workdir / ("cs.exe" if os.name == "nt" else "cs")
    try:
        with urllib.request.urlopen(url, timeout=120) as response, archive.open("wb") as out:
            shutil.copyfileobj(response, out)
        if url.endswith(".zip"):
            with zipfile.ZipFile(archive) as bundle:
                member = next(
                    (name for name in bundle.namelist() if name.endswith(".exe")), None
                )
                if member is None:
                    raise KernelError("The coursier archive did not contain a launcher.")
                target.write_bytes(bundle.read(member))
        else:
            with gzip.open(archive, "rb") as source, target.open("wb") as out:
                shutil.copyfileobj(source, out)
    except KernelError:
        raise
    except Exception as exc:
        raise KernelError(f"Could not download coursier from {url}: {exc}") from exc
    if os.name != "nt":
        target.chmod(0o755)
    return target


def install_scala_kernel() -> Dict[str, Any]:
    """Install the almond Scala kernel for the current user through coursier."""

    if any(k["language"] == "scala" for k in list_kernels()["kernels"]):
        return {
            "installed": False,
            "already_installed": True,
            "message": "A Scala kernel is already installed.",
        }

    _tool("java")  # almond runs on the JVM

    settings = get_settings()
    settings.ensure_directories()
    workdir = Path(tempfile.mkdtemp(prefix="almond-", dir=str(settings.spark_local_dir)))
    target = _user_kernels_dir() / SCALA_KERNEL
    try:
        cs = _coursier_executable(workdir)
        command = [
            str(cs),
            "launch",
            "--use-bootstrap",
            ALMOND_APP,
            "-M",
            "almond.ScalaKernel",
            "--",
            "--install",
        ]
        env = os.environ.copy()
        env["JUPYTER_DATA_DIR"] = str(_user_kernels_dir().parent)
        try:
            completed = subprocess.run(
                command,
                cwd=str(workdir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=ALMOND_INSTALL_TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            raise KernelError(
                "Installing the Scala kernel timed out after "
                f"{ALMOND_INSTALL_TIMEOUT} seconds. Check your network connection and retry."
            ) from exc
        except OSError as exc:
            raise KernelError(f"Could not run the almond installer: {exc}") from exc

        output = _clean(completed.stdout or "")
        installed = (target / "kernel.json").exists() or any(
            kernel["language"] == "scala" for kernel in list_kernels()["kernels"]
        )
        if not installed:
            detail = output.strip()[-2000:]
            suffix = f" Installer output: {detail}" if detail else ""
            raise KernelError(
                "The almond installer did not register a Scala kernel." + suffix
            )

        logger.info("Installed Scala (almond) kernel into %s", target)
        return {
            "installed": True,
            "already_installed": False,
            "message": f"Installed the Scala (almond) kernel in {target}.",
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


class _KernelSession:
    def __init__(self, kernel_name: str) -> None:
        spec_manager = _spec_manager()
        if kernel_name not in spec_manager.get_all_specs():
            raise KernelError(
                f"Kernel '{kernel_name}' is not installed. Install it first "
                "(Java: 'Install Java kernel' in the notebook toolbar)."
            )
        self.kernel_name = kernel_name
        self.lock = threading.RLock()
        self.manager = KernelManager(kernel_name=kernel_name)
        self.manager.kernel_spec_manager = spec_manager
        env: Optional[Dict[str, str]] = None
        kernel_spec = self.manager.kernel_spec
        if kernel_spec is not None and (kernel_spec.language or "").lower() == "java":
            extra = _spark_kernel_env()
            if extra:
                # The spec env is applied after the launch env, so update both
                # to win over a classpath written by an older installation.
                kernel_spec.env.update(extra)
                env = dict(os.environ)
                env.update(extra)
        self.manager.start_kernel(env=env)
        self.client = self.manager.client()
        self.client.start_channels()
        try:
            self.client.wait_for_ready(timeout=KERNEL_START_TIMEOUT)
        except RuntimeError as exc:
            self.shutdown()
            raise KernelError(f"Kernel '{kernel_name}' did not start: {exc}") from exc

    def shutdown(self) -> None:
        try:
            self.client.stop_channels()
        except Exception:  # pragma: no cover - best effort
            pass
        try:
            self.manager.shutdown_kernel(now=True)
        except Exception:  # pragma: no cover - best effort
            pass


class KernelService:
    """Keeps one running kernel per (notebook, kernel name)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: Dict[str, Dict[str, _KernelSession]] = {}

    def _session(self, notebook_id: str, kernel_name: str) -> _KernelSession:
        with self._lock:
            per_notebook = self._sessions.setdefault(notebook_id, {})
            session = per_notebook.get(kernel_name)
            if session is None:
                session = _KernelSession(kernel_name)
                per_notebook[kernel_name] = session
            return session

    def execute(
        self,
        notebook_id: str,
        kernel_name: str,
        code: str,
        timeout_seconds: Optional[int] = None,
        target: Optional[str] = None,
    ) -> Dict[str, Any]:
        timeout = timeout_seconds or get_settings().query_timeout_seconds
        started = time.perf_counter()
        token = cancellation_registry.begin(target) if target else None

        try:
            session = self._session(notebook_id, kernel_name)

            def interrupt() -> None:
                try:
                    session.manager.interrupt_kernel()
                except Exception:  # pragma: no cover - best effort
                    pass

            if token is not None:
                token.add_callback(interrupt)

            stdout: List[str] = []
            stderr: List[str] = []
            results: List[str] = []
            try:
                with session.lock:
                    msg_id = session.client.execute(
                        code, store_history=True, allow_stdin=False
                    )
                    deadline = time.monotonic() + timeout
                    while True:
                        if token is not None and token.cancelled:
                            interrupt()
                            raise KernelCancelledError("Cell cancelled by user.")
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            interrupt()
                            raise KernelError(
                                f"Cell exceeded the {timeout}s timeout and was interrupted."
                            )
                        try:
                            msg = session.client.get_iopub_msg(
                                timeout=min(remaining, 1.0)
                            )
                        except queue.Empty:
                            continue
                        if msg.get("parent_header", {}).get("msg_id") != msg_id:
                            continue
                        kind = msg["msg_type"]
                        content = msg.get("content", {})
                        if kind == "stream":
                            stream = (
                                stderr
                                if content.get("name") == "stderr"
                                else stdout
                            )
                            stream.append(content.get("text", ""))
                        elif kind in ("execute_result", "display_data"):
                            text = (content.get("data") or {}).get("text/plain")
                            if text:
                                results.append(
                                    text
                                    if isinstance(text, str)
                                    else "".join(text)
                                )
                        elif kind == "error":
                            trace = content.get("traceback") or [
                                f"{content.get('ename', 'Error')}: {content.get('evalue', '')}"
                            ]
                            stderr.append("\n".join(trace) + "\n")
                        elif (
                            kind == "status"
                            and content.get("execution_state") == "idle"
                        ):
                            break
                    if token is not None and token.cancelled:
                        raise KernelCancelledError("Cell cancelled by user.")
            finally:
                if token is not None:
                    token.remove_callback(interrupt)

            out_text = _clean("".join(stdout))[:MAX_OUTPUT_CHARS]
            err_text = _clean("".join(stderr))[:MAX_OUTPUT_CHARS]
            result_text = _clean("\n".join(results)) if results else None
            return {
                "script": code,
                "engine": kernel_name,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "execution_time_ms": round(
                    (time.perf_counter() - started) * 1000, 2
                ),
                "truncated": False,
                "max_rows": 0,
                "stdout": out_text,
                "stderr": err_text,
                "result_type": "text/plain" if result_text else None,
                "result_repr": result_text,
            }
        finally:
            if token is not None:
                cancellation_registry.finish(token)

    def reset(self, notebook_id: str) -> bool:
        with self._lock:
            sessions = self._sessions.pop(notebook_id, {})
        for session in sessions.values():
            session.shutdown()
        return bool(sessions)

    def reset_all(self) -> None:
        with self._lock:
            notebooks = list(self._sessions)
        for notebook_id in notebooks:
            self.reset(notebook_id)


kernel_service = KernelService()
atexit.register(lambda: kernel_service.reset_all())
