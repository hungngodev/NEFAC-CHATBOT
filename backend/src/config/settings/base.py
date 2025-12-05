"""
Base configuration types and enums for the NEFAC chatbot system.
"""

from enum import Enum

from pydantic import BaseModel, Field


class SearchAPI(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    TAVILY = "tavily"
    NONE = "none"


class MCPConfig(BaseModel):
    url: str | None = Field(
        default=None,
    )
    """The URL of the MCP server"""
    tools: list[str | None] | None = Field(
        default=None,
    )
    """The tools to make available to the LLM"""
    auth_required: bool | None = Field(
        default=False,
    )
    """Whether the MCP server requires authentication"""
