from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.response import success_response
from app.schemas.domain import RuleVersionRead, SampleRead
from app.schemas.rules_actions import (
    RuleVersionWrite,
    SampleApproveAction,
    SampleRejectAction,
    SampleReviewAction,
    SampleSendTrainingAction,
)
from app.services.rules_service import (
    approve_sample,
    create_rule_version_from_rule,
    list_rule_versions,
    reject_sample,
    review_sample,
    send_sample_to_training,
)


router = APIRouter(prefix="/api/v1", tags=["rules-actions"])


@router.get("/rules/{rule_id}/versions")
def read_rule_versions(rule_id: int, db: Session = Depends(get_db)):
    items = list_rule_versions(db, rule_id, limit=200)
    return success_response([RuleVersionRead.model_validate(item).model_dump(mode="json") for item in items])


@router.post("/rules/{rule_id}/versions")
def add_rule_version(rule_id: int, payload: RuleVersionWrite, db: Session = Depends(get_db)):
    item = create_rule_version_from_rule(
        db,
        rule_id,
        change_summary=payload.change_summary,
        created_by=payload.created_by,
    )
    return success_response(RuleVersionRead.model_validate(item).model_dump(mode="json"), "created")


@router.post("/samples/{sample_id}/review")
def action_review(sample_id: int, payload: SampleReviewAction, db: Session = Depends(get_db)):
    item = review_sample(db, sample_id, payload)
    return success_response(SampleRead.model_validate(item).model_dump(mode="json"), "reviewed")


@router.post("/samples/{sample_id}/approve")
def action_approve(sample_id: int, payload: SampleApproveAction, db: Session = Depends(get_db)):
    item = approve_sample(db, sample_id, payload)
    return success_response(SampleRead.model_validate(item).model_dump(mode="json"), "approved")


@router.post("/samples/{sample_id}/reject")
def action_reject(sample_id: int, payload: SampleRejectAction, db: Session = Depends(get_db)):
    item = reject_sample(db, sample_id, payload)
    return success_response(SampleRead.model_validate(item).model_dump(mode="json"), "rejected")


@router.post("/samples/{sample_id}/send-training")
def action_send_training(sample_id: int, payload: SampleSendTrainingAction, db: Session = Depends(get_db)):
    sample, queue_item = send_sample_to_training(db, sample_id, payload)
    return success_response(
        {
            "sample": SampleRead.model_validate(sample).model_dump(mode="json"),
            "training_queue_item_id": queue_item.id,
        },
        "queued",
    )
