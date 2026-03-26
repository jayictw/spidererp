from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CrawlerNormalizedRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company_name: str = ""
    website: str = ""
    person_name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    whatsapp: str = ""
    country: str = ""
    source_url: str = ""
    crawl_time: str = ""
    confidence: float = 0.0
    raw_text: str = ""
    raw_html_excerpt: str = ""


class CrawlerPreviewRequest(BaseModel):
    url: str = Field(..., min_length=1)
    timeout: int = Field(default=20, ge=1, le=120)
    max_retries: int = Field(default=2, ge=0, le=5)
    respect_robots: bool = True
    user_agent: str = "Mozilla/5.0 (compatible; LeadParserBot/1.0)"


class CrawlerRobotsCheckRequest(BaseModel):
    url: str = Field(..., min_length=1)
    user_agent: str = "Mozilla/5.0 (compatible; LeadParserBot/1.0)"


class CrawlerPreviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    normalized_url: str
    robots_allowed: bool
    raw_count: int
    deduped_count: int
    records: list[CrawlerNormalizedRecord] = Field(default_factory=list)


class CrawlerRobotsCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    normalized_url: str
    robots_url: str
    allowed: bool
    fetched: bool
    note: str = ""

