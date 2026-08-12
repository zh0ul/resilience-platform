"""Shared pytest fixtures and skip guards."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import boto3
import pytest
from botocore.config import Config

from resilience_platform.qumulo_client import QumuloSession, create_rest_client
from resilience_platform.safety import SafetyError, assert_disposable
from resilience_platform.settings import Settings, get_settings


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live: requires disposable Qumulo cluster")
    config.addinivalue_line("markers", "destructive: mutates cluster state")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_live = config.getoption("-m", default="") and "live" in config.getoption("-m", default="")
    if config.getoption("-m", default="") == "live":
        run_live = True
    if not run_live and "not live" not in config.getoption("-m", default=""):
        # default addopts already excludes live
        pass


@pytest.fixture(scope="session")
def settings() -> Settings:
    cfg = get_settings()
    os.environ.setdefault("RESILIENCE_RUN_ID", cfg.effective_run_id)
    return cfg


@pytest.fixture(scope="session")
def run_namespace(settings: Settings) -> str:
    return settings.run_namespace


def _require_live(settings: Settings) -> None:
    if not settings.enable_live_tests:
        pytest.skip("Live tests disabled (RESILIENCE_ENABLE_LIVE_TESTS=false)")
    try:
        assert_disposable(settings)
    except SafetyError as exc:
        pytest.skip(str(exc))


@pytest.fixture(scope="session")
def live_rest_session(settings: Settings) -> Generator[QumuloSession, None, None]:
    _require_live(settings)
    if not settings.live_rest_configured():
        pytest.skip("Qumulo REST credentials not configured")
    session = create_rest_client(settings)
    session.login()
    yield session


@pytest.fixture(scope="session")
def s3_client(settings: Settings):
    _require_live(settings)
    if not settings.live_s3_configured():
        pytest.skip("S3 endpoint/credentials not configured")
    client = boto3.client(
        "s3",
        endpoint_url=settings.qumulo_s3_endpoint,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_default_region,
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        verify=settings.tls_verify if isinstance(settings.tls_verify, bool) else True,
    )
    yield client


@pytest.fixture(scope="session")
def nfs_mount(settings: Settings) -> Path:
    _require_live(settings)
    if not settings.live_nfs_configured():
        pytest.skip("NFS mount not available (configure QUMULO_NFS_EXPORT and mount path)")
    return settings.nfs_mount_path


@pytest.fixture(scope="session")
def smb_mount(settings: Settings) -> Path:
    _require_live(settings)
    if not settings.live_smb_configured():
        pytest.skip("SMB mount not available (configure QUMULO_SMB_* and mount path)")
    return settings.smb_mount_path


@pytest.fixture
def run_subdir(settings: Settings, request: pytest.FixtureRequest) -> Path:
    """Per-test subdirectory under the run namespace on mounted paths."""
    name = request.node.name.replace("[", "_").replace("]", "_")
    sub = f"{settings.effective_run_id}/{name}"
    return Path(sub)
