"""Unit tests for deterministic payload generation."""

from __future__ import annotations

from resilience_platform.checksums import deterministic_payload, payload_with_header, sha256_hex


def test_deterministic_payload_is_reproducible() -> None:
    first = deterministic_payload(8192, seed=99)
    second = deterministic_payload(8192, seed=99)
    assert first == second
    assert len(first) == 8192


def test_payload_with_header_includes_label() -> None:
    payload = payload_with_header(128, seed=7, label="cross-proto")
    assert payload.startswith(b"\x00\x00\x00\x07")
    assert b"cross-proto" in payload[:40]


def test_sha256_hex() -> None:
    expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert sha256_hex(b"hello") == expected
