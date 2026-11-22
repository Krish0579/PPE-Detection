"""CSV / JSON / executive PDF exporters over :class:`ReportData`."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict

from src.reporting.model import ReportData

CSV_COLUMNS = (
    "id",
    "opened_at",
    "camera_id",
    "zone_id",
    "violation",
    "severity",
    "state",
    "occurrences",
    "evidence_count",
    "human_reviewed",
)

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value: object) -> object:
    """Neutralise spreadsheet formula injection in exported text cells."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def to_csv(report: ReportData) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in report.incidents:
        writer.writerow({k: _safe_cell(row.get(k, "")) for k in CSV_COLUMNS})
    return buffer.getvalue()


def to_json(report: ReportData) -> str:
    return json.dumps(asdict(report), indent=2, sort_keys=True, default=str)


def to_pdf(report: ReportData) -> bytes:
    """Executive summary PDF generated from the data model (requires reportlab)."""
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=report.title, author="SAFE SIGHT AI")
    story = [
        Paragraph(escape(report.title), styles["Title"]),
        Paragraph(escape(f"Period: {report.period_start} → {report.period_end}"), styles["Normal"]),
        Paragraph(escape(f"Generated {report.generated_at} by {report.generated_by}"), styles["Normal"]),
        Spacer(1, 12),
    ]

    def table(title: str, rows: list[list[object]]) -> None:
        story.append(Paragraph(escape(title), styles["Heading2"]))
        if len(rows) <= 1:
            story.append(Paragraph("No data for this period.", styles["Normal"]))
            return
        tbl = Table([[escape(str(c)) for c in r] for r in rows], hAlign="LEFT")
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9ca3af")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.extend([tbl, Spacer(1, 10)])

    table("Summary", [["Metric", "Value"], *[[k, v] for k, v in report.totals.items()]])
    table("Incidents by severity", [["Severity", "Count"], *report.by_severity.items()])
    table("Incidents by zone", [["Zone", "Count"], *report.by_zone.items()])
    table("Daily trend", [["Date", "Incidents"], *report.daily_trend.items()])
    table(
        "Unresolved incidents",
        [["ID", "Zone", "Violation", "Severity", "State"]]
        + [[u["id"], u["zone_id"], u["violation"], u["severity"], u["state"]] for u in report.unresolved[:50]],
    )
    table(
        "Corrective actions",
        [["Incident", "At", "Actor", "Action", "Note"]]
        + [[a["incident_id"], a["at"][:19], a["actor"], a["action"], a["note"][:60]] for a in report.corrective_actions[:50]],
    )
    refs = [
        [c["detected_condition"], f"{r['standard']} {r['citation']}", r["title"]]
        for c in report.compliance
        for r in c["references"]
    ]
    table("Configured requirement references", [["Detected condition", "Reference", "Title"], *refs])
    story.append(Paragraph(escape(report.disclaimer), styles["Italic"]))
    doc.build(story)
    return buffer.getvalue()
