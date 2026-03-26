from __future__ import annotations

from pydantic import BaseModel, Field


class SampleReviewAction(BaseModel):
    note: str = ""


class SampleApproveAction(BaseModel):
    linked_rule_id: int | None = None
    note: str = ""


class SampleRejectAction(BaseModel):
    reason: str = ""


class SampleSendTrainingAction(BaseModel):
    priority: int = 0
    linked_rule_id: int | None = None
    note: str = ""


class SampleMarkDuplicateAction(BaseModel):
    duplicate_of_sample_id: int
    dedupe_key: str = ""
    duplicate_reason: str = ""
    source: str = "manual"


class RuleVersionWrite(BaseModel):
    change_summary: str = ""
    created_by: str = "system"
    rule_snapshot: dict = Field(default_factory=dict)
