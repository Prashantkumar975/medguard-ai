"""Add snapshot extraction state, useful FK indexes, and immutable audit rows.

Revision ID: 7a6c4f2e9b13
Revises: 3d9f2c1a8b64
Create Date: 2026-10-29
"""
from alembic import op

revision = "7a6c4f2e9b13"
down_revision = "3d9f2c1a8b64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE snapshots ADD COLUMN IF NOT EXISTS extraction_status VARCHAR(20) NOT NULL DEFAULT 'pending'")
    op.execute("ALTER TABLE snapshots ADD COLUMN IF NOT EXISTS extraction_error TEXT")

    # Normalize any pre-existing duplicate page versions before enforcing the
    # invariant. This changes only version labels, not snapshot contents.
    op.execute("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY page_id ORDER BY fetched_at, id) AS new_version
            FROM snapshots
        )
        UPDATE snapshots AS s SET version = ranked.new_version
        FROM ranked WHERE s.id = ranked.id
    """)
    op.create_index("uq_snapshots_page_version", "snapshots", ["page_id", "version"], unique=True)
    op.create_index("ix_claims_snapshot_id", "claims", ["snapshot_id"], unique=False)
    op.create_index("ix_evidence_chunk_id", "evidence", ["chunk_id"], unique=False)
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.create_unique_constraint("uq_users_org_email", "users", ["organization_id", "email"])

    op.execute("""
        CREATE OR REPLACE FUNCTION medguard_reject_audit_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit records are immutable';
        END;
        $$
    """)
    for table in ("reviews", "audit_logs"):
        op.execute(f"""
            CREATE TRIGGER {table}_immutable
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION medguard_reject_audit_mutation()
        """)


def downgrade() -> None:
    for table in ("reviews", "audit_logs"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
    op.execute("DROP FUNCTION IF EXISTS medguard_reject_audit_mutation()")
    op.drop_index("ix_evidence_chunk_id", table_name="evidence")
    op.drop_index("ix_claims_snapshot_id", table_name="claims")
    op.drop_index("uq_snapshots_page_version", table_name="snapshots")
    op.drop_constraint("uq_users_org_email", "users", type_="unique")
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.drop_column("snapshots", "extraction_error")
    op.drop_column("snapshots", "extraction_status")
