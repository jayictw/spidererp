from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.response import error_response, success_response
from app.models import AuditLog, ErrorBucket, Job, JobRun, Rule, RuleVersion, Sample, SystemConfig, TrainingQueueItem
from app.schemas.domain import (
    AuditLogCreate,
    AuditLogRead,
    ErrorBucketCreate,
    ErrorBucketRead,
    JobCreate,
    JobRead,
    JobRunCreate,
    JobRunRead,
    RuleCreate,
    RuleRead,
    RuleVersionRead,
    SampleCreate,
    SampleRead,
    SampleTraceResponse,
    SystemConfigItem,
    TrainingQueueItemCreate,
    TrainingQueueItemUpdate,
    TrainingQueueItemRead,
)
from app.schemas.rules_actions import SampleMarkDuplicateAction
from app.services.query_utils import (
    build_page_data,
    build_sorted_select,
    normalize_page,
    normalize_sort_order,
    paginate_statement,
    validate_sort_field,
)
from app.services.seed_service import build_seed_preview, seed_database
from app.services.sample_service import create_sample as create_sample_service, get_sample_trace, mark_duplicate_sample
from app.services.domain_service import (
    create_job as create_job_service,
    create_run as create_run_service,
    create_rule as create_rule_service,
    create_training_queue_item as create_training_queue_item_service,
    delete_job as delete_job_service,
    delete_rule as delete_rule_service,
    ensure_controlled_queue_status,
    ensure_controlled_status,
    update_job as update_job_service,
    update_rule as update_rule_service,
    update_training_queue_item as update_training_queue_item_service,
    upsert_config as upsert_config_service,
)


router = APIRouter(prefix="/api/v1")


def _read_all(db: Session, model, schema, limit: int = 50, filters: dict | None = None):
    stmt = select(model)
    for field, value in (filters or {}).items():
        if value is not None:
            stmt = stmt.where(getattr(model, field) == value)
    items = db.execute(stmt.limit(limit)).scalars().all()
    return [schema.model_validate(item).model_dump(mode="json") for item in items]


def _apply_keyword_filter(stmt, keyword: str | None, columns) -> object:
    if not keyword:
        return stmt
    needle = f"%{keyword.strip()}%"
    conditions = [column.ilike(needle) for column in columns]
    return stmt.where(or_(*conditions))


def _set_page_headers(
    response: Response,
    *,
    total: int,
    page: int,
    page_size: int,
    total_pages: int,
    sort_by: str,
    sort_order: str,
) -> None:
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    response.headers["X-Total-Pages"] = str(total_pages)
    response.headers["X-Sort-By"] = sort_by
    response.headers["X-Sort-Order"] = sort_order


