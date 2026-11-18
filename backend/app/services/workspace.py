from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .folder_picker import FolderPickerError, pick_directory
from .runtime_settings import (
    clear_runtime_setting,
    get_runtime_setting,
    set_runtime_setting,
)

logger = logging.getLogger(__name__)

WORKSPACE_ROOT_KEY = "workspace_root"

_MAX_TREE_ENTRIES = 5_000
_MAX_TEXT_BYTES = 5 * 1024 * 1024

_SKIP_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".idea",
    ".vscode",
    "__pycache__",
    "node_modules",
    ".venv",
    ".venv-corrupted",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}

_TEXT_EXTENSIONS = {
    ".txt",
    ".text",
    ".md",
    ".markdown",
    ".json",
    ".jsonl",
    ".csv",
    ".tsv",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".log",
    ".py",
    ".ipynb",
    ".sql",
    ".r",
    ".scala",
    ".sh",
    ".bat",
    ".ps1",
    ".html",
    ".htm",
    ".css",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}

_LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".ipynb": "python",
    ".sql": "sql",
    ".json": "json",
    ".jsonl": "json",
    ".csv": "csv",
    ".tsv": "csv",
    ".md": "markdown",
    ".markdown": "markdown",
    ".html": "html",
    ".htm": "html",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".css": "css",
    ".sh": "shell",
    ".bat": "shell",
    ".ps1": "shell",
}


class WorkspaceError(RuntimeError):
    """General workspace problem (no root, missing file, invalid input)."""


class WorkspacePathError(WorkspaceError):
    """A requested path escapes the workspace root."""


class WorkspaceNotFoundError(WorkspaceError):
    """A requested file does not exist."""


def _resolve_root() -> Path:
    raw = get_runtime_setting(WORKSPACE_ROOT_KEY)
    if not raw:
        raise WorkspaceError("No workspace folder is open. Choose a folder first.")
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise WorkspaceError(f"Workspace folder no longer exists: {root}")
    return root


def _resolve_inside(root: Path, relative: str) -> Path:
    relative = (relative or "").strip().replace("\\", "/")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise WorkspacePathError("Path is outside the workspace folder.") from exc
    return candidate


def open_workspace(path: str) -> Dict[str, Any]:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise WorkspaceError(f"Not a directory: {root}")
    set_runtime_setting(WORKSPACE_ROOT_KEY, str(root))
    logger.info("Opened workspace folder %s", root)
    return describe_workspace()


def pick_workspace() -> Dict[str, Any]:
    try:
        selected = pick_directory("Select a folder with files or notebooks")
    except FolderPickerError as exc:
        raise WorkspaceError(str(exc)) from exc
    if not selected:
        return describe_workspace()
    return open_workspace(selected)


def close_workspace() -> Dict[str, Any]:
    clear_runtime_setting(WORKSPACE_ROOT_KEY)
    return describe_workspace()


