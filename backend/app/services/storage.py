from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..config import get_settings


class StoragePathError(ValueError):
    pass


class StorageNotFoundError(FileNotFoundError):
    pass


_SUFFIX_CATEGORIES = {
    ".parquet": "parquet",
    ".avro": "avro",
    ".json": "json",
    ".orc": "orc",
    ".csv": "csv",
    ".crc": "checksum",
    ".db": "database",
    ".log": "log",
    ".txt": "text",
    ".gz": "archive",
    ".zip": "archive",
}

# Binary formats we never decode as text in the preview endpoint.
_BINARY_SUFFIXES = {
    ".parquet",
    ".orc",
    ".avro",
    ".db",
    ".gz",
    ".zip",
    ".jar",
    ".class",
    ".snappy",
    ".zst",
    ".lz4",
    ".bin",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
}

_LANGUAGE_BY_SUFFIX = {
    ".json": "json",
    ".jsonl": "json",
    ".log": "log",
    ".csv": "csv",
    ".tsv": "csv",
    ".md": "markdown",
    ".markdown": "markdown",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def _category_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in _SUFFIX_CATEGORIES:
        return _SUFFIX_CATEGORIES[suffix]
    return suffix.lstrip(".") or "other"


def _language_for(path: Path) -> str:
    return _LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "text")


def _iso_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _resolve_target(relative_path: str) -> Tuple[Path, Path, str]:
    settings = get_settings()
    root = settings.warehouse_dir.resolve()
    normalized = (relative_path or "").strip().replace("\\", "/").strip("/")
    target = (root / normalized).resolve()

    try:
        target.relative_to(root)
    except ValueError as exc:
        raise StoragePathError("Path escapes the lakehouse warehouse directory.") from exc

    if not target.exists():
        raise StorageNotFoundError(normalized or ".")
    if not target.is_dir():
        raise StoragePathError("The storage explorer can only open directories.")
    return root, target, normalized


def _has_children(path: Path) -> bool:
    try:
        with os.scandir(path) as entries:
            return next(entries, None) is not None
    except OSError:
        return False


def explore_storage(
    relative_path: str = "",
    depth: Optional[int] = None,
    max_entries: Optional[int] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    root, target, normalized = _resolve_target(relative_path)

    max_depth = settings.storage_max_depth if depth is None else max(0, depth)
    entry_limit = settings.storage_max_entries if max_entries is None else max_entries
    max_depth = min(max_depth, 12)
    entry_limit = max(1, min(entry_limit, 50_000))

    summary: Dict[str, Any] = {
        "files": 0,
        "directories": 0,
        "bytes": 0,
        "by_category": {},
        "truncated": False,
        "max_entries": entry_limit,
        "max_depth": max_depth,
    }
    counter = {"entries": 0}

    tree = _scan_directory(
        target,
        relative=normalized,
        depth=0,
        max_depth=max_depth,
        entry_limit=entry_limit,
        counter=counter,
        summary=summary,
    )

    if normalized == "":
        tree["name"] = root.name or "data_warehouse"

    return {
        "root": str(root),
        "path": normalized,
        "tree": tree,
        "summary": summary,
    }


def resolve_storage_file(relative_path: str) -> Tuple[Path, str]:
    """Resolve a warehouse-relative file path for preview or download.

    Paths are resolved against ``warehouse_dir`` and must stay inside it, so the
    storage endpoints can never expose arbitrary files from the host machine.
    """

    root = get_settings().warehouse_dir.resolve()
    normalized = (relative_path or "").strip().replace("\\", "/").strip("/")
    if not normalized:
        raise StoragePathError("A file path is required.")

    target = (root / normalized).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise StoragePathError(
            "Path escapes the lakehouse warehouse directory."
        ) from exc

    if not target.exists():
        raise StorageNotFoundError(normalized)
    if not target.is_file():
        raise StoragePathError("The storage explorer can only open files.")
    return target, normalized


def read_storage_file(relative_path: str) -> Dict[str, Any]:
    """Read a warehouse file for the read-only storage preview."""

    settings = get_settings()
    target, normalized = resolve_storage_file(relative_path)

    size = target.stat().st_size
    max_bytes = max(1, settings.storage_preview_max_bytes)
    binary = target.suffix.lower() in _BINARY_SUFFIXES
    truncated = False
    data = b""

    if not binary:
        try:
            with target.open("rb") as handle:
                data = handle.read(max_bytes + 1)
        except OSError as exc:
            raise StoragePathError(f"Could not read file: {exc}") from exc
        if len(data) > max_bytes:
            data = data[:max_bytes]
            truncated = True
        # NUL bytes are a reliable signal for binary content that slipped past
        # the extension allow-list (e.g. an extension-less data file).
        if b"\x00" in data[:8192]:
            binary = True

    return {
        "path": normalized,
        "name": target.name,
        "content": "" if binary else data.decode("utf-8", errors="replace"),
        "language": _language_for(target),
        "size": size,
        "binary": binary,
        "truncated": truncated,
        "max_bytes": max_bytes,
    }


def _scan_directory(
    directory: Path,
    relative: str,
    depth: int,
    max_depth: int,
    entry_limit: int,
    counter: Dict[str, int],
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    stat = directory.stat()
    node: Dict[str, Any] = {
        "name": directory.name,
        "path": relative,
        "type": "directory",
        "size": 0,
        "modified": _iso_timestamp(stat.st_mtime),
        "extension": None,
        "category": None,
        "children": [],
        "truncated": False,
    }
    summary["directories"] += 1

    try:
        with os.scandir(directory) as iterator:
            entries = sorted(
                iterator,
                key=lambda entry: (
                    not entry.is_dir(follow_symlinks=False),
                    entry.name.lower(),
                ),
            )
    except OSError:
        node["truncated"] = True
        return node

    child_size = 0
    for entry in entries:
        if counter["entries"] >= entry_limit:
            summary["truncated"] = True
            node["truncated"] = True
            break
        if entry.is_symlink():
            continue

        counter["entries"] += 1
        child_relative = f"{relative}/{entry.name}" if relative else entry.name
        try:
            entry_stat = entry.stat(follow_symlinks=False)
        except OSError:
            continue

        if entry.is_dir(follow_symlinks=False):
            if depth < max_depth:
                child = _scan_directory(
                    Path(entry.path),
                    relative=child_relative,
                    depth=depth + 1,
                    max_depth=max_depth,
                    entry_limit=entry_limit,
                    counter=counter,
                    summary=summary,
                )
            else:
                child = {
                    "name": entry.name,
                    "path": child_relative,
                    "type": "directory",
                    "size": 0,
                    "modified": _iso_timestamp(entry_stat.st_mtime),
                    "extension": None,
                    "category": None,
                    "children": [],
                    "truncated": _has_children(Path(entry.path)),
                }
            child_size += child["size"]
            node["children"].append(child)
            continue

        category = _category_for(Path(entry.name))
        file_node = {
            "name": entry.name,
            "path": child_relative,
            "type": "file",
            "size": entry_stat.st_size,
            "modified": _iso_timestamp(entry_stat.st_mtime),
            "extension": Path(entry.name).suffix.lower() or None,
            "category": category,
            "children": [],
            "truncated": False,
        }
        child_size += entry_stat.st_size
        node["children"].append(file_node)

        summary["files"] += 1
        summary["bytes"] += entry_stat.st_size
        bucket = summary["by_category"].setdefault(
            category, {"files": 0, "bytes": 0}
        )
        bucket["files"] += 1
        bucket["bytes"] += entry_stat.st_size

    node["size"] = child_size
    return node
