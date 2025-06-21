from typing import List, Optional

from pydantic import BaseModel


class LoadingStatusResponse(BaseModel):
    """
    Defines the response schema for the /loading-status endpoint.
    """

    current: int
    total: int
    status: str
    is_loading: bool


# Schemas for the /ask-llm streaming response events


class SearchResult(BaseModel):
    title: str
    link: str
    type: str
    timestamp_seconds: Optional[int] = None
    summary: Optional[str] = None
    content: Optional[str] = None


class ContextEvent(BaseModel):
    order: int
    context: List[SearchResult]


class ReformulatedEvent(BaseModel):
    order: int
    reformulated: str


class MessageEvent(BaseModel):
    order: int
    message: str
