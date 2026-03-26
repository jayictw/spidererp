from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


def _db_url() -> str:
    tmp_dir = Path(__file__).resolve().parent / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{tmp_dir / f'samples-trace-page-{uuid4().hex}.db'}"


def _create_rule(client: TestClient) -> int:
    resp = client.post(
        "/api/v1/rules",
        json={
            "rule_name": f"page-trace-rule-{uuid4().hex[:8]}",
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
        "rule_name": "page-trace-rule",
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
        "confidence": 0.8,
    }


def test_samples_page_trace_view_minimal():
    app = create_app(database_url=_db_url())
    client = TestClient(app)
    rule_id = _create_rule(client)

    first = client.post("/api/v1/samples", json=_sample_payload(rule_id, email="ui@example.com", source_url="https://example.com/1", title="lead1"))
    first_id = first.json()["data"]["id"]
    client.post("/api/v1/samples", json=_sample_payload(rule_id, email="ui@example.com", source_url="https://example.com/2", title="lead2"))

    page = client.get(f"/samples?trace_sample_id={first_id}")
    assert page.status_code == 200
    text = page.text
    assert "查看 trace" in text
    assert "audit_timeline" in text
    assert "extractor_name" in text


def test_samples_page_trace_not_found_does_not_crash():
    app = create_app(database_url=_db_url())
    client = TestClient(app)
    page = client.get("/samples?trace_sample_id=999999")
    assert page.status_code == 200
    assert "sample not found" in page.text.lower()
    assert "sample_not_found" in page.text


def test_samples_page_trace_invalid_id_shows_error():
    app = create_app(database_url=_db_url())
    client = TestClient(app)
    page = client.get("/samples?trace_sample_id=abc")
    assert page.status_code == 200
    assert "trace_sample_id 无效" in page.text
    assert "invalid_trace_sample_id" in page.text
