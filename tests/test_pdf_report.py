"""Tests for Certified Audit PDF report generation and UI integration."""
import io
import time
from unittest.mock import MagicMock, patch

from pypdf import PdfReader

from src.storage.evidence import EvidenceManager
from src.storage.pdf_report import generate_audit_pdf
from src.ui.components import render_reports_view


def test_generate_audit_pdf_returns_valid_pdf_bytes_and_content():
    """Verify that generate_audit_pdf generates valid PDF data with all expected audit details."""
    now = time.time()
    personnel = [
        {
            "worker_id": 1,
            "person_name": "Person 1",
            "missing_ppe": {"No Helmet", "No Safety Vest"},
            "compliant_ppe": {"Boots", "Gloves"},
            "zone": "CAM-01 · Production Floor Primary",
            "first_seen": now - 120,
            "last_seen": now,
            "dwell_seconds": 120.0,
            "status": "Active Violation",
        },
        {
            "worker_id": 2,
            "person_name": "Person 2",
            "missing_ppe": set(),
            "compliant_ppe": {"Helmet", "Vest", "Boots", "Gloves"},
            "zone": "CAM-02 · Loading Dock",
            "first_seen": now - 300,
            "last_seen": now,
            "dwell_seconds": 300.0,
            "status": "Compliant",
        },
    ]
    events = [
        {
            "id": 101,
            "timestamp": now - 60,
            "event_type": "VIOLATION",
            "violation_type": "No Helmet, No Safety Vest",
            "person_id": 1,
            "zone": "CAM-01 · Production Floor Primary",
            "status": "UNRESOLVED",
        }
    ]
    counts = {"person": 2, "helmet": 1, "vest": 1}

    pdf_bytes = generate_audit_pdf(
        total_frames=1500,
        fps=29.97,
        model_name="yolov8n-ppe.pt",
        counts=counts,
        person_incidents=personnel,
        events=events,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")

    # Read PDF text content with pypdf
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    extracted_text = " ".join([page.extract_text() for page in reader.pages])

    # Check Executive Metrics ("how many hasn't")
    assert "SAFE SIGHT" in extracted_text
    assert "Certified Safety Audit Report" in extracted_text
    assert "TOTAL MONITORED" in extracted_text
    assert "NON-COMPLIANT" in extracted_text
    assert "COMPLIANT" in extracted_text

    # Check Personnel Breakdown ("who, what, when, how")
    assert "Person 1" in extracted_text
    assert "Helmet" in extracted_text
    assert "Safety Vest" in extracted_text
    assert "CAM-01" in extracted_text
    assert "Active Violation" in extracted_text

    # Check Compliance / OSHA statement
    assert "OSHA" in extracted_text or "ISO 45001" in extracted_text


def test_generate_audit_pdf_empty_session():
    """Verify PDF generation succeeds gracefully for empty sessions with no personnel."""
    pdf_bytes = generate_audit_pdf(
        total_frames=0,
        fps=0.0,
        model_name="safesight-core",
        counts={},
        person_incidents=[],
        events=[],
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")

    reader = PdfReader(io.BytesIO(pdf_bytes))
    extracted_text = " ".join([page.extract_text() for page in reader.pages])
    assert "No Missing PPE Detected" in extracted_text or "100%" in extracted_text


def test_evidence_manager_generate_pdf_report(tmp_path):
    """Verify EvidenceManager wraps generate_audit_pdf properly."""
    mgr = EvidenceManager(storage_dir=tmp_path)
    now = time.time()
    events = [
        {
            "id": 1,
            "timestamp": now,
            "event_type": "VIOLATION",
            "violation_type": "No Vest",
            "person_id": 1,
            "zone": "CAM-01",
            "status": "UNRESOLVED",
        }
    ]
    pdf_bytes = mgr.generate_pdf_report(
        total_frames=100,
        fps=30.0,
        model_name="yolov8n-ppe.pt",
        counts={"person": 1, "no-vest": 1},
        events=events,
        person_incidents=[
            {
                "worker_id": 1,
                "person_name": "Person 1",
                "missing_ppe": {"No Vest"},
                "compliant_ppe": {"Helmet"},
                "zone": "CAM-01",
                "first_seen": now - 30,
                "last_seen": now,
                "status": "Active Violation",
            }
        ],
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")


def test_render_reports_view_offers_pdf_download(tmp_path):
    """Verify render_reports_view provides the Certified Audit PDF download button."""
    mgr = EvidenceManager(storage_dir=tmp_path)

    col1_mock = MagicMock()
    col2_mock = MagicMock()

    with patch("streamlit.columns", return_value=(col1_mock, col2_mock)), \
         patch("src.ui.components.render_html"):
        render_reports_view(
            evidence_mgr=mgr,
            total_frames=50,
            fps=25.0,
            model_name="yolov8n.pt",
            counts={"person": 1},
            detections=[],
            events=[],
            workers=[],
        )

        # col1 should download CSV
        col1_mock.download_button.assert_called_once()
        c1_kwargs = col1_mock.download_button.call_args.kwargs
        assert c1_kwargs["mime"] == "text/csv"

        # col2 should download PDF instead of JSON
        col2_mock.download_button.assert_called_once()
        c2_kwargs = col2_mock.download_button.call_args.kwargs
        assert "PDF" in c2_kwargs["label"]
        assert c2_kwargs["mime"] == "application/pdf"
        assert c2_kwargs["file_name"].endswith(".pdf")
        assert isinstance(c2_kwargs["data"], bytes)
        assert c2_kwargs["data"].startswith(b"%PDF-")


def test_generate_audit_pdf_includes_osha_and_severity():
    """Verify PDF contains explicit OSHA standard clauses, severity levels, and page numbering."""
    now = time.time()
    personnel = [
        {
            "worker_id": 1,
            "person_name": "Person 1",
            "missing_ppe": {"No Helmet"},
            "compliant_ppe": {"Vest"},
            "zone": "CAM-01 · Production Floor",
            "first_seen": now - 60,
            "last_seen": now,
            "dwell_seconds": 60.0,
            "status": "Active Violation",
        }
    ]
    pdf_bytes = generate_audit_pdf(
        total_frames=500,
        fps=30.0,
        model_name="yolov8n-ppe.pt",
        counts={"person": 1, "no-helmet": 1},
        person_incidents=personnel,
        events=[],
    )
    reader = PdfReader(io.BytesIO(pdf_bytes))
    extracted_text = " ".join([page.extract_text() for page in reader.pages])

    # Regulatory standard clause
    assert "29 CFR 1910.135" in extracted_text or "Head Protection" in extracted_text
    # Severity classification
    assert "CRITICAL" in extracted_text or "HIGH" in extracted_text
    # Two-pass page numbering
    assert "Page 1 of" in extracted_text


def test_generate_audit_pdf_with_snapshot_thumbnail(tmp_path):
    """Verify PDF can embed photo evidence thumbnail for non-compliant incidents."""
    from PIL import Image

    snap_file = tmp_path / "viol_test_01.jpg"
    img = Image.new("RGB", (120, 90), color=(200, 50, 50))
    img.save(snap_file, format="JPEG")

    now = time.time()
    personnel = [
        {
            "worker_id": 1,
            "person_name": "Person 1",
            "missing_ppe": {"No Helmet"},
            "compliant_ppe": set(),
            "zone": "CAM-01",
            "first_seen": now - 30,
            "last_seen": now,
            "snapshot_path": str(snap_file),
            "status": "Active Violation",
        }
    ]
    pdf_bytes = generate_audit_pdf(
        total_frames=200,
        fps=30.0,
        model_name="yolov8n-ppe.pt",
        counts={"person": 1},
        person_incidents=personnel,
        events=[],
        include_snapshots=True,
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000

