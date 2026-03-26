from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.response import error_response
from app.models import JobRun, Sample
from app.models.base import utc_now
from app.services.audit_service import write_audit_log

DEDUPE_VERSION = "v1"
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"gclid", "fbclid", "yclid", "mc_cid", "mc_eid"}


@dataclass(frozen=True, slots=True)
class DedupeDecision:
    key: str
    reason: str
    is_duplicate: bool
    duplicate_of_sample_id: int | None = None


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def normalize_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    host = (parsed.hostname or "").lower()
    if not host:
        return ""
    port = parsed.port
    netloc = host
    if port and not ((parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    query_items = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=False):
        k = key.lower()
        if k.startswith(TRACKING_QUERY_PREFIXES) or k in TRACKING_QUERY_KEYS:
            continue
        query_items.append((key, val))
    query = urlencode(sorted(query_items), doseq=True)
    return urlunparse((parsed.scheme.lower(), netloc, path, "", query, ""))


def _origin_from_url(value: str) -> str:
    normalized = normalize_url(value)
    if not normalized:
        return ""
    parsed = urlparse(normalized)
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def build_dedupe_key(
    *,
    website: str = "",
    email: str = "",
    company_name: str = "",
    title: str = "",
    source_url: str = "",
) -> tuple[str, str]:
    canonical_origin = _origin_from_url(website) or _origin_from_url(source_url)
    canonical_url = normalize_url(source_url) or normalize_url(website)
    normalized_email = _normalize_email(email)
    normalized_company = _normalize_text(company_name)
    normalized_title = _normalize_text(title)

    if canonical_origin and normalized_email:
        return f"{canonical_origin}||{normalized_email}", "dedupe_v1:email_origin_match"

    # fallback key: low risk, requires canonical_url and at least company or title
    if canonical_url and (normalized_company or normalized_title):
        return f"{canonical_url}||{normalized_company}||{normalized_title}", "dedupe_v1:fallback_signature_match"

    return "", "dedupe_v1:insufficient_keys"


def extract_dedupe_key_from_sample(sample: Sample) -> tuple[str, str]:
    payload = sample.normalized_payload if isinstance(sample.normalized_payload, dict) else {}
    website = payload.get("website") or sample.source_url
    email = payload.get("email") or ""
    company_name = payload.get("company_name") or payload.get("source_name") or sample.source_name
    title = payload.get("title") or sample.title
    source_url = payload.get("source_url") or sample.source_url
    return build_dedupe_key(
        website=website,
        email=email,
        company_name=company_name,
        title=title,
        source_url=source_url,
    )


def find_primary_sample_by_dedupe_key(
    db: Session,
    dedupe_key: str,
    *,
    exclude_sample_id: int | None = None,
) -> Sample | None:
    if not dedupe_key:
        return None
    stmt = select(Sample).where(Sample.dedupe_key == dedupe_key, Sample.is_duplicate.is_(False))
    if exclude_sample_id is not None:
        stmt = stmt.where(Sample.id != exclude_sample_id)
    stmt = stmt.order_by(Sample.crawl_time.asc(), Sample.id.asc())
    return db.execute(stmt).scalars().first()


def detect_duplicate(
    db: Session,
    sample: Sample,
    *,
    explicit_key: str = "",
) -> DedupeDecision:
    if explicit_key:
        key = explicit_key
        reason = "dedupe_v1:explicit_key"
    else:
        key, reason = extract_dedupe_key_from_sample(sample)
    if not key:
        return DedupeDecision(key="", reason=reason, is_duplicate=False, duplicate_of_sample_id=None)
    primary = find_primary_sample_by_dedupe_key(db, key, exclude_sample_id=sample.id)
    if primary is None:
        return DedupeDecision(key=key, reason=reason, is_duplicate=False, duplicate_of_sample_id=None)
    return DedupeDecision(
        key=key,
        reason=reason,
        is_duplicate=True,
        duplicate_of_sample_id=primary.id,
    )


def mark_duplicate(
    db: Session,
    sample_id: int,
    *,
    duplicate_of_sample_id: int,
    duplicate_reason: str = "",
    dedupe_key: str = "",
    operator: str = "system",
    source: str = "auto",
) -> Sample:
    sample = db.get(Sample, sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail=error_response("sample_not_found", "sample not found"))
    primary = db.get(Sample, duplicate_of_sample_id)
    if primary is None:
        raise HTTPException(status_code=404, detail=error_response("sample_not_found", "duplicate target not found"))
    if sample.id == primary.id:
        raise HTTPException(
            status_code=400,
            detail=error_response("invalid_duplicate_target", "sample cannot be duplicate_of itself"),
        )

    derived_key, _ = extract_dedupe_key_from_sample(sample)
    resolved_dedupe_key = dedupe_key or sample.dedupe_key or derived_key
    normalized_reason = (duplicate_reason or "").strip()
    if normalized_reason:
        if not normalized_reason.startswith("dedupe_v1:"):
            normalized_reason = f"dedupe_v1:{normalized_reason}"
    else:
        normalized_reason = "dedupe_v1:dedupe_key_match"
    was_duplicate = bool(sample.is_duplicate)
    sample.is_duplicate = True
    sample.duplicate_of_sample_id = primary.id
    sample.duplicate_reason = normalized_reason
    sample.marked_duplicate_at = utc_now()
    sample.dedupe_version = DEDUPE_VERSION
    sample.dedupe_key = resolved_dedupe_key
    if sample.run_id is not None and not was_duplicate:
        run = db.get(JobRun, sample.run_id)
        if run is not None:
            run.total_duplicate += 1
            run.dedupe_version = DEDUPE_VERSION
    write_audit_log(
        db,
        object_type="sample",
        object_id=str(sample.id),
        action="mark_duplicate",
        status=sample.status,
        summary=sample.duplicate_reason,
        source=source,
        operator=operator,
        sample_id=sample.id,
        rule_version_id=sample.rule_version_id,
        dedupe_key=resolved_dedupe_key,
        detail_json={
            "sample_id": sample.id,
            "duplicate_of_sample_id": primary.id,
            "dedupe_key": resolved_dedupe_key,
            "duplicate_reason": normalized_reason,
            "idempotent_mark": was_duplicate,
        },
    )
    db.flush()
    return sample


def apply_dedupe_v1(db: Session, sample: Sample, *, operator: str = "system", source: str = "auto") -> Sample | None:
    decision = detect_duplicate(db, sample, explicit_key=sample.dedupe_key)
    sample.dedupe_key = decision.key
    sample.dedupe_version = DEDUPE_VERSION
    if not decision.is_duplicate:
        sample.is_duplicate = False
        sample.duplicate_of_sample_id = None
        sample.duplicate_reason = decision.reason
        sample.marked_duplicate_at = None
        return None
    return mark_duplicate(
        db,
        sample.id,
        duplicate_of_sample_id=decision.duplicate_of_sample_id or sample.id,
        duplicate_reason=decision.reason,
        dedupe_key=decision.key,
        operator=operator,
        source=source,
    )
