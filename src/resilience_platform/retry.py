"""Retry helpers for bounded propagation polling."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def poll_until(
    predicate: Callable[[], T | None],
    *,
    timeout_seconds: float = 30.0,
    interval_seconds: float = 0.5,
    description: str = "condition",
) -> T:
    """Poll until predicate returns a non-None value or timeout."""
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result is not None:
                return result
        except Exception as exc:  # noqa: BLE001 - capture for timeout message
            last_error = exc
        time.sleep(interval_seconds)

    detail = f" while waiting for {description}"
    if last_error:
        msg = f"Timed out after {timeout_seconds}s{detail}: {last_error}"
        raise TimeoutError(msg) from last_error
    msg = f"Timed out after {timeout_seconds}s{detail}"
    raise TimeoutError(msg)
