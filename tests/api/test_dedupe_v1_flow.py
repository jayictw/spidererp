from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


def _db_url() -> str:
    tmp_dir = Path(__file__).resolve().parents[1] / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{tmp_dir / f'dedupe-v1-{uuid4().hex}.db'}"


def _bootstrap_client() -> TestClient:
    app = create_app(database_url=_db_url())
    return TestClient(app)


def _create_job_and_run(client: TestClient) -> tuple[int, int]:
    job_resp = client.post(
        "/api/v1/jobs",
        json={
            "task_name": f"dedupe-job-{uuid4().hex[:8]}",
            "crawl_scope": "public_web",
            "source_type": "website",
            "keywords": ["dedupe"],
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
    job_id = job_resp.json()["data"]["id"]
    run_resp = client.post(
        "/api/v1/runs",
        json={
            "job_id": job_id,
            "status": "running",
            "started_at": None,
            "finished_at": None,
            "total_found": 0,
            "total_parsed": 0,
            "total_failed": 0,
            "total_review": 0,
            "total_approved": 0,
            "run_note": "",
        },
    )
    run_id = run_resp.json()["data"]["id"]
    return job_id, run_id


def _create_rule(client: TestClient) -> int:
    resp = client.post(
        "/api/v1/rules",
        json={
            "rule_name": f"dedupe-rule-{uuid4().hex[:8]}",
            "hit_hint": "email",
            "explanation_rule": "extract email",
            "sample_input": "a@example.com",
            "expected_output": '{"email":"a@example.com"}',
            "version_note": "v1",
            "enabled": True,
            "auto_approve_on_hit": False,
        },
    )
    return resp.json()["data"]["id"]


def _sample_payload(rule_id: int, *, email: str, source_url: str, title: str = "lead A", job_id: int | None = None, run_id: int | None = None) -> dict:
    return {
        "job_id": job_id,
        "run_id": run_id,
        "rule_id": rule_id,
        "rule_name": "dedupe-rule",
        "source_name": "crawler",
        "title": title,
        "keyword": "lead",
        "status": "parsed",
        "erp_status": "",
        "raw_payload": {"text": email},
        "normalized_payload": {
            "website": "https://example.com",
            "email": email,
            "company_name": "ACME",
            "title": title,
            "source_url": source_url,
        },
        "source_url": source_url,
        "crawl_time": "2026-01-01T00:00:00Z",
        "confidence": 0.9,
    }


def test_sample_create_persists_dedupe_fields_and_marks_duplicate():
    client = _bootstrap_client()
    rule_id = _create_rule(client)

    first = client.post("/api/v1/samples", json=_sample_payload(rule_id, email="dup@example.com", source_url="https://example.com/a"))
    assert first.status_code == 200
    first_data = first.json()["data"]
    assert first_data["dedupe_version"] == "v1"
    assert first_data["extractor_name"] == "crawler"
    assert first_data["extractor_version"] == "v0.2"
    assert first_data["is_duplicate"] is False
    assert first_data["dedupe_key"] == "https://example.com||dup@example.com"

    second = client.post("/api/v1/samples", json=_sample_payload(rule_id, email="dup@example.com", source_url="https://example.com/b", title="lead B"))
    assert second.status_code == 200
    second_data = second.json()["data"]
    assert second_data["is_duplicate"] is True
    assert second_data["duplicate_of_sample_id"] == first_data["id"]
    assert second_data["dedupe_key"] == "https://example.com||dup@example.com"
    assert second_data["duplicate_reason"].startswith("dedupe_v1:")
    assert second_data["marked_duplicate_at"] is not None


def test_non_duplicate_sample_not_marked():
    client = _bootstrap_client()
    rule_id = _create_rule(client)

    first = client.post("/api/v1/samples", json=_sample_payload(rule_id, email="a@example.com", source_url="https://example.com/a"))
    second = client.post("/api/v1/samples", json=_sample_payload(rule_id, email="b@example.com", source_url="https://example.com/b"))

    assert first.status_code == 200 and second.status_code == 200
    second_data = second.json()["data"]
    assert second_data["is_duplicate"] is False
    assert second_data["duplicate_of_sample_id"] is None


def test_mark_duplicate_endpoint_ok_and_boundary():
    client = _bootstrap_client()
    rule_id = _create_rule(client)
    job_id, run_id = _create_job_and_run(client)

    first = client.post("/api/v1/samples", json=_sample_payload(rule_id, email="manual@example.com", source_url="https://example.com/m1", job_id=job_id, run_id=run_id))
    second = client.post("/api/v1/samples", json=_sample_payload(rule_id, email="other@example.com", source_url="https://example.com/m2", job_id=job_id, run_id=run_id))
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]

    marked = client.post(
        f"/api/v1/samples/{second_id}/mark-duplicate",
        json={
            "duplicate_of_sample_id": first_id,
            "dedupe_key": "https://example.com||manual@example.com",
            "duplicate_reason": "manual_review_match",
            "source": "manual",
        },
    )
    assert marked.status_code == 200
    marked_data = marked.json()["data"]
    assert marked_data["is_duplicate"] is True
    assert marked_data["duplicate_of_sample_id"] == first_id
    assert marked_data["duplicate_reason"].startswith("dedupe_v1:")

    run_after_first_mark = client.get(f"/api/v1/runs/{run_id}")
    assert run_after_first_mark.status_code == 200
    assert run_after_first_mark.json()["data"]["total_duplicate"] == 1

    marked_again = client.post(
        f"/api/v1/samples/{second_id}/mark-duplicate",
        json={
            "duplicate_of_sample_id": first_id,
            "dedupe_key": "https://example.com||manual@example.com",
            "duplicate_reason": "manual_review_match_again",
            "source": "manual",
        },
    )
    assert marked_again.status_code == 200
    run_after_second_mark = client.get(f"/api/v1/runs/{run_id}")
    assert run_after_second_mark.status_code == 200
    assert run_after_second_mark.json()["data"]["total_duplicate"] == 1

    not_found = client.post(
        "/api/v1/samples/999999/mark-duplicate",
        json={"duplicate_of_sample_id": first_id, "dedupe_key": "", "duplicate_reason": "x", "source": "manual"},
    )
    assert not_found.status_code == 404

    self_ref = client.post(
        f"/api/v1/samples/{first_id}/mark-duplicate",
        json={"duplicate_of_sample_id": first_id, "dedupe_key": "", "duplicate_reason": "manual", "source": "manual"},
    )
    assert self_ref.status_code == 400
