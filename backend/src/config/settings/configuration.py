import os
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

import src.config.models as models_module
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
from src.config.settings.quick_agent import QuickAgentConfig
from src.config.settings.research import ResearchConfig, ResearchModelsConfig
from src.config.settings.retrieval import RetrievalConfig
from src.config.settings.supervisor import SupervisorConfig
from src.config.settings.system_prompts import SystemPromptsConfig


class Configuration(
    SupervisorConfig,
    QueryTransformerConfig,
    ContextualStrategyConfig,
    DecompositionStrategyConfig,
    FactualStrategyConfig,
    HydeStrategyConfig,
    MultiQueryStrategyConfig,
    StepBackStrategyConfig,
    RetrievalConfig,
    CoreModelsConfig,
    SystemPromptsConfig,
    ResearchConfig,
    ResearchModelsConfig,
    QuickAgentConfig,
    BaseModel,
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
    research_mode: Literal["deep", "quick"] = Field(default="deep", description="The research mode to use: 'deep' for comprehensive research, 'quick' for fast answers.", metadata={"x_oap_ui_config": {"type": "select", "options": ["deep", "quick"], "label": "Research Mode"}})
    enable_graph_search: bool = Field(default=False, description="Enable or disable graph-based retrieval.", metadata={"x_oap_ui_config": {"type": "boolean", "label": "Enable Graph Search"}})

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig | None = None) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())

        # Build a suffix->full mapping for supported model names
        try:
            _suffix_to_full = {m.split(":", 1)[1]: m for m in getattr(models_module, "SUPPORTED_MODELS", []) if ":" in m}
        except Exception:
            _suffix_to_full = {}

        def _normalize_model(value: Any) -> Any:
            if not isinstance(value, str):
                return value
            if ":" in value:
                return value
            # Try exact suffix match first
            if value in _suffix_to_full:
                return _suffix_to_full[value]
            # Heuristic provider prefix based on common patterns
            if value.startswith("gpt-"):
                return f"openai:{value}"
            if value.startswith("claude-"):
                return f"anthropic:{value}"
            return value

        values: dict[str, Any] = {}
        for field_name in field_names:
            raw = os.environ.get(field_name.upper(), configurable.get(field_name))
            # Normalize any *_model fields to provider-prefixed values
            if isinstance(raw, str) and field_name.endswith("_model"):
                raw = _normalize_model(raw)
            values[field_name] = raw

        # Filter out None values to allow Pydantic defaults to work
        filtered_values = {k: v for k, v in values.items() if v is not None}
        return cls(**filtered_values)

    class Config:
        arbitrary_types_allowed = True
