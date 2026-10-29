"""LangGraph multi-agent investigation workflow.

Pipeline: crawl/snapshot -> claim extraction -> evidence retrieval ->
verification -> risk assessment -> incident generation -> human review.

Deterministic steps (crawling, hashing, risk, permissions) are plain code; the
LLM is used only for claim extraction and semantic comparison. Investigation runs
are persisted to agent_runs so interrupted jobs can be diagnosed or resumed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import (
    AgentRun,
    Claim,
    Evidence,
    Incident,
    Notification,
    OrgSetting,
    ReferenceChunk,
    Scan,
    Site,
    Snapshot,
    new_id,
)
from app.services.crawler.crawler import crawl_site
from app.services.extraction.claims import extract_claims
from app.services.retrieval.search import hybrid_search
from app.services.risk import engine as risk_engine
from app.services.verification import verify as verify_mod

log = logging.getLogger(__name__)


class PipelineState(TypedDict, total=False):
    scan_id: str
    site_id: str
    organization_id: str
    run_id: str
    urls: list[str]
    changed_pages: list[dict]
    claims: list[dict]
    incidents_created: list[str]
    warnings: list[str]
    error: str


def _record_trace(db, incident_id: str, step: str, detail: str) -> None:
    from app.models import IncidentTrace

    db.add(IncidentTrace(incident_id=incident_id, step=step, detail=detail))


def node_crawl(state: PipelineState) -> PipelineState:
    """Discovery + snapshots + change detection (deterministic)."""
    db = SessionLocal()
    try:
        scan = db.get(Scan, state["scan_id"])
        site = db.get(Site, state["site_id"])
        scan.status = "running"
        scan.started_at = datetime.now(timezone.utc)
        db.commit()

        result = crawl_site(db, scan, site)
        changed = [
            {"url": p.url, "hash": p.content_hash, "text": p.text,
             "snapshot_id": p.snapshot_id, "last_modified": p.last_modified}
            for p in result.pages
            if p.changed or p.extraction_pending
        ]
        if result.errors and not result.pages:
            scan.status = "failed"
            scan.error = "; ".join(result.errors)[:2000]
            scan.finished_at = datetime.now(timezone.utc)
            scan.duration_s = max(0, int((scan.finished_at - scan.started_at).total_seconds())) if scan.started_at else 0
            site.last_scan_status = "failed"
            db.commit()
            return {"error": scan.error, "changed_pages": []}
        return {"changed_pages": changed}
    finally:
        db.close()


def node_extract(state: PipelineState) -> PipelineState:
    """Claim extraction with the configured open-weight model (real, never mocked)."""
    db = SessionLocal()
    try:
        scan = db.get(Scan, state["scan_id"])
        all_claims: list[dict] = []
        extraction_failed = False
        for page in state.get("changed_pages", []):
            snap = db.get(Snapshot, page.get("snapshot_id"))
            if snap is None:
                continue
            claims, failures = extract_claims(page["text"], page["url"])
            for f in failures:
                log.warning("extraction failure %s: %s — %s", f.reason, f.url, f.detail)
            for c in claims:
                rec = c.model_dump()
                rec["snapshot_id"] = snap.id
                rec["url"] = page["url"]
                all_claims.append(rec)
            failed = [f for f in failures if f.reason in {"model_unavailable", "invalid_output"}]
            extraction_failed = extraction_failed or bool(failed)
            snap.extraction_status = "failed" if failed else "completed"
            snap.extraction_error = "; ".join(f.detail for f in failed)[:2000] or None
        scan.claims_extracted = len(all_claims)
        db.commit()
        if not all_claims and extraction_failed:
            # Failed snapshots stay eligible for extraction on the next scan.
            scan.status = "failed"
            scan.finished_at = datetime.now(timezone.utc)
            scan.error = "Claim extraction failed; the page will be retried on the next scan."
            scan.duration_s = max(0, int((scan.finished_at - scan.started_at).total_seconds())) if scan.started_at else 0
            db.commit()
            return {"error": scan.error, "claims": []}
        return {"claims": all_claims}
    finally:
        db.close()


def node_verify(state: PipelineState) -> PipelineState:
    """Evidence retrieval + verification + risk + incident persistence."""
    db = SessionLocal()
    created: list[str] = []
    try:
        org = state["organization_id"]
        site = db.get(Site, state["site_id"])
        scan = db.get(Scan, state["scan_id"])
        run_id = state.get("run_id") or "manual"

        from app.services.extraction.claims import ExtractedClaim

        for rec in state.get("claims", []):
            claim_model = ExtractedClaim.model_validate(
                {k: rec[k] for k in (
                    "claim_text", "category", "medication", "population",
                    "formulation", "dosage", "source_offsets", "extraction_confidence",
                )}
            )
            query_parts = [claim_model.claim_text]
            if claim_model.medication:
                query_parts.append(claim_model.medication)
            hits = hybrid_search(db, org, " ".join(query_parts), jurisdiction=site.jurisdiction)

            # persist the claim row
            db_claim = Claim(
                organization_id=org,
                snapshot_id=rec["snapshot_id"],
                site_id=site.id,
                statement=claim_model.claim_text,
                context_label="; ".join(
                    value for value in (
                        claim_model.category,
                        claim_model.medication,
                        claim_model.population,
                        claim_model.formulation,
                        claim_model.dosage,
                    ) if value
                ) or None,
                offsets_start=claim_model.source_offsets[0],
                offsets_end=claim_model.source_offsets[1],
                category=claim_model.category,
                medication=claim_model.medication,
                population=claim_model.population,
                formulation=claim_model.formulation,
                dosage=claim_model.dosage,
                extraction_model=state.get("model_id", f"{settings.llm_provider}/{settings.llm_model if settings.llm_provider != 'ollama' else settings.ollama_model}"),
                extraction_confidence=claim_model.extraction_confidence,
            )
            db.add(db_claim)
            db.flush()

            evidence_texts = [h.text for h in hits]
            ev_dates = []
            ev_juris = []
            for h in hits:
                chunk = db.get(ReferenceChunk, h.chunk_id)
                doc = chunk.document if chunk else None
                ev_dates.append(doc.effective_date if doc else None)
                ev_juris.append(doc.jurisdiction if doc else None)

            snap = db.get(Snapshot, rec["snapshot_id"])
            outcome = verify_mod.verify(
                claim_model,
                evidence_texts,
                ev_dates,
                page_last_modified=snap.last_modified if snap and snap.last_modified else snap.fetched_at if snap else None,
                jurisdiction=site.jurisdiction,
                evidence_jurisdictions=ev_juris,
            )

            # Supported claims remain in the claim history but are not incidents
            # and therefore do not enter the human review queue.
            if outcome.verdict == "SUPPORTED":
                continue

            risk = risk_engine.score(
                category=claim_model.category,
                verdict=outcome.verdict,
                extraction_confidence=claim_model.extraction_confidence,
                evidence_similarities=[h.similarity for h in hits if h.similarity is not None],
                pages_hosting_claim=1,
                site_page_count=max(site.pages, 1),
                llm_relation=outcome.llm_relation,
            )

            # Dedupe: source identity + normalized claim + evidence relationship + version
            import hashlib

            top_doc = hits[0].document_id if hits else "none"
            norm_claim = " ".join(claim_model.claim_text.lower().split())[:180]
            dedupe_key = hashlib.sha256(
                f"{site.id}|{norm_claim}|{top_doc}|{snap.content_hash if snap else 'x'}".encode()
            ).hexdigest()[:32]

            existing = db.scalar(
                select(Incident).where(
                    Incident.organization_id == org,
                    Incident.dedupe_key == dedupe_key,
                )
            )
            if existing is not None:
                db.flush()
                continue

            from sqlalchemy import text

            seq = db.execute(text("SELECT nextval('incident_number_seq')")).scalar_one()
            incident = Incident(
                public_id=f"INC-{seq}",
                number=seq,
                organization_id=org,
                site_id=site.id,
                snapshot_id=rec["snapshot_id"],
                claim_id=db_claim.id,
                agent_run_id=run_id,
                scan_id=scan.id,
                title=_incident_title(claim_model, outcome.verdict),
                verdict=outcome.verdict,
                priority=risk.priority,
                status="open",
                rationale=outcome.rationale,
                harm=risk.harm,
                exposure=risk.exposure,
                evidence_strength=risk.evidence_strength,
                uncertainty=risk.uncertainty,
                dedupe_key=dedupe_key,
            )
            # The public ID is built from the database sequence, which is safe
            # across simultaneous workers and organizations.
            db.add(incident)
            db.flush()

            for rank, h in enumerate(hits[:3]):
                quote, quote_start, quote_end = _evidence_excerpt(claim_model.claim_text, h.text)
                db.add(Evidence(
                    incident_id=incident.id,
                    chunk_id=h.chunk_id,
                    document_id=h.document_id,
                    rank=rank,
                    section=h.section,
                    quote=quote,
                    offsets_start=quote_start,
                    offsets_end=quote_end,
                    similarity=h.similarity,
                    retrieval_method=h.method,
                ))

            # trace
            _record_trace(db, incident.id, "Discovery", "Page change detected and snapshot stored")
            _record_trace(db, incident.id, "Extraction", f"Claim extracted with clinical context (category: {claim_model.category})")
            _record_trace(db, incident.id, "Reference matching", f"Matched {len(hits)} reference chunk(s) from the organization library")
            _record_trace(db, incident.id, "Verification", f"Hybrid retrieval and context filters applied (relation: {outcome.llm_relation or 'n/a'})")
            for chk in outcome.structured:
                _record_trace(db, incident.id, "Structured check", f"{chk.name}: {chk.detail}")
            _record_trace(db, incident.id, "Risk Assessment", f"Priority {incident.priority} computed (composite harm={risk.harm}, exposure={risk.exposure}, evidence={risk.evidence_strength}, uncertainty={risk.uncertainty})")
            if incident.verdict != "SUPPORTED":
                org_setting = db.get(OrgSetting, org)
                notification_settings = (org_setting.notifications if org_setting else {}) or {}
                threshold = notification_settings.get("min_priority", "high")
                priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
                notify = priority_rank.get(incident.priority, 3) <= priority_rank.get(threshold, 1)
                if notify:
                    _record_trace(db, incident.id, "Alert", "In-app notification created")
                    db.add(Notification(
                        organization_id=org,
                        kind="finding",
                        tone=incident.priority if incident.priority in ("critical", "high") else None,
                        title=f"New {incident.priority} finding on {site.domain}",
                        detail=incident.title,
                        href=f"/incidents/{incident.public_id}",
                    ))
                else:
                    _record_trace(db, incident.id, "Alert", f"No in-app notification created (organization threshold: {threshold})")
            created.append(incident.public_id)
            db.commit()

        if scan is not None:
            scan.status = "completed"
            scan.finished_at = datetime.now(timezone.utc)
            scan.duration_s = max(0, int((scan.finished_at - scan.started_at).total_seconds())) if scan.started_at else 0
            site.last_scan_status = "completed"
            db.commit()
        return {"incidents_created": created}
    except Exception as exc:
        log.exception("verification node failed")
        db.rollback()
        scan = db.get(Scan, state["scan_id"]) if state.get("scan_id") else None
        if scan is not None:
            scan.status = "failed"
            scan.error = str(exc)[:2000]
            scan.finished_at = datetime.now(timezone.utc)
            scan.duration_s = max(0, int((scan.finished_at - scan.started_at).total_seconds())) if scan.started_at else 0
            site = db.get(Site, scan.site_id)
            if site is not None:
                site.last_scan_status = "failed"
            db.commit()
        return {"error": str(exc), "incidents_created": created}
    finally:
        db.close()


def _incident_title(claim, verdict: str) -> str:
    med = claim.medication or "Site claim"
    suffix = {
        "POTENTIAL_CONTRADICTION": "conflicts with retrieved reference evidence",
        "POSSIBLY_OUTDATED": "may be outdated versus a retrieved reference",
        "INCOMPLETE_INFORMATION": "is missing important safety context",
        "INSUFFICIENT_EVIDENCE": "lacks supporting authoritative evidence",
        "SUPPORTED": "is consistent with guidance",
    }.get(verdict, "requires review")
    snippet = claim.claim_text[:80].rstrip()
    return f"{med}: {snippet}… — {suffix}"


def _evidence_excerpt(claim_text: str, text: str, limit: int = 800) -> tuple[str, int, int]:
    """Return a verbatim, relevant sentence and its offsets within the chunk."""
    import re

    stop = {"the", "and", "for", "with", "that", "this", "from", "are", "can", "may", "not", "use"}
    terms = {t.lower() for t in re.findall(r"[A-Za-z0-9]+", claim_text) if len(t) > 2 and t.lower() not in stop}
    candidates = [(m.start(), m.end(), m.group(0).strip()) for m in re.finditer(r"[^.!?]+(?:[.!?]+|$)", text)]
    if not candidates:
        return text[:limit], 0, min(len(text), limit)
    start, end, sentence = max(
        candidates,
        key=lambda item: len(terms.intersection(t.lower() for t in re.findall(r"[A-Za-z0-9]+", item[2]))),
    )
    if len(sentence) > limit:
        sentence = sentence[:limit]
        end = start + len(sentence)
    leading = len(text[start:end]) - len(text[start:end].lstrip())
    start += leading
    sentence = text[start:end].rstrip()
    end = start + len(sentence)
    return sentence, start, end


def _route_after_crawl(state: PipelineState) -> str:
    return "stop" if state.get("error") else "continue"


def _route_after_extract(state: PipelineState) -> str:
    return "stop" if state.get("error") else "continue"


def build_graph():
    g = StateGraph(PipelineState)
    g.add_node("crawl", node_crawl)
    g.add_node("extract", node_extract)
    g.add_node("verify", node_verify)
    g.add_edge(START, "crawl")
    g.add_conditional_edges("crawl", _route_after_crawl, {"continue": "extract", "stop": END})
    g.add_conditional_edges("extract", _route_after_extract, {"continue": "verify", "stop": END})
    g.add_edge("verify", END)
    return g.compile()


def run_investigation(scan_id: str) -> dict[str, Any]:
    """Execute the full investigation for a scan, persisting the agent run."""
    db = SessionLocal()
    run_id = f"run_{new_id()[:8]}"
    try:
        scan = db.get(Scan, scan_id)
        if scan is None:
            raise ValueError(f"scan {scan_id} not found")
        run = AgentRun(
            id=run_id,
            organization_id=scan.organization_id,
            scan_id=scan.id,
            status="running",
            current_step="crawl",
            state={},
        )
        db.add(run)
        db.commit()

        graph = build_graph()
        final = graph.invoke({
            "scan_id": scan.id,
            "site_id": scan.site_id,
            "organization_id": scan.organization_id,
            "run_id": run_id,
        })

        run.status = "failed" if final.get("error") else "completed"
        run.current_step = "end"
        run.error = final.get("error")
        run.state = {
            "changed_pages": len(final.get("changed_pages", [])),
            "claims": len(final.get("claims", [])),
            "incidents": final.get("incidents_created", []),
        }
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return final
    finally:
        db.close()
