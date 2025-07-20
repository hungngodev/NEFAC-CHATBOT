from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from operator import add
from typing import Annotated, Any, ClassVar, Generic, Literal, TypedDict, TypeVar

from langchain_core.documents import Document
from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class AgentState(MessagesState):
    """
    Unified state for the hierarchical multi-agent system.
    This is the single source of truth that flows through all nodes.
    """

    summarized_messages: list[AnyMessage]

    # Core conversation fields
    user_query: str = Field(description="Current user query")
    # Contextualizer
    contextualized_query: str | None = Field(default=None, description="Standalone query with context")

    final_documents: Annotated[list[Document], add] = Field(default_factory=list, description="Final list of retrieved documents")
    final_context: str | None = Field(default=None, description="Final formatted context from all retrievals")
    # Final answer
    final_answer: str | None = Field(default=None, description="Generated final answer")
    # Error handling
    error: str | None = Field(default=None, description="Error message if any")
