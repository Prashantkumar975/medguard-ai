"""PDF audit report generation from real database records (reportlab)."""
from __future__ import annotations

import io
from datetime import datetime, timezone

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
        f"Incident {incident.public_id} · Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"Status: {incident.status} · Priority: {incident.priority}",
        SMALL,
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Finding", H2))
    story.append(Paragraph(incident.title, BODY))
    story.append(Paragraph(f"Verdict: <b>{incident.verdict}</b>", BODY))
    story.append(Spacer(1, 4))

    story.append(Paragraph("Monitored page", H2))
    story.append(Paragraph(f"Site: {site_domain or '—'}<br/>URL: {snap.url if snap else '—'}", BODY))
    if snap:
        story.append(Paragraph(
            f"Snapshot fetched: {snap.fetched_at.strftime('%Y-%m-%d %H:%M UTC') if snap.fetched_at else '—'} · "
            f"Content hash: sha256:{snap.content_hash[:16]}…",
            BODY,
        ))

    story.append(Paragraph("Original medical claim (model-extracted)", H2))
    if claim:
        story.append(Paragraph(f"“{claim.statement}”", BODY))
        story.append(Paragraph(
            f"Category: {claim.category or '—'} · Medication: {claim.medication or '—'} · "
            f"Population: {claim.population or '—'} · Formulation: {claim.formulation or '—'} · "
            f"Dosage: {claim.dosage or '—'}",
            BODY,
        ))
        story.append(Paragraph(
            f"Extracted by {claim.extraction_model} (confidence {claim.extraction_confidence or 0:.2f}) · "
            f"Character offsets [{claim.offsets_start}, {claim.offsets_end}]",
            SMALL,
        ))

    story.append(Paragraph("Evidence (verified source material)", H2))
    if incident.evidence:
        for ev in incident.evidence:
            doc_row = ev.document
            story.append(Paragraph(
                f"<b>{doc_row.authority if doc_row else '—'}</b> — {doc_row.title if doc_row else '—'} "
                f"(v{doc_row.version if doc_row else '?'}, effective {doc_row.effective_date if doc_row else '—'})",
                BODY,
            ))
            story.append(Paragraph(f"Section: {ev.section or '—'}", BODY))
            story.append(Paragraph(f"“{ev.quote}”", BODY))
            story.append(Paragraph(f"Source: {doc_row.source_url if doc_row else '—'}", SMALL))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("No authoritative evidence was matched to this claim.", BODY))

    story.append(Paragraph("Verification rationale (model-generated analysis)", H2))
    story.append(Paragraph(incident.rationale or "—", BODY))

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
            f"· {tr.at.strftime('%Y-%m-%d %H:%M')} — <b>{tr.step}</b>: {tr.detail}", BODY
        ))

    story.append(Paragraph("Reviewer status", H2))
    if incident.reviews:
        r = incident.reviews[-1]
        story.append(Paragraph(
            f"{r.decision} by {r.reviewer.name} on {r.created_at.strftime('%Y-%m-%d %H:%M UTC')}: “{r.rationale}”",
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
