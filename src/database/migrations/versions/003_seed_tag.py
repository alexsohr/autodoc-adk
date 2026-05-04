"""Add seed_tag column to repositories for E2E fixture cleanup.

Revision ID: 003_seed_tag
Revises: 002
Create Date: 2026-05-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_seed_tag"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column("seed_tag", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_repositories_seed_tag",
        "repositories",
        ["seed_tag"],
    )


def downgrade() -> None:
    op.drop_index("ix_repositories_seed_tag", table_name="repositories")
    op.drop_column("repositories", "seed_tag")
