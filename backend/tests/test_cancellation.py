from __future__ import annotations

from app.services.cancellation import CancellationRegistry, CancelToken


def test_token_runs_callbacks_once() -> None:
    token = CancelToken("sql")
    calls: list[int] = []
    token.add_callback(lambda: calls.append(1))

    assert token.cancelled is False
    assert token.cancel() is True
    assert token.cancelled is True
    assert calls == [1]

    # A second cancel is a no-op and does not re-run callbacks.
    assert token.cancel() is False
    assert calls == [1]


def test_callback_added_after_cancel_runs_immediately() -> None:
    token = CancelToken("pyspark")
    token.cancel()
    calls: list[str] = []

    token.add_callback(lambda: calls.append("stop"))

    assert calls == ["stop"]


def test_registry_cancels_only_the_active_token() -> None:
    registry = CancellationRegistry()
    token = registry.begin("java")

    assert registry.cancel("java") is True
    assert token.cancelled is True
    assert registry.cancel("java") is False

    registry.finish(token)
    assert registry.cancel("java") is False


def test_finishing_an_old_token_does_not_clear_the_new_one() -> None:
    registry = CancellationRegistry()
    first = registry.begin("sql")
    second = registry.begin("sql")

    registry.finish(first)

    assert registry.cancel("sql") is True
    assert second.cancelled is True
