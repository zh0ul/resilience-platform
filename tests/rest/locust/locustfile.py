"""Locust load scenarios for the Qumulo REST control plane.

Three professional scenarios in one locustfile, selected via LOCUST_SCENARIO:

  - health_read   : filesystem stats + cluster version with schema checks
  - openmetrics   : OpenMetrics polling with latency/error classification
  - etag_conflict : range read + stale ETag PATCH must not silently overwrite

Run (offline collection / dry run against lab):

  locust -f tests/rest/locust/locustfile.py --host https://HOST:8000 --headless -u 5 -r 1 -t 30s

Environment:
  QUMULO_USER, QUMULO_PASSWORD, QUMULO_CA_BUNDLE, LOCUST_SCENARIO
"""

from __future__ import annotations

import os
import random
from typing import Any

from locust import HttpUser, between, events, task
from locust.exception import StopUser

REQUIRED_FS_KEYS = {"raw_size_bytes", "block_size_bytes", "total_size_bytes", "free_size_bytes"}
SCENARIO = os.environ.get("LOCUST_SCENARIO", "health_read")
FIXTURE_PATH = os.environ.get(
    "LOCUST_FIXTURE_PATH",
    "/resilience-fixtures/locust-seed.bin",
)


def _encoded_fixture_path(path: str) -> str:
    from urllib.parse import quote

    return quote(path.lstrip("/"), safe="")


class AuthenticatedQumuloUser(HttpUser):
    """Base user that authenticates once per simulated operator session."""

    wait_time = between(0.2, 1.0)
    abstract = True

    def on_start(self) -> None:
        ca_bundle = os.environ.get("QUMULO_CA_BUNDLE")
        if ca_bundle:
            self.client.verify = ca_bundle

        username = os.environ.get("QUMULO_USER", "")
        password = os.environ.get("QUMULO_PASSWORD", "")
        if not username or not password:
            raise StopUser("QUMULO_USER and QUMULO_PASSWORD are required for live Locust runs")

        with self.client.post(
            "/v1/session/login",
            json={"username": username, "password": password},
            name="POST /v1/session/login",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"login failed: {response.status_code}")
                raise StopUser()
            token = response.json().get("bearer_token")
            if not token:
                response.failure("login response missing bearer_token")
                raise StopUser()
            self.client.headers["Authorization"] = f"Bearer {token}"


class HealthReadUser(AuthenticatedQumuloUser):
    """Scenario 1: authenticated filesystem and health reads with schema validation."""

    @task(6)
    def read_file_system_stats(self) -> None:
        with self.client.get(
            "/v1/file-system",
            name="GET /v1/file-system",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"unexpected status: {response.status_code}")
                return
            try:
                body: dict[str, Any] = response.json()
            except Exception as exc:  # noqa: BLE001
                response.failure(f"invalid JSON: {exc}")
                return
            if not REQUIRED_FS_KEYS.issubset(body.keys()):
                response.failure(f"missing keys: {REQUIRED_FS_KEYS - body.keys()}")
                return
            response.success()

    @task(4)
    def read_cluster_version(self) -> None:
        with self.client.get(
            "/v1/cluster/version",
            name="GET /v1/cluster/version",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"unexpected status: {response.status_code}")
                return
            body = response.json()
            if "version" not in body and "build" not in body:
                response.failure("version response missing version/build fields")
                return
            response.success()


class OpenMetricsUser(AuthenticatedQumuloUser):
    """Scenario 2: OpenMetrics polling with semantic failure classification."""

    @task
    def poll_openmetrics(self) -> None:
        with self.client.get(
            "/v2/metrics/endpoints/default/data",
            name="GET /v2/metrics/endpoints/default/data",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"metrics poll failed: {response.status_code}")
                return
            text = response.text or ""
            if not text.strip():
                response.failure("empty OpenMetrics payload")
                return
            if "#" not in text and "qumulo" not in text.lower():
                response.failure("response does not look like OpenMetrics")
                return
            response.success()


class EtagConcurrencyUser(AuthenticatedQumuloUser):
    """Scenario 3: range read + stale ETag PATCH must fail with 412."""

    wait_time = between(0.5, 2.0)
    _cached_etag: str | None = None

    @task(3)
    def read_fixture_range(self) -> None:
        ref = _encoded_fixture_path(FIXTURE_PATH)
        offset = random.randint(0, 4096)
        with self.client.get(
            f"/v1/files/{ref}/data",
            params={"offset": offset, "length": 4096, "skip-atime-update": "true"},
            name="GET /v1/files/{fixture}/data [4KiB]",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                response.failure("fixture missing; seed /resilience-fixtures/locust-seed.bin first")
                return
            if response.status_code != 200:
                response.failure(f"range read failed: {response.status_code}")
                return
            etag = response.headers.get("ETag", "").strip('"')
            if etag:
                self._cached_etag = etag
            response.success()

    @task(1)
    def stale_etag_patch_must_fail(self) -> None:
        ref = _encoded_fixture_path(FIXTURE_PATH)
        stale = self._cached_etag or "STALE-ETAG-FOR-TEST"
        with self.client.patch(
            f"/v1/files/{ref}/data",
            data=b"locust-stale-write-attempt",
            headers={"If-Match": f'"{stale}"', "Content-Type": "application/octet-stream"},
            name="PATCH /v1/files/{fixture}/data [stale ETag]",
            catch_response=True,
        ) as response:
            if response.status_code == 412:
                response.success()
                return
            if response.status_code == 200:
                response.failure("stale ETag write succeeded — possible lost-update bug")
                return
            response.failure(f"expected 412 for stale ETag, got {response.status_code}")


_SCENARIO_MAP = {
    "health_read": HealthReadUser,
    "openmetrics": OpenMetricsUser,
    "etag_conflict": EtagConcurrencyUser,
}


@events.init.add_listener
def _select_scenario(environment: Any, **_kwargs: Any) -> None:
    selected = _SCENARIO_MAP.get(SCENARIO, HealthReadUser)
    environment.user_classes = [selected]
