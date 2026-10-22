"""Reference document ingestion: chunking + embedding into pgvector."""
from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.models import ReferenceChunk, ReferenceDocument
from app.services.retrieval.embeddings import embed_texts

log = logging.getLogger(__name__)

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 120) -> list[str]:
    """Sentence-aware chunking with overlap."""
    sentences = SENTENCE_SPLIT.split(text.strip())
    chunks: list[str] = []
    current = ""
    for s in sentences:
        if len(current) + len(s) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = current[-overlap:] + " " + s if overlap else s
        else:
            current = f"{current} {s}".strip()
    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if len(c) >= 40]


def ingest_document(
    db: Session,
    doc: ReferenceDocument,
    section_texts: list[tuple[str | None, str]],
) -> list[ReferenceChunk]:
    """Ingest (section, text) pairs for a document: chunk, embed, store."""
    prepared: list[tuple[str | None, str]] = []
    for section, text in section_texts:
        for piece in chunk_text(text):
            prepared.append((section, piece))
    if not prepared:
        return []

    vectors = embed_texts([t for _, t in prepared])
    chunks = [
        ReferenceChunk(document_id=doc.id, section=section, text=text, chunk_index=i, embedding=vec)
        for i, ((section, text), vec) in enumerate(zip(prepared, vectors))
    ]
    db.add_all(chunks)
    db.commit()
    log.info("ingested %d chunks for document %s", len(chunks), doc.title[:60])
    return chunks
