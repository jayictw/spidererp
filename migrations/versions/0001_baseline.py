"""baseline schema

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-03-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_name", sa.String(length=255), nullable=False),
        sa.Column("crawl_scope", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("start_page", sa.Integer(), nullable=False),
        sa.Column("max_pages", sa.Integer(), nullable=False),
        sa.Column("time_range", sa.String(length=100), nullable=False),
        sa.Column("include_domains", sa.JSON(), nullable=False),
        sa.Column("exclude_rules", sa.JSON(), nullable=False),
        sa.Column("rule_notes", sa.Text(), nullable=False),
        sa.Column("schedule_mode", sa.String(length=50), nullable=False),
        sa.Column("schedule_note", sa.Text(), nullable=False),
        sa.Column("n8n_webhook", sa.String(length=500), nullable=False),
        sa.Column("auto_push_n8n", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_enabled", "jobs", ["enabled"])
    op.create_index("ix_jobs_updated_at", "jobs", ["updated_at"])

    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_found", sa.Integer(), nullable=False),
        sa.Column("total_parsed", sa.Integer(), nullable=False),
        sa.Column("total_failed", sa.Integer(), nullable=False),
        sa.Column("total_review", sa.Integer(), nullable=False),
        sa.Column("total_approved", sa.Integer(), nullable=False),
        sa.Column("run_note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_job_runs_job_id", "job_runs", ["job_id"])
    op.create_index("ix_job_runs_status", "job_runs", ["status"])

    op.create_table(
        "rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("hit_hint", sa.Text(), nullable=False),
        sa.Column("explanation_rule", sa.Text(), nullable=False),
        sa.Column("sample_input", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=False),
        sa.Column("version_note", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("auto_approve_on_hit", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("rule_name", name="uq_rules_rule_name"),
    )
    op.create_index("ix_rules_enabled", "rules", ["enabled"])
    op.create_index("ix_rules_updated_at", "rules", ["updated_at"])

    op.create_table(
        "rule_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("rules.id"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("rule_snapshot", sa.JSON(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rule_versions_rule_id", "rule_versions", ["rule_id"])

    op.create_table(
        "samples",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("job_runs.id"), nullable=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("rules.id"), nullable=True),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("keyword", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("erp_status", sa.String(length=50), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("crawl_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_samples_job_id", "samples", ["job_id"])
    op.create_index("ix_samples_run_id", "samples", ["run_id"])
    op.create_index("ix_samples_rule_id", "samples", ["rule_id"])
    op.create_index("ix_samples_status", "samples", ["status"])
    op.create_index("ix_samples_crawl_time", "samples", ["crawl_time"])

    op.create_table(
        "error_buckets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("error_reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_error_buckets_status", "error_buckets", ["status"])
    op.create_index("ix_error_buckets_updated_at", "error_buckets", ["updated_at"])

    op.create_table(
        "training_queue_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sample_id", sa.Integer(), sa.ForeignKey("samples.id"), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("queue_status", sa.String(length=50), nullable=False),
        sa.Column("linked_rule_id", sa.Integer(), sa.ForeignKey("rules.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_training_queue_items_sample_id", "training_queue_items", ["sample_id"])
    op.create_index("ix_training_queue_items_queue_status", "training_queue_items", ["queue_status"])
    op.create_index("ix_training_queue_items_linked_rule_id", "training_queue_items", ["linked_rule_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("object_type", sa.String(length=100), nullable=False),
        sa.Column("object_id", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("operator", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_audit_logs_event_time", "audit_logs", ["event_time"])
    op.create_index("ix_audit_logs_object_type", "audit_logs", ["object_type"])
    op.create_index("ix_audit_logs_status", "audit_logs", ["status"])

    op.create_table(
        "system_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("erp_base_url", sa.String(length=500), nullable=False),
        sa.Column("n8n_webhook", sa.String(length=500), nullable=False),
        sa.Column("n8n_token", sa.String(length=255), nullable=False),
        sa.Column("erp_intake_token", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_configs")
    op.drop_index("ix_audit_logs_status", table_name="audit_logs")
    op.drop_index("ix_audit_logs_object_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_event_time", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_training_queue_items_linked_rule_id", table_name="training_queue_items")
    op.drop_index("ix_training_queue_items_queue_status", table_name="training_queue_items")
    op.drop_index("ix_training_queue_items_sample_id", table_name="training_queue_items")
    op.drop_table("training_queue_items")
    op.drop_index("ix_error_buckets_updated_at", table_name="error_buckets")
    op.drop_index("ix_error_buckets_status", table_name="error_buckets")
    op.drop_table("error_buckets")
    op.drop_index("ix_samples_crawl_time", table_name="samples")
    op.drop_index("ix_samples_status", table_name="samples")
    op.drop_index("ix_samples_rule_id", table_name="samples")
    op.drop_index("ix_samples_run_id", table_name="samples")
    op.drop_index("ix_samples_job_id", table_name="samples")
    op.drop_table("samples")
    op.drop_index("ix_rule_versions_rule_id", table_name="rule_versions")
    op.drop_table("rule_versions")
    op.drop_index("ix_rules_updated_at", table_name="rules")
    op.drop_index("ix_rules_enabled", table_name="rules")
    op.drop_table("rules")
    op.drop_index("ix_job_runs_status", table_name="job_runs")
    op.drop_index("ix_job_runs_job_id", table_name="job_runs")
    op.drop_table("job_runs")
    op.drop_index("ix_jobs_updated_at", table_name="jobs")
    op.drop_index("ix_jobs_enabled", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_table("jobs")
