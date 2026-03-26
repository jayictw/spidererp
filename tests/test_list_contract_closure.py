from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


def _db_url() -> str:
    tmp_dir = Path(__file__).resolve().parent / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{tmp_dir / f'list-contract-{uuid4().hex}.db'}"


def _seed_minimal(client: TestClient):
    client.post(
        "/api/v1/jobs",
        json={
            "task_name": "job-list",
            "crawl_scope": "public_web",
            "source_type": "website",
            "keywords": ["k"],
            "start_page": 1,
            "max_pages": 1,
            "time_range": "",
            "include_domains": [],
            "exclude_rules": [],
            "rule_notes": "",
            "schedule_mode": "manual",
            "schedule_note": "",
            "n8n_webhook": "",
            "auto_push_n8n": False,
            "enabled": True,
            "status": "pending",
        },
    )
    rule = client.post(
        "/api/v1/rules",
        json={
            "rule_name": f"rule-{uuid4().hex[:8]}",
            "hit_hint": "email",
            "explanation_rule": "x",
            "sample_input": "x",
            "expected_output": "x",
            "version_note": "v1",
            "enabled": True,
            "auto_approve_on_hit": False,
        },
    ).json()["data"]
    client.post(
        "/api/v1/samples",
        json={
            "rule_id": rule["id"],
            "rule_name": rule["rule_name"],
            "source_name": "crawler",
            "title": "sample-a",
            "keyword": "k",
            "status": "parsed",
            "erp_status": "",
            "raw_payload": {"text": "x"},
            "normalized_payload": {"website": "https://example.com", "email": "a@example.com"},
            "source_url": "https://example.com/a",
            "crawl_time": "2026-01-01T00:00:00Z",
            "confidence": 0.7,
        },
    )


def test_four_pages_open_and_safe_with_queries():
    app = create_app(database_url=_db_url())
    client = TestClient(app)
    _seed_minimal(client)

    pages = [
        "/jobs?keyword=job&status=pending&source_type=website&sort_by=updated_at&sort_order=desc&page=1&page_size=20",
        "/rules?keyword=rule&enabled=true&auto_approve_on_hit=false&sort_by=updated_at&sort_order=desc&page=1&page_size=20",
        "/samples?keyword=sample&status=parsed&is_duplicate=false&sort_by=crawl_time&sort_order=desc&page=1&page_size=20",
        "/audit?keyword=sample&object_type=sample&status=approved&sort_by=event_time&sort_order=desc&page=1&page_size=20",
    ]
    for url in pages:
        resp = client.get(url)
        assert resp.status_code == 200


def test_illegal_sort_does_not_break_pages_and_api_guard_works():
    app = create_app(database_url=_db_url())
    client = TestClient(app)

    # pages should not crash with illegal sort in query string
    for page in ("/jobs?sort_by=illegal", "/rules?sort_by=illegal", "/samples?sort_by=illegal", "/audit?sort_by=illegal"):
        resp = client.get(page)
        assert resp.status_code == 200

    # APIs should still guard illegal sort
    for api in ("/api/v1/jobs?sort_by=illegal", "/api/v1/rules?sort_by=illegal", "/api/v1/samples?sort_by=illegal", "/api/v1/audit?sort_by=illegal"):
        resp = client.get(api)
        assert resp.status_code == 400