def _build_page_result(
    db: Session,
    stmt,
    *,
    response: Response,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    sort_column,
):
    ordered_stmt = build_sorted_select(stmt, sort_field=sort_column, sort_order=sort_order)
    items, meta = paginate_statement(db, ordered_stmt, page=page, page_size=page_size)
    _set_page_headers(
        response,
        total=meta.total,
        page=meta.page,
        page_size=meta.page_size,
        total_pages=meta.total_pages,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return items


@router.get("/health")
def health():
    return success_response({"status": "ok"})


@router.get("/dashboard/summary")
def dashboard_summary():
    return success_response(
        {
            "tasks": 0,
            "active_rules": 0,
            "pending_rules": 0,
            "parse_failed": 0,
            "approved": 0,
            "running_or_waiting": 0,
            "pending_explain": 0,
            "training_pending": 0,
        }
    )


@router.get("/jobs")
def list_jobs(
    response: Response,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc"),
    keyword: str | None = None,
    status: str | None = None,
    enabled: bool | None = None,
    source_type: str | None = None,
):
    if status is not None:
        ensure_controlled_status(status)
    page, page_size = normalize_page(page, page_size, default_page_size=50)
    sort_order = normalize_sort_order(sort_order)
    try:
        sort_field = validate_sort_field(sort_by, {"id", "task_name", "status", "enabled", "created_at", "updated_at"}, "updated_at")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=error_response("invalid_sort", str(exc))) from exc
    sort_columns = {
        "id": Job.id,
        "task_name": Job.task_name,
        "status": Job.status,
        "enabled": Job.enabled,
        "created_at": Job.created_at,
        "updated_at": Job.updated_at,
    }

    stmt = select(Job)
    stmt = _apply_keyword_filter(stmt, keyword, [Job.task_name, Job.rule_notes, Job.schedule_note])
    if status is not None:
        stmt = stmt.where(Job.status == status)
    if enabled is not None:
        stmt = stmt.where(Job.enabled == enabled)
    if source_type is not None:
        stmt = stmt.where(Job.source_type == source_type)
    ordered_stmt = build_sorted_select(stmt, sort_field=sort_columns[sort_field], sort_order=sort_order)
    rows, meta = paginate_statement(db, ordered_stmt, page=page, page_size=page_size)
    items = [JobRead.model_validate(item).model_dump(mode="json") for item in rows]
    payload = build_page_data(
        items=items,
        total=meta.total,
        page=meta.page,
        page_size=meta.page_size,
        sort_by=sort_field,
        sort_order=sort_order,
    )
    _set_page_headers(
        response,
        total=meta.total,
        page=meta.page,
        page_size=meta.page_size,
        total_pages=meta.total_pages,
        sort_by=sort_field,
        sort_order=sort_order,
    )
    return success_response(payload)


@router.post("/jobs")
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    job = create_job_service(db, payload)
    return success_response(JobRead.model_validate(job).model_dump(mode="json"), "created")


@router.put("/jobs/{job_id}")
def update_job_item(job_id: int, payload: JobCreate, db: Session = Depends(get_db)):
    job = update_job_service(db, job_id, payload)
    return success_response(JobRead.model_validate(job).model_dump(mode="json"), "saved")


@router.delete("/jobs/{job_id}")
def delete_job_item(job_id: int, db: Session = Depends(get_db)):
    delete_job_service(db, job_id)
    return success_response(message="deleted")


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=error_response("job_not_found", "job not found"))
    return success_response(JobRead.model_validate(job).model_dump(mode="json"))


@router.get("/jobs/{job_id}/runs")
def list_job_runs(job_id: int, db: Session = Depends(get_db), limit: int = Query(default=50, ge=1, le=500)):
    if not db.get(Job, job_id):
        raise HTTPException(status_code=404, detail=error_response("job_not_found", "job not found"))
    return success_response(_read_all(db, JobRun, JobRunRead, limit=limit, filters={"job_id": job_id}))


@router.get("/runs")
def list_runs(db: Session = Depends(get_db), status: str | None = None, limit: int = Query(default=50, ge=1, le=500)):
    if status is not None:
        ensure_controlled_status(status)
    return success_response(_read_all(db, JobRun, JobRunRead, limit=limit, filters={"status": status}))


@router.post("/runs")
def create_run(payload: JobRunCreate, db: Session = Depends(get_db)):
    run = create_run_service(db, payload)
    return success_response(JobRunRead.model_validate(run).model_dump(mode="json"), "created")


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(JobRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=error_response("run_not_found", "run not found"))
    return success_response(JobRunRead.model_validate(run).model_dump(mode="json"))


