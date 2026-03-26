from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, utc_now


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    crawl_scope: Mapped[str] = mapped_column(String(100), nullable=False, default="public_web")
    source_type: Mapped[str] = mapped_column(String(100), nullable=False, default="website")
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    start_page: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    time_range: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    include_domains: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    exclude_rules: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    rule_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    schedule_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    schedule_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    n8n_webhook: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    auto_push_n8n: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")

    runs: Mapped[list["JobRun"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    samples: Mapped[list["Sample"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobRun(Base, TimestampMixin):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_approved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duplicate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dedupe_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")
    run_note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    job: Mapped[Job] = relationship(back_populates="runs")
    samples: Mapped[list["Sample"]] = relationship(back_populates="run")


class Rule(Base, TimestampMixin):
    __tablename__ = "rules"
    __table_args__ = (UniqueConstraint("rule_name", name="uq_rules_rule_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hit_hint: Mapped[str] = mapped_column(Text, nullable=False, default="")
    explanation_rule: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sample_input: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_approve_on_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    versions: Mapped[list["RuleVersion"]] = relationship(back_populates="rule", cascade="all, delete-orphan")
    samples: Mapped[list["Sample"]] = relationship(back_populates="rule")


class RuleVersion(Base, TimestampMixin):
    __tablename__ = "rule_versions"
    __table_args__ = (UniqueConstraint("rule_id", "version_no", name="uq_rule_versions_rule_id_version_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rule_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="system")

    rule: Mapped[Rule] = relationship(back_populates="versions")


class Sample(Base, TimestampMixin):
    __tablename__ = "samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("job_runs.id"), nullable=True, index=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("rules.id"), nullable=True, index=True)
    rule_version_id: Mapped[int | None] = mapped_column(ForeignKey("rule_versions.id"), nullable=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    keyword: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    erp_status: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    normalized_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    crawl_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    extractor_name: Mapped[str] = mapped_column(String(100), nullable=False, default="crawler")
    extractor_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v0.2")
    dedupe_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")
    dedupe_key: Mapped[str] = mapped_column(String(512), nullable=False, default="", index=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    duplicate_of_sample_id: Mapped[int | None] = mapped_column(ForeignKey("samples.id"), nullable=True, index=True)
    duplicate_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    marked_duplicate_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[Job | None] = relationship(back_populates="samples")
    run: Mapped[JobRun | None] = relationship(back_populates="samples")
    rule: Mapped[Rule | None] = relationship(back_populates="samples")
    rule_version: Mapped[RuleVersion | None] = relationship()

    @property
    def linked_rule_id(self) -> int | None:
        return self.rule_id

    @linked_rule_id.setter
    def linked_rule_id(self, value: int | None) -> None:
        self.rule_id = value

    @property
    def linked_rule_name(self) -> str:
        if self.rule is not None:
            return self.rule.rule_name
        return self.rule_name


class ErrorBucket(Base, TimestampMixin):
    __tablename__ = "error_buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    error_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    source: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class TrainingQueueItem(Base, TimestampMixin):
    __tablename__ = "training_queue_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queue_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    linked_rule_id: Mapped[int | None] = mapped_column(ForeignKey("rules.id"), nullable=True, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    sample: Mapped[Sample] = relationship()
    linked_rule: Mapped[Rule | None] = relationship()

    @property
    def linked_rule_name(self) -> str:
        if self.linked_rule is not None:
            return self.linked_rule.rule_name
        if self.sample.rule is not None:
            return self.sample.rule.rule_name
        return ""


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    object_type: Mapped[str] = mapped_column(String(100), nullable=False)
    object_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    operator: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    detail_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    sample_id: Mapped[int | None] = mapped_column(ForeignKey("samples.id"), nullable=True, index=True)
    rule_version_id: Mapped[int | None] = mapped_column(ForeignKey("rule_versions.id"), nullable=True, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(512), nullable=False, default="", index=True)
    trace_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v0.2")


class SystemConfig(Base, TimestampMixin):
    __tablename__ = "system_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    erp_base_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    n8n_webhook: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    n8n_token: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    erp_intake_token: Mapped[str] = mapped_column(String(255), nullable=False, default="")

