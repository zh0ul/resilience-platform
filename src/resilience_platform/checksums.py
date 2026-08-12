"""Deterministic payload generation and checksum utilities."""

from __future__ import annotations

import hashlib
import random
import struct
from typing import Final

DEFAULT_CHUNK_SIZE: Final[int] = 1024 * 1024


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def deterministic_payload(size: int, seed: int) -> bytes:
    """Generate reproducible binary payload from a seed."""
    if size <= 0:
        return b""

    rng = random.Random(seed)
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk_len = min(remaining, DEFAULT_CHUNK_SIZE)
        chunks.append(rng.randbytes(chunk_len))
        remaining -= chunk_len
    return b"".join(chunks)


def payload_with_header(size: int, seed: int, label: str) -> bytes:
    """Payload prefixed with a deterministic header for cross-protocol correlation."""
    header = struct.pack(">I", seed) + label.encode("utf-8")[:32].ljust(32, b"\x00")
    body_size = max(size - len(header), 0)
    return header + deterministic_payload(body_size, seed)
