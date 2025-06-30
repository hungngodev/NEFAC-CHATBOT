from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """
    Represents the shared state of the agentic workflow.
    """

    session_id: Optional[str] = Field(default=None, description="Unique identifier for the current session (used for session memory in Pinecone)")
    query: str = Field(description="The user's original query")
    chat_history: List[BaseMessage] = Field(description="The conversation history")
    history_summary: Optional[str] = Field(description="A summary of the conversation history")

    contextualized_query: Optional[str] = Field(description="The query after contextualization")
    intent: Optional[str] = Field(description="The user's classified intent")

    retrieval_method: Optional[str] = Field(description="The chosen retrieval strategy")
    retrieval_selection: Optional[dict] = Field(description="The chosen retrieval methods and weights")

    transformed_query: Optional[str] = Field(description="The transformed query for retrieval")
    documents: Optional[List[str]] = Field(description="The retrieved documents")

    answer: Optional[str] = Field(description="The final generated answer")
    validation: Optional[dict] = Field(description="The validation result")
    entities: Optional[List[str]] = Field(description="Extracted entities from the query")

    metadata_filters: Optional[dict] = Field(description="Filters to apply to retrieved documents based on metadata")
    priorities: Optional[List[Dict[str, Any]]] = Field(description="Prioritization rules for retrieved documents based on metadata")
    extracted_info: Optional[Any] = Field(description="Extracted information from documents")
    summarized_content: Optional[Any] = Field(description="Summarized content of documents")
    citations: Optional[Any] = Field(description="Citations and source attribution for documents")
    session_memory: Optional[List[Dict[str, Any]]] = Field(default=None, description="Relevant session memory items retrieved from Pinecone for the current query")
    structured_query: Optional[str] = Field(description="Cypher query for structured data retrieval from graph database")
    statistical_query: Optional[str] = Field(description="Cypher query for statistical data retrieval from graph database")
    error: Optional[str] = Field(description="Any error that occurred during the workflow")
