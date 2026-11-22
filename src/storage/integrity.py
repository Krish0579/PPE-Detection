"""Evidence integrity primitives: SHA-256 file hashing and verification."""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path


def compute_image_sha256(image_bytes: bytes) -> str:
    """Return the SHA-256 digest of the exact evidence bytes stored on disk."""
    return hashlib.sha256(image_bytes).hexdigest()


def compute_file_sha256(filepath: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(filepath).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def verify_snapshot_integrity(filepath: str | Path, expected_hash: str) -> bool:
    try:
        actual = compute_file_sha256(filepath)
    except (OSError, ValueError):
        return False
    return hmac.compare_digest(actual.lower(), str(expected_hash).lower())
