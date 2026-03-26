from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.response import error_response
from app.models import Job, JobRun, Rule, Sample, SystemConfig, TrainingQueueItem
from app.schemas.domain import JobCreate, JobRunCreate, RuleCreate, SystemConfigItem, TrainingQueueItemCreate, TrainingQueueItemUpdate
from app.schemas.statuses import ALLOWED_DOMAIN_STATUSES, ALLOWED_QUEUE_STATUSES
from app.services.audit_service import write_audit_log
from app.services.rules_service import build_rule_snapshot, create_rule_version


def _get_or_404(db: Session, model: type[Any], *, object_name: str, object_id: int):
    item = db.get(model, object_id)
    if item is None:
        raise HTTPException(status_code=404, detail=error_response(f"{object_name}_not_found", f"{object_name} not found"))
    return item


def _ensure_member(value: str, *, allowed: set[str], field_name: str) -> str:
    if value not in allowed:
        raise HTTPException(
            status_code=400,
            detail=error_response("invalid_status", f"unsupported {field_name}: {value}"),
        )
    return value


def create_job(db: Session, payload: JobCreate, *, operator: str = "system") -> Job:
    job = Job(**payload.model_dump())
    db.add(job)
    db.flush()
    write_audit_log(
        db,
        object_type="job",
        object_id=str(job.id),
        action="create",
        status="approved",
        summary=f"job created: {job.task_name}",
        operator=operator,
        detail_json={"job_id": job.id, "task_name": job.task_name, "payload": payload.model_dump()},
    )
    db.commit()
    db.refresh(job)
    return job


def update_job(db: Session, job_id: int, payload: JobCreate, *, operator: str = "system") -> Job:
    job = _get_or_404(db, Job, object_name="job", object_id=job_id)
    previous = {
        "task_name": job.task_name,
        "status": job.status,
    }
    for key, value in payload.model_dump().items():
        setattr(job, key, value)
    write_audit_log(
        db,
        object_type="job",
        object_id=str(job.id),
        action="update",
        status="approved",
        summary=f"job updated: {job.task_name}",
        operator=operator,
        detail_json={"job_id": job.id, "before": previous, "after": payload.model_dump()},
    )
    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, job_id: int, *, operator: str = "system") -> None:
    job = _get_or_404(db, Job, object_name="job", object_id=job_id)
    summary = f"job deleted: {job.task_name}"
    detail = {"job_id": job.id, "task_name": job.task_name}
    db.delete(job)
    write_audit_log(
        db,
        object_type="job",
        object_id=str(job.id),
        action="delete",
        status="approved",
        summary=summary,
        operator=operator,
        detail_json=detail,
    )
    db.commit()


def create_run(db: Session, payload: JobRunCreate, *, operator: str = "system") -> JobRun:
    if db.get(Job, payload.job_id) is None:
        raise HTTPException(status_code=404, detail=error_response("job_not_found", "job not found"))
    run = JobRun(**payload.model_dump())
    db.add(run)
    db.flush()
    write_audit_log(
        db,
        object_type="job_run",
        object_id=str(run.id),
        action="create",
        status=run.status,
        summary=f"job run created for job {run.job_id}",
        operator=operator,
        detail_json={"run_id": run.id, "job_id": run.job_id, "payload": payload.model_dump()},
    )
    db.commit()
    db.refresh(run)
    return run


def create_rule(db: Session, payload: RuleCreate, *, operator: str = "system") -> Rule:
    rule = Rule(**payload.model_dump())
    db.add(rule)
    db.flush()
    create_rule_version(
        db,
        rule,
        change_summary="initial",
        created_by=operator,
        rule_snapshot=payload.model_dump(),
    )
    write_audit_log(
        db,
        object_type="rule",
        object_id=str(rule.id),
        action="create",
        status="approved",
        summary=f"rule created: {rule.rule_name}",
        operator=operator,
        detail_json={"rule_id": rule.id, "rule_name": rule.rule_name, "payload": payload.model_dump()},
    )
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(db: Session, rule_id: int, payload: RuleCreate, *, operator: str = "system") -> Rule:
    rule = _get_or_404(db, Rule, object_name="rule", object_id=rule_id)
    previous = build_rule_snapshot(rule)
    for key, value in payload.model_dump().items():
        setattr(rule, key, value)
    create_rule_version(
        db,
        rule,
        change_summary=payload.version_note or "updated",
        created_by=operator,
        rule_snapshot=build_rule_snapshot(rule),
    )
    write_audit_log(
        db,
        object_type="rule",
        object_id=str(rule.id),
        action="update",
        status="approved",
        summary=f"rule updated: {rule.rule_name}",
        operator=operator,
        detail_json={"rule_id": rule.id, "before": previous, "after": payload.model_dump()},
    )
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule_id: int, *, operator: str = "system") -> None:
    rule = _get_or_404(db, Rule, object_name="rule", object_id=rule_id)
    db.execute(update(Sample).where(Sample.rule_id == rule.id).values(rule_id=None))
    db.execute(update(TrainingQueueItem).where(TrainingQueueItem.linked_rule_id == rule.id).values(linked_rule_id=None))
    db.delete(rule)
    write_audit_log(
        db,
        object_type="rule",
        object_id=str(rule.id),
        action="delete",
        status="approved",
        summary=f"rule deleted: {rule.rule_name}",
        operator=operator,
        detail_json={"rule_id": rule.id, "rule_name": rule.rule_name},
    )
    db.commit()


