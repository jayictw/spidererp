from __future__ import annotations

import threading
import time
from collections import defaultdict
from urllib.parse import urlparse


class DomainRateLimiter:
    def __init__(self, delay_seconds: float = 2.0):
        self.delay_seconds = max(0.0, delay_seconds)
        self._lock = threading.Lock()
        self._last_request_at: dict[str, float] = defaultdict(float)

    def _domain_key(self, url: str) -> str:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host and parsed.netloc:
            host = parsed.netloc.lower()
        return host.removeprefix("www.")

    def acquire(self, url: str) -> float:
        domain = self._domain_key(url)
        if not domain or self.delay_seconds <= 0:
            return 0.0

        with self._lock:
            now = time.monotonic()
            last = self._last_request_at[domain]
            wait_for = max(0.0, self.delay_seconds - (now - last))
            self._last_request_at[domain] = now + wait_for

        if wait_for > 0:
            time.sleep(wait_for)
        return wait_for

