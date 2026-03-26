"""v0.2 delta for list indexes, dedupe and traceability

Revision ID: 0002_v02_delta_lists_dedupe_trace
Revises: 0001_baseline
Create Date: 2026-03-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_v02_delta_lists_dedupe_trace"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_jobs_status_enabled_updated_at", "jobs", ["status", "enabled", "updated_at"], unique=False)
    op.create_index("ix_rules_enabled_updated_at", "rules", ["enabled", "updated_at"], unique=False)

    with op.batch_alter_table("job_runs") as batch_op:
        batch_op.add_column(sa.Column("total_duplicate", sa.Integer(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("dedupe_version", sa.String(length=20), nullable=False, server_default=sa.text("'v1'")))

    with op.batch_alter_table("rule_versions") as batch_op:
        batch_op.create_unique_constraint("uq_rule_versions_rule_id_version_no", ["rule_id", "version_no"])

    with op.batch_alter_table("samples") as batch_op:
        batch_op.add_column(sa.Column("rule_version_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("extractor_name", sa.String(length=100), nullable=False, server_default=sa.text("'crawler'")))
        batch_op.add_column(sa.Column("extractor_version", sa.String(length=50), nullable=False, server_default=sa.text("'v0.2'")))
        batch_op.add_column(sa.Column("dedupe_version", sa.String(length=20), nullable=False, server_default=sa.text("'v1'")))
        batch_op.add_column(sa.Column("dedupe_key", sa.String(length=512), nullable=False, server_default=sa.text("''")))
        batch_op.add_column(sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("duplicate_of_sample_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("duplicate_reason", sa.Text(), nullable=False, server_default=sa.text("''")))
        batch_op.add_column(sa.Column("marked_duplicate_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key("fk_samples_rule_version_id_rule_versions", "rule_versions", ["rule_version_id"], ["id"])
        batch_op.create_foreign_key("fk_samples_duplicate_of_sample_id_samples", "samples", ["duplicate_of_sample_id"], ["id"])
        batch_op.create_index("ix_samples_dedupe_key", ["dedupe_key"])
        batch_op.create_index("ix_samples_is_duplicate", ["is_duplicate"])
        batch_op.create_index("ix_samples_rule_version_id", ["rule_version_id"])
    op.create_index("ix_samples_status_crawl_time", "samples", ["status", "crawl_time"], unique=False)
    op.create_index("ix_samples_is_duplicate_crawl_time", "samples", ["is_duplicate", "crawl_time"], unique=False)

    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.add_column(sa.Column("sample_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("rule_version_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("dedupe_key", sa.String(length=512), nullable=False, server_default=sa.text("''")))
        batch_op.add_column(sa.Column("trace_version", sa.String(length=20), nullable=False, server_default=sa.text("'v0.2'")))
        batch_op.create_foreign_key("fk_audit_logs_sample_id_samples", "samples", ["sample_id"], ["id"])
        batch_op.create_foreign_key("fk_audit_logs_rule_version_id_rule_versions", "rule_versions", ["rule_version_id"], ["id"])
        batch_op.create_index("ix_audit_logs_sample_id", ["sample_id"])
        batch_op.create_index("ix_audit_logs_rule_version_id", ["rule_version_id"])
        batch_op.create_index("ix_audit_logs_dedupe_key", ["dedupe_key"])
    op.create_index("ix_audit_object_type_event_time", "audit_logs", ["object_type", "event_time"], unique=False)
    op.create_index("ix_audit_sample_event_time", "audit_logs", ["sample_id", "event_time"], unique=False)
    op.create_index("ix_audit_rule_version_event_time", "audit_logs", ["rule_version_id", "event_time"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_rule_version_event_time", table_name="audit_logs")
    op.drop_index("ix_audit_sample_event_time", table_name="audit_logs")
    op.drop_index("ix_audit_object_type_event_time", table_name="audit_logs")
    op.drop_index("ix_samples_is_duplicate_crawl_time", table_name="samples")
    op.drop_index("ix_samples_status_crawl_time", table_name="samples")
    op.drop_index("ix_rules_enabled_updated_at", table_name="rules")
    op.drop_index("ix_jobs_status_enabled_updated_at", table_name="jobs")

    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_index("ix_audit_logs_dedupe_key")
        batch_op.drop_index("ix_audit_logs_rule_version_id")
        batch_op.drop_index("ix_audit_logs_sample_id")
        batch_op.drop_constraint("fk_audit_logs_rule_version_id_rule_versions", type_="foreignkey")
        batch_op.drop_constraint("fk_audit_logs_sample_id_samples", type_="foreignkey")
        batch_op.drop_column("trace_version")
        batch_op.drop_column("dedupe_key")
        batch_op.drop_column("rule_version_id")
        batch_op.drop_column("sample_id")

    with op.batch_alter_table("samples") as batch_op:
        batch_op.drop_index("ix_samples_rule_version_id")
        batch_op.drop_index("ix_samples_is_duplicate")
        batch_op.drop_index("ix_samples_dedupe_key")
        batch_op.drop_constraint("fk_samples_duplicate_of_sample_id_samples", type_="foreignkey")
        batch_op.drop_constraint("fk_samples_rule_version_id_rule_versions", type_="foreignkey")
        batch_op.drop_column("marked_duplicate_at")
        batch_op.drop_column("duplicate_reason")
        batch_op.drop_column("duplicate_of_sample_id")
        batch_op.drop_column("is_duplicate")
        batch_op.drop_column("dedupe_key")
        batch_op.drop_column("dedupe_version")
        batch_op.drop_column("extractor_version")
        batch_op.drop_column("extractor_name")
        batch_op.drop_column("rule_version_id")

    with op.batch_alter_table("rule_versions") as batch_op:
        batch_op.drop_constraint("uq_rule_versions_rule_id_version_no", type_="unique")

    with op.batch_alter_table("job_runs") as batch_op:
        batch_op.drop_column("dedupe_version")
        batch_op.drop_column("total_duplicate")
