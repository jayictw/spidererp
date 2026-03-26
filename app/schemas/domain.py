from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.statuses import ALLOWED_DOMAIN_STATUSES, ALLOWED_QUEUE_STATUSES


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _validate_controlled_value(value: str, *, allowed: set[str], field_name: str) -> str:
    if value not in allowed:
        raise ValueError(f'unsupported {field_name}: {value}')
    return value


class ControlledStatusBase(BaseModel):
    @field_validator('status', check_fields=False)
    @classmethod
    def _validate_status(cls, value: str) -> str:
        return _validate_controlled_value(value, allowed=ALLOWED_DOMAIN_STATUSES, field_name='status')


class ControlledQueueStatusBase(BaseModel):
    @field_validator('queue_status', check_fields=False)
    @classmethod
    def _validate_queue_status(cls, value: str) -> str:
        return _validate_controlled_value(value, allowed=ALLOWED_QUEUE_STATUSES, field_name='queue_status')


class JobBase(ControlledStatusBase):
    task_name: str
    crawl_scope: str = 'public_web'
    source_type: str = 'website'
    keywords: list[str] = Field(default_factory=list)
    start_page: int = 1
    max_pages: int = 1
    time_range: str = ''
    include_domains: list[str] = Field(default_factory=list)
    exclude_rules: list[str] = Field(default_factory=list)
    rule_notes: str = ''
    schedule_mode: str = 'manual'
    schedule_note: str = ''
    n8n_webhook: str = ''
    auto_push_n8n: bool = False
    enabled: bool = True
    status: str = 'pending'


class JobCreate(JobBase):
    pass


class JobRead(JobBase, ORMBase):
    id: int
    created_at: datetime
    updated_at: datetime


class JobRunBase(ControlledStatusBase):
    job_id: int
    status: str = 'pending'
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_found: int = 0
    total_parsed: int = 0
    total_failed: int = 0
    total_review: int = 0
    total_approved: int = 0
    total_duplicate: int = 0
    dedupe_version: str = 'v1'
    run_note: str = ''


class JobRunCreate(JobRunBase):
    pass


class JobRunRead(JobRunBase, ORMBase):
    id: int
    created_at: datetime
    updated_at: datetime


class RuleBase(BaseModel):
    rule_name: str
    hit_hint: str = ''
    explanation_rule: str = ''
    sample_input: str = ''
    expected_output: str = ''
    version_note: str = ''
    enabled: bool = True
    auto_approve_on_hit: bool = False


class RuleCreate(RuleBase):
    pass


class RuleRead(RuleBase, ORMBase):
    id: int
    created_at: datetime
    updated_at: datetime


class RuleVersionBase(BaseModel):
    rule_id: int
    version_no: int = 1
    rule_snapshot: dict[str, Any] = Field(default_factory=dict)
    change_summary: str = ''
    created_by: str = 'system'


class RuleVersionCreate(RuleVersionBase):
    pass


class RuleVersionRead(RuleVersionBase, ORMBase):
    id: int
    created_at: datetime


class SampleBase(ControlledStatusBase):
    job_id: int | None = None
    run_id: int | None = None
    rule_id: int | None = None
    linked_rule_id: int | None = None
    rule_version_id: int | None = None
    rule_name: str = ''
    source_name: str = ''
    title: str = ''
    keyword: str = ''
    status: str = 'pending'
    erp_status: str = ''
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    normalized_payload: dict[str, Any] = Field(default_factory=dict)
    source_url: str = ''
    crawl_time: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = 0.0
    extractor_name: str = 'crawler'
    extractor_version: str = 'v0.2'
    dedupe_version: str = 'v1'
    dedupe_key: str = ''
    is_duplicate: bool = False
    duplicate_of_sample_id: int | None = None
    duplicate_reason: str = ''
    marked_duplicate_at: datetime | None = None

    @model_validator(mode='after')
    def _sync_rule_link(self) -> 'SampleBase':
        if self.rule_id is None and self.linked_rule_id is None:
            return self
        if self.rule_id is None:
            self.rule_id = self.linked_rule_id
            return self
        if self.linked_rule_id is None:
            self.linked_rule_id = self.rule_id
            return self
        if self.rule_id != self.linked_rule_id:
            raise ValueError('rule_id and linked_rule_id must match when both are provided')
        return self


