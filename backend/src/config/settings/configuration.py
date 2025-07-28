import os
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from src.config.settings.base import MCPConfig
from src.config.settings.core_models import CoreModelsConfig
from src.config.settings.query_transformation import (
    ContextualStrategyConfig,
    DecompositionStrategyConfig,
    FactualStrategyConfig,
    HydeStrategyConfig,
    MultiQueryStrategyConfig,
    QueryTransformerConfig,
    StepBackStrategyConfig,
)
from src.config.settings.research import ResearchConfig, ResearchModelsConfig
from src.config.settings.retrieval import RetrievalConfig
from src.config.settings.supervisor import SupervisorConfig
from src.config.settings.system_prompts import SystemPromptsConfig


class Configuration(
    SupervisorConfig, QueryTransformerConfig, ContextualStrategyConfig, DecompositionStrategyConfig, FactualStrategyConfig, HydeStrategyConfig, MultiQueryStrategyConfig, StepBackStrategyConfig, RetrievalConfig, CoreModelsConfig, SystemPromptsConfig, ResearchConfig, ResearchModelsConfig, BaseModel
):
    """
    Unified configuration for the NEFAC chatbot application.

    This single configuration class works with both LangGraph Studio (for prompt editing)
    and the existing workflow system. It provides centralized access to all node
    configurations with proper validation and type safety.

    Inherits from multiple specialized configuration classes for better organization.
    """

    # MCP server configuration
    mcp_config: MCPConfig | None = Field(default=None, optional=True, metadata={"x_oap_ui_config": {"type": "mcp", "description": "MCP server configuration"}})
    mcp_prompt: str | None = Field(default=None, optional=True, metadata={"x_oap_ui_config": {"type": "text", "description": "Any additional instructions to pass along to the Agent regarding the MCP tools that are available to it."}})

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig | None = None) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())
        values: dict[str, Any] = {field_name: os.environ.get(field_name.upper(), configurable.get(field_name)) for field_name in field_names}
        return cls(**{k: v for k, v in values.items() if v is not None})

    class Config:
        arbitrary_types_allowed = True
