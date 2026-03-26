from pathlib import Path

import requests
from fastapi.testclient import TestClient

from app.main import create_app


def _local_db_url(name: str) -> str:
    tmp_dir = Path(__file__).resolve().parent / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / name
    if db_path.exists():
        db_path.unlink()
    return f"sqlite:///{db_path}"


class _DummyResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status: {self.status_code}", response=self)


def test_health_success():
    app = create_app(database_url=_local_db_url("health.db"))
    client = TestClient(app)

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_dashboard_page_available():
    app = create_app(database_url=_local_db_url("dashboard.db"))
    client = TestClient(app)

    response = client.get("/dashboard")
    assert response.status_code == 200


def test_crawler_preview_ssl_disabled_smoke(monkeypatch):
    db_url = _local_db_url("crawler_preview.db")

    # Scoped env config for this test only.
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("CRAWLER_SSL_VERIFY", "false")

    from app.core.config import get_settings
    from app.services import crawler_service as crawler_service_module

    get_settings.cache_clear()
    crawler_service_module._crawler_service = None

    def fake_requests_get(url, timeout=20, headers=None):  # noqa: ANN001, ARG001
        if str(url).endswith("/robots.txt"):
            return _DummyResponse("User-agent: *\nAllow: /\n", 200)
        return _DummyResponse("", 404)

    def fake_session_get(self, url, timeout=20, verify=True, headers=None):  # noqa: ANN001, ARG001
        html = """
        <html><body>
        <h1>Example Corp</h1>
        <p>Contact Alice</p>
        <p>Email: alice@example.com</p>
        <p>Phone: +1 212-555-0100</p>
        </body></html>
        """
        return _DummyResponse(html, 200)

    monkeypatch.setattr("app.crawler.robots.requests.get", fake_requests_get)
    monkeypatch.setattr(requests.Session, "get", fake_session_get)

    app = create_app(database_url=db_url)
    client = TestClient(app)

    response = client.post("/api/v1/crawler/preview", json={"url": "https://example.com"})
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True

    records = body["data"]["records"]
    assert len(records) >= 1
    record = records[0]
    expected_keys = {
        "company_name",
        "website",
        "person_name",
        "title",
        "email",
        "phone",
        "whatsapp",
        "country",
        "source_url",
        "crawl_time",
        "confidence",
    }
    assert expected_keys.issubset(set(record.keys()))