def create_training_queue_item(db: Session, payload: TrainingQueueItemCreate, *, operator: str = "system") -> TrainingQueueItem:
    sample = _get_or_404(db, Sample, object_name="sample", object_id=payload.sample_id)
    if payload.linked_rule_id is not None and db.get(Rule, payload.linked_rule_id) is None:
        raise HTTPException(status_code=404, detail=error_response("rule_not_found", "rule not found"))
    if payload.linked_rule_id is None and sample.rule_id is not None and db.get(Rule, sample.rule_id) is None:
        raise HTTPException(status_code=404, detail=error_response("rule_not_found", "rule not found"))
    item = TrainingQueueItem(**payload.model_dump())
    db.add(item)
    db.flush()
    write_audit_log(
        db,
        object_type="training_queue_item",
        object_id=str(item.id),
        action="create",
        status="approved",
        summary=f"training queue item created for sample {item.sample_id}",
        operator=operator,
        detail_json={"item_id": item.id, "payload": payload.model_dump()},
    )
    db.commit()
    db.refresh(item)
    return item


def update_training_queue_item(
    db: Session,
    item_id: int,
    payload: TrainingQueueItemUpdate,
    *,
    operator: str = "system",
) -> TrainingQueueItem:
    item = _get_or_404(db, TrainingQueueItem, object_name="training_queue_item", object_id=item_id)
    if payload.linked_rule_id is not None and db.get(Rule, payload.linked_rule_id) is None:
        raise HTTPException(status_code=404, detail=error_response("rule_not_found", "rule not found"))
    previous = {
        "priority": item.priority,
        "queue_status": item.queue_status,
        "linked_rule_id": item.linked_rule_id,
        "note": item.note,
    }
    update_data = payload.model_dump(exclude_none=True)
    update_data.pop("sample_id", None)
    for key, value in update_data.items():
        setattr(item, key, value)
    write_audit_log(
        db,
        object_type="training_queue_item",
        object_id=str(item.id),
        action="update",
        status="approved",
        summary=f"training queue item updated: {item.id}",
        operator=operator,
        detail_json={"item_id": item.id, "before": previous, "after": update_data},
    )
    db.commit()
    db.refresh(item)
    return item


def upsert_config(db: Session, payload: SystemConfigItem, *, operator: str = "system") -> SystemConfig:
    config = db.get(SystemConfig, 1)
    previous = None if config is None else {
        "erp_base_url": config.erp_base_url,
        "n8n_webhook": config.n8n_webhook,
        "n8n_token": config.n8n_token,
        "erp_intake_token": config.erp_intake_token,
    }
    if config is None:
        config = SystemConfig(id=1, **payload.model_dump())
        db.add(config)
    else:
        for key, value in payload.model_dump().items():
            setattr(config, key, value)
    write_audit_log(
        db,
        object_type="system_config",
        object_id=str(config.id),
        action="update",
        status="approved",
        summary="system config updated",
        operator=operator,
        detail_json={"config_id": config.id, "before": previous, "after": payload.model_dump()},
    )
    db.commit()
    db.refresh(config)
    return config


def ensure_controlled_status(value: str) -> str:
    return _ensure_member(value, allowed=ALLOWED_DOMAIN_STATUSES, field_name="status")


def ensure_controlled_queue_status(value: str) -> str:
    return _ensure_member(value, allowed=ALLOWED_QUEUE_STATUSES, field_name="queue_status")
