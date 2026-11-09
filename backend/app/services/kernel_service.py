"""Jupyter kernels for non-Python notebooks (for example the IJava Java kernel).

The built-in ``python3`` entry keeps using the in-process PySpark engine. Any
other kernel is started through ``jupyter_client``. One kernel process is kept
per notebook and language, so variables persist between cells like Jupyter.
"""

from __future__ import annotations

import atexit
import glob
import json
import logging
import os
import queue
import re
import shutil
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
from .jvm_runner import _tool

logger = logging.getLogger(__name__)

BUILTIN_KERNEL = "python3"
BUILTIN_DISPLAY = "Python 3 (PySpark built-in)"
JAVA_KERNEL = "java"
IJAVA_VERSION = "1.3.0"
IJAVA_URL = (
    "https://github.com/SpencerPark/IJava/releases/download/"
    f"v{IJAVA_VERSION}/ijava-{IJAVA_VERSION}.zip"
)
MAX_OUTPUT_CHARS = 200_000
KERNEL_START_TIMEOUT = 180


class KernelError(RuntimeError):
    """A kernel is missing, failed to start, or cannot run the cell."""


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _clean(text: str) -> str:
    """Remove terminal color codes and normalise Windows line endings."""

    return _ANSI_ESCAPE.sub("", text).replace("\r\n", "\n")


def is_builtin(kernel_name: Optional[str]) -> bool:
    return not kernel_name or kernel_name in (BUILTIN_KERNEL, "pyspark")


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
        }
    ]
    try:
        specs = _spec_manager().get_all_specs()
    except Exception as exc:  # pragma: no cover - broken kernel folders
        logger.warning("Could not enumerate Jupyter kernels: %s", exc)
        specs = {}

    for name, info in sorted(specs.items()):
        spec = info.get("spec", {})
        language = (spec.get("language") or "").lower()
        if name == BUILTIN_KERNEL or language in ("", "python"):
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
    }


def _user_kernels_dir() -> Path:
    return Path(jupyter_data_dir()) / "kernels"


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
            "env": {},
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
        self.manager.start_kernel()
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
    ) -> Dict[str, Any]:
        timeout = timeout_seconds or get_settings().query_timeout_seconds
        started = time.perf_counter()
        session = self._session(notebook_id, kernel_name)

        stdout: List[str] = []
        stderr: List[str] = []
        results: List[str] = []
        with session.lock:
            msg_id = session.client.execute(code, store_history=True, allow_stdin=False)
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    try:
                        session.manager.interrupt_kernel()
                    except Exception:  # pragma: no cover - best effort
                        pass
                    raise KernelError(f"Cell exceeded the {timeout}s timeout and was interrupted.")
                try:
                    msg = session.client.get_iopub_msg(timeout=min(remaining, 1.0))
                except queue.Empty:
                    continue
                if msg.get("parent_header", {}).get("msg_id") != msg_id:
                    continue
                kind = msg["msg_type"]
                content = msg.get("content", {})
                if kind == "stream":
                    target = stderr if content.get("name") == "stderr" else stdout
                    target.append(content.get("text", ""))
                elif kind in ("execute_result", "display_data"):
                    text = (content.get("data") or {}).get("text/plain")
                    if text:
                        results.append(text if isinstance(text, str) else "".join(text))
                elif kind == "error":
                    trace = content.get("traceback") or [
                        f"{content.get('ename', 'Error')}: {content.get('evalue', '')}"
                    ]
                    stderr.append("\n".join(trace) + "\n")
                elif kind == "status" and content.get("execution_state") == "idle":
                    break

        out_text = _clean("".join(stdout))[:MAX_OUTPUT_CHARS]
        err_text = _clean("".join(stderr))[:MAX_OUTPUT_CHARS]
        result_text = _clean("\n".join(results)) if results else None
        return {
            "script": code,
            "engine": kernel_name,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "execution_time_ms": round((time.perf_counter() - started) * 1000, 2),
            "truncated": False,
            "max_rows": 0,
            "stdout": out_text,
            "stderr": err_text,
            "result_type": "text/plain" if result_text else None,
            "result_repr": result_text,
        }

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
