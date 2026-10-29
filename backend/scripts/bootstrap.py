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
        org = db.scalar(select(Organization).where(Organization.name == settings.seed_org_name))
        if org is None:
            org = Organization(name=settings.seed_org_name, subscription_plan="trial")
            db.add(org)
            db.commit()
            db.refresh(org)

        if len(settings.seed_admin_password) < 12:
            raise ValueError("SEED_ADMIN_PASSWORD must be configured with at least 12 characters")
        admin = db.scalar(select(User).where(
            User.organization_id == org.id,
            User.email == settings.seed_admin_email.lower().strip(),
        ))
        if admin is None:
            admin = User(
                organization_id=org.id,
                name=settings.seed_admin_name,
                email=settings.seed_admin_email.lower().strip(),
                password_hash=hash_password(settings.seed_admin_password),
                role="admin",
            )
            db.add(admin)
            db.commit()
            print(f"Created admin {settings.seed_admin_email}; password read from environment")
        return org.id, admin.id
    finally:
        db.close()


if __name__ == "__main__":
    org_id, user_id = bootstrap()
    print(f"org={org_id} admin={user_id}")
