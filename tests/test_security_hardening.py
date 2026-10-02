"""Regression tests for upload, checkpoint, and evidence safety boundaries."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.core.validation import (
    UploadValidationError,
    persist_upload,
    read_uploaded_bytes,
    validate_model_path,
    validate_upload_name,
)
from src.storage.evidence import EvidenceManager


@dataclass
class FakeUpload:
    name: str
    payload: bytes

    @property
    def size(self) -> int:
        return len(self.payload)

    def getvalue(self) -> bytes:
        return self.payload


class TestSecurityHardening(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="safesight_security_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_rejects_traversal_and_unsupported_upload_names(self) -> None:
        with self.assertRaises(UploadValidationError):
            validate_upload_name("../../incident.jpg", {".jpg"})
        with self.assertRaises(UploadValidationError):
            validate_upload_name("checkpoint.exe", {".pt"})
        with self.assertRaises(UploadValidationError):
            read_uploaded_bytes(FakeUpload("photo.jpg", b"x" * 11), {".jpg"}, 10)

    def test_persists_upload_under_generated_name(self) -> None:
        upload = FakeUpload("shopfloor image.jpg", b"approved-content")
        stored = persist_upload(upload, {".jpg"}, 1024, self.temp_dir / "uploads", "image")
        self.assertEqual(stored.original_name, "shopfloor image.jpg")
        self.assertNotEqual(stored.path.name, stored.original_name)
        self.assertTrue(stored.path.name.startswith("image-"))
        self.assertEqual(stored.path.read_bytes(), b"approved-content")
        self.assertEqual(len(stored.sha256), 64)

    def test_model_path_is_limited_to_trusted_directory(self) -> None:
        trusted_models = self.temp_dir / "models"
        trusted_models.mkdir()
        trusted_model = trusted_models / "reviewed.pt"
        trusted_model.write_bytes(b"checkpoint")
        external_model = self.temp_dir / "outside.pt"
        external_model.write_bytes(b"checkpoint")

        self.assertEqual(validate_model_path(str(trusted_model), trusted_models), trusted_model.resolve())
        with self.assertRaises(UploadValidationError):
            validate_model_path(str(external_model), trusted_models)
        self.assertEqual(
            validate_model_path(str(external_model), trusted_models, allow_external_paths=True),
            external_model.resolve(),
        )

    def test_evidence_status_is_constrained_and_filename_is_safe(self) -> None:
        manager = EvidenceManager(storage_dir=self.temp_dir / "evidence", db_path=self.temp_dir / "events.db")
        event_id = manager.log_event("VIOLATION", "No Helmet")
        self.assertFalse(manager.update_event_status(event_id, "DELETE FROM events"))
        self.assertTrue(manager.update_event_status(event_id, "ACKNOWLEDGED"))

        record = manager.save_snapshot(np.zeros((32, 32, 3), dtype=np.uint8), ["../../no-helmet"])
        self.assertIsNotNone(record)
        self.assertTrue(Path(record["path"]).is_file())
        self.assertNotIn("..", Path(record["path"]).name)


if __name__ == "__main__":
    unittest.main()
