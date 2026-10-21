"""Embedding providers. fastembed (ONNX, CPU-friendly) is the default; the model
name and license are documented in README. Provider is configurable."""
from __future__ import annotations

import logging
import threading

from app.core.config import settings

log = logging.getLogger(__name__)

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    with _lock:
        if _model is None:
            if settings.embedding_provider == "sentence-transformers":
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(settings.embedding_model)
            else:
                from fastembed import TextEmbedding

                _model = TextEmbedding(settings.embedding_model)
        return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    if settings.embedding_provider == "sentence-transformers":
        vectors = model.encode(texts, normalize_embeddings=True)
        return [list(map(float, v)) for v in vectors]
    out = [list(map(float, v)) for v in model.embed(texts)]
    return out


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
