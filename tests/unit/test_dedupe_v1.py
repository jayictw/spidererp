from app.services.dedupe_service import build_dedupe_key, normalize_url


def test_normalize_url_basic_cases():
    assert normalize_url("example.com/path/?utm_source=abc#frag") == "https://example.com/path"
    assert normalize_url("HTTP://Example.com:80/a/?b=1&fbclid=1") == "http://example.com/a?b=1"
    assert normalize_url("https://example.com:443/a/") == "https://example.com/a"


def test_build_dedupe_key_with_email():
    key, reason = build_dedupe_key(
        website="https://example.com/company",
        email=" Sales@Example.com ",
        company_name="ACME",
        title="CEO",
        source_url="https://example.com/company",
    )
    assert key == "https://example.com||sales@example.com"
    assert reason == "dedupe_v1:email_origin_match"


def test_build_dedupe_key_without_email_fallback():
    key, reason = build_dedupe_key(
        website="",
        email="",
        company_name=" ACME Corp ",
        title=" Founder ",
        source_url="https://example.com/about?utm_campaign=x",
    )
    assert key == "https://example.com/about||acme corp||founder"
    assert reason == "dedupe_v1:fallback_signature_match"


def test_build_dedupe_key_insufficient_fields():
    key, reason = build_dedupe_key(
        website="",
        email="",
        company_name="",
        title="",
        source_url="",
    )
    assert key == ""
    assert reason == "dedupe_v1:insufficient_keys"

