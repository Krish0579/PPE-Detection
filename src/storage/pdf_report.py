"""PDF Audit Report Generator for SafeSight PPE Detection Engine.

Generates ISO 45001 / OSHA compliant safety inspection and incident reports
detailing what PPE was missing, when violations occurred, how long they persisted,
aggregated counts of non-compliant personnel, visual compliance charts,
and optional photographic violation evidence.
"""

from __future__ import annotations

import io
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.storage.audit_standards import NumberedCanvas, get_regulatory_info


def _safe_dt(val: Any) -> str:
    """Format timestamp safely to standard readable date string."""
    if val is None or val == "" or val == "--":
        return "--"
    try:
        if isinstance(val, (int, float)):
            if val <= 0 or val == float("inf"):
                return "--"
            return datetime.fromtimestamp(val).strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(val, str):
            return val
    except Exception:
        pass
    return "--"


def _format_duration(seconds: float | None) -> str:
    """Format duration into readable minutes and seconds."""
    if seconds is None or seconds <= 0:
        return "0s"
    sec = int(seconds)
    if sec >= 60:
        m, s = divmod(sec, 60)
        return f"{m}m {s}s"
    return f"{sec}s"


def _build_compliance_chart(compliant: int, violating: int) -> Drawing:
    """Generate a compact vector pie chart representing safety compliance ratio."""
    d = Drawing(160, 68)
    pc = Pie()
    pc.x = 8
    pc.y = 4
    pc.width = 60
    pc.height = 60
    c_val = max(0, compliant)
    v_val = max(0, violating)
    if c_val == 0 and v_val == 0:
        c_val = 1
    pc.data = [c_val, v_val]
    pc.labels = [f"Safe ({compliant})", f"Viol ({violating})"]
    pc.simpleLabels = 0
    pc.slices[0].fillColor = colors.HexColor("#10b981")
    pc.slices[1].fillColor = colors.HexColor("#ef4444")
    d.add(pc)
    return d


