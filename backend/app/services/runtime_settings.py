from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import get_settings

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()


def _settings_path() -> Path:
    return get_settings().runtime_settings_file


def _read_all() -> Dict[str, Any]:
    path = _settings_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:  # pragma: no cover - corrupt file
        logger.warning("Could not read runtime settings %s: %s", path, exc)
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _write_all(data: Dict[str, Any]) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    tmp.replace(path)


def get_runtime_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with _LOCK:
        value = _read_all().get(key)
    if value is None:
        return default
    return str(value)


def set_runtime_setting(key: str, value: Optional[str]) -> None:
    with _LOCK:
        data = _read_all()
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
        _write_all(data)


def clear_runtime_setting(key: str) -> None:
    set_runtime_setting(key, None)
