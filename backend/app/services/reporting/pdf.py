"""PDF audit report generation from real database records (reportlab)."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Incident

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1x", parent=styles["Heading1"], fontSize=16, spaceAfter=6)
H2 = ParagraphStyle("H2x", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("Bodyx", parent=styles["BodyText"], fontSize=9, leading=12)
SMALL = ParagraphStyle("Smallx", parent=styles["BodyText"], fontSize=7.5, leading=9, textColor=colors.grey)


def _safe(value, fallback: str = "—") -> str:
    return escape(str(value)) if value is not None and str(value) else fallback


def build_incident_pdf(db, incident: Incident) -> bytes:
    """Build a downloadable audit report for one incident."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    story = []

    claim = incident.claim
    snap = incident.snapshot
    site_domain = ""
    if snap is not None:
        from urllib.parse import urlparse

        site_domain = urlparse(snap.url).netloc

    story.append(Paragraph("MedGuard AI — Incident Audit Report", H1))
    story.append(Paragraph(
        f"Incident {_safe(incident.public_id)} · Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"Status: {_safe(incident.status)} · Priority: {_safe(incident.priority)}",
        SMALL,
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Finding", H2))
    story.append(Paragraph(_safe(incident.title), BODY))
    story.append(Paragraph(f"Verdict: <b>{_safe(incident.verdict)}</b>", BODY))
    story.append(Spacer(1, 4))

    story.append(Paragraph("Monitored page", H2))
    story.append(Paragraph(f"Site: {_safe(site_domain)}<br/>URL: {_safe(snap.url if snap else None)}", BODY))
    if snap:
        story.append(Paragraph(
            f"Snapshot fetched: {snap.fetched_at.strftime('%Y-%m-%d %H:%M UTC') if snap.fetched_at else '—'} · "
            f"Content hash: sha256:{snap.content_hash[:16]}…",
            BODY,
        ))

    story.append(Paragraph("Original medical claim (model-extracted)", H2))
    if claim:
        story.append(Paragraph(f"“{_safe(claim.statement)}”", BODY))
        story.append(Paragraph(
            f"Category: {_safe(claim.category)} · Medication: {_safe(claim.medication)} · "
            f"Population: {_safe(claim.population)} · Formulation: {_safe(claim.formulation)} · "
            f"Dosage: {_safe(claim.dosage)}",
            BODY,
        ))
        story.append(Paragraph(
            f"Extracted by {_safe(claim.extraction_model)} (confidence {claim.extraction_confidence or 0:.2f}) · "
            f"Character offsets [{claim.offsets_start}, {claim.offsets_end}]",
            SMALL,
        ))

    story.append(Paragraph("Evidence (verified source material)", H2))
    if incident.evidence:
        for ev in incident.evidence:
            doc_row = ev.document
            story.append(Paragraph(
                f"<b>{_safe(doc_row.authority if doc_row else None)}</b> — {_safe(doc_row.title if doc_row else None)} "
                f"(v{_safe(doc_row.version if doc_row else None, '?')}, effective {_safe(doc_row.effective_date if doc_row else None)})",
                BODY,
            ))
            story.append(Paragraph(f"Section: {_safe(ev.section)}", BODY))
            story.append(Paragraph(f"“{_safe(ev.quote)}”", BODY))
            story.append(Paragraph(f"Source: {_safe(doc_row.source_url if doc_row else None)}", SMALL))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("No authoritative evidence was matched to this claim.", BODY))

    story.append(Paragraph("Verification rationale (model-generated analysis)", H2))
    story.append(Paragraph(_safe(incident.rationale), BODY))

    story.append(Paragraph("Risk assessment (triage aid, not a clinical judgment)", H2))
    risk_data = [
        ["Component", "Value"],
        ["Harm", f"{incident.harm:.2f}"],
        ["Exposure", f"{incident.exposure:.2f}"],
        ["Evidence strength", f"{incident.evidence_strength:.2f}"],
        ["Uncertainty", f"{incident.uncertainty:.2f}"],
        ["Priority", incident.priority],
    ]
    t = Table(risk_data, colWidths=[60 * mm, 40 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(t)

    story.append(Paragraph("Investigation trace", H2))
    for tr in incident.trace:
        story.append(Paragraph(
            f"· {tr.at.strftime('%Y-%m-%d %H:%M')} — <b>{_safe(tr.step)}</b>: {_safe(tr.detail)}", BODY
        ))

    story.append(Paragraph("Reviewer status", H2))
    if incident.reviews:
        r = incident.reviews[-1]
        story.append(Paragraph(
            f"{_safe(r.decision)} by {_safe(r.reviewer.name)} on {r.created_at.strftime('%Y-%m-%d %H:%M UTC')}: “{_safe(r.rationale)}”",
            BODY,
        ))
    else:
        story.append(Paragraph("Awaiting human review.", BODY))

    story.append(Paragraph("Recommended human follow-up", H2))
    followups = {
        "POTENTIAL_CONTRADICTION": "Have a qualified clinician verify the conflict and notify the site owner for correction.",
        "POSSIBLY_OUTDATED": "Confirm whether the page reflects the latest guidance; request an update from the site owner.",
        "INCOMPLETE_INFORMATION": "Review the page for missing safety qualifiers with a subject-matter expert.",
        "INSUFFICIENT_EVIDENCE": "Manually assess the claim; the knowledge base has no matching authoritative source.",
        "SUPPORTED": "No action required unless the source material changes.",
    }
    story.append(Paragraph(followups.get(incident.verdict, "Human review required."), BODY))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "DISCLAIMER: MedGuard AI is a medical content quality-assurance tool, not a clinical decision-making system. "
        "Model-generated analysis is clearly distinguished above from verified source material. "
        "Potentially harmful findings require expert review before any statement is treated as a confirmed medical error.",
        SMALL,
    ))

    doc.build(story)
    return buf.getvalue()
