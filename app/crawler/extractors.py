from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{6,}\d)(?!\d)")
WHATSAPP_RE = re.compile(r"(?i)\b(?:whatsapp|wa\.me)\b[:\s\-]*([+\d][\d\s().-]{6,}\d)")
WHATSAPP_URL_RE = re.compile(r"(?i)https?://wa\.me/([0-9]+)")


@dataclass(slots=True)
class ExtractedContacts:
    emails: list[str]
    phones: list[str]
    whatsapps: list[str]


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def extract_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    return normalize_whitespace(soup.get_text(" ", strip=True))


def extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        return normalize_whitespace(title_tag.get_text(" ", strip=True))
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return normalize_whitespace(h1.get_text(" ", strip=True))
    return ""


def extract_company_name(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    meta_candidates = [
        ("property", "og:site_name"),
        ("name", "application-name"),
        ("name", "twitter:site"),
    ]
    for attr, value in meta_candidates:
        tag = soup.find("meta", attrs={attr: value})
        content = tag.get("content", "").strip() if tag else ""
        if content:
            return normalize_whitespace(content)

    title = extract_title(html)
    if title:
        return title.split("|")[0].split("-")[0].strip()

    host = urlparse(url).hostname or ""
    if host:
        return host.removeprefix("www.")
    return ""


def extract_contacts(text: str) -> ExtractedContacts:
    emails = _unique_matches(EMAIL_RE.findall(text))
    phones = _unique_matches(_sanitize_phone(candidate) for candidate in PHONE_RE.findall(text))
    whatsapps = _unique_matches(
        [
            *_sanitize_whatsapp_matches(WHATSAPP_RE.findall(text)),
            *_sanitize_whatsapp_matches(WHATSAPP_URL_RE.findall(text)),
        ]
    )
    return ExtractedContacts(emails=emails, phones=phones, whatsapps=whatsapps)


def _sanitize_phone(value: str) -> str:
    cleaned = normalize_whitespace(value)
    cleaned = re.sub(r"[^\d+()\-.\s]", "", cleaned)
    cleaned = normalize_whitespace(cleaned)
    return cleaned


def _sanitize_whatsapp_matches(values: Iterable[str]) -> list[str]:
    return [_sanitize_phone(value) for value in values if value]


def _unique_matches(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = normalize_whitespace(value).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized if "@" in normalized else normalize_whitespace(value))
    return ordered


def html_excerpt(html: str, limit: int = 1200) -> str:
    excerpt = normalize_whitespace(re.sub(r"<[^>]+>", " ", html))
    return excerpt[:limit]


def visible_text_excerpt(text: str, limit: int = 4000) -> str:
    return normalize_whitespace(text)[:limit]

