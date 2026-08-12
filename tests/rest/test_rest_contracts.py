"""Offline REST contract tests using mocked HTTP responses."""

from __future__ import annotations

import json

import pytest
import responses

from resilience_platform.settings import Settings


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        QUMULO_HOST="lab.qumulo.local",
        QUMULO_USER="admin",
        QUMULO_PASSWORD="secret",
        QUMULO_VERIFY_TLS=False,
    )


@responses.activate
def test_login_contract_returns_bearer_token(mock_settings: Settings) -> None:
    responses.add(
        responses.POST,
        f"{mock_settings.rest_base_url}/v1/session/login",
        json={
            "bearer_token": "1:TESTTOKEN",
            "key_id": "kid",
            "key": "key",
            "algorithm": "hmac-sha-256",
        },
        status=200,
    )
    import requests

    response = requests.post(
        f"{mock_settings.rest_base_url}/v1/session/login",
        json={"username": mock_settings.qumulo_user, "password": mock_settings.qumulo_password},
        verify=False,
    )
    assert response.status_code == 200
    body = response.json()
    assert "bearer_token" in body
    assert body["bearer_token"].startswith("1:")


@responses.activate
def test_file_system_stats_contract(mock_settings: Settings) -> None:
    responses.add(
        responses.GET,
        f"{mock_settings.rest_base_url}/v1/file-system",
        json={
            "raw_size_bytes": "102420130627584",
            "block_size_bytes": 4096,
            "total_size_bytes": "47953309859840",
            "free_size_bytes": "7365139591168",
        },
        status=200,
    )
    import requests

    response = requests.get(
        f"{mock_settings.rest_base_url}/v1/file-system",
        headers={"Authorization": "Bearer 1:TESTTOKEN"},
        verify=False,
    )
    assert response.status_code == 200
    stats = response.json()
    required = {"raw_size_bytes", "block_size_bytes", "total_size_bytes", "free_size_bytes"}
    assert required.issubset(stats.keys())
    assert stats["block_size_bytes"] == 4096


@responses.activate
def test_openmetrics_contract_contains_metric_lines(mock_settings: Settings) -> None:
    sample = "# HELP qumulo_iops_read IOPS read rate\nqumulo_iops_read 42.0\n"
    responses.add(
        responses.GET,
        f"{mock_settings.rest_base_url}/v2/metrics/endpoints/default/data",
        body=sample,
        status=200,
        content_type="text/plain; version=0.0.4",
    )
    import requests

    response = requests.get(
        f"{mock_settings.rest_base_url}/v2/metrics/endpoints/default/data",
        headers={"Authorization": "Bearer 1:TESTTOKEN"},
        verify=False,
    )
    assert response.status_code == 200
    assert "qumulo_iops_read" in response.text


@responses.activate
def test_stale_etag_patch_returns_precondition_failed(mock_settings: Settings) -> None:
    file_ref = "%2Fresilience-fixtures%2Frun1%2Fseed.bin"
    responses.add(
        responses.PATCH,
        f"{mock_settings.rest_base_url}/v1/files/{file_ref}/data",
        json={"error": "Precondition Failed", "etag": "NEWETAG"},
        status=412,
    )
    import requests

    response = requests.patch(
        f"{mock_settings.rest_base_url}/v1/files/{file_ref}/data",
        headers={"Authorization": "Bearer 1:TESTTOKEN", "If-Match": '"STALE"'},
        data=b"updated",
        verify=False,
    )
    assert response.status_code == 412
    assert json.loads(response.text)["error"] == "Precondition Failed"
