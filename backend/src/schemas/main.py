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


class Citation(BaseModel):
    id: str = Field(description="Unique identifier for the citation")
    context: str = Field(description="The citation used to generate the search result")


class SearchResult(BaseModel):
    title: str = Field(description="The title of the search result")
    link: str = Field(description="The link to the source of search result")
    summary: str = Field(description="A brief summary of the search result and relvance to prompt")
    citations: List[Citation] = Field(description="A list of citations used to generate the search result")
    type: Optional[str] = None
    timestamp_seconds: Optional[int] = None
    content: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[SearchResult] = Field(description="A list of search results")


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

    method: Literal[
        "multiquery",
        "decompose",
        "stepback",
        "hyde",
        "ragfusion",
        "factual",
        "contextual",
        "default",
    ] = Field(description="The selected query construction method.")


class RetrievalSelection(BaseModel):
    """
    Schema for selecting one or more retrieval strategies and their weights.
    """

    methods: List[Literal["graph", "dense", "sparse"]] = Field(
        ...,
        description=("Which retrieval methods to apply—any combination of:\n" "• graph  – Neo4j knowledge-graph retriever\n" "• dense  – Qdrant semantic vector retriever\n" "• sparse – Elasticsearch BM25 keyword retriever"),
    )
    weights: List[float] = Field(
        ...,
        description=("A parallel list of weights for each method, summing to 1.0 if possible.\n" "If lengths mismatch or sum != 1, weights will be normalized equally."),
    )


class MultiStepReasoning(BaseModel):
    """
    Schema for multi-step reasoning.
    """

    reasoning_steps: List[str] = Field(
        ...,
        description="A list of reasoning steps to answer the user's query.",
    )


class Validation(BaseModel):
    """
    Schema for validating the generated answer.
    """

    is_valid: bool = Field(
        ...,
        description="Whether the generated answer is valid or not.",
    )
    reasoning: str = Field(
        ...,
        description="The reasoning behind the validation.",
    )
