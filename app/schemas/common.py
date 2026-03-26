from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiSuccessResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(from_attributes=True)

    success: bool = True
    data: T | None = None
    message: str = ""


class ApiErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool = False
    error: str
    message: str = ""


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool = True
    message: str = ""

