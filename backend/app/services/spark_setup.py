from __future__ import annotations

import logging
import re
import shutil
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import pyspark

from ..config import get_settings
from .folder_picker import FolderPickerError, pick_directory
from .runtime_settings import (
    clear_runtime_setting,
    get_runtime_setting,
    set_runtime_setting,
)

logger = logging.getLogger(__name__)

SPARK_HOME_KEY = "spark_home"

_RELEASE_RE = re.compile(r"Spark\s+(\d+\.\d+\.\d+)")
_CORE_JAR_RE = re.compile(r"spark-core_2\.\d+-(\d+\.\d+\.\d+)\.jar$")
_SCALA_JAR_RE = re.compile(r"scala-library-(2\.\d+)\.\d+\.jar$")

_DOWNLOAD_LOCK = threading.Lock()
_DOWNLOAD_THREAD: Optional[threading.Thread] = None
_DOWNLOAD_STATE: Dict[str, Any] = {}


class SparkSetupError(RuntimeError):
    """Raised when a Spark installation cannot be selected or installed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def client_version() -> str:
    return pyspark.__version__


def required_major_minor() -> str:
    return ".".join(client_version().split(".")[:2])


def bundled_home() -> Path:
    return Path(pyspark.__file__).resolve().parent


def read_release_version(home: Path) -> Optional[str]:
    release = home / "RELEASE"
    if release.is_file():
        try:
            text = release.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        match = _RELEASE_RE.search(text)
        if match:
            return match.group(1)
    jars = home / "jars"
    if jars.is_dir():
        for jar in jars.glob("spark-core_2.*.jar"):
            match = _CORE_JAR_RE.search(jar.name)
            if match:
                return match.group(1)
    return None


def read_scala_version(home: Path) -> Optional[str]:
    jars = home / "jars"
    if not jars.is_dir():
        return None
    for jar in jars.glob("scala-library-*.jar"):
        match = _SCALA_JAR_RE.search(jar.name)
        if match:
            return match.group(1)
    return None


def describe_spark_home(path: str | Path) -> Dict[str, Any]:
    """Inspect a candidate Spark home and report whether this backend can use it."""

    resolved = Path(path).expanduser()
    info: Dict[str, Any] = {
        "path": str(resolved),
        "exists": resolved.exists(),
        "valid": False,
        "version": None,
        "scala_version": None,
        "compatible": False,
        "reason": None,
    }

    if not info["exists"]:
        info["reason"] = "Path does not exist."
        return info
    if not resolved.is_dir():
        info["reason"] = "Path is not a directory."
        return info

    has_layout = (resolved / "jars").is_dir() and (resolved / "bin").is_dir()
    if not has_layout:
        info["reason"] = (
            "Not an Apache Spark installation (missing 'jars' or 'bin' folder)."
        )
        return info

    info["valid"] = True
    info["version"] = read_release_version(resolved)
    info["scala_version"] = read_scala_version(resolved)

    client = client_version()
    required = required_major_minor()

    if not info["version"]:
        info["reason"] = "Could not determine the Spark version of this folder."
        return info
    if not info["version"].startswith(required + "."):
        info["reason"] = (
            f"Spark {info['version']} is not compatible with this backend, which "
            f"runs PySpark {client} and requires Spark {required}.x."
        )
        return info
    if info["scala_version"] and info["scala_version"] != "2.13":
        info["reason"] = (
            f"Spark {info['version']} is built for Scala {info['scala_version']}, "
            "but the Delta/Iceberg connectors require Scala 2.13."
        )
        return info

    info["compatible"] = True
    return info


def _configured_home() -> tuple[Optional[str], str]:
    runtime_home = get_runtime_setting(SPARK_HOME_KEY)
    if runtime_home:
        return runtime_home, "runtime"
    settings = get_settings()
    if settings.spark_home:
        return str(settings.spark_home), "env"
    return None, "bundled"


def resolve_spark_home() -> Dict[str, Any]:
    """Return the Spark home the session should use, plus its inspection info.

    Raises :class:`SparkSetupError` when an explicitly configured home is
    invalid or incompatible with the installed PySpark client.
    """

    configured, source = _configured_home()
    if configured is None:
        info = describe_spark_home(bundled_home())
        info["source"] = "bundled"
        return info

    info = describe_spark_home(configured)
    info["source"] = source
    if not info["valid"]:
        raise SparkSetupError(
            f"Configured Spark home '{configured}' is not usable: {info['reason']}"
        )
    if not info["compatible"]:
        raise SparkSetupError(
            f"Configured Spark home '{configured}' is incompatible: {info['reason']}"
        )
    return info


def get_spark_config() -> Dict[str, Any]:
    from ..spark_manager import spark_manager

    settings = get_settings()
    configured, source = _configured_home()

    effective = describe_spark_home(configured) if configured else describe_spark_home(
        bundled_home()
    )
    effective["source"] = source

    return {
        "pyspark_version": client_version(),
        "required_spark_version": required_major_minor() + ".x",
        "bundled_home": str(bundled_home()),
        "bundled_version": read_release_version(bundled_home()) or client_version(),
        "configured_home": configured,
        "configured_source": source,
        "effective": effective,
        "download_dir": str(settings.spark_dist_dir),
        "download_available_version": client_version(),
        "spark_started": spark_manager.is_started,
        "spark_version": spark_manager.version,
    }


def _restart_session() -> None:
    from ..spark_manager import spark_manager

    with spark_manager.sql_lock:
        spark_manager.stop()


def set_spark_home(path: str) -> Dict[str, Any]:
    info = describe_spark_home(path)
    if not info["valid"]:
        raise SparkSetupError(info["reason"] or "Not a valid Spark installation.")
    if not info["compatible"]:
        raise SparkSetupError(info["reason"] or "This Spark version is not compatible.")

    resolved = str(Path(path).expanduser().resolve())
    set_runtime_setting(SPARK_HOME_KEY, resolved)
    _restart_session()
    logger.info("Using external Spark home: %s", resolved)
    return get_spark_config()


def clear_spark_home() -> Dict[str, Any]:
    clear_runtime_setting(SPARK_HOME_KEY)
    _restart_session()
    logger.info("Reverted to the Spark home bundled with PySpark")
    return get_spark_config()


def browse_for_spark_home() -> Optional[str]:
    """Open a native folder picker on the backend machine.

    Returns the selected path, or ``None`` if the user cancelled. Raises
    :class:`SparkSetupError` when no graphical session is available.
    """

    try:
        return pick_directory("Select your Apache Spark installation folder")
    except FolderPickerError as exc:
        raise SparkSetupError(str(exc)) from exc


# --- optional download & install -------------------------------------------


def _empty_download_state() -> Dict[str, Any]:
    return {
        "state": "idle",
        "version": None,
        "url": None,
        "destination": None,
        "downloaded_bytes": 0,
        "total_bytes": 0,
        "percent": 0.0,
        "speed_bps": 0.0,
        "message": "",
        "error": None,
        "installed_path": None,
        "started_at": None,
        "finished_at": None,
    }


def _update_download(**values: Any) -> None:
    with _DOWNLOAD_LOCK:
        _DOWNLOAD_STATE.update(values)


def get_download_status() -> Dict[str, Any]:
    with _DOWNLOAD_LOCK:
        if not _DOWNLOAD_STATE:
            return _empty_download_state()
        return dict(_DOWNLOAD_STATE)


def _download_url(version: str) -> str:
    return (
        "https://archive.apache.org/dist/spark/"
        f"spark-{version}/spark-{version}-bin-hadoop3.tgz"
    )


def start_download(
    version: Optional[str] = None, destination: Optional[str] = None
) -> Dict[str, Any]:
    global _DOWNLOAD_THREAD

    required = required_major_minor()
    target_version = (version or client_version()).strip()
    if not target_version.startswith(required + "."):
        raise SparkSetupError(
            f"Only Spark {required}.x can be installed because this backend runs "
            f"PySpark {client_version()}."
        )

    settings = get_settings()
    dest_root = (
        Path(destination).expanduser() if destination else settings.spark_dist_dir
    )
    dest_root.mkdir(parents=True, exist_ok=True)

    with _DOWNLOAD_LOCK:
        if _DOWNLOAD_THREAD is not None and _DOWNLOAD_THREAD.is_alive():
            raise SparkSetupError("A Spark download is already in progress.")
        _DOWNLOAD_STATE.clear()
        _DOWNLOAD_STATE.update(_empty_download_state())
        _DOWNLOAD_STATE.update(
            {
                "state": "starting",
                "version": target_version,
                "url": _download_url(target_version),
                "destination": str(dest_root),
                "message": "Preparing download…",
            }
        )

    thread = threading.Thread(
        target=_download_worker,
        args=(target_version, dest_root),
        name="spark-download",
        daemon=True,
    )
    _DOWNLOAD_THREAD = thread
    thread.start()
    return get_download_status()


def _safe_extract(archive: Path, target_dir: Path) -> Path:
    import tarfile

    tmp = target_dir / (".extract-" + uuid.uuid4().hex)
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar.getmembers():
                member_path = (tmp / member.name).resolve()
                if not str(member_path).startswith(str(tmp.resolve())):
                    raise SparkSetupError(
                        "Refusing to extract an archive with unsafe paths."
                    )
                if member.issym() or member.islnk():
                    continue
                tar.extract(member, tmp)
        entries = [entry for entry in tmp.iterdir()]
        if len(entries) != 1 or not entries[0].is_dir():
            raise SparkSetupError("Unexpected Spark archive layout.")
        return entries[0]
    finally:
        shutil.rmtree(tmp, ignore_errors=True) if tmp.exists() and not any(
            tmp.iterdir()
        ) else None


def _download_worker(version: str, dest_root: Path) -> None:
    archive = dest_root / f"spark-{version}-bin-hadoop3.tgz"
    part = archive.with_suffix(archive.suffix + ".part")
    url = _download_url(version)
    started = time.perf_counter()

    try:
        _update_download(state="running", message="Downloading Spark…")
        request = urllib.request.Request(
            url, headers={"User-Agent": "open-lakehouse-workbench"}
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            total = int(response.headers.get("Content-Length") or 0)
            _update_download(total_bytes=total)
            downloaded = 0
            with part.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    elapsed = max(time.perf_counter() - started, 0.001)
                    _update_download(
                        downloaded_bytes=downloaded,
                        percent=round(downloaded / total * 100, 2) if total else 0.0,
                        speed_bps=round(downloaded / elapsed, 1),
                    )

        part.replace(archive)
        _update_download(
            state="extracting",
            message="Extracting Spark archive…",
            percent=100.0,
        )

        spark_dir = _safe_extract(archive, dest_root)
        final_dir = dest_root / f"spark-{version}-bin-hadoop3"
        if final_dir.exists():
            shutil.rmtree(final_dir, ignore_errors=True)
        shutil.move(str(spark_dir), str(final_dir))

        _update_download(
            state="installing",
            message="Activating the downloaded Spark installation…",
        )
        set_runtime_setting(SPARK_HOME_KEY, str(final_dir.resolve()))
        _restart_session()

        logger.info("Installed Spark %s at %s", version, final_dir)
        _update_download(
            state="done",
            message="Spark installed and selected.",
            installed_path=str(final_dir.resolve()),
            finished_at=_utc_now(),
        )
    except Exception as exc:  # pragma: no cover - network/environment dependent
        logger.exception("Spark download failed")
        with _DOWNLOAD_LOCK:
            if _DOWNLOAD_STATE.get("started_at") is None:
                _DOWNLOAD_STATE["started_at"] = _utc_now()
        _update_download(
            state="error",
            error=str(exc),
            message="Download failed.",
            finished_at=_utc_now(),
        )
    finally:
        try:
            if part.exists():
                part.unlink()
        except OSError:  # pragma: no cover - best effort
            pass
        with _DOWNLOAD_LOCK:
            if _DOWNLOAD_STATE.get("started_at") is None:
                _DOWNLOAD_STATE["started_at"] = _utc_now()