def test_api_smoke():
    app = create_app(database_url=_local_db_url("smoke.db"))
    client = TestClient(app)

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["success"] is True

    preview = client.get("/api/v1/seeds/preview")
    assert preview.status_code == 200
    assert preview.json()["success"] is True
    assert "jobs" in preview.json()["data"]

    job_payload = {
        "task_name": "smoke job",
        "crawl_scope": "public_web",
        "source_type": "website",
        "keywords": ["contact"],
        "start_page": 1,
        "max_pages": 1,
        "time_range": "",
        "include_domains": ["example.com"],
        "exclude_rules": [],
        "rule_notes": "",
        "schedule_mode": "manual",
        "schedule_note": "",
        "n8n_webhook": "",
        "auto_push_n8n": False,
        "enabled": True,
        "status": "pending",
    }
    job_resp = client.post("/api/v1/jobs", json=job_payload)
    assert job_resp.status_code == 200
    job_id = job_resp.json()["data"]["id"]

    update_job_resp = client.put(
        f"/api/v1/jobs/{job_id}",
        json={**job_payload, "task_name": "smoke job updated", "status": "running", "enabled": False},
    )
    assert update_job_resp.status_code == 200
    assert update_job_resp.json()["data"]["task_name"] == "smoke job updated"

    rule_payload = {
        "rule_name": "smoke rule",
        "hit_hint": "email",
        "explanation_rule": "extract email",
        "sample_input": "hello@example.com",
        "expected_output": '{"email":"hello@example.com"}',
        "version_note": "smoke",
        "enabled": True,
        "auto_approve_on_hit": False,
    }
    rule_resp = client.post("/api/v1/rules", json=rule_payload)
    assert rule_resp.status_code == 200
    rule_id = rule_resp.json()["data"]["id"]

    update_rule_resp = client.put(
        f"/api/v1/rules/{rule_id}",
        json={**rule_payload, "version_note": "smoke-updated"},
    )
    assert update_rule_resp.status_code == 200
    assert update_rule_resp.json()["data"]["version_note"] == "smoke-updated"

    version_resp = client.post(
        f"/api/v1/rules/{rule_id}/versions",
        json={"change_summary": "manual version", "created_by": "tester"},
    )
    assert version_resp.status_code == 200
    assert version_resp.json()["success"] is True

    run_resp = client.post(
        "/api/v1/runs",
        json={
            "job_id": job_id,
            "status": "parsed",
            "started_at": None,
            "finished_at": None,
            "total_found": 1,
            "total_parsed": 1,
            "total_failed": 0,
            "total_review": 1,
            "total_approved": 0,
            "run_note": "done",
        },
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["data"]["id"]

    sample_payload = {
        "job_id": job_id,
        "run_id": run_id,
        "linked_rule_id": rule_id,
        "rule_name": "smoke rule",
        "source_name": "example",
        "title": "contact",
        "keyword": "contact",
        "status": "parsed",
        "erp_status": "",
        "raw_payload": {"text": "hello@example.com"},
        "normalized_payload": {"email": "hello@example.com"},
        "source_url": "https://example.com/contact",
        "crawl_time": "2026-01-01T00:00:00Z",
        "confidence": 0.9,
    }
    sample_resp = client.post("/api/v1/samples", json=sample_payload)
    assert sample_resp.status_code == 200
    sample_data = sample_resp.json()["data"]
    sample_id = sample_data["id"]
    assert sample_data["linked_rule_id"] == rule_id

    illegal_send_resp = client.post(
        f"/api/v1/samples/{sample_id}/send-training",
        json={"priority": 1, "linked_rule_id": rule_id, "note": "illegal"},
    )
    assert illegal_send_resp.status_code == 409
    assert illegal_send_resp.json()["error"] == "invalid_transition"

    review_resp = client.post(f"/api/v1/samples/{sample_id}/review", json={"note": "needs review"})
    assert review_resp.status_code == 200
    assert review_resp.json()["data"]["status"] == "review"

    approve_resp = client.post(
        f"/api/v1/samples/{sample_id}/approve",
        json={"linked_rule_id": rule_id, "note": "approved"},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["data"]["status"] == "approved"

    queue_resp = client.post(
        f"/api/v1/samples/{sample_id}/send-training",
        json={"priority": 2, "linked_rule_id": rule_id, "note": "queue it"},
    )
    assert queue_resp.status_code == 200
    queue_data = queue_resp.json()["data"]
    queue_item_id = queue_data["training_queue_item_id"]

    queue_update_resp = client.put(
        f"/api/v1/training-queue/{queue_item_id}",
        json={
            "sample_id": sample_id,
            "priority": 3,
            "queue_status": "running",
            "linked_rule_id": rule_id,
            "note": "updated queue",
        },
    )
    assert queue_update_resp.status_code == 200
    assert queue_update_resp.json()["data"]["queue_status"] == "running"
    assert queue_update_resp.json()["data"]["linked_rule_name"] == "smoke rule"

    reject_sample_resp = client.post(
        "/api/v1/samples",
        json={
            **sample_payload,
            "title": "contact 2",
            "status": "parsed",
            "source_url": "https://example.com/contact-2",
        },
    )
    assert reject_sample_resp.status_code == 200
    reject_sample_id = reject_sample_resp.json()["data"]["id"]

    review_second_resp = client.post(f"/api/v1/samples/{reject_sample_id}/review", json={"note": "needs manual check"})
    assert review_second_resp.status_code == 200

    reject_resp = client.post(f"/api/v1/samples/{reject_sample_id}/reject", json={"reason": "bad data"})
    assert reject_resp.status_code == 200
    assert reject_resp.json()["data"]["status"] == "failed"

    config_resp = client.put(
        "/api/v1/config",
        json={
            "erp_base_url": "https://erp.example.com",
            "n8n_webhook": "https://n8n.example.com/webhook",
            "n8n_token": "",
            "erp_intake_token": "",
        },
    )
    assert config_resp.status_code == 200

    delete_rule_resp = client.delete(f"/api/v1/rules/{rule_id}")
    assert delete_rule_resp.status_code == 200

    delete_job_resp = client.delete(f"/api/v1/jobs/{job_id}")
    assert delete_job_resp.status_code == 200

    audit_resp = client.get("/api/v1/audit?limit=200")
    assert audit_resp.status_code == 200
    assert audit_resp.json()["success"] is True
    audit_entries = audit_resp.json()["data"]["items"]
    observed_actions = {(item["object_type"], item["action"]) for item in audit_entries}
    expected_actions = {
        ("job", "create"),
        ("job", "update"),
        ("job", "delete"),
        ("job_run", "create"),
        ("rule", "create"),
        ("rule", "update"),
        ("rule", "delete"),
        ("rule_version", "create"),
        ("sample", "review"),
        ("sample", "approve"),
        ("sample", "send_training"),
        ("sample", "reject"),
        ("training_queue_item", "update"),
        ("system_config", "update"),
    }
    assert expected_actions.issubset(observed_actions)

    list_resp = client.get("/api/v1/samples")
    assert list_resp.status_code == 200
    assert list_resp.json()["success"] is True
