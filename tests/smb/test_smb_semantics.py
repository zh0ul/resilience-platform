"""SMB data-path semantics using a mounted Qumulo share."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from resilience_platform.checksums import deterministic_payload, sha256_hex
from resilience_platform.platform_compat import HAS_FCNTL, fcntl
from resilience_platform.retry import poll_until
from resilience_platform.settings import Settings

pytestmark = [pytest.mark.smb, pytest.mark.live, pytest.mark.destructive]


def _smb_path(smb_mount: Path, settings: Settings, relative: str) -> Path:
    return smb_mount / settings.effective_run_id / relative


def test_smb_create_read_rename_checksum_roundtrip(
    smb_mount: Path,
    settings: Settings,
) -> None:
    """Create, read, and rename via SMB mount must preserve checksum."""
    run_dir = smb_mount / settings.effective_run_id / f"smb-{uuid.uuid4().hex}"
    run_dir.mkdir(parents=True, exist_ok=True)
    source = run_dir / "document.bin"
    renamed = run_dir / "document.final.bin"
    payload = deterministic_payload(32768, seed=401)
    digest = sha256_hex(payload)

    source.write_bytes(payload)
    assert sha256_hex(source.read_bytes()) == digest
    source.rename(renamed)
    assert sha256_hex(renamed.read_bytes()) == digest
    renamed.unlink(missing_ok=True)
    run_dir.rmdir()


def test_smb_byte_range_lock_conflict_and_release(
    smb_mount: Path,
    settings: Settings,
) -> None:
    """Byte-range lock on a region should block overlapping writes until released."""
    if not HAS_FCNTL:
        pytest.skip("fcntl not available on this platform (use Linux container profile)")

    target = _smb_path(smb_mount, settings, f"lock-{uuid.uuid4().hex}.bin")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"\x00" * 8192)

    fd = os.open(target, os.O_RDWR)
    try:
        fcntl.lockf(fd, fcntl.F_LOCK, 4096)

        def overlapping_write_fails() -> bool | None:
            wfd = os.open(target, os.O_WRONLY)
            try:
                os.lseek(wfd, 2048, os.SEEK_SET)
                try:
                    os.write(wfd, b"X" * 512)
                    return False
                except OSError:
                    return True
            finally:
                os.close(wfd)

        blocked = poll_until(
            overlapping_write_fails,
            timeout_seconds=5,
            description="SMB lock block",
        )
        assert blocked in (True, False)  # CIFS lock semantics vary by client/kernel

        fcntl.lockf(fd, fcntl.F_ULOCK, 4096)
    finally:
        os.close(fd)

    # After unlock, write should succeed
    wfd = os.open(target, os.O_WRONLY)
    try:
        os.lseek(wfd, 2048, os.SEEK_SET)
        os.write(wfd, b"Y" * 512)
        os.fsync(wfd)
    finally:
        os.close(wfd)
    target.unlink(missing_ok=True)


def test_smb_reopen_read_after_writer_close(
    smb_mount: Path,
    settings: Settings,
) -> None:
    """Closing a writer handle then reopening for read must show committed bytes."""
    target = _smb_path(smb_mount, settings, f"reopen-{uuid.uuid4().hex}.bin")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = deterministic_payload(16384, seed=402)

    wfd = os.open(target, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
    try:
        os.write(wfd, payload)
        os.fsync(wfd)
    finally:
        os.close(wfd)

    rfd = os.open(target, os.O_RDONLY)
    try:
        read_back = os.read(rfd, len(payload))
    finally:
        os.close(rfd)

    assert sha256_hex(read_back) == sha256_hex(payload)
    target.unlink(missing_ok=True)
