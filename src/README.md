# src

Python package root; installed editable via `pip install -e ".[dev]"` for local development and Docker test images.

**Status:** Implemented.

| Path | Purpose |
|------|---------|
| [`resilience_platform/`](resilience_platform/) | Shared library used by pytest, Locust, and the CLI: typed settings, disposable-environment safety guards, Qumulo REST client wrappers, fixture helpers, checksum utilities, retry logic, and evidence writers. Exposes the `resilience-preflight` entrypoint. |

See [directories.md](../directories.md) for the full repository layout.
