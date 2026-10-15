from typing import Generic, TypeVar

from src.schemas.base import CamelModel

T = TypeVar("T")


class MessageResponse(CamelModel):
    message: str


class Page(CamelModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
