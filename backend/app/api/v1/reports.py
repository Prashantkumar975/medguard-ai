"""PDF audit report generation from real database records."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Incident, User
from app.services.reporting.pdf import build_incident_pdf

router = APIRouter()


@router.get("/{incident_id}/pdf")
def incident_pdf(incident_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inc = db.scalar(
        select(Incident).where(Incident.public_id == incident_id, Incident.organization_id == user.organization_id)
    )
    if inc is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    pdf_bytes = build_incident_pdf(db, inc)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{inc.public_id}-audit-report.pdf"'},
    )