@router.get("/rules")
def list_rules(
    response: Response,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc"),
    keyword: str | None = None,
    enabled: bool | None = None,
    auto_approve_on_hit: bool | None = None,
):
    page, page_size = normalize_page(page, page_size, default_page_size=50)
    sort_order = normalize_sort_order(sort_order)
    try:
        sort_field = validate_sort_field(
            sort_by,
            {"id", "rule_name", "enabled", "auto_approve_on_hit", "created_at", "updated_at"},
            "updated_at",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=error_response("invalid_sort", str(exc))) from exc
    sort_columns = {
        "id": Rule.id,
        "rule_name": Rule.rule_name,
        "enabled": Rule.enabled,
        "auto_approve_on_hit": Rule.auto_approve_on_hit,
        "created_at": Rule.created_at,
        "updated_at": Rule.updated_at,
    }

    stmt = select(Rule)
    stmt = _apply_keyword_filter(stmt, keyword, [Rule.rule_name, Rule.hit_hint, Rule.explanation_rule, Rule.version_note])
    if enabled is not None:
        stmt = stmt.where(Rule.enabled == enabled)
    if auto_approve_on_hit is not None:
        stmt = stmt.where(Rule.auto_approve_on_hit == auto_approve_on_hit)
    ordered_stmt = build_sorted_select(stmt, sort_field=sort_columns[sort_field], sort_order=sort_order)
    rows, meta = paginate_statement(db, ordered_stmt, page=page, page_size=page_size)
    items = [RuleRead.model_validate(item).model_dump(mode="json") for item in rows]
    payload = build_page_data(
        items=items,
        total=meta.total,
        page=meta.page,
        page_size=meta.page_size,
        sort_by=sort_field,
        sort_order=sort_order,
    )
    _set_page_headers(
        response,
        total=meta.total,
        page=meta.page,
        page_size=meta.page_size,
        total_pages=meta.total_pages,
        sort_by=sort_field,
        sort_order=sort_order,
    )
    return success_response(payload)


@router.post("/rules")
def create_rule(payload: RuleCreate, db: Session = Depends(get_db)):
    rule = create_rule_service(db, payload)
    return success_response(RuleRead.model_validate(rule).model_dump(mode="json"), "created")


@router.put("/rules/{rule_id}")
def update_rule_item(rule_id: int, payload: RuleCreate, db: Session = Depends(get_db)):
    rule = update_rule_service(db, rule_id, payload)
    return success_response(RuleRead.model_validate(rule).model_dump(mode="json"), "saved")


@router.delete("/rules/{rule_id}")
def delete_rule_item(rule_id: int, db: Session = Depends(get_db)):
    delete_rule_service(db, rule_id)
    return success_response(message="deleted")


@router.get("/rules/{rule_id}")
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=error_response("rule_not_found", "rule not found"))
    return success_response(RuleRead.model_validate(rule).model_dump(mode="json"))


@router.get("/rule-versions")
def list_rule_versions(
    db: Session = Depends(get_db),
    rule_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
):
    return success_response(_read_all(db, RuleVersion, RuleVersionRead, limit=limit, filters={"rule_id": rule_id}))


