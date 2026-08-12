"""Unit tests for settings and safety guards."""

from __future__ import annotations

import pytest

from resilience_platform.safety import (
    SafetyError,
    assert_disposable,
    assert_fixture_path_allowed,
    assert_s3_key_allowed,
)
from resilience_platform.settings import Settings


def test_fixture_root_rejects_root() -> None:
    with pytest.raises(ValueError, match="must not be filesystem root"):
        Settings(RESILIENCE_FIXTURE_ROOT="/")


def test_assert_disposable_requires_opt_in() -> None:
    cfg = Settings(
        RESILIENCE_ENABLE_LIVE_TESTS=False,
        RESILIENCE_ACK_DISPOSABLE_TARGET=True,
        RESILIENCE_ENV_LABEL="disposable-vm",
    )
    with pytest.raises(SafetyError, match="disabled"):
        assert_disposable(cfg)


def test_assert_disposable_requires_acknowledgement() -> None:
    cfg = Settings(
        RESILIENCE_ENABLE_LIVE_TESTS=True,
        RESILIENCE_ACK_DISPOSABLE_TARGET=False,
        RESILIENCE_ENV_LABEL="disposable-vm",
    )
    with pytest.raises(SafetyError, match="acknowledged"):
        assert_disposable(cfg)


def test_assert_disposable_rejects_unknown_env_label() -> None:
    cfg = Settings(
        RESILIENCE_ENABLE_LIVE_TESTS=True,
        RESILIENCE_ACK_DISPOSABLE_TARGET=True,
        RESILIENCE_ENV_LABEL="production",
    )
    with pytest.raises(SafetyError, match="allow-list"):
        assert_disposable(cfg)


def test_assert_disposable_passes_for_allowlisted_label() -> None:
    cfg = Settings(
        RESILIENCE_ENABLE_LIVE_TESTS=True,
        RESILIENCE_ACK_DISPOSABLE_TARGET=True,
        RESILIENCE_ENV_LABEL="disposable-vm",
        RESILIENCE_FIXTURE_ROOT="/resilience-fixtures",
        RESILIENCE_RUN_ID="abc123",
    )
    assert_disposable(cfg)


def test_assert_fixture_path_allowed() -> None:
    cfg = Settings(
        RESILIENCE_FIXTURE_ROOT="/resilience-fixtures",
        RESILIENCE_RUN_ID="run1",
    )
    assert_fixture_path_allowed("/resilience-fixtures/run1/object.bin", cfg)
def test_assert_s3_key_allowed() -> None:
    cfg = Settings(
        RESILIENCE_FIXTURE_ROOT="/resilience-fixtures",
        RESILIENCE_RUN_ID="run1",
    )
    assert_s3_key_allowed("run1/object.bin", cfg)
    with pytest.raises(SafetyError, match="outside allowed prefix"):
        assert_s3_key_allowed("outside-run/object.bin", cfg)
