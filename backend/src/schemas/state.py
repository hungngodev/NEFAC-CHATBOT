from __future__ import annotations

import operator
from operator import add
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


###################
# Structured Outputs
###################
class ConductResearch(BaseModel):
    """Call this tool to conduct research on a specific topic."""

    research_topic: str = Field(
        description="The topic to research. Should be a single topic, and should be described in high detail (at least a paragraph).",
    )


class ResearchComplete(BaseModel):
    """Call this tool to indicate that the research is complete."""


class Summary(BaseModel):
    summary: str
    key_excerpts: str


###################
# State Definitions
###################
class DocumentSearchParamsModel(BaseModel):
    weights: dict[str, float]
    vector_k: int
    keyword_k: int
    ensemble_k: int


class RetrievalPlanModel(BaseModel):
    methods: list[str]
    doc_search_params: DocumentSearchParamsModel
    rerank_k: int


class RetrievalSubgraphState(TypedDict):
    """State for the retrieval subgraph."""

    # The `retrieval_query` from  is used as the input query.
    retrieval_query: str = ""
    retrieval_plan: dict[str, Any] = {}
    graph_documents: list[Document] = []
    document_search_documents: list[Document] = []
    documents: list[Document] = []  # Final combined list
    accumulated_documents: Annotated[list[Document], add] = Field(default_factory=list, description="Final list of retrieved documents")


class QueryTransformerState(RetrievalSubgraphState):
    """Standalone state for the query transformer workflow."""

    transformed_query: str  # The input query to transform
    method_used: Literal["multiquery", "decompose", "stepback", "hyde", "factual", "contextual", "default"]  # Which transformation method was applied
    transformed_context: str  # Formatted final context
    generated_queries: list[str]  # For multi-query strategy
    sub_questions: list[str]  # For decomposition strategy
    step_back_question: str  # For step-back strategy
    hypothetical_document: str  # For HyDE strategy


def override_reducer(current_value, new_value):
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)


class AgentInputState(MessagesState):
    """InputState is only 'messages'"""


class AgentState(MessagesState):
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    research_brief: str | None
    raw_notes: Annotated[list[str], override_reducer] = []
    notes: Annotated[list[str], override_reducer] = []
    final_report: str
    final_documents: Annotated[list[Document], add] = Field(default_factory=list, description="Final list of retrieved documents")


class SupervisorState(TypedDict):
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    research_brief: str
    notes: Annotated[list[str], override_reducer] = []
    research_iterations: int = 0
    raw_notes: Annotated[list[str], override_reducer] = []


class ResearcherState(TypedDict):
    researcher_messages: Annotated[list[MessageLikeRepresentation], operator.add]
    tool_call_iterations: int = 0
    research_topic: str
    compressed_research: str
    raw_notes: Annotated[list[str], override_reducer] = []


class ResearcherOutputState(BaseModel):
    compressed_research: str
    raw_notes: Annotated[list[str], override_reducer] = []


# Import metadata schemas for crawler compatibility
