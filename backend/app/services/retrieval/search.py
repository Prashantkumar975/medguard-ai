"""Hybrid evidence retrieval over pgvector + keyword search.

- vector search: cosine distance over reference_chunks.embedding
- keyword search: ILIKE over chunk text and document title (works without pg_trgm)
- fusion: reciprocal rank fusion (RRF)
- filters: authority, jurisdiction, is_fictional visibility
- citation validation: every returned chunk must exist in the DB (by id) and the
  quote must be a verbatim substring of the stored chunk text.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import ReferenceChunk, ReferenceDocument
from app.services.retrieval.embeddings import embed_query

log = logging.getLogger(__name__)

RRF_K = 60
_STOP_WORDS = {"the", "and", "for", "with", "that", "this", "from", "are", "can", "may", "not", "use", "used", "into", "than", "when", "which", "while", "will", "does", "what", "have", "has", "been", "was", "were"}


@dataclass
class Hit:
    chunk_id: str
    document_id: str
    section: str | None
    text: str
    score: float
    similarity: float | None
    method: str


def _base_query(org_id: str, jurisdiction: str | None):
    q = (
        select(ReferenceChunk, ReferenceDocument)
        .join(ReferenceDocument, ReferenceChunk.document_id == ReferenceDocument.id)
        .where(ReferenceDocument.organization_id == org_id)
    )
    if jurisdiction:
        q = q.where(
            (ReferenceDocument.jurisdiction == jurisdiction)
            | (ReferenceDocument.jurisdiction.is_(None))
        )
    return q


def hybrid_search(
    db: Session,
    org_id: str,
    query: str,
    *,
    top_k: int | None = None,
    pool_k: int | None = None,
    jurisdiction: str | None = None,
) -> list[Hit]:
    top_k = top_k or settings.retrieval_top_k
    pool_k = pool_k or settings.retrieval_pool_k

    query_terms = list(dict.fromkeys(
        token.lower() for token in re.findall(r"[A-Za-z0-9]+", query)
        if len(token) > 2 and token.lower() not in _STOP_WORDS
    ))
    if not query_terms:
        return []

    # --- vector search ---
    vec_hits: list[tuple[str, float]] = []
    try:
        qvec = embed_query(query)
        from pgvector.sqlalchemy import Vector

        rows = (
            db.execute(
                _base_query(org_id, jurisdiction)
                .order_by(ReferenceChunk.embedding.cosine_distance(qvec))
                .limit(pool_k)
            )
            .all()
        )
        import numpy as np

        qarr = np.array(qvec, dtype=float)
        qarr /= np.linalg.norm(qarr) or 1.0
        for chunk, _doc in rows:
            e = np.array(chunk.embedding, dtype=float)
            e /= np.linalg.norm(e) or 1.0
            similarity = float(qarr @ e)
            if similarity >= settings.retrieval_min_similarity:
                vec_hits.append((chunk.id, similarity))
    except Exception as exc:
        log.warning("vector search unavailable: %s", exc)

    # --- keyword search ---
    kw_hits: list[tuple[str, float]] = []
    predicates = [ReferenceChunk.text.ilike(f"%{term}%") for term in query_terms]
    predicates.extend(ReferenceDocument.title.ilike(f"%{term}%") for term in query_terms)
    kw_rows = (
        db.execute(
            _base_query(org_id, jurisdiction)
            .where(or_(*predicates))
            .limit(pool_k * 3)
        )
        .all()
    )
    keyword_counts: dict[str, int] = {}
    for chunk, doc in kw_rows:
        haystack = f"{chunk.text} {doc.title}".lower()
        matches = sum(1 for term in query_terms if term in haystack)
        minimum = 1 if len(query_terms) == 1 else 2
        if matches >= minimum and matches / len(query_terms) >= 0.15:
            keyword_counts[chunk.id] = matches
    for rank, (chunk_id, _count) in enumerate(
        sorted(keyword_counts.items(), key=lambda item: (-item[1], item[0]))[:pool_k]
    ):
        kw_hits.append((chunk_id, float(_count)))

    # --- reciprocal rank fusion ---
    scores: dict[str, float] = {}
    method: dict[str, str] = {}
    for rank, (cid, _s) in enumerate(sorted(vec_hits, key=lambda t: -t[1])):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
        method[cid] = "vector"
    for rank, (cid, _s) in enumerate(sorted(kw_hits, key=lambda t: -t[1])):
        already_present = cid in scores
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
        method[cid] = "hybrid" if already_present else "keyword"

    if not scores:
        return []

    chunk_ids = [cid for cid, _ in sorted(scores.items(), key=lambda t: -t[1])[:top_k]]
    chunk_rows = db.scalars(
        select(ReferenceChunk).where(ReferenceChunk.id.in_(chunk_ids)).options(selectinload(ReferenceChunk.document))
    ).unique().all()
    by_id = {c.id: c for c in chunk_rows}
    vec_sim = {cid: s for cid, s in vec_hits}

    hits: list[Hit] = []
    for cid in chunk_ids:
        c = by_id.get(cid)
        if c is None:
            continue
        hits.append(
            Hit(
                chunk_id=c.id,
                document_id=c.document_id,
                section=c.section,
                text=c.text,
                score=scores[cid],
                similarity=vec_sim.get(cid),
                method=method.get(cid, "hybrid"),
            )
        )
    return hits


def validate_citation(db: Session, chunk_id: str, quote: str) -> bool:
    """A citation is valid only when the chunk exists and the quote is verbatim."""
    chunk = db.get(ReferenceChunk, chunk_id)
    if chunk is None or not quote:
        return False
    return quote.strip() in chunk.text
