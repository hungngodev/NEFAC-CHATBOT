from typing import List, Literal, Optional

from pydantic import BaseModel, Field


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


class IntentClassification(BaseModel):
    """Schema for the intent classification of the user query."""

    intent: Literal["document request", "general"] = Field(description="Classify the user's intent. If they are asking for information that could be found in NEFAC's documents, classify as 'document request'. Otherwise, classify as 'general'.")


class MethodSelection(BaseModel):
    """Schema for the query construction method selection."""

    method: Literal["multiquery", "decompose", "stepback", "hyde", "ragfusion", "default"] = Field(description="The selected query construction method.")
