from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests


@dataclass(slots=True)
class RobotsCheckResult:
    url: str
    normalized_url: str
    robots_url: str
    allowed: bool
    fetched: bool
    note: str = ""


def normalize_url(url: str) -> str:
    value = url.strip()
    if not value:
        raise ValueError("url is required")
    if "://" not in value:
        value = f"https://{value}"

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("only http and https urls are supported")
    if not parsed.netloc:
        raise ValueError("invalid url")

    normalized = parsed._replace(fragment="")
    return urlunparse(normalized)


def build_robots_url(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    return urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))


def check_robots(url: str, user_agent: str, timeout: int = 20) -> RobotsCheckResult:
    normalized_url = normalize_url(url)
    robots_url = build_robots_url(normalized_url)
    parser = RobotFileParser()
    parser.set_url(robots_url)

    try:
        response = requests.get(robots_url, timeout=timeout, headers={"User-Agent": user_agent})
        if response.status_code == 200:
            parser.parse(response.text.splitlines())
            allowed = parser.can_fetch(user_agent, normalized_url)
            return RobotsCheckResult(
                url=url,
                normalized_url=normalized_url,
                robots_url=robots_url,
                allowed=allowed,
                fetched=True,
                note="robots parsed",
            )
        if response.status_code in {401, 403}:
            return RobotsCheckResult(
                url=url,
                normalized_url=normalized_url,
                robots_url=robots_url,
                allowed=False,
                fetched=True,
                note=f"robots returned {response.status_code}",
            )
        return RobotsCheckResult(
            url=url,
            normalized_url=normalized_url,
            robots_url=robots_url,
            allowed=True,
            fetched=False,
            note=f"robots unavailable ({response.status_code})",
        )
    except requests.RequestException as exc:
        return RobotsCheckResult(
            url=url,
            normalized_url=normalized_url,
            robots_url=robots_url,
            allowed=True,
            fetched=False,
            note=f"robots check failed: {exc.__class__.__name__}",
        )

