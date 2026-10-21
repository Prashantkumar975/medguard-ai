"""Bootstrap the database: organization + admin user (idempotent).

Usage: python -m scripts.bootstrap
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Organization, User


def bootstrap() -> tuple[str, str]:
    db = SessionLocal()
    try:
        org = db.scalar(select(Organization).limit(1))
        if org is None:
            org = Organization(name="MedGuard Demo Org", subscription_plan="trial")
            db.add(org)
            db.commit()
            db.refresh(org)

        admin = db.scalar(select(User).where(User.email == settings.seed_admin_email))
        if admin is None:
            admin = User(
                organization_id=org.id,
                name=settings.seed_admin_name,
                email=settings.seed_admin_email,
                password_hash=hash_password(settings.seed_admin_password),
                role="admin",
            )
            db.add(admin)
            db.commit()
            print(f"Created admin {settings.seed_admin_email} / {settings.seed_admin_password}")
        return org.id, admin.id
    finally:
        db.close()


if __name__ == "__main__":
    org_id, user_id = bootstrap()
    print(f"org={org_id} admin={user_id}")
