# Resilience Platform Directory Layout

This table describes the monorepo structure for the Customer-Workload Resilience Platform. Paths are relative to the repository root (`resilience-platform/`).

Directories marked **implemented** contain code today; **planned** directories exist as placeholders or are defined in the [90-day proposal](Q-90.md) but not yet populated.

| Directory | Status | Description |
|---|---|---|
| `src/` | implemented | Python package root; installed editable via `pip install -e ".[dev]"` for local development and Docker test images. |
| `src/resilience_platform/` | implemented | Shared library used by pytest, Locust, and the CLI: typed settings, disposable-environment safety guards, Qumulo REST client wrappers, fixture helpers, checksum utilities, retry logic, and evidence writers. Exposes the `resilience-preflight` entrypoint. |
| `scripts/` | implemented | Operational shell helpers for containerized and CI test runs—not part of the installable Python package. |
| `scripts/mount_protocols.sh` | implemented | Entrypoint wrapper for the Docker `protocols` profile: mounts NFS and SMB fixture paths from environment variables, registers signal-safe unmount on exit, then execs the test command. |
| `tests/` | implemented | Test suite organized by protocol and run mode (offline by default; live integration opt-in). |
| `tests/unit/` | implemented | Offline pytest coverage for settings, safety gates, and checksum helpers—runs without a cluster. |
| `tests/rest/` | implemented | REST control-plane tests targeting Qumulo Core HTTPS API (port 8000): mocked contract tests run offline; Locust scenarios require a live cluster. |
| `tests/rest/locust/` | implemented | Locust load scenarios (`health_read`, `openmetrics`, `etag_conflict`) with Python-native assertions and CSV evidence output. |
| `tests/s3/` | implemented | S3-compatible data-path tests (PUT/HEAD/GET, multipart, listing) against the Qumulo S3 endpoint (port 9000 when enabled). Skipped offline unless live safety gates pass. |
| `tests/nfs/` | implemented | Native Linux NFS client tests for integrity, rename, and advisory locking. Requires a mounted export and live opt-in. |
| `tests/smb/` | implemented | SMB client tests for round-trip I/O, locks, and reopen behavior. Requires a mounted share and live opt-in. |
| `tests/cross_protocol/` | implemented | Cross-protocol namespace consistency tests (S3↔NFS, NFS↔SMB, SMB↔S3/NFS, REST↔NFS) with checksum and metadata verification; writes failure artifacts on mismatch. |
| `platform/` | planned | GitOps-managed Kubernetes resources for the test platform itself—managed by Argo CD as the long-lived desired state of the resilience infrastructure. |
| `platform/base/` | planned | Shared platform foundation: namespaces, service accounts, RBAC, network policies, quotas, priority classes, observability scrape config, artifact repository settings, and secret references. |
| `platform/overlays/` | planned | Environment-specific Kustomize overlays for test lanes: sandbox, VM, cloud, and qualified-hardware. |
| `workflows/` | planned | Argo Workflows definitions for ephemeral test execution, evidence collection, and cleanup. |
| `workflows/templates/` | planned | Reusable WorkflowTemplates for the canonical test DAG: provision, preflight, load, fault injection, verification, reporting, and cleanup. |
| `workflows/schedules/` | planned | CronWorkflows for scheduled test lanes such as nightly integration and weekly resilience runs. |
| `scenarios/` | planned | Declarative scenario definitions combining customer-shaped workload profiles, fault catalog entries, and invariants to be executed by workflow templates. |
| `dashboards/` | planned | Grafana dashboards for correlating workload, Qumulo OpenMetrics, fault timestamps, Argo workflow status, and per-run evidence. |
| `policies/` | planned | Release quality policy: required vs. advisory gates, quarantine rules, waiver records with owner and expiration, and flake-handling conventions. |
| `docs/` | planned | Platform documentation: architecture decision records (ADRs), test authoring guide, operational runbooks, troubleshooting decision trees, and the test/scenario catalog. |
| `evidence/` | runtime | Per-run artifact output directory (gitignored). Locust CSVs, cross-protocol failure JSON, and other immutable run evidence keyed by run ID. Created on demand—not checked into Git. |

## Repository tree

Current layout with planned directories shown for context:

```text
resilience-platform/
├── src/
│   └── resilience_platform/     # shared Python library + CLI
├── scripts/
│   └── mount_protocols.sh       # NFS/SMB mount wrapper for Docker
├── tests/
│   ├── unit/                    # offline safety, settings, checksums
│   ├── rest/
│   │   ├── test_rest_contracts.py
│   │   └── locust/
│   ├── s3/
│   ├── nfs/
│   ├── smb/
│   └── cross_protocol/
├── platform/                    # planned — Argo CD GitOps
│   ├── base/
│   └── overlays/
├── workflows/                   # planned — Argo Workflows
│   ├── templates/
│   └── schedules/
├── scenarios/                   # planned
├── dashboards/                  # planned
├── policies/                    # planned
├── docs/                        # planned
└── evidence/                    # runtime output (gitignored)
```
