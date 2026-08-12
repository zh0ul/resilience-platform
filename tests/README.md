# tests

Test suite organized by protocol and run mode. Offline tests run by default; live integration tests require explicit opt-in against a disposable cluster (see root [`README.md`](../README.md) safety gates).

**Status:** Implemented.

| Directory | Tests | Default run |
|-----------|-------|-------------|
| [`unit/`](unit/) | Settings, safety, checksums | Always |
| [`rest/`](rest/) | Mocked REST contracts | Always |
| [`rest/locust/`](rest/locust/) | 3 Locust scenarios | Live / load |
| [`s3/`](s3/) | PUT/HEAD/GET, multipart, listing | Live (skipped offline) |
| [`nfs/`](nfs/) | Integrity, rename, advisory locks | Live (skipped offline) |
| [`smb/`](smb/) | Round-trip, locks, reopen | Live (skipped offline) |
| [`cross_protocol/`](cross_protocol/) | S3↔NFS, NFS↔SMB, SMB↔S3/NFS, REST↔NFS | Live (skipped offline) |

Shared fixtures and skip guards live in [`conftest.py`](conftest.py).

See [directories.md](../directories.md) for the full repository layout.
