from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.response import error_response, success_response
from app.schemas.crawler import (
    CrawlerPreviewRequest,
    CrawlerPreviewResponse,
    CrawlerRobotsCheckRequest,
    CrawlerRobotsCheckResponse,
)
from app.services.crawler_service import CrawlerError, get_crawler_service


router = APIRouter(prefix="/api/v1/crawler", tags=["crawler"])


@router.post("/preview", response_model=None)
def preview(payload: CrawlerPreviewRequest):
    service = get_crawler_service()
    try:
        result = service.preview(
            url=payload.url,
            timeout=payload.timeout,
            max_retries=payload.max_retries,
            respect_robots=payload.respect_robots,
            user_agent=payload.user_agent,
        )
        validated = CrawlerPreviewResponse.model_validate(result).model_dump(mode="json")
        return success_response(validated, "preview generated")
    except CrawlerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=error_response(exc.code, str(exc))) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=error_response("invalid_url", str(exc))) from exc


@router.post("/robots-check", response_model=None)
def robots_check(payload: CrawlerRobotsCheckRequest):
    service = get_crawler_service()
    try:
        result = service.robots_check(payload.url, user_agent=payload.user_agent)
        validated = CrawlerRobotsCheckResponse.model_validate(result).model_dump(mode="json")
        return success_response(validated, "robots checked")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=error_response("invalid_url", str(exc))) from exc
