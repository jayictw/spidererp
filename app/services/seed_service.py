from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, ErrorBucket, Job, JobRun, Rule, RuleVersion, Sample, SystemConfig, TrainingQueueItem
from app.models.base import utc_now


def _parse_dt(value: str) -> datetime:
    normalized = value.replace('Z', '+00:00')
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def build_seed_preview() -> dict[str, Sequence[dict]]:
    return {
        'jobs': [
            {
                'task_name': '公开网站线索采集示例',
                'crawl_scope': 'public_web',
                'source_type': 'website',
                'keywords': ['contact', 'about', 'team'],
                'start_page': 1,
                'max_pages': 2,
                'time_range': '',
                'include_domains': ['example.com'],
                'exclude_rules': ['login', 'captcha'],
                'rule_notes': 'MVP seed job',
                'schedule_mode': 'manual',
                'schedule_note': 'placeholder',
                'n8n_webhook': '',
                'auto_push_n8n': False,
                'enabled': True,
                'status': 'pending',
            }
        ],
        'rules': [
            {
                'rule_name': 'Email Contact Rule',
                'hit_hint': 'email pattern',
                'explanation_rule': 'extract public email mentions',
                'sample_input': 'Contact us at hello@example.com',
                'expected_output': '{"email":"hello@example.com"}',
                'version_note': 'seed',
                'enabled': True,
                'auto_approve_on_hit': False,
            }
        ],
        'samples': [
            {
                'source_name': 'Example Site',
                'title': 'Contact',
                'keyword': 'contact',
                'status': 'review',
                'rule_name': 'Email Contact Rule',
                'erp_status': '',
                'raw_payload': {'text': 'Contact us at hello@example.com'},
                'normalized_payload': {
                    'company_name': 'Example Co',
                    'website': 'https://example.com',
                    'person_name': '',
                    'title': 'Contact',
                    'email': 'hello@example.com',
                    'phone': '',
                    'whatsapp': '',
                    'country': '',
                    'source_url': 'https://example.com/contact',
                    'crawl_time': '2026-01-01T00:00:00Z',
                    'confidence': 0.88,
                    'raw_text': 'Contact us at hello@example.com',
                    'raw_html_excerpt': '<p>Contact us</p>',
                },
                'source_url': 'https://example.com/contact',
                'crawl_time': '2026-01-01T00:00:00Z',
                'confidence': 0.88,
            }
        ],
    }


def _seed_singletons(db: Session) -> int:
    existing = db.get(SystemConfig, 1)
    if existing is None:
        db.add(SystemConfig(id=1, erp_base_url='', n8n_webhook='', n8n_token='', erp_intake_token=''))
        return 1
    return 0


def seed_database(db: Session) -> dict[str, int]:
    counts = {
        'jobs': 0,
        'rules': 0,
        'runs': 0,
        'samples': 0,
        'error_buckets': 0,
        'training_queue': 0,
        'audit_logs': 0,
        'configs': 0,
    }
    preview = build_seed_preview()

    if not db.execute(select(Job)).first():
        for payload in preview['jobs']:
            db.add(Job(**payload))
            counts['jobs'] += 1

    if not db.execute(select(Rule)).first():
        for payload in preview['rules']:
            db.add(Rule(**payload))
            counts['rules'] += 1
        db.flush()
        rule = db.execute(select(Rule).where(Rule.rule_name == 'Email Contact Rule')).scalar_one_or_none()
        if rule:
            db.add(
                RuleVersion(
                    rule_id=rule.id,
                    version_no=1,
                    rule_snapshot=preview['rules'][0],
                    change_summary='seed',
                    created_by='system',
                )
            )

    db.flush()
    job = db.execute(select(Job).order_by(Job.id.asc())).scalar_one_or_none()
    rule = db.execute(select(Rule).where(Rule.rule_name == 'Email Contact Rule')).scalar_one_or_none()

    if job and rule and not db.execute(select(JobRun)).first():
        run = JobRun(
            job_id=job.id,
            status='parsed',
            started_at=utc_now(),
            finished_at=utc_now(),
            total_found=1,
            total_parsed=1,
            total_failed=0,
            total_review=1,
            total_approved=0,
            run_note='seed',
        )
        db.add(run)
        db.flush()
        counts['runs'] += 1
        if not db.execute(select(Sample)).first():
            sample_payload = preview['samples'][0]
            sample_payload = {k: v for k, v in sample_payload.items() if k != 'rule_name'}
            if isinstance(sample_payload.get('crawl_time'), str):
                sample_payload['crawl_time'] = _parse_dt(sample_payload['crawl_time'])
            sample = Sample(
                job_id=job.id,
                run_id=run.id,
                rule_id=rule.id,
                rule_name=rule.rule_name,
                **sample_payload,
            )
            db.add(sample)
            db.flush()
            counts['samples'] += 1
            db.add(
                TrainingQueueItem(
                    sample_id=sample.id,
                    priority=1,
                    queue_status='pending',
                    linked_rule_id=rule.id,
                    note='seed',
                )
            )
            counts['training_queue'] += 1

    if not db.execute(select(ErrorBucket)).first():
        db.add(
            ErrorBucket(
                rule_name='Email Contact Rule',
                error_reason='missing confidence',
                status='pending',
                source='seed',
                count=1,
            )
        )
        counts['error_buckets'] += 1

    if not db.execute(select(AuditLog)).first():
        db.add(
            AuditLog(
                event_time=utc_now(),
                object_type='seed',
                object_id='bootstrap',
                source='system',
                action='seed',
                status='approved',
                operator='system',
                summary='Seed data initialized',
                detail_json={'seed': True},
            )
        )
        counts['audit_logs'] += 1

    counts['configs'] += _seed_singletons(db)
    db.commit()
    return counts


if __name__ == '__main__':
    from app.core.config import get_settings
    from app.db.init_db import init_database
    from app.db.session import create_session_factory

    settings = get_settings()
    init_database(settings.database_url)
    session_factory = create_session_factory(settings.database_url)
    session = session_factory()
    try:
        print(seed_database(session))
    finally:
        session.close()
