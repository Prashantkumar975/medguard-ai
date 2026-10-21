"""Medical reference library — contract: GET /references?q=."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import ReferenceChunk, ReferenceDocument, User
from app.schemas import ReferenceChunkOut, ReferenceDocOut

router = APIRouter()


@router.get("", response_model=list[ReferenceDocOut])
def list_references(
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(ReferenceDocument)
        .options(selectinload(ReferenceDocument.chunks))
        .where(ReferenceDocument.organization_id == user.organization_id)
        .order_by(ReferenceDocument.effective_date.desc().nullslast())
    )
    docs = db.scalars(stmt).unique().all()
    ql = (q or "").lower()
    out: list[ReferenceDocOut] = []
    for d in docs:
        chunks = [ReferenceChunkOut(section=c.section, text=c.text) for c in d.chunks]
        if ql:
            if ql not in d.title.lower() and not any(ql in c.text.lower() for c in d.chunks):
                continue
        out.append(
            ReferenceDocOut(
                id=d.id,
                authority=d.authority,
                doc_type=d.doc_type,
                title=d.title,
                version=d.version,
                effective_date=d.effective_date,
                url=d.source_url,
                identifiers=d.identifiers,
                is_fictional=d.is_fictional,
                chunks=chunks,
            )
        )
    return out
