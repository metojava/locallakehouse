"""Cancellation support for long-running editor commands.

Each editor window runs at most one command at a time. The route handlers
register a :class:`CancelToken` under a stable target (``sql``, ``pyspark``,
``java``, ``scala`` or ``notebook:<id>``). The UI can then call
``POST /api/cancel`` with that target to stop the latest command.

The token owns a list of callbacks supplied by the execution engine, so the
registry does not need to know whether cancellation means cancelling a Spark
job group, interrupting a Jupyter kernel, or killing a subprocess.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)


def _invoke(callback: Callable[[], None]) -> None:
    try:
        callback()
    except Exception as exc:  # pragma: no cover - best effort cancellation
        logger.warning("Cancellation callback failed: %s", exc)


class CancelToken:
    """A one-shot cancellation signal plus callbacks that stop the work."""

    def __init__(self, target: str) -> None:
        self.target = target
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[], None]] = []

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def add_callback(self, callback: Callable[[], None]) -> None:
        """Register a stop callback, or run it immediately if already cancelled."""

        run_now = False
        with self._lock:
            if self._event.is_set():
                run_now = True
            else:
                self._callbacks.append(callback)
        if run_now:
            _invoke(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        with self._lock:
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass

    def cancel(self) -> bool:
        """Signal cancellation. Returns ``False`` if it was already cancelled."""

        with self._lock:
            if self._event.is_set():
                return False
            self._event.set()
            callbacks = list(self._callbacks)
            self._callbacks.clear()

        for callback in callbacks:
            _invoke(callback)
        return True


class CancellationRegistry:
    """Maps an editor target to the token of its latest command."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: Dict[str, CancelToken] = {}

    def begin(self, target: str) -> CancelToken:
        token = CancelToken(target)
        with self._lock:
            self._active[target] = token
        return token

    def finish(self, token: CancelToken) -> None:
        with self._lock:
            if self._active.get(token.target) is token:
                self._active.pop(token.target, None)

    def cancel(self, target: str) -> bool:
        with self._lock:
            token = self._active.get(target)
        if token is None:
            return False
        return token.cancel()

    def active_targets(self) -> List[str]:
        with self._lock:
            return sorted(self._active)


cancellation_registry = CancellationRegistry()
