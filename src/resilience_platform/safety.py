"""Safety guards for disposable-environment test execution."""

from __future__ import annotations

from resilience_platform.settings import Settings, get_settings


class SafetyError(RuntimeError):
    """Raised when a test attempts to run outside an approved disposable target."""


def assert_disposable(settings: Settings | None = None) -> None:
    """Verify live/destructive tests are explicitly enabled against an allow-listed target."""
    cfg = settings or get_settings()

    if not cfg.enable_live_tests:
        raise SafetyError(
            "Live tests are disabled. Set RESILIENCE_ENABLE_LIVE_TESTS=true to opt in."
        )

    if not cfg.ack_disposable_target:
        raise SafetyError(
            "Disposable target not acknowledged. "
            "Set RESILIENCE_ACK_DISPOSABLE_TARGET=true after confirming the cluster is disposable."
        )

    if not cfg.env_label:
        raise SafetyError("RESILIENCE_ENV_LABEL must be set for live tests.")

    if cfg.env_label not in cfg.allowed_env_label_set:
        raise SafetyError(
            f"Environment label {cfg.env_label!r} is not in allow-list: "
            f"{sorted(cfg.allowed_env_label_set)}"
        )

    if not cfg.fixture_root.startswith("/resilience"):
        raise SafetyError(
            f"fixture_root {cfg.fixture_root!r} must start with /resilience to prevent "
            "accidental writes to production namespaces."
        )


def assert_fixture_path_allowed(path: str, settings: Settings | None = None) -> None:
    """Ensure a filesystem path stays within the configured run namespace."""
    cfg = settings or get_settings()
    normalized = path.replace("\\", "/").rstrip("/")
    allowed_prefix = cfg.run_namespace.rstrip("/")
    if not normalized.startswith(allowed_prefix):
        msg = f"Path {path!r} is outside allowed namespace {allowed_prefix!r}"
        raise SafetyError(msg)


def assert_s3_key_allowed(key: str, settings: Settings | None = None) -> None:
    """Ensure an S3 object key stays within the configured run prefix."""
    cfg = settings or get_settings()
    prefix = f"{cfg.effective_run_id}/"
    if not key.startswith(prefix):
        msg = f"S3 key {key!r} is outside allowed prefix {prefix!r}"
        raise SafetyError(msg)
