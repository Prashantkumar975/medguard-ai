"""Add HNSW vector index and pg_trgm keyword indexes for hybrid search.

Revision ID: 3d9f2c1a8b64
Revises: 0b8b6a4749d0
Create Date: 2026-10-21

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "3d9f2c1a8b64"
down_revision = "0b8b6a4749d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pg_trgm powers the ILIKE '%term%' keyword leg of hybrid_search.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ANN index for the cosine-distance vector leg (pgvector >= 0.5 required;
    # the bundled extension is 0.8.x). Without it every search seq-scans.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_reference_chunks_embedding_hnsw "
        "ON reference_chunks USING hnsw (embedding vector_cosine_ops)"
    )

    # Trigram indexes so substring keyword matching stops seq-scanning.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_reference_chunks_text_trgm "
        "ON reference_chunks USING gin (text gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_reference_documents_title_trgm "
        "ON reference_documents USING gin (title gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_reference_documents_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_reference_chunks_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_reference_chunks_embedding_hnsw")
