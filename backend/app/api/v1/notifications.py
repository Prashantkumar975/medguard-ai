"""In-app notifications — contract: GET /notifications, POST .../read, POST .../read-all."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Notification, User
from app.schemas import NotificationOut

router = APIRouter()


@router.get("", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(
        select(Notification)
        .where(Notification.organization_id == user.organization_id)
        .order_by(Notification.at.desc())
        .limit(100)
    ).all()
    return [
        NotificationOut(
            id=n.id, kind=n.kind, tone=n.tone, title=n.title, detail=n.detail, at=n.at, href=n.href, read=n.read
        )
        for n in rows
    ]


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.execute(
        update(Notification)
        .where(Notification.organization_id == user.organization_id, Notification.read.is_(False))
        .values(read=True)
    )
    db.commit()
    return {"ok": True}


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.scalar(
        select(Notification).where(Notification.id == notification_id, Notification.organization_id == user.organization_id)
    )
    if n is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.read = True
    db.commit()
    return {"ok": True}
