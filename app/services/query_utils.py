from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class PaginationResult:
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    sort_by: str
    sort_order: str


def normalize_page(page: int | None, page_size: int | None, *, default_page: int = 1, default_page_size: int = 20) -> tuple[int, int]:
    safe_page = default_page if page is None or page < 1 else page
    safe_page_size = default_page_size if page_size is None or page_size < 1 else page_size
    safe_page_size = min(safe_page_size, 200)
    return safe_page, safe_page_size


def normalize_sort_order(sort_order: str | None) -> str:
    value = (sort_order or "desc").lower()
    return "asc" if value == "asc" else "desc"


def validate_sort_field(sort_by: str | None, allowed: set[str], default: str) -> str:
    if not sort_by:
        return default
    if sort_by not in allowed:
        raise ValueError(f"unsupported sort field: {sort_by}")
    return sort_by


def apply_keyword_filters(stmt: Select, conditions: list[Any]) -> Select:
    if not conditions:
        return stmt
    return stmt.where(or_(*conditions))


def paginate_statement(
    db: Session,
    stmt: Select,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Any], PaginationResult]:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int(db.execute(count_stmt).scalar_one())
    offset = (page - 1) * page_size
    items = list(db.execute(stmt.limit(page_size).offset(offset)).scalars().all())
    total_pages = ceil(total / page_size) if total else 0
    return items, PaginationResult(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        sort_by="",
        sort_order="desc",
    )


def build_sorted_select(stmt: Select, *, sort_field: Any, sort_order: str) -> Select:
    order_clause = sort_field.asc() if sort_order == "asc" else sort_field.desc()
    return stmt.order_by(order_clause)


def set_pagination_meta(result: PaginationResult, *, sort_by: str, sort_order: str) -> PaginationResult:
    return PaginationResult(
        items=result.items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        sort_by=sort_by,
        sort_order=sort_order,
    )


def keyword_columns(*columns: Any) -> list[Any]:
    return list(columns)


def build_page_data(*, items: list[Any], total: int, page: int, page_size: int, sort_by: str, sort_order: str) -> dict[str, Any]:
    return {
        "items": items,
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": (page * page_size) < total,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    }