def _build_entries(
    root: Path,
    base: Path,
    depth: int,
    counter: List[int],
    max_entries: int,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    try:
        children = sorted(
            base.iterdir(),
            key=lambda item: (not item.is_dir(), item.name.lower()),
        )
    except OSError:
        return entries

    for child in children:
        if counter[0] >= max_entries:
            break
        if child.is_symlink():
            continue
        if child.is_dir() and child.name in _SKIP_DIRS:
            continue
        if not child.is_dir() and child.suffix.lower() not in _TEXT_EXTENSIONS:
            continue

        counter[0] += 1
        try:
            is_dir = child.is_dir()
            size = 0 if is_dir else child.stat().st_size
            extension = "" if is_dir else (child.suffix.lower() or "")
            entry: Dict[str, Any] = {
                "name": child.name,
                "path": child.relative_to(root).as_posix(),
                "type": "directory" if is_dir else "file",
                "size": size,
                "extension": extension or None,
                "children": [],
            }
            if is_dir and depth > 1:
                entry["children"] = _build_entries(
                    root, child, depth - 1, counter, max_entries
                )
            entries.append(entry)
        except OSError:
            continue
    return entries


def describe_workspace(depth: int = 4, max_entries: int = _MAX_TREE_ENTRIES) -> Dict[str, Any]:
    raw = get_runtime_setting(WORKSPACE_ROOT_KEY)
    if not raw:
        return {
            "root": None,
            "name": None,
            "exists": False,
            "tree": [],
            "truncated": False,
        }

    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        return {
            "root": str(root),
            "name": root.name,
            "exists": False,
            "tree": [],
            "truncated": False,
        }

    counter = [0]
    tree = _build_entries(root, root, max(depth, 1), counter, max_entries)
    return {
        "root": str(root),
        "name": root.name,
        "exists": True,
        "tree": tree,
        "truncated": counter[0] >= max_entries,
    }


def _resolve_file(relative: str) -> Path:
    root = _resolve_root()
    path = _resolve_inside(root, relative)
    if not path.is_file():
        raise WorkspaceNotFoundError(f"File not found: {relative}")
    return path


def resolve_data_path(path: str) -> str:
    """Resolve a notebook data path.

    Absolute paths are used as-is; relative ("logical") paths are resolved
    against the currently open workspace folder.
    """

    text = (path or "").strip()
    if not text:
        raise WorkspaceError("A file path is required.")

    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        root = _resolve_root()
        resolved = _resolve_inside(root, text)

    if not resolved.exists():
        raise WorkspaceNotFoundError(f"File not found: {path}")
    return str(resolved)


def read_text_file(relative: str) -> Dict[str, Any]:
    path = _resolve_file(relative)
    if path.suffix.lower() not in _TEXT_EXTENSIONS:
        raise WorkspaceError(
            f"'{path.name}' is not a supported text file."
        )
    if path.stat().st_size > _MAX_TEXT_BYTES:
        raise WorkspaceError("File is too large to open (limit 5 MB).")
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise WorkspaceError(f"Could not read file: {exc}") from exc
    suffix = path.suffix.lower()
    return {
        "path": path.relative_to(_resolve_root()).as_posix(),
        "name": path.name,
        "content": content,
        "language": _LANGUAGE_BY_EXTENSION.get(suffix, "text"),
        "size": len(content.encode("utf-8")),
    }


def write_text_file(relative: str, content: str) -> Dict[str, Any]:
    path = _resolve_file(relative)
    if path.suffix.lower() not in _TEXT_EXTENSIONS:
        raise WorkspaceError(f"'{path.name}' is not a supported text file.")
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise WorkspaceError(f"Could not save file: {exc}") from exc
    return {"path": relative, "size": len(content.encode("utf-8"))}


def _join_source(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str(part) for part in value)
    if value is None:
        return ""
    return str(value)


def _extract_outputs(raw_outputs: Any) -> List[Dict[str, str]]:
    outputs: List[Dict[str, str]] = []
    if not isinstance(raw_outputs, list):
        return outputs
    for raw in raw_outputs:
        if not isinstance(raw, dict):
            continue
        kind = "text"
        output_type = raw.get("output_type")
        if output_type == "stream":
            text = _join_source(raw.get("text"))
            if raw.get("name") == "stderr":
                kind = "error"
        elif output_type in ("execute_result", "display_data"):
            data = raw.get("data") or {}
            text = _join_source(data.get("text/plain")) if isinstance(data, dict) else ""
        elif output_type == "error":
            kind = "error"
            traceback = raw.get("traceback")
            trace_text = "\n".join(traceback) if isinstance(traceback, list) else ""
            header = f"{raw.get('ename', 'Error')}: {raw.get('evalue', '')}".strip()
            text = (header + ("\n" + trace_text if trace_text else "")).strip()
        else:
            continue
        if text:
            outputs.append({"kind": kind, "text": text})
    return outputs


def load_notebook(relative: str) -> Dict[str, Any]:
    path = _resolve_file(relative)
    if path.suffix.lower() != ".ipynb":
        raise WorkspaceError(f"'{path.name}' is not a Jupyter notebook (.ipynb).")
    if path.stat().st_size > _MAX_TEXT_BYTES * 4:
        raise WorkspaceError("Notebook is too large to open.")
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as exc:
        raise WorkspaceError(f"Could not parse notebook: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("cells"), list):
        raise WorkspaceError("This file is not a valid Jupyter notebook.")

    cells: List[Dict[str, Any]] = []
    for index, raw in enumerate(data["cells"]):
        if not isinstance(raw, dict):
            continue
        raw_type = raw.get("cell_type", "code")
        cell_type = "markdown" if raw_type in ("markdown", "raw") else "code"
        cells.append(
            {
                "id": f"cell-{index + 1}",
                "type": cell_type,
                "source": _join_source(raw.get("source")),
                "outputs": _extract_outputs(raw.get("outputs") if cell_type == "code" else []),
            }
        )

    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    kernelspec = metadata.get("kernelspec") if isinstance(metadata.get("kernelspec"), dict) else {}
    kernel_name = str(kernelspec.get("name") or "python3")
    kernel_display = str(kernelspec.get("display_name") or "Python 3 (PySpark built-in)")
    kernel_language = str(kernelspec.get("language") or "python").lower()
    if kernel_name in ("python3", "pyspark"):
        kernel_name, kernel_display, kernel_language = (
            "python3",
            "Python 3 (PySpark built-in)",
            "python",
        )
    elif kernel_name == "sql":
        kernel_name, kernel_display, kernel_language = (
            "sql",
            "SQL (Spark SQL built-in)",
            "sql",
        )

    return {
        "path": path.relative_to(_resolve_root()).as_posix(),
        "name": path.name,
        "cells": cells,
        "kernel_name": kernel_name,
        "kernel_display_name": kernel_display,
        "kernel_language": kernel_language,
        "nbformat": data.get("nbformat") if isinstance(data.get("nbformat"), int) else None,
        "nbformat_minor": data.get("nbformat_minor")
        if isinstance(data.get("nbformat_minor"), int)
        else None,
    }


def _empty_notebook() -> Dict[str, Any]:
    return {
        "cells": [],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3 (PySpark)",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def create_notebook(relative_name: str) -> Dict[str, Any]:
    root = _resolve_root()
    name = (relative_name or "").strip().replace("\\", "/")
    if not name:
        raise WorkspaceError("Notebook name is required.")
    if not name.lower().endswith(".ipynb"):
        name = f"{name}.ipynb"

    path = _resolve_inside(root, name)
    if path.exists():
        raise WorkspaceError(f"'{path.name}' already exists in this folder.")
    if not path.parent.is_dir():
        raise WorkspaceError("The target folder does not exist.")
    if not path.stem.strip():
        raise WorkspaceError("Notebook name is required.")

    try:
        path.write_text(
            json.dumps(_empty_notebook(), indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        raise WorkspaceError(f"Could not create notebook: {exc}") from exc

    logger.info("Created notebook %s", path)
    return load_notebook(path.relative_to(root).as_posix())
