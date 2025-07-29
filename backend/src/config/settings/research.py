"""
Research configurations for the NEFAC chatbot system.
"""

from typing import Annotated

from pydantic import BaseModel, Field

import src.config.models as models_module
import src.config.node_names as node_names_module
import src.config.prompts as prompts_module
from src.config.settings.base import SearchAPI


class ResearchConfig(BaseModel):
    """Configuration for research functionality."""

    max_structured_output_retries: int = Field(default=3, metadata={"x_oap_ui_config": {"type": "number", "default": 3, "min": 1, "max": 10, "description": "Maximum number of retries for structured output calls from models"}})
    allow_clarification: bool = Field(default=True, metadata={"x_oap_ui_config": {"type": "boolean", "default": True, "description": "Whether to allow the researcher to ask the user clarifying questions before starting research"}})
    max_concurrent_research_units: int = Field(
        default=5,
        metadata={
            "x_oap_ui_config": {
                "type": "slider",
                "default": 5,
                "min": 1,
                "max": 20,
                "step": 1,
                "description": "Maximum number of research units to run concurrently. This will allow the researcher to use multiple sub-agents to conduct research. Note: with more concurrency, you may run into rate limits.",
            }
        },
    )

    search_api: SearchAPI = Field(
        default=SearchAPI.TAVILY,
        metadata={
            "x_oap_ui_config": {
                "type": "select",
                "default": "tavily",
                "description": "Search API to use for research. NOTE: Make sure your Researcher Model supports the selected search API.",
                "options": [{"label": "Tavily", "value": SearchAPI.TAVILY.value}, {"label": "OpenAI Native Web Search", "value": SearchAPI.OPENAI.value}, {"label": "Anthropic Native Web Search", "value": SearchAPI.ANTHROPIC.value}, {"label": "None", "value": SearchAPI.NONE.value}],
            }
        },
    )
    max_researcher_iterations: int = Field(
        default=3,
        metadata={"x_oap_ui_config": {"type": "slider", "default": 3, "min": 1, "max": 10, "step": 1, "description": "Maximum number of research iterations for the Research Supervisor. This is the number of times the Research Supervisor will reflect on the research and ask follow-up questions."}},
    )
    max_react_tool_calls: int = Field(default=5, metadata={"x_oap_ui_config": {"type": "slider", "default": 5, "min": 1, "max": 30, "step": 1, "description": "Maximum number of tool calling iterations to make in a single researcher step."}})


class ResearchModelsConfig(BaseModel):
    """Configuration for research models and prompts."""

    clarify_with_user_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_CLARIFY_WITH_USER_MODEL,
        description="Model for clarifying user questions before research.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_CLARIFY_WITH_USER],
            "langgraph_type": "model",
        },
    )

    clarify_with_user_instructions: str = Field(
        default=prompts_module.DEFAULT_CLARIFY_WITH_USER_INSTRUCTIONS,
        description="Instructions for clarifying user queries before research.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_CLARIFY_WITH_USER],
            "langgraph_type": "prompt",
        },
    )

    transform_messages_into_research_topic_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_TRANSFORM_MESSAGES_INTO_RESEARCH_TOPIC_MODEL,
        description="Model for transforming conversation messages into research topics.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_WRITE_RESEARCH_BRIEF],
            "langgraph_type": "model",
        },
    )

    transform_messages_into_research_topic_prompt: str = Field(
        default=prompts_module.DEFAULT_TRANSFORM_MESSAGES_INTO_RESEARCH_TOPIC_PROMPT,
        description="Prompt for transforming conversation messages into research topics.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_WRITE_RESEARCH_BRIEF],
            "langgraph_type": "prompt",
        },
    )

    compress_research_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_COMPRESS_RESEARCH_MODEL,
        description="Model for compressing research topics into concise summaries.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_COMPRESS_RESEARCH],
            "langgraph_type": "model",
        },
    )

    compress_research_system_prompt: str = Field(
        default=prompts_module.DEFAULT_COMPRESS_RESEARCH_SYSTEM_PROMPT,
        description="Prompt for compressing and cleaning research findings.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_COMPRESS_RESEARCH],
            "langgraph_type": "prompt",
        },
    )

    compress_research_simple_human_message: str = Field(
        default=prompts_module.DEFAULT_COMPRESS_RESEARCH_SIMPLE_HUMAN_MESSAGE,
        description="Simple human message for research compression.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_COMPRESS_RESEARCH],
            "langgraph_type": "prompt",
        },
    )

    final_report_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_FINAL_REPORT_MODEL,
        description="Model for generating the final research report.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_FINAL_REPORT_GENERATION],
            "langgraph_type": "model",
        },
    )
