from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


def _local_db_url(name: str) -> str:
    tmp_dir = Path(__file__).resolve().parents[1] / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_dir / f"{Path(name).stem}-{uuid4().hex}.db"
    return f"sqlite:///{db_path}"


def _assert_list_contract(body: dict):
    assert body["success"] is True
    assert isinstance(body["data"]["items"], list)
    meta = body["data"]["meta"]
    for key in ("total", "page", "page_size", "has_next", "sort_by", "sort_order"):
        assert key in meta


def _bootstrap_client() -> TestClient:
    app = create_app(database_url=_local_db_url("list_endpoints.db"))
    client = TestClient(app)

    job_1 = {
        "task_name": "job alpha",
        "crawl_scope": "public_web",
        "source_type": "website",
        "keywords": ["alpha"],
        "start_page": 1,
        "max_pages": 1,
        "time_range": "",
        "include_domains": ["example.com"],
        "exclude_rules": [],
        "rule_notes": "first",
        "schedule_mode": "manual",
        "schedule_note": "",
        "n8n_webhook": "",
        "auto_push_n8n": False,
        "enabled": True,
        "status": "pending",
    }
    job_2 = {**job_1, "task_name": "job beta", "source_type": "directory", "enabled": False, "status": "running", "keywords": ["beta"]}

    r1 = client.post("/api/v1/jobs", json=job_1)
    r2 = client.post("/api/v1/jobs", json=job_2)
    job_id = r1.json()["data"]["id"]

    rule_1 = {
        "rule_name": "rule alpha",
        "hit_hint": "email",
        "explanation_rule": "extract email",
        "sample_input": "a@example.com",
        "expected_output": '{"email":"a@example.com"}',
        "version_note": "v1",
        "enabled": True,
        "auto_approve_on_hit": False,
    }
    rule_2 = {**rule_1, "rule_name": "rule beta", "hit_hint": "phone", "enabled": False, "auto_approve_on_hit": True}
    rr1 = client.post("/api/v1/rules", json=rule_1)
    client.post("/api/v1/rules", json=rule_2)
    rule_id = rr1.json()["data"]["id"]

    run_resp = client.post(
        "/api/v1/runs",
        json={
            "job_id": job_id,
            "status": "parsed",
            "started_at": None,
            "finished_at": None,
            "total_found": 2,
            "total_parsed": 2,
            "total_failed": 0,
            "total_review": 1,
            "total_approved": 1,
            "run_note": "run",
        },
    )
    run_id = run_resp.json()["data"]["id"]

    sample_base = {
        "job_id": job_id,
        "run_id": run_id,
        "linked_rule_id": rule_id,
        "rule_name": "rule alpha",
        "source_name": "crawler-a",
        "title": "alpha sample",
        "keyword": "alpha",
        "status": "parsed",
        "erp_status": "",
        "raw_payload": {"text": "alpha"},
        "normalized_payload": {"website": "https://example.com", "email": "a@example.com"},
        "source_url": "https://example.com/a",
        "crawl_time": "2026-01-01T00:00:00Z",
        "confidence": 0.9,
        "rule_version_id": 1,
    }
    s1 = client.post("/api/v1/samples", json=sample_base)
    s1_id = s1.json()["data"]["id"]
    s2_payload = {**sample_base, "title": "beta sample", "keyword": "beta", "status": "review", "source_name": "crawler-b", "source_url": "https://example.com/b"}
    client.post("/api/v1/samples", json=s2_payload)

    client.post(
        f"/api/v1/samples/{s1_id}/mark-duplicate",
        json={"duplicate_of_sample_id": s1_id, "dedupe_key": "https://example.com||a@example.com", "duplicate_reason": "manual", "source": "manual"},
    )

    client.post(
        "/api/v1/audit",
        json={
            "event_time": "2026-01-01T00:00:00Z",
            "object_type": "sample",
            "object_id": str(s1_id),
            "source": "system",
            "action": "mark_duplicate",
            "status": "approved",
            "operator": "tester",
            "summary": "sample dedupe",
            "detail_json": {"trace_version": "v0.2"},
            "sample_id": s1_id,
            "rule_version_id": 1,
            "dedupe_key": "https://example.com||a@example.com",
            "trace_version": "v0.2",
        },
    )

    return client


