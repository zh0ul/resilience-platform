"""CLI entrypoint for preflight safety checks."""

from __future__ import annotations

import sys

from resilience_platform.qumulo_client import create_rest_client
from resilience_platform.safety import SafetyError, assert_disposable
from resilience_platform.settings import get_settings


def main() -> None:
    settings = get_settings()
    try:
        assert_disposable(settings)
    except SafetyError as exc:
        print(f"PREFLIGHT FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

    if not settings.live_rest_configured():
        print("PREFLIGHT FAILED: Qumulo REST credentials not configured.", file=sys.stderr)
        sys.exit(1)

    session = create_rest_client(settings)
    stats = session.read_fs_stats()
    version = session.read_cluster_version()
    print("PREFLIGHT OK")
    print(f"  env_label: {settings.env_label}")
    print(f"  run_id: {settings.effective_run_id}")
    print(f"  namespace: {settings.run_namespace}")
    print(f"  cluster_version: {version}")
    print(f"  fs_stats: {stats}")


if __name__ == "__main__":
    main()
