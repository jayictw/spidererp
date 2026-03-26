from __future__ import annotations

import logging
from typing import Any

import requests

from app.core.config import get_settings
from app.crawler.limiter import DomainRateLimiter
from app.crawler.parse import dedupe_records, parse_html
from app.crawler.robots import RobotsCheckResult, check_robots, normalize_url


class CrawlerError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class CrawlerService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.session = requests.Session()
        self.rate_limiter = DomainRateLimiter(self.settings.crawler_per_domain_delay)
        self.user_agent = "Mozilla/5.0 (compatible; LeadParserBot/1.0)"
        self.ssl_verify = self.settings.crawler_ssl_verify
        self.logger = logging.getLogger(__name__)
        if not self.ssl_verify:
            self.logger.warning("CRAWLER_SSL_VERIFY=false detected; SSL certificate verification is disabled for crawler requests")

    def robots_check(self, url: str, user_agent: str | None = None, timeout: int | None = None) -> dict[str, Any]:
        agent = user_agent or self.user_agent
        result = check_robots(url, agent, timeout=timeout or self.settings.crawler_default_timeout)
        return self._robots_result_to_dict(result)

    def preview(
        self,
        url: str,
        timeout: int | None = None,
        max_retries: int | None = None,
        respect_robots: bool = True,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        normalized_url = normalize_url(url)
        agent = user_agent or self.user_agent
        robots_result = check_robots(normalized_url, agent, timeout=timeout or self.settings.crawler_default_timeout)
        if respect_robots and not robots_result.allowed:
            raise CrawlerError("robots_disallowed", "robots.txt disallows fetching this url", 403)

        html = self.fetch_html(
            normalized_url,
            timeout=timeout or self.settings.crawler_default_timeout,
            max_retries=max_retries if max_retries is not None else self.settings.crawler_max_retries,
            user_agent=agent,
        )
        parsed_records = parse_html(normalized_url, html)
        deduped_records = dedupe_records(parsed_records)
        return {
            "url": url,
            "normalized_url": normalized_url,
            "robots_allowed": robots_result.allowed,
            "raw_count": len(parsed_records),
            "deduped_count": len(deduped_records),
            "records": [record.model_dump(mode="json") for record in deduped_records],
        }

    def fetch_html(
        self,
        url: str,
        timeout: int,
        max_retries: int,
        user_agent: str,
    ) -> str:
        normalized_url = normalize_url(url)
        last_error: Exception | None = None
        attempts = max_retries + 1

        for attempt in range(attempts):
            self.rate_limiter.acquire(normalized_url)
            try:
                response = self.session.get(
                    normalized_url,
                    timeout=timeout,
                    verify=self.ssl_verify,
                    headers={
                        "User-Agent": user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                )
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise requests.HTTPError(f"retryable status: {response.status_code}", response=response)
                response.raise_for_status()
                return response.text
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
                last_error = exc
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if isinstance(exc, requests.HTTPError) and status_code not in {429, 500, 502, 503, 504}:
                    break
                if attempt >= max(0, attempts - 1):
                    break
            except requests.RequestException as exc:
                last_error = exc
                break

            if attempt < attempts - 1:
                self._backoff_sleep(attempt)
        message = f"failed to fetch html: {last_error}"
        if not self.ssl_verify:
            message += " (dev note: CRAWLER_SSL_VERIFY=false, SSL verification disabled)"
        raise CrawlerError("fetch_failed", message, 502)

    def _backoff_sleep(self, attempt: int) -> None:
        delay = min(10.0, 0.5 * (2**attempt))
        if delay > 0:
            import time

            time.sleep(delay)

    def _robots_result_to_dict(self, result: RobotsCheckResult) -> dict[str, Any]:
        return {
            "url": result.url,
            "normalized_url": result.normalized_url,
            "robots_url": result.robots_url,
            "allowed": result.allowed,
            "fetched": result.fetched,
            "note": result.note,
        }


_crawler_service: CrawlerService | None = None


def get_crawler_service() -> CrawlerService:
    global _crawler_service
    if _crawler_service is None:
        _crawler_service = CrawlerService()
    return _crawler_service
