"""Qumulo REST client helpers built on the official SDK."""

from __future__ import annotations

from typing import Any

import requests
from qumulo.rest_client import RestClient

from resilience_platform.settings import Settings, get_settings


class QumuloSession:
    """Authenticated REST session with bearer token management."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: RestClient | None = None
        self._bearer_token: str | None = None

    @property
    def client(self) -> RestClient:
        if self._client is None:
            self._client = RestClient(self.settings.qumulo_host, self.settings.qumulo_rest_port)
        return self._client

    def login(self) -> str:
        self.client.login(self.settings.qumulo_user, self.settings.qumulo_password)
        token = getattr(self.client, "bearer_token", None)
        if not token:
            # SDK stores token internally; fetch via session endpoint if needed
            token = self._login_via_http()
        self._bearer_token = token
        return token

    def _login_via_http(self) -> str:
        response = requests.post(
            f"{self.settings.rest_base_url}/v1/session/login",
            json={
                "username": self.settings.qumulo_user,
                "password": self.settings.qumulo_password,
            },
            verify=self.settings.tls_verify,
            timeout=30,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        return str(payload["bearer_token"])

    @property
    def bearer_token(self) -> str:
        if self._bearer_token is None:
            return self.login()
        return self._bearer_token

    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.bearer_token}"}

    def http_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(self.auth_headers())
        session.verify = self.settings.tls_verify
        return session

    def read_fs_stats(self) -> dict[str, Any]:
        result: dict[str, Any] = self.client.fs.read_fs_stats()
        return result

    def read_cluster_version(self) -> dict[str, Any]:
        result: dict[str, Any] = self.client.cluster.cluster_get_version()
        return result


def create_rest_client(settings: Settings | None = None) -> QumuloSession:
    return QumuloSession(settings)
