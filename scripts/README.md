# scripts

Operational shell helpers for containerized and CI test runs — not part of the installable Python package.

**Status:** Implemented.

| Script | Purpose |
|--------|---------|
| [`mount_protocols.sh`](mount_protocols.sh) | Docker `protocols` profile entrypoint: mounts NFS and SMB fixture paths from environment variables, registers signal-safe unmount on exit, then execs the test command. |

See [directories.md](../directories.md) for the full repository layout.