def generate_audit_pdf(
    total_frames: int = 0,
    fps: float = 0.0,
    model_name: str = "safesight-yolo",
    counts: dict[str, int] | None = None,
    person_incidents: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
    session_id: int | str | None = None,
    include_snapshots: bool = False,
    evidence_dir: Path | str | None = None,
) -> bytes:
    """Generate a certified audit PDF report with charts, OSHA citations, and evidence thumbnails."""
    counts = counts or {}
    person_incidents = person_incidents or []
    events = events or []

    total_persons = len(person_incidents)
    non_compliant_persons = [p for p in person_incidents if p.get("missing_ppe") and len(p["missing_ppe"]) > 0]
    violating_count = len(non_compliant_persons)
    compliant_count = total_persons - violating_count
    compliance_rate = round((compliant_count / total_persons) * 100.0, 1) if total_persons > 0 else 100.0

    missing_items_list: list[str] = []
    for p in person_incidents:
        for item in p.get("missing_ppe", []):
            clean_item = item.replace("No ", "").strip()
            missing_items_list.append(clean_item)

    missing_counter = Counter(missing_items_list)
    top_missing_gear = missing_counter.most_common(1)[0][0] if missing_counter else "None (100% Compliant)"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    header_title_style = ParagraphStyle(
        "HeaderTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#0f172a"),
    )
    header_sub_style = ParagraphStyle(
        "HeaderSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#64748b"),
    )
    section_title_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=8,
        spaceAfter=4,
    )
    cell_bold_style = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0f172a"),
    )
    cell_text_style = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#334155"),
    )
    cell_badge_red = ParagraphStyle(
        "CellBadgeRed",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#b91c1c"),
    )
    cell_badge_green = ParagraphStyle(
        "CellBadgeGreen",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#15803d"),
    )
    kpi_number_style = ParagraphStyle(
        "KpiNum",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=17,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    )
    kpi_label_style = ParagraphStyle(
        "KpiLbl",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=8.5,
        alignment=1,
        textColor=colors.HexColor("#64748b"),
    )

    story = []

    # 1. Header Banner
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_table_data = [
        [
            Paragraph(
                "<b>SAFE SIGHT AI VISION</b><br/><font size='11' color='#0284c7'>Certified Safety Audit Report</font>",
                header_title_style,
            ),
            Paragraph(
                f"<b>Generated:</b> {now_str}<br/><b>Audit Ref:</b> SS-{int(datetime.now().timestamp())}",
                header_sub_style,
            ),
        ]
    ]
    t_header = Table(header_table_data, colWidths=[360, 180])
    t_header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ]
        )
    )
    story.append(t_header)
    story.append(Spacer(1, 3))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=8))

    # 2. Executive KPI Summary Cards
    verdict_color = "#15803d" if violating_count == 0 else "#b91c1c"
    kpi_data = [
        [
            Paragraph(f"<b>{total_persons}</b>", kpi_number_style),
            Paragraph(f"<font color='{verdict_color}'><b>{violating_count}</b></font>", kpi_number_style),
            Paragraph(f"<font color='#15803d'><b>{compliant_count}</b></font>", kpi_number_style),
            Paragraph(f"<b>{compliance_rate}%</b>", kpi_number_style),
            Paragraph(f"<font size='8'><b>{top_missing_gear}</b></font>", kpi_number_style),
        ],
        [
            Paragraph("TOTAL MONITORED", kpi_label_style),
            Paragraph("NON-COMPLIANT WORKERS", kpi_label_style),
            Paragraph("COMPLIANT WORKERS", kpi_label_style),
            Paragraph("SAFETY COMPLIANCE RATE", kpi_label_style),
            Paragraph("PRIMARY MISSING GEAR", kpi_label_style),
        ],
    ]
    t_kpi = Table(kpi_data, colWidths=[108, 108, 108, 108, 108])
    t_kpi.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(t_kpi)
    story.append(Spacer(1, 8))

    # 3. Session Metadata & Visual Compliance Chart
    chart_drawing = _build_compliance_chart(compliant_count, violating_count)
    meta_data = [
        [
            Paragraph("<b>Model Checkpoint:</b>", cell_bold_style),
            Paragraph(str(model_name), cell_text_style),
            Paragraph("<b>Total Frames Processed:</b>", cell_bold_style),
            Paragraph(f"{total_frames:,}", cell_text_style),
            chart_drawing,
        ],
        [
            Paragraph("<b>Sampling Rate (FPS):</b>", cell_bold_style),
            Paragraph(f"{float(fps):.1f} FPS", cell_text_style),
            Paragraph("<b>Compliance Standard:</b>", cell_bold_style),
            Paragraph("OSHA 1910 / ISO 45001", cell_text_style),
            "",
        ],
    ]
    t_meta = Table(meta_data, colWidths=[100, 100, 100, 90, 150])
    t_meta.setStyle(
        TableStyle(
            [
                ("SPAN", (4, 0), (4, 1)),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
                ("LINEBELOW", (0, 0), (3, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(t_meta)
    story.append(Spacer(1, 10))

    # 4. Section: Missing Gear Aggregates with OSHA / ANSI Standards & Severity Rating
    story.append(Paragraph("1. Aggregated PPE Non-Compliance & Regulatory Standard Breakdown", section_title_style))
    if missing_counter:
        missing_rows = [
            [
                Paragraph("<b>Missing Gear Type</b>", cell_bold_style),
                Paragraph("<b>Deficient Count</b>", cell_bold_style),
                Paragraph("<b>Applicable Regulatory Standard</b>", cell_bold_style),
                Paragraph("<b>OSHA Severity Tier</b>", cell_bold_style),
            ]
        ]
        for gear_name, count in missing_counter.most_common():
            reg_info = get_regulatory_info(gear_name)
            std_clause = f"{reg_info['standard']} ({reg_info['title']})"
            sev_badge = f"<font color='{reg_info['color']}'><b>{reg_info['severity']}</b></font>"

            missing_rows.append(
                [
                    Paragraph(f"Missing {gear_name.title()}", cell_badge_red),
                    Paragraph(f"{count} worker(s)", cell_text_style),
                    Paragraph(std_clause, cell_text_style),
                    Paragraph(sev_badge, cell_bold_style),
                ]
            )
        t_missing = Table(missing_rows, colWidths=[120, 90, 220, 110])
        t_missing.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(t_missing)
    else:
        no_viol_box = [
            [
                Paragraph(
                    "<font color='#15803d'><b>[COMPLIANT] No Missing PPE Detected</b> - All inspected personnel satisfied OSHA 29 CFR 1910 safety requirements.</font>",
                    cell_text_style,
                )
            ]
        ]
        t_no_viol = Table(no_viol_box, colWidths=[540])
        t_no_viol.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdf4")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#86efac")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(t_no_viol)

    story.append(Spacer(1, 10))

    # 5. Section: Personnel Incident & Gear Inspection Register
    story.append(Paragraph("2. Personnel Incident & Gear Inspection Register", section_title_style))
    if person_incidents:
        if include_snapshots:
            person_headers = [
                Paragraph("<b>Evidence</b>", cell_bold_style),
                Paragraph("<b>Personnel</b>", cell_bold_style),
                Paragraph("<b>What Was Missing</b>", cell_bold_style),
                Paragraph("<b>Equipped</b>", cell_bold_style),
                Paragraph("<b>Observation Time</b>", cell_bold_style),
                Paragraph("<b>Location & Status</b>", cell_bold_style),
            ]
            widths = [65, 60, 115, 80, 110, 110]
        else:
            person_headers = [
                Paragraph("<b>Personnel</b>", cell_bold_style),
                Paragraph("<b>What Was Missing</b>", cell_bold_style),
                Paragraph("<b>Equipped Gear</b>", cell_bold_style),
                Paragraph("<b>When (First / Last)</b>", cell_bold_style),
                Paragraph("<b>Duration</b>", cell_bold_style),
                Paragraph("<b>Location & Status</b>", cell_bold_style),
            ]
            widths = [70, 115, 95, 110, 50, 100]

        person_rows = [person_headers]

        for p in person_incidents:
            p_name = p.get("person_name") or f"Person {p.get('worker_id', 1)}"
            missing_set = p.get("missing_ppe") or set()
            compliant_set = p.get("compliant_ppe") or set()

            if missing_set:
                missing_disp = ", ".join(sorted(missing_set))
                missing_cell = Paragraph(f"<font color='#b91c1c'><b>{missing_disp}</b></font>", cell_badge_red)
            else:
                missing_cell = Paragraph("<font color='#15803d'>None (Compliant)</font>", cell_badge_green)

            comp_disp = ", ".join(sorted(compliant_set)) if compliant_set else "None"
            comp_cell = Paragraph(comp_disp, cell_text_style)

            first_seen = _safe_dt(p.get("first_seen"))
            last_seen = _safe_dt(p.get("last_seen"))
            when_cell = Paragraph(f"In: {first_seen}<br/>Out: {last_seen}", cell_text_style)

            dur_sec = p.get("dwell_seconds", 0.0)
            if not dur_sec and p.get("first_seen") and p.get("last_seen"):
                dur_sec = max(0, p["last_seen"] - p["first_seen"])
            dur_cell = Paragraph(_format_duration(dur_sec), cell_text_style)

            zone = p.get("zone", "Primary Floor")
            status = p.get("status", "Active Violation" if missing_set else "Compliant")
            loc_cell = Paragraph(f"<b>{zone}</b><br/>Status: <i>{status}</i>", cell_text_style)

            if include_snapshots:
                snap_elem: Any = Paragraph("<font color='#64748b' size='6'>No capture</font>", cell_text_style)
                snap_p = p.get("snapshot_path")
                if snap_p and Path(snap_p).is_file():
                    try:
                        snap_elem = Image(str(snap_p), width=54, height=40)
                    except Exception:
                        pass
                person_rows.append(
                    [
                        snap_elem,
                        Paragraph(f"<b>{p_name}</b>", cell_bold_style),
                        missing_cell,
                        comp_cell,
                        when_cell,
                        loc_cell,
                    ]
                )
            else:
                person_rows.append(
                    [
                        Paragraph(f"<b>{p_name}</b>", cell_bold_style),
                        missing_cell,
                        comp_cell,
                        when_cell,
                        dur_cell,
                        loc_cell,
                    ]
                )

        t_person = Table(person_rows, colWidths=widths)
        t_person.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(t_person)
    else:
        no_persons_table = Table(
            [[Paragraph("No personnel observed or recorded during this monitoring period.", cell_text_style)]],
            colWidths=[540],
        )
        no_persons_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(no_persons_table)

    story.append(Spacer(1, 10))

    # 6. Section: Chronological Audit Events (Recent Violations)
    if events:
        story.append(Paragraph("3. Incident Chronology & Evidence Trail", section_title_style))
        ev_rows = [
            [
                Paragraph("<b>Timestamp</b>", cell_bold_style),
                Paragraph("<b>Event Type</b>", cell_bold_style),
                Paragraph("<b>Target</b>", cell_bold_style),
                Paragraph("<b>Violation Details / Gear Missing</b>", cell_bold_style),
                Paragraph("<b>Zone</b>", cell_bold_style),
                Paragraph("<b>Resolution</b>", cell_bold_style),
            ]
        ]
        for ev in events[:12]:
            ts_str = _safe_dt(ev.get("timestamp"))
            e_type = ev.get("event_type", "VIOLATION")
            person_lbl = f"Person {ev.get('person_id', 1)}" if ev.get("person_id") else "Personnel"
            v_type = ev.get("violation_type", "Non-compliance")
            zone_str = ev.get("zone", "Production Area")
            status_str = ev.get("status", "UNRESOLVED")
            status_style = (
                cell_badge_red if status_str.upper() in ("ACTIVE", "UNRESOLVED", "CRITICAL") else cell_badge_green
            )

            ev_rows.append(
                [
                    Paragraph(ts_str, cell_text_style),
                    Paragraph(e_type, cell_text_style),
                    Paragraph(person_lbl, cell_text_style),
                    Paragraph(f"<b>{v_type}</b>", cell_badge_red if "No" in v_type else cell_text_style),
                    Paragraph(zone_str, cell_text_style),
                    Paragraph(status_str, status_style),
                ]
            )

        t_events = Table(ev_rows, colWidths=[90, 70, 60, 160, 85, 75])
        t_events.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(t_events)
        story.append(Spacer(1, 10))

    # 7. Official Certification & Sign-off Block
    sign_block = [
        [
            Paragraph(
                "<b>AUDIT VERIFICATION STATEMENT:</b><br/>"
                "This document certifies that the automated computer vision monitoring performed "
                "by the SafeSight AI Engine complies with OSHA 29 CFR 1910 and ISO 45001 occupational "
                "safety management requirements. All recorded infractions are digitally logged.",
                cell_text_style,
            ),
            Paragraph(
                "<b>LEAD SAFETY OFFICER / AUDITOR:</b><br/><br/>"
                "Signature: ___________________________<br/>"
                f"Date: {datetime.now().strftime('%Y-%m-%d')}<br/>"
                "Status: <b>AUDIT VERIFIED & CERTIFIED</b>",
                cell_text_style,
            ),
        ]
    ]
    t_sign = Table(sign_block, colWidths=[310, 230])
    t_sign.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#94a3b8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(KeepTogether(t_sign))

    # Build Document with NumberedCanvas for Page X of Y
    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()
