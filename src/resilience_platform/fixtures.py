"""Fixture lifecycle: seed, verify, and bounded cleanup."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from resilience_platform.checksums import payload_with_header, sha256_hex
from resilience_platform.qumulo_client import QumuloSession
from resilience_platform.safety import assert_disposable, assert_fixture_path_allowed
from resilience_platform.settings import Settings, get_settings


@dataclass
class FixtureRecord:
    """Evidence record for a seeded test artifact."""

    path: str
    size: int
    seed: int
    sha256: str
    label: str = "fixture"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunManifest:
    """Immutable run context written to the evidence directory."""

    run_id: str
    env_label: str
    fixture_root: str
    run_namespace: str
    started_at: str
    fixtures: list[FixtureRecord] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


class FixtureManager:
    """Create and track deterministic fixtures via REST."""

    def __init__(self, session: QumuloSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.manifest = RunManifest(
            run_id=self.settings.effective_run_id,
            env_label=self.settings.env_label,
            fixture_root=self.settings.fixture_root,
            run_namespace=self.settings.run_namespace,
            started_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    def _file_ref(self, relative_path: str) -> str:
        full_path = f"{self.settings.run_namespace}/{relative_path.lstrip('/')}"
        assert_fixture_path_allowed(full_path, self.settings)
        return quote(full_path, safe="")

    def write_file_via_rest(
        self,
        relative_path: str,
        *,
        size: int = 4096,
        seed: int = 42,
        label: str = "fixture",
    ) -> FixtureRecord:
        assert_disposable(self.settings)
        payload = payload_with_header(size, seed, label)
        file_ref = self._file_ref(relative_path)
        url = f"{self.settings.rest_base_url}/v1/files/{file_ref}/data"
        response = self.session.http_session().put(
            url,
            data=payload,
            headers={"Content-Type": "application/octet-stream"},
            timeout=120,
        )
        response.raise_for_status()
        record = FixtureRecord(
            path=f"{self.settings.run_namespace}/{relative_path.lstrip('/')}",
            size=len(payload),
            seed=seed,
            sha256=sha256_hex(payload),
            label=label,
        )
        self.manifest.fixtures.append(record)
        return record

    def read_file_via_rest(
        self,
        relative_path: str,
        *,
        offset: int = 0,
        length: int | None = None,
    ) -> bytes:
        file_ref = self._file_ref(relative_path)
        params: dict[str, str | int] = {"offset": offset, "skip-atime-update": "true"}
        if length is not None:
            params["length"] = length
        url = f"{self.settings.rest_base_url}/v1/files/{file_ref}/data"
        response = self.session.http_session().get(url, params=params, timeout=120)
        response.raise_for_status()
        return response.content

    def get_etag(self, relative_path: str) -> str:
        file_ref = self._file_ref(relative_path)
        url = f"{self.settings.rest_base_url}/v1/files/{file_ref}/data"
        response = self.session.http_session().head(url, timeout=30)
        response.raise_for_status()
        etag = response.headers.get("ETag", "").strip('"')
        if not etag:
            msg = f"No ETag returned for {relative_path}"
            raise RuntimeError(msg)
        return etag

    def patch_with_etag(self, relative_path: str, data: bytes, etag: str) -> requests.Response:
        assert_disposable(self.settings)
        file_ref = self._file_ref(relative_path)
        url = f"{self.settings.rest_base_url}/v1/files/{file_ref}/data"
        return self.session.http_session().patch(
            url,
            data=data,
            headers={"If-Match": f'"{etag}"', "Content-Type": "application/octet-stream"},
            timeout=120,
        )

    def persist_manifest(self) -> Path:
        evidence_dir = self.settings.evidence_dir / self.settings.effective_run_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = evidence_dir / "manifest.json"
        manifest_path.write_text(self.manifest.to_json(), encoding="utf-8")
        return manifest_path
