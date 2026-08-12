"""NFS data-path semantics using a mounted Qumulo export."""

from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path

import pytest
from resilience_platform.platform_compat import HAS_FCNTL, fcntl

from resilience_platform.checksums import deterministic_payload, sha256_hex
from resilience_platform.retry import poll_until
from resilience_platform.settings import Settings

pytestmark = [pytest.mark.nfs, pytest.mark.live, pytest.mark.destructive]


def _nfs_path(nfs_mount: Path, settings: Settings, relative: str) -> Path:
    return nfs_mount / settings.effective_run_id / relative


@pytest.mark.parametrize("size", [8192, 256 * 1024])
def test_nfs_write_fsync_read_integrity(
    nfs_mount: Path,
    settings: Settings,
    size: int,
) -> None:
    """Write + fsync + read must preserve byte-identical content."""
    target = _nfs_path(nfs_mount, settings, f"integrity-{uuid.uuid4().hex}.bin")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = deterministic_payload(size, seed=301)

    fd = os.open(target, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)

    read_back = target.read_bytes()
    assert sha256_hex(read_back) == sha256_hex(payload)
    target.unlink(missing_ok=True)


def test_nfs_atomic_rename_visibility_under_concurrent_readers(
    nfs_mount: Path,
    settings: Settings,
) -> None:
    """Readers polling the final name must eventually see full content after atomic rename."""
    run_dir = nfs_mount / settings.effective_run_id / f"rename-{uuid.uuid4().hex}"
    run_dir.mkdir(parents=True, exist_ok=True)
    temp_path = run_dir / "object.tmp"
    final_path = run_dir / "object.final"
    payload = deterministic_payload(65536, seed=302)
    digest = sha256_hex(payload)
    stop = threading.Event()
    observations: list[str] = []

    def reader() -> None:
        while not stop.is_set():
            if final_path.exists():
                data = final_path.read_bytes()
                if data:
                    observations.append(sha256_hex(data))
            stop.wait(0.05)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()

    temp_path.write_bytes(payload)
    os.rename(temp_path, final_path)

    def _seen_correct() -> str | None:
        return digest if digest in observations else None

    poll_until(_seen_correct, timeout_seconds=10, description="NFS rename visibility")
    stop.set()
    thread.join(timeout=2)
    final_path.unlink(missing_ok=True)
    run_dir.rmdir()


def test_nfs_advisory_lock_contention_and_recovery(
    nfs_mount: Path,
    settings: Settings,
) -> None:
    """Exclusive advisory lock blocks writers; recovery succeeds after release."""
    if not HAS_FCNTL:
        pytest.skip("fcntl not available on this platform (use Linux container profile)")

    target = _nfs_path(nfs_mount, settings, f"lock-{uuid.uuid4().hex}.bin")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"initial")

    lock_holder = threading.Event()
    release = threading.Event()
    lock_error: list[Exception] = []

    def hold_lock() -> None:
        fd = os.open(target, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            lock_holder.set()
            release.wait(5)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    holder = threading.Thread(target=hold_lock, daemon=True)
    holder.start()
    poll_until(
        lambda: True if lock_holder.is_set() else None,
        timeout_seconds=5,
        description="lock held",
    )

    def attempt_write() -> None:
        fd = os.open(target, os.O_WRONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.write(fd, b"should-not-win")
        except BlockingIOError as exc:
            lock_error.append(exc)
        finally:
            os.close(fd)

    writer = threading.Thread(target=attempt_write, daemon=True)
    writer.start()
    writer.join(timeout=5)
    assert lock_error, "expected non-blocking lock attempt to fail while lock held"

    release.set()
    holder.join(timeout=5)

    fd = os.open(target, os.O_WRONLY | os.O_TRUNC)
    try:
        os.write(fd, b"recovered")
        os.fsync(fd)
    finally:
        os.close(fd)
    assert target.read_bytes() == b"recovered"
    target.unlink(missing_ok=True)
