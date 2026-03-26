from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from app.crawler.extractors import (
    ExtractedContacts,
    extract_company_name,
    extract_contacts,
    extract_title,
    extract_visible_text,
    html_excerpt,
    visible_text_excerpt,
)
from app.schemas.crawler import CrawlerNormalizedRecord


def _website_origin(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    host = parsed.hostname or ""
    if not host:
        return ""
    netloc = host.lower()
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return f"{scheme}://{netloc}"


def _base_confidence(company_name: str, title: str, contacts: ExtractedContacts, text: str) -> float:
    score = 0.15
    if company_name:
        score += 0.2
    if title:
        score += 0.15
    if contacts.emails:
        score += 0.2
    if contacts.phones:
        score += 0.15
    if contacts.whatsapps:
        score += 0.1
    if len(text) > 200:
        score += 0.05
    return min(1.0, round(score, 2))


def parse_html(url: str, html: str) -> list[CrawlerNormalizedRecord]:
    visible_text = extract_visible_text(html)
    title = extract_title(html)
    company_name = extract_company_name(html, url)
    contacts = extract_contacts(visible_text)
    crawl_time = datetime.now(UTC).isoformat()
    website = _website_origin(url)
    confidence = _base_confidence(company_name, title, contacts, visible_text)
    records: list[CrawlerNormalizedRecord] = []

    if contacts.emails:
        for email in contacts.emails:
            records.append(
                CrawlerNormalizedRecord(
                    company_name=company_name,
                    website=website,
                    person_name="",
                    title=title,
                    email=email,
                    phone=contacts.phones[0] if contacts.phones else "",
                    whatsapp=contacts.whatsapps[0] if contacts.whatsapps else "",
                    country="",
                    source_url=url,
                    crawl_time=crawl_time,
                    confidence=confidence,
                    raw_text=visible_text_excerpt(visible_text),
                    raw_html_excerpt=html_excerpt(html),
                )
            )
    elif contacts.phones or contacts.whatsapps:
        records.append(
            CrawlerNormalizedRecord(
                company_name=company_name,
                website=website,
                person_name="",
                title=title,
                email="",
                phone=contacts.phones[0] if contacts.phones else "",
                whatsapp=contacts.whatsapps[0] if contacts.whatsapps else "",
                country="",
                source_url=url,
                crawl_time=crawl_time,
                confidence=confidence,
                raw_text=visible_text_excerpt(visible_text),
                raw_html_excerpt=html_excerpt(html),
            )
        )
    else:
        records.append(
            CrawlerNormalizedRecord(
                company_name=company_name,
                website=website,
                person_name="",
                title=title,
                email="",
                phone="",
                whatsapp="",
                country="",
                source_url=url,
                crawl_time=crawl_time,
                confidence=confidence,
                raw_text=visible_text_excerpt(visible_text),
                raw_html_excerpt=html_excerpt(html),
            )
        )

    return records


def dedupe_records(records: list[CrawlerNormalizedRecord]) -> list[CrawlerNormalizedRecord]:
    seen: set[tuple[str, str]] = set()
    deduped: list[CrawlerNormalizedRecord] = []
    for record in records:
        website = record.website.strip().lower()
        email = record.email.strip().lower()
        if not website and not email:
            deduped.append(record)
            continue
        key = (website, email)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped

