from __future__ import annotations

import operator
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


class InternalDocumentSearch(BaseModel):
    """Call this tool to search internal documents and knowledge base using intelligent retrieval strategies.

    Use this for legal documents, organizational policies, NEFAC-related content, or any internal resources.
    The system automatically selects the optimal search strategy based on query characteristics.
    """

    query: str = Field(description="The search query for internal documents. Be specific and detailed for best results. Examples: 'First Amendment rights for journalists', 'FOIA exemptions for law enforcement', 'NEFAC v. Department of Justice'")


class ResearchComplete(BaseModel):
    """Call this tool to indicate that the research is complete."""


class Summary(BaseModel):
    summary: str
    key_excerpts: str


###################
# State Definitions
###################


class RetrievalPlanModel(BaseModel):
    """Flattened plan schema for provider-compatible structured output.

    The retrieval planner produces these top-level fields, which the node then
    reshapes into the nested runtime format expected elsewhere.
    """

    keyword_weight: float
    vector_weight: float
    vector_k: int
    keyword_k: int
    graph_k: int
    rerank_k: int


def reduce_documents(current_docs: list[Document] | None, new_docs: list[Document] | None) -> list[Document]:
    if current_docs is None:
        current_docs = []
    if new_docs is None:
        new_docs = []

    seen = set()
    unique_docs = []

    # Add existing docs
    for doc in current_docs:
        # Use a tuple of content and source as key
        key = (doc.page_content, str(doc.metadata.get("source", "")))
        if key not in seen:
            seen.add(key)
            unique_docs.append(doc)

    # Add new docs
    for doc in new_docs:
        key = (doc.page_content, str(doc.metadata.get("source", "")))
        if key not in seen:
            seen.add(key)
            unique_docs.append(doc)

    return unique_docs


class RetrievalSubgraphState(TypedDict):
    """State for the retrieval subgraph."""

    # The `retrieval_query` from  is used as the input query.
    retrieval_query: str = ""
    retrieval_plan: dict[str, Any] = {}
    graph_documents: list[Document] = []
    document_search_documents: list[Document] = []
    documents: Annotated[list[Document], reduce_documents] = []  # Final combined list


class QueryTransformerState(RetrievalSubgraphState):
    """Standalone state for the query transformer workflow."""

    transformed_query: str  # The input query to transform
    method_used: Literal["multiquery", "decompose", "stepback", "hyde", "factual", "contextual", "default"]  # Which transformation method was applied
    transformed_context: str  # Formatted final context
    generated_queries: list[str]  # For multi-query strategy
    sub_questions: list[str]  # For decomposition strategy
    step_back_question: str  # For step-back strategy
    hypothetical_document: str  # For HyDE strategy
    # ✅ ADD: Support for tool call context in Send() API
    _source_tool_call: dict = {}  # Store original tool call for result processing


class QueryTransformerOutputState(TypedDict):
    """Output state for query transformer - following legacy Send() API pattern."""

    _completed_query_results: Annotated[list[dict], operator.add]  # ✅ Key field for Send() API aggregation


def override_reducer(current_value, new_value):
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)


class BaseResearchState(TypedDict):
    """Base state with common research fields."""

    research_brief: str | None
    notes: Annotated[list[str], override_reducer]
    raw_notes: Annotated[list[str], override_reducer]
    final_documents: Annotated[list[Document], reduce_documents]


class AgentInputState(MessagesState):
    """InputState is only 'messages'"""


class AgentState(MessagesState):
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    final_report: str

    # BaseResearchState fields explicitly defined to avoid metaclass conflict
    research_brief: str | None
    notes: Annotated[list[str], override_reducer]
    raw_notes: Annotated[list[str], override_reducer]
    final_documents: Annotated[list[Document], reduce_documents]


class QuickAgentState(AgentState):
    """State for the Quick Agent subgraph."""

    tool_call_iterations: int = 0
    final_report: str = ""


class SupervisorState(BaseResearchState):
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    research_iterations: int = 0
    # Send() API aggregation fields (following legacy pattern)
    completed_research_results: Annotated[list["ResearcherOutputState"], operator.add] = []
    research_tool_calls: list[dict] = []  # Store tool calls for result matching


class ResearcherState(BaseResearchState):
    researcher_messages: Annotated[list[MessageLikeRepresentation], operator.add]
    tool_call_iterations: int = 0
    research_topic: str
    compressed_research: str
    _completed_query_results: Annotated[list[dict], override_reducer] = []  # Aggregated query transformer results (supports override clears)
    _answered_tool_call_ids: Annotated[list[str], operator.add] = []
    documents: Annotated[list[Document], reduce_documents] = []


class ResearcherOutputState(BaseModel):
    compressed_research: str
    raw_notes: Annotated[list[str], override_reducer] = []
    documents: list[Document] = Field(default_factory=list)


class ResearcherSendOutputState(TypedDict):
    """Output envelope for Send() aggregation from the research_team subgraph.

    Aggregates individual researcher outputs so the supervisor can match them
    back to ConductResearch tool calls using `completed_research_results`.
    """

    completed_research_results: Annotated[list["ResearcherOutputState"], operator.add]


# Import metadata schemas for crawler compatibility