def test_jobs_list_contract_paging_sort_filter():
    client = _bootstrap_client()

    resp = client.get("/api/v1/jobs")
    assert resp.status_code == 200
    _assert_list_contract(resp.json())

    paged = client.get("/api/v1/jobs?page=1&page_size=1")
    assert paged.status_code == 200
    assert paged.json()["data"]["meta"]["page_size"] == 1

    sorted_resp = client.get("/api/v1/jobs?sort_by=task_name&sort_order=asc")
    assert sorted_resp.status_code == 200
    assert sorted_resp.json()["data"]["meta"]["sort_by"] == "task_name"
    assert sorted_resp.json()["data"]["meta"]["sort_order"] == "asc"

    invalid_sort = client.get("/api/v1/jobs?sort_by=unknown")
    assert invalid_sort.status_code == 400

    filtered = client.get("/api/v1/jobs?status=pending&enabled=true&keyword=alpha&source_type=website")
    assert filtered.status_code == 200
    items = filtered.json()["data"]["items"]
    assert all(item["status"] == "pending" for item in items)


def test_rules_list_contract_paging_sort_filter():
    client = _bootstrap_client()

    resp = client.get("/api/v1/rules")
    assert resp.status_code == 200
    _assert_list_contract(resp.json())

    paged = client.get("/api/v1/rules?page=1&page_size=1")
    assert paged.status_code == 200
    assert paged.json()["data"]["meta"]["page_size"] == 1

    sorted_resp = client.get("/api/v1/rules?sort_by=rule_name&sort_order=desc")
    assert sorted_resp.status_code == 200
    assert sorted_resp.json()["data"]["meta"]["sort_by"] == "rule_name"
    assert sorted_resp.json()["data"]["meta"]["sort_order"] == "desc"

    invalid_sort = client.get("/api/v1/rules?sort_by=unknown")
    assert invalid_sort.status_code == 400

    filtered = client.get("/api/v1/rules?enabled=true&auto_approve_on_hit=false&keyword=alpha")
    assert filtered.status_code == 200
    items = filtered.json()["data"]["items"]
    assert all(item["enabled"] is True for item in items)


def test_samples_list_contract_paging_sort_filter():
    client = _bootstrap_client()

    resp = client.get("/api/v1/samples")
    assert resp.status_code == 200
    _assert_list_contract(resp.json())

    paged = client.get("/api/v1/samples?page=1&page_size=1")
    assert paged.status_code == 200
    assert paged.json()["data"]["meta"]["page_size"] == 1

    sorted_resp = client.get("/api/v1/samples?sort_by=confidence&sort_order=asc")
    assert sorted_resp.status_code == 200
    assert sorted_resp.json()["data"]["meta"]["sort_by"] == "confidence"
    assert sorted_resp.json()["data"]["meta"]["sort_order"] == "asc"

    invalid_sort = client.get("/api/v1/samples?sort_by=unknown")
    assert invalid_sort.status_code == 400

    filtered = client.get("/api/v1/samples?status=parsed&is_duplicate=true&rule_version_id=1&keyword=alpha")
    assert filtered.status_code == 200
    items = filtered.json()["data"]["items"]
    assert all(item["status"] == "parsed" for item in items)
    assert all(item["is_duplicate"] is True for item in items)


def test_audit_list_contract_paging_sort_filter():
    client = _bootstrap_client()

    resp = client.get("/api/v1/audit")
    assert resp.status_code == 200
    _assert_list_contract(resp.json())

    paged = client.get("/api/v1/audit?page=1&page_size=1")
    assert paged.status_code == 200
    assert paged.json()["data"]["meta"]["page_size"] == 1

    sorted_resp = client.get("/api/v1/audit?sort_by=event_time&sort_order=desc")
    assert sorted_resp.status_code == 200
    assert sorted_resp.json()["data"]["meta"]["sort_by"] == "event_time"
    assert sorted_resp.json()["data"]["meta"]["sort_order"] == "desc"

    invalid_sort = client.get("/api/v1/audit?sort_by=unknown")
    assert invalid_sort.status_code == 400

    filtered = client.get("/api/v1/audit?object_type=sample&action=mark_duplicate&status=approved&keyword=dedupe")
    assert filtered.status_code == 200
    items = filtered.json()["data"]["items"]
    assert all(item["object_type"] == "sample" for item in items)