@router.get("/samples")
def list_samples(
    response: Response,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort_by: str = Query(default="crawl_time"),
    sort_order: str = Query(default="desc"),
    keyword: str | None = None,
    status: str | None = None,
    rule_id: int | None = None,
    rule_name: str | None = None,
    rule_version_id: int | None = None,
    source_name: str | None = None,
    domain: str | None = None,
    is_duplicate: bool | None = None,
    dedupe_key: str | None = None,
    confidence_min: float | None = None,
    confidence_max: float | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    if status is not None:
        ensure_controlled_status(status)
    page, page_size = normalize_page(page, page_size, default_page_size=20)
    sort_order = normalize_sort_order(sort_order)
    try:
        sort_field = validate_sort_field(
            sort_by,
            {
                "id",
                "title",
                "rule_name",
                "status",
                "source_name",
                "confidence",
                "crawl_time",
                "created_at",
                "is_duplicate",
            },
            "crawl_time",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=error_response("invalid_sort", str(exc))) from exc
    sort_columns = {
        "id": Sample.id,
        "title": Sample.title,
        "rule_name": Sample.rule_name,
        "status": Sample.status,
        "source_name": Sample.source_name,
        "confidence": Sample.confidence,
        "crawl_time": Sample.crawl_time,
        "created_at": Sample.created_at,
        "is_duplicate": Sample.is_duplicate,
    }

    stmt = select(Sample)
    stmt = _apply_keyword_filter(
        stmt,
        keyword,
        [Sample.rule_name, Sample.source_name, Sample.title, Sample.source_url, Sample.dedupe_key, Sample.keyword],
    )
    if status is not None:
        stmt = stmt.where(Sample.status == status)
    if rule_id is not None:
        stmt = stmt.where(Sample.rule_id == rule_id)
    if rule_name is not None:
        stmt = stmt.where(Sample.rule_name == rule_name)
    if rule_version_id is not None:
        stmt = stmt.where(Sample.rule_version_id == rule_version_id)
    if source_name is not None:
        stmt = stmt.where(Sample.source_name == source_name)
    if domain is not None:
        stmt = stmt.where(Sample.source_url.ilike(f"%://{domain}%"))
    if is_duplicate is not None:
        stmt = stmt.where(Sample.is_duplicate == is_duplicate)
    if dedupe_key is not None:
        stmt = stmt.where(Sample.dedupe_key == dedupe_key)
    if confidence_min is not None:
        stmt = stmt.where(Sample.confidence >= confidence_min)
    if confidence_max is not None:
        stmt = stmt.where(Sample.confidence <= confidence_max)
    if date_from is not None:
        stmt = stmt.where(Sample.crawl_time >= date_from)
    if date_to is not None:
        stmt = stmt.where(Sample.crawl_time <= date_to)

    ordered_stmt = build_sorted_select(stmt, sort_field=sort_columns[sort_field], sort_order=sort_order)
    rows, meta = paginate_statement(db, ordered_stmt, page=page, page_size=page_size)
    items = [SampleRead.model_validate(item).model_dump(mode="json") for item in rows]
    payload = build_page_data(
        items=items,
        total=meta.total,
        page=meta.page,
        page_size=meta.page_size,
        sort_by=sort_field,
        sort_order=sort_order,
    )
    _set_page_headers(
        response,
        total=meta.total,
        page=meta.page,
        page_size=meta.page_size,
        total_pages=meta.total_pages,
        sort_by=sort_field,
        sort_order=sort_order,
    )
    return success_response(payload)


@router.post("/samples")
def create_sample(payload: SampleCreate, db: Session = Depends(get_db)):
    sample = create_sample_service(db, payload)
    return success_response(SampleRead.model_validate(sample).model_dump(mode="json"), "created")


@router.get("/samples/{sample_id}")
def get_sample(sample_id: int, db: Session = Depends(get_db)):
    sample = db.get(Sample, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail=error_response("sample_not_found", "sample not found"))
    return success_response(SampleRead.model_validate(sample).model_dump(mode="json"))


@router.get("/samples/{sample_id}/trace")
def get_sample_trace_route(sample_id: int, db: Session = Depends(get_db)):
    payload = get_sample_trace(db, sample_id)
    validated = SampleTraceResponse.model_validate(payload).model_dump(mode="json")
    return success_response(validated)


@router.post("/samples/{sample_id}/mark-duplicate")
def mark_duplicate_route(sample_id: int, payload: SampleMarkDuplicateAction, db: Session = Depends(get_db)):
    sample = mark_duplicate_sample(
        db,
        sample_id,
        duplicate_of_sample_id=payload.duplicate_of_sample_id,
        dedupe_key=payload.dedupe_key,
        duplicate_reason=payload.duplicate_reason,
        source=payload.source,
    )
    return success_response(SampleRead.model_validate(sample).model_dump(mode="json"), "marked_duplicate")


@router.get("/error-buckets")
def list_error_buckets(db: Session = Depends(get_db), status: str | None = None, limit: int = Query(default=50, ge=1, le=500)):
    if status is not None:
        ensure_controlled_status(status)
    return success_response(_read_all(db, ErrorBucket, ErrorBucketRead, limit=limit, filters={"status": status}))


@router.post("/error-buckets")
def create_error_bucket(payload: ErrorBucketCreate, db: Session = Depends(get_db)):
    item = ErrorBucket(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return success_response(ErrorBucketRead.model_validate(item).model_dump(mode="json"), "created")


@router.get("/training-queue")
def list_training_queue(
    db: Session = Depends(get_db),
    queue_status: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
):
    if queue_status is not None:
        ensure_controlled_queue_status(queue_status)
    return success_response(_read_all(db, TrainingQueueItem, TrainingQueueItemRead, limit=limit, filters={"queue_status": queue_status}))


@router.post("/training-queue")
def create_training_queue_item(payload: TrainingQueueItemCreate, db: Session = Depends(get_db)):
    item = create_training_queue_item_service(db, payload)
    return success_response(TrainingQueueItemRead.model_validate(item).model_dump(mode="json"), "created")


@router.put("/training-queue/{item_id}")
def update_training_queue_item_route(item_id: int, payload: TrainingQueueItemUpdate, db: Session = Depends(get_db)):
    item = update_training_queue_item_service(db, item_id, payload)
    return success_response(TrainingQueueItemRead.model_validate(item).model_dump(mode="json"), "saved")


@router.get("/audit")
def list_audit_logs(
    response: Response,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="event_time"),
    sort_order: str = Query(default="desc"),
    keyword: str | None = None,
    status: str | None = None,
    object_type: str | None = None,
    action: str | None = None,
    operator: str | None = None,
    sample_id: int | None = None,
    rule_version_id: int | None = None,
):
    if status is not None:
        ensure_controlled_status(status)
    page, page_size = normalize_page(page, page_size, default_page_size=50)
    sort_order = normalize_sort_order(sort_order)
    try:
        sort_field = validate_sort_field(
            sort_by,
            {"id", "event_time", "status", "object_type", "action"},
            "event_time",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=error_response("invalid_sort", str(exc))) from exc
    sort_columns = {
        "id": AuditLog.id,
        "event_time": AuditLog.event_time,
        "status": AuditLog.status,
        "object_type": AuditLog.object_type,
        "action": AuditLog.action,
    }

    stmt = select(AuditLog)
    stmt = _apply_keyword_filter(stmt, keyword, [AuditLog.object_type, AuditLog.object_id, AuditLog.source, AuditLog.action, AuditLog.operator, AuditLog.summary, AuditLog.dedupe_key])
    if status is not None:
        stmt = stmt.where(AuditLog.status == status)
    if object_type is not None:
        stmt = stmt.where(AuditLog.object_type == object_type)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if operator is not None:
        stmt = stmt.where(AuditLog.operator == operator)
    if sample_id is not None:
        stmt = stmt.where(AuditLog.sample_id == sample_id)
    if rule_version_id is not None:
        stmt = stmt.where(AuditLog.rule_version_id == rule_version_id)
    ordered_stmt = build_sorted_select(stmt, sort_field=sort_columns[sort_field], sort_order=sort_order)
    rows, meta = paginate_statement(db, ordered_stmt, page=page, page_size=page_size)
    items = [AuditLogRead.model_validate(item).model_dump(mode="json") for item in rows]
    payload = build_page_data(
        items=items,
        total=meta.total,
        page=meta.page,
        page_size=meta.page_size,
        sort_by=sort_field,
        sort_order=sort_order,
    )
    _set_page_headers(
        response,
        total=meta.total,
        page=meta.page,
        page_size=meta.page_size,
        total_pages=meta.total_pages,
        sort_by=sort_field,
        sort_order=sort_order,
    )
    return success_response(payload)


@router.post("/audit")
def create_audit_log(payload: AuditLogCreate, db: Session = Depends(get_db)):
    item = AuditLog(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return success_response(AuditLogRead.model_validate(item).model_dump(mode="json"), "created")


@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    config = db.get(SystemConfig, 1)
    if not config:
        config = SystemConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return success_response(SystemConfigItem.model_validate(config).model_dump(mode="json"))


@router.put("/config")
def upsert_config(payload: SystemConfigItem, db: Session = Depends(get_db)):
    config = upsert_config_service(db, payload)
    return success_response(SystemConfigItem.model_validate(config).model_dump(mode="json"), "saved")


@router.get("/seeds/preview")
def seeds_preview():
    return success_response(build_seed_preview())


@router.post("/seeds/load")
def seeds_load(db: Session = Depends(get_db)):
    summary = seed_database(db)
    return success_response(summary, "seeded")