class SampleCreate(SampleBase):
    pass


class SampleRead(SampleBase, ORMBase):
    id: int
    created_at: datetime
    updated_at: datetime
    linked_rule_name: str = ''


class ErrorBucketBase(ControlledStatusBase):
    rule_name: str = ''
    error_reason: str = ''
    source: str = ''
    count: int = 0


class ErrorBucketCreate(ErrorBucketBase):
    pass


class ErrorBucketRead(ErrorBucketBase, ORMBase):
    id: int
    snapshot_time: datetime
    updated_at: datetime
    created_at: datetime


class TrainingQueueItemBase(ControlledQueueStatusBase):
    sample_id: int
    priority: int = 0
    queue_status: str = 'pending'
    linked_rule_id: int | None = None
    note: str = ''


class TrainingQueueItemCreate(TrainingQueueItemBase):
    pass


class TrainingQueueItemUpdate(BaseModel):
    sample_id: int | None = None
    priority: int | None = None
    queue_status: str | None = None
    linked_rule_id: int | None = None
    note: str | None = None

    @field_validator('queue_status')
    @classmethod
    def _validate_queue_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_controlled_value(value, allowed=ALLOWED_QUEUE_STATUSES, field_name='queue_status')


class TrainingQueueItemRead(TrainingQueueItemBase, ORMBase):
    id: int
    created_at: datetime
    updated_at: datetime
    linked_rule_name: str = ''


class AuditLogBase(ControlledStatusBase):
    event_time: datetime = Field(default_factory=datetime.utcnow)
    object_type: str
    object_id: str
    source: str = 'system'
    action: str = ''
    operator: str = ''
    summary: str = ''
    detail_json: dict[str, Any] = Field(default_factory=dict)
    sample_id: int | None = None
    rule_version_id: int | None = None
    dedupe_key: str = ''
    trace_version: str = 'v0.2'


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogRead(AuditLogBase, ORMBase):
    id: int


class SystemConfigBase(BaseModel):
    erp_base_url: str = ''
    n8n_webhook: str = ''
    n8n_token: str = ''
    erp_intake_token: str = ''


class SystemConfigItem(SystemConfigBase, ORMBase):
    pass


class SampleTraceAuditLogRead(AuditLogRead):
    sample_id: int | None = None
    rule_version_id: int | None = None
    dedupe_key: str = ''
    trace_version: str = 'v0.2'


class SampleTraceDedupeRead(ORMBase):
    dedupe_version: str = 'v1'
    dedupe_key: str = ''
    is_duplicate: bool = False
    duplicate_of_sample_id: int | None = None
    duplicate_reason: str = ''
    marked_duplicate_at: datetime | None = None


class SampleTraceExtractorRead(ORMBase):
    extractor_name: str = 'crawler'
    extractor_version: str = 'v0.2'


class SampleTraceRuleRead(ORMBase):
    rule_id: int | None = None
    rule_version_id: int | None = None


class SampleTracePrimarySampleRead(ORMBase):
    id: int
    title: str = ''
    source_name: str = ''
    source_url: str = ''
    status: str = 'pending'


class SampleTraceTimelineItemRead(ORMBase):
    event_time: datetime
    action: str = ''
    status: str = 'pending'
    operator: str = ''
    summary: str = ''
    dedupe_key: str = ''
    trace_version: str = 'v0.2'


class SampleTraceResponse(ORMBase):
    sample: SampleRead
    dedupe: SampleTraceDedupeRead
    extractor: SampleTraceExtractorRead
    rule: SampleTraceRuleRead
    primary_sample: SampleTracePrimarySampleRead | None = None
    audit_timeline: list[SampleTraceTimelineItemRead] = Field(default_factory=list)
