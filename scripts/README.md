# scripts

Operational shell helpers for containerized, CI, and local Ubuntu dev runs — not part of the installable Python package.

**Status:** Implemented.

| Script | Purpose |
|--------|---------|
| [`setup_ubuntu.sh`](setup_ubuntu.sh) | Ubuntu dev bootstrap: apt packages, `.venv`, and `pip install -e ".[dev]"`. Use `--protocols` to install NFS/SMB mount utilities. |
| [`run_offline_checks.sh`](run_offline_checks.sh) | Run offline pytest, ruff, and mypy via the project venv. |
| [`mount_protocols.sh`](mount_protocols.sh) | Docker `protocols` profile entrypoint (and bare-metal Linux): mounts NFS and SMB fixture paths from environment variables, registers signal-safe unmount on exit, then execs the test command. |

See [directories.md](../directories.md) for the full repository layout.
