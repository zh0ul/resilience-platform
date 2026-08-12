"""Cross-protocol namespace consistency across S3, NFS, SMB, and REST."""

from __future__ import annotations

import contextlib
import uuid
from pathlib import Path

import pytest

from resilience_platform.checksums import deterministic_payload, payload_with_header, sha256_hex
from resilience_platform.evidence import write_failure_artifact
from resilience_platform.fixtures import FixtureManager
from resilience_platform.retry import poll_until
from resilience_platform.settings import Settings

pytestmark = [pytest.mark.cross_protocol, pytest.mark.live, pytest.mark.destructive]


def test_s3_write_nfs_read_byte_agreement(
    s3_client,
    nfs_mount: Path,
    settings: Settings,
) -> None:
    """Object written via S3 must be byte-identical when read through NFS."""
    rel = f"cross-s3-nfs-{uuid.uuid4().hex}.bin"
    key = f"{settings.effective_run_id}/{rel}"
    payload = payload_with_header(65536, seed=501, label="s3-to-nfs")
    digest = sha256_hex(payload)

    s3_client.put_object(Bucket=settings.s3_bucket, Key=key, Body=payload)

    nfs_path = nfs_mount / settings.effective_run_id / rel

    def nfs_matches() -> str | None:
        if not nfs_path.exists():
            return None
        got = nfs_path.read_bytes()
        if len(got) != len(payload):
            return None
        return digest if sha256_hex(got) == digest else None

    try:
        result = poll_until(nfs_matches, timeout_seconds=30, description="S3→NFS propagation")
        assert result == digest
    except TimeoutError as exc:
        write_failure_artifact(
            "s3_nfs_mismatch",
            {"key": key, "nfs_path": str(nfs_path), "expected_sha256": digest},
            settings,
        )
        raise exc
    finally:
        s3_client.delete_object(Bucket=settings.s3_bucket, Key=key)
        nfs_path.unlink(missing_ok=True)


def test_nfs_write_atomic_rename_smb_visibility(
    nfs_mount: Path,
    smb_mount: Path,
    settings: Settings,
) -> None:
    """NFS atomic rename must become visible to SMB readers on the same namespace."""
    rel_dir = f"cross-nfs-smb-{uuid.uuid4().hex}"
    rel_final = f"{rel_dir}/object.final"
    payload = deterministic_payload(32768, seed=502)
    digest = sha256_hex(payload)

    nfs_dir = nfs_mount / settings.effective_run_id / rel_dir
    nfs_dir.mkdir(parents=True, exist_ok=True)
    nfs_tmp = nfs_dir / "object.tmp"
    nfs_final = nfs_dir / "object.final"
    nfs_tmp.write_bytes(payload)
    nfs_tmp.rename(nfs_final)

    smb_path = smb_mount / settings.effective_run_id / rel_final

    def smb_matches() -> str | None:
        if not smb_path.exists():
            return None
        got = smb_path.read_bytes()
        return digest if sha256_hex(got) == digest else None

    try:
        result = poll_until(
            smb_matches,
            timeout_seconds=30,
            description="NFS rename→SMB visibility",
        )
        assert result == digest
    except TimeoutError as exc:
        write_failure_artifact(
            "nfs_smb_mismatch",
            {"nfs_final": str(nfs_final), "smb_path": str(smb_path), "expected_sha256": digest},
            settings,
        )
        raise exc
    finally:
        smb_path.unlink(missing_ok=True)
        nfs_final.unlink(missing_ok=True)
        nfs_dir.rmdir()


def test_smb_overwrite_visible_via_s3_and_nfs(
    smb_mount: Path,
    nfs_mount: Path,
    s3_client,
    settings: Settings,
) -> None:
    """SMB overwrite must converge to the same bytes via NFS read and S3 GET."""
    rel = f"cross-smb-all-{uuid.uuid4().hex}.bin"
    initial = deterministic_payload(8192, seed=503)
    updated = payload_with_header(8192, seed=504, label="smb-overwrite")
    digest = sha256_hex(updated)

    target = smb_mount / settings.effective_run_id / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(initial)
    target.write_bytes(updated)

    nfs_path = nfs_mount / settings.effective_run_id / rel
    s3_key = f"{settings.effective_run_id}/{rel}"

    def all_paths_match() -> str | None:
        if not nfs_path.exists():
            return None
        nfs_digest = sha256_hex(nfs_path.read_bytes())
        if nfs_digest != digest:
            return None
        try:
            s3_body = s3_client.get_object(Bucket=settings.s3_bucket, Key=s3_key)["Body"].read()
        except s3_client.exceptions.NoSuchKey:
            return None
        if sha256_hex(s3_body) != digest:
            return None
        return digest

    try:
        result = poll_until(
            all_paths_match,
            timeout_seconds=45,
            description="SMB→NFS/S3 convergence",
        )
        assert result == digest
    except TimeoutError as exc:
        write_failure_artifact(
            "smb_convergence_failure",
            {
                "smb_path": str(target),
                "nfs_path": str(nfs_path),
                "s3_key": s3_key,
                "expected_sha256": digest,
            },
            settings,
        )
        raise exc
    finally:
        target.unlink(missing_ok=True)
        nfs_path.unlink(missing_ok=True)
        with contextlib.suppress(Exception):
            s3_client.delete_object(Bucket=settings.s3_bucket, Key=s3_key)


@pytest.mark.rest
def test_rest_seeded_fixture_visible_to_nfs(
    live_rest_session,
    nfs_mount: Path,
    settings: Settings,
) -> None:
    """REST-written fixture must be readable via NFS with matching checksum."""
    manager = FixtureManager(live_rest_session, settings)
    rel = f"cross-rest-nfs-{uuid.uuid4().hex}.bin"
    record = manager.write_file_via_rest(rel, size=16384, seed=505, label="rest-to-nfs")
    nfs_path = nfs_mount / settings.effective_run_id / rel

    def nfs_matches() -> str | None:
        if not nfs_path.exists():
            return None
        got = nfs_path.read_bytes()
        return record.sha256 if sha256_hex(got) == record.sha256 else None

    try:
        result = poll_until(nfs_matches, timeout_seconds=30, description="REST→NFS propagation")
        assert result == record.sha256
    finally:
        nfs_path.unlink(missing_ok=True)
        manager.persist_manifest()
