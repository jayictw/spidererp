"""fix missing rule_versions.updated_at for seed/runtime consistency

Revision ID: 0003_v02_fix_rule_versions_updated_at
Revises: 0002_v02_delta_lists_dedupe_trace
Create Date: 2026-03-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_v02_fix_rule_versions_updated_at"
down_revision = "0002_v02_delta_lists_dedupe_trace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rule_versions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("rule_versions") as batch_op:
        batch_op.drop_column("updated_at")
