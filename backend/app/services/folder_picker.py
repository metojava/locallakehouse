from __future__ import annotations

import threading
from typing import Any, Callable, Optional


class FolderPickerError(RuntimeError):
    """Raised when a native folder picker cannot be shown."""


def _run_dialog(show: Callable[[Any], Optional[str]], name: str) -> Optional[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog  # noqa: F401
    except Exception as exc:  # pragma: no cover - depends on Tk install
        raise FolderPickerError(
            "A native file dialog is unavailable in this environment. "
            "Enter the path manually."
        ) from exc

    result: dict[str, Optional[str]] = {"path": None}

    def _worker() -> None:
        root = tk.Tk()
        try:
            root.withdraw()
            root.wm_attributes("-topmost", True)
            selected = show(root)
            result["path"] = selected or None
        finally:
            try:
                root.destroy()
            except Exception:  # pragma: no cover - best effort
                pass

    thread = threading.Thread(target=_worker, name=name, daemon=True)
    thread.start()
    thread.join(timeout=300)
    if thread.is_alive():
        raise FolderPickerError("The file dialog did not return a selection in time.")
    return result["path"]


def pick_directory(title: str) -> Optional[str]:
    """Open a native folder picker on the backend machine.

    Returns the selected directory or ``None`` if cancelled. Raises
    :class:`FolderPickerError` when no graphical session is available.
    """

    return _run_dialog(
        lambda _root: _filedialog().askdirectory(title=title), "folder-picker"
    )


def pick_file(title: str) -> Optional[str]:
    """Open a native file picker on the backend machine (any file type)."""

    filetypes = [
        ("Data files", "*.csv *.tsv *.json *.jsonl *.parquet *.orc *.avro *.txt"),
        ("All files", "*.*"),
    ]
    return _run_dialog(
        lambda _root: _filedialog().askopenfilename(title=title, filetypes=filetypes),
        "file-picker",
    )


def _filedialog() -> Any:
    from tkinter import filedialog

    return filedialog
