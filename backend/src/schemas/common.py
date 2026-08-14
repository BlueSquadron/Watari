"""Shared Pydantic schemas: response envelope, pagination, errors."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PaginationMeta(BaseModel):
    """Pagination metadata returned on list endpoints."""

    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_count: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ApiResponse[T](BaseModel):
    """Standard success response envelope."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: T
    meta: PaginationMeta | None = None


class ErrorDetail(BaseModel):
    """Field-level error detail."""

    field: str
    message: str
    code: str


class ApiError(BaseModel):
    """Standard error response envelope."""

    code: str
    message: str
    details: list[ErrorDetail] | None = None
    request_id: str


class PaginationParams(BaseModel):
    """Query parameters for paginated list endpoints."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def build_pagination_meta(total_count: int, page: int, page_size: int) -> PaginationMeta:
    """Compute PaginationMeta from total row count and current paging params."""
    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0
    return PaginationMeta(
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=total_pages,
    )


__all__ = [
    "ApiResponse",
    "ApiError",
    "ErrorDetail",
    "PaginationMeta",
    "PaginationParams",
    "build_pagination_meta",
]
