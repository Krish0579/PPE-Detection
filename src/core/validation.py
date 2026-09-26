"""Validation and safe persistence helpers for operator-supplied files.

The Streamlit UI is a trust boundary: browser uploads and editable model paths
must be checked before OpenCV or PyTorch attempts to process them.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class UploadValidationError(ValueError):
    """Raised when an operator-supplied file does not meet the safety policy."""


class UploadedFileLike(Protocol):
    """Minimal interface shared by Streamlit uploaded files and test doubles."""

    name: str
    size: int

    def getvalue(self) -> bytes: ...


@dataclass(frozen=True)
class StoredUpload:
    """Immutable metadata for a validated, privately stored upload."""

    path: Path
    original_name: str
    size: int
    sha256: str


def _normalise_suffixes(allowed_suffixes: Iterable[str]) -> set[str]:
    return {suffix.lower() if suffix.startswith(".") else f".{suffix.lower()}" for suffix in allowed_suffixes}


def validate_upload_name(name: str, allowed_suffixes: Iterable[str]) -> str:
    """Return a safe display name or reject traversal, control characters, and bad types."""
    if not isinstance(name, str) or not name.strip():
        raise UploadValidationError("A file name is required.")
    if len(name) > 180 or any(ord(char) < 32 for char in name):
        raise UploadValidationError("The file name contains unsupported characters.")
    if "/" in name or "\\" in name or name in {".", ".."}:
        raise UploadValidationError("File paths are not accepted; upload a file by name.")

    safe_name = Path(name).name
    if safe_name != name or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ -]*", safe_name):
        raise UploadValidationError("The file name contains unsupported characters.")
    if Path(safe_name).suffix.lower() not in _normalise_suffixes(allowed_suffixes):
        allowed = ", ".join(sorted(_normalise_suffixes(allowed_suffixes)))
        raise UploadValidationError(f"Unsupported file type. Allowed types: {allowed}.")
    return safe_name


def read_uploaded_bytes(
    uploaded: UploadedFileLike,
    allowed_suffixes: Iterable[str],
    max_bytes: int,
) -> tuple[str, bytes]:
    """Validate an uploaded object before its content reaches a decoder or model loader."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    safe_name = validate_upload_name(uploaded.name, allowed_suffixes)
    declared_size = int(getattr(uploaded, "size", 0) or 0)
    if declared_size <= 0:
        raise UploadValidationError("The uploaded file is empty.")
    if declared_size > max_bytes:
        raise UploadValidationError(f"The uploaded file exceeds the {max_bytes // (1024 * 1024)} MB limit.")

    content = uploaded.getvalue()
    if not content:
        raise UploadValidationError("The uploaded file is empty.")
    if len(content) > max_bytes:
        raise UploadValidationError(f"The uploaded file exceeds the {max_bytes // (1024 * 1024)} MB limit.")
    return safe_name, content


def persist_upload(
    uploaded: UploadedFileLike,
    allowed_suffixes: Iterable[str],
    max_bytes: int,
    destination_dir: Path,
    prefix: str,
) -> StoredUpload:
    """Atomically persist a validated upload with a generated, non-user-controlled filename."""
    safe_name, content = read_uploaded_bytes(uploaded, allowed_suffixes, max_bytes)
    return persist_upload_bytes(safe_name, content, destination_dir, prefix)


def persist_upload_bytes(
    safe_name: str,
    content: bytes,
    destination_dir: Path,
    prefix: str,
) -> StoredUpload:
    """Atomically persist already-validated bytes without reading an upload twice."""
    destination_dir = Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(safe_name).suffix.lower()
    destination = destination_dir / f"{prefix}-{uuid.uuid4().hex}{suffix}"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination_dir, prefix=".upload-", suffix=suffix, delete=False) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)
        temp_path.replace(destination)
    except OSError as exc:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise UploadValidationError("The server could not securely store the uploaded file.") from exc

    return StoredUpload(
        path=destination,
        original_name=safe_name,
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )


def validate_model_path(
    candidate: str,
    trusted_model_dir: Path,
    allow_external_paths: bool = False,
) -> Path:
    """Validate a checkpoint path before deserializing a PyTorch/YOLO model.

    Arbitrary checkpoints are disabled by default because PyTorch checkpoints are
    executable deserialization inputs. Production deployments should place
    reviewed weights in the trusted model directory during release.
    """
    if not candidate or not candidate.strip():
        raise UploadValidationError("A model checkpoint path is required.")
    path = Path(candidate).expanduser().resolve()
    trusted_dir = Path(trusted_model_dir).resolve()
    if path.suffix.lower() != ".pt":
        raise UploadValidationError("Only .pt YOLO checkpoints are supported.")
    if not allow_external_paths:
        try:
            path.relative_to(trusted_dir)
        except ValueError as exc:
            raise UploadValidationError("Model checkpoints must be stored in the trusted models directory.") from exc
    if not path.is_file():
        raise UploadValidationError("The selected model checkpoint does not exist.")
    return path
