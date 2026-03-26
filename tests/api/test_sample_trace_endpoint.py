from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.db.session import create_sqlalchemy_engine
from app.models import AuditLog
from app.models.base import utc_now
from sqlalchemy.orm import Session


def _db_url() -> str:
    tmp_dir = Path(__file__).resolve().parents[1] / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{tmp_dir / f'trace-{uuid4().hex}.db'}"


def _client() -> TestClient:
    app = create_app(database_url=_db_url())
    return TestClient(app)


def _create_rule(client: TestClient) -> int:
    resp = client.post(
        "/api/v1/rules",
        json={
            "rule_name": f"trace-rule-{uuid4().hex[:8]}",
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


def _sample_payload(rule_id: int, *, email: str, source_url: str, title: str) -> dict:
    return {
        "rule_id": rule_id,
        "rule_name": "trace-rule",
        "source_name": "crawler",
        "title": title,
        "keyword": "trace",
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
        "confidence": 0.95,
    }


def test_trace_returns_sample_and_timeline_for_existing_sample():
    client = _client()
    rule_id = _create_rule(client)
    created = client.post("/api/v1/samples", json=_sample_payload(rule_id, email="t1@example.com", source_url="https://example.com/t1", title="trace-1"))
    sample_id = created.json()["data"]["id"]

    trace_resp = client.get(f"/api/v1/samples/{sample_id}/trace")
    assert trace_resp.status_code == 200
    body = trace_resp.json()
    assert body["success"] is True
    data = body["data"]
    assert "sample" in data
    assert "dedupe" in data
    assert "extractor" in data
    assert "rule" in data
    assert "primary_sample" in data
    assert "audit_timeline" in data
    assert isinstance(data["audit_timeline"], list)


def test_trace_for_duplicate_sample_contains_primary_sample():
    client = _client()
    rule_id = _create_rule(client)
    first = client.post("/api/v1/samples", json=_sample_payload(rule_id, email="dup-trace@example.com", source_url="https://example.com/a", title="a"))
    first_id = first.json()["data"]["id"]
    second = client.post("/api/v1/samples", json=_sample_payload(rule_id, email="dup-trace@example.com", source_url="https://example.com/b", title="b"))
    second_id = second.json()["data"]["id"]

    trace_resp = client.get(f"/api/v1/samples/{second_id}/trace")
    assert trace_resp.status_code == 200
    data = trace_resp.json()["data"]
    assert data["dedupe"]["is_duplicate"] is True
    assert data["dedupe"]["duplicate_of_sample_id"] == first_id
    assert data["primary_sample"] is not None
    assert data["primary_sample"]["id"] == first_id
    assert data["dedupe"]["duplicate_reason"].startswith("dedupe_v1:")


def test_trace_audit_timeline_item_structure():
    client = _client()
    rule_id = _create_rule(client)
    created = client.post("/api/v1/samples", json=_sample_payload(rule_id, email="timeline@example.com", source_url="https://example.com/tl", title="timeline"))
    sample_id = created.json()["data"]["id"]

    trace_resp = client.get(f"/api/v1/samples/{sample_id}/trace")
    assert trace_resp.status_code == 200
    timeline = trace_resp.json()["data"]["audit_timeline"]
    assert len(timeline) >= 1
    item = timeline[0]
    for key in ("event_time", "action", "status", "operator", "summary", "dedupe_key", "trace_version"):
        assert key in item


def test_trace_timeline_trace_version_fallback_to_v02():
    db_url = _db_url()
    app = create_app(database_url=db_url)
    client = TestClient(app)
    rule_id = _create_rule(client)
    created = client.post("/api/v1/samples", json=_sample_payload(rule_id, email="fallback@example.com", source_url="https://example.com/fallback", title="fallback"))
    sample_id = created.json()["data"]["id"]

    engine = create_sqlalchemy_engine(db_url)
    with Session(engine) as session:
        item = AuditLog(
            event_time=utc_now(),
            object_type="sample",
            object_id=str(sample_id),
            source="system",
            action="manual_trace_event",
            status="approved",
            operator="tester",
            summary="force empty trace version",
            detail_json={},
            sample_id=sample_id,
            dedupe_key="",
            trace_version="",
        )
        session.add(item)
        session.commit()

    trace_resp = client.get(f"/api/v1/samples/{sample_id}/trace")
    assert trace_resp.status_code == 200
    timeline = trace_resp.json()["data"]["audit_timeline"]
    assert any(item.get("trace_version") == "v0.2" for item in timeline)


def test_trace_returns_404_when_sample_missing():
    client = _client()
    missing = client.get("/api/v1/samples/999999/trace")
    assert missing.status_code == 404
    body = missing.json()
    assert body["success"] is False
    assert body["error"] == "sample_not_found"
