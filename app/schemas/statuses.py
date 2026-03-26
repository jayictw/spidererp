from __future__ import annotations

from typing import Final


ALLOWED_DOMAIN_STATUSES: Final[set[str]] = {
    "pending",
    "running",
    "parsed",
    "review",
    "failed",
    "approved",
    "exported",
}

ALLOWED_QUEUE_STATUSES: Final[set[str]] = {
    "pending",
    "running",
    "review",
    "approved",
}

