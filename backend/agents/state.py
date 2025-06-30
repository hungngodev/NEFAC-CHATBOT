from typing import List, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """
    Represents the shared state of the agentic workflow.
    """

    query: str = Field(description="The user's original query")
    chat_history: List[BaseMessage] = Field(description="The conversation history")

    contextualized_query: Optional[str] = Field(
        description="The query after contextualization"
    )
    intent: Optional[str] = Field(description="The user's classified intent")

    retrieval_method: Optional[str] = Field(description="The chosen retrieval strategy")
    retrieval_selection: Optional[dict] = Field(
        description="The chosen retrieval methods and weights"
    )

    transformed_query: Optional[str] = Field(
        description="The transformed query for retrieval"
    )
    documents: Optional[List[str]] = Field(description="The retrieved documents")

    answer: Optional[str] = Field(description="The final generated answer")
    validation: Optional[dict] = Field(description="The validation result")
    entities: Optional[List[str]] = Field(
        description="Extracted entities from the query"
    )

    error: Optional[str] = Field(
        description="Any error that occurred during the workflow"
    )
