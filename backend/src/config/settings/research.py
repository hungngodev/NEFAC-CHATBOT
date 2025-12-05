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

    max_structured_output_retries: int = Field(default=3, json_schema_extra={"x_oap_ui_config": {"type": "number", "default": 3, "min": 1, "max": 10, "description": "Maximum number of retries for structured output calls from models"}})
    allow_clarification: bool = Field(default=True, json_schema_extra={"x_oap_ui_config": {"type": "boolean", "default": True, "description": "Whether to allow the researcher to ask the user clarifying questions before starting research"}})
    max_concurrent_research_units: int = Field(
        default=3,
        json_schema_extra={
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
        json_schema_extra={
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
        json_schema_extra={
            "x_oap_ui_config": {"type": "slider", "default": 3, "min": 1, "max": 10, "step": 1, "description": "Maximum number of research iterations for the Research Supervisor. This is the number of times the Research Supervisor will reflect on the research and ask follow-up questions."}
        },
    )
    max_react_tool_calls: int = Field(default=3, json_schema_extra={"x_oap_ui_config": {"type": "slider", "default": 3, "min": 1, "max": 30, "step": 1, "description": "Maximum number of tool calling iterations to make in a single researcher step."}})

    # Hard limit on how many InternalDocumentSearch calls are processed per iteration.
    # Additional calls in the same assistant message will be deferred with a ToolMessage.
    max_internal_search_calls_per_turn: int = Field(
        default=2,
        json_schema_extra={
            "x_oap_ui_config": {
                "type": "slider",
                "default": 2,
                "min": 1,
                "max": 10,
                "step": 1,
                "description": "Maximum number of InternalDocumentSearch calls to process per researcher iteration.",
            }
        },
    )

    # Graph recursion limit for LangGraph runloops (prevents infinite bouncing)
    graph_recursion_limit: int = Field(
        default=60,
        json_schema_extra={
            "x_oap_ui_config": {
                "type": "slider",
                "default": 60,
                "min": 10,
                "max": 200,
                "step": 5,
                "description": "Maximum recursion depth for graph execution before aborting (LangGraph recursion_limit).",
            }
        },
    )


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

    # Alias commonly used in code
    clarify_with_user_prompt: str = Field(
        default=prompts_module.DEFAULT_CLARIFY_WITH_USER_INSTRUCTIONS,
        description="Prompt for clarifying user queries before research (alias of instructions).",
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

    research_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_RESEARCH_MODEL,
        description="Model for the main researcher agent.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_RESEARCHER],
            "langgraph_type": "model",
        },
    )

    research_system_prompt: str = Field(
        default=prompts_module.DEFAULT_RESEARCH_SYSTEM_PROMPT,
        description="System prompt for the main researcher agent.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_RESEARCHER],
            "langgraph_type": "prompt",
        },
    )

    lead_researcher_prompt: str = Field(
        default=prompts_module.DEFAULT_LEAD_RESEARCHER_PROMPT,
        description="Prompt given to the supervisor/lead researcher to coordinate research.",
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

    # === Max token budgets ===
    research_model_max_tokens: int = Field(
        default=1024,
        description="Maximum generation tokens for research-oriented model calls (also used for clarify step).",
    )
    compression_model_max_tokens: int = Field(
        default=1024,
        description="Maximum generation tokens for the research compression model.",
    )
    final_report_model_max_tokens: int = Field(
        default=2048,
        description="Maximum generation tokens for the final report generation model.",
    )

    # === Additional prompts used in research workflow ===
    final_report_generation_prompt: str = Field(
        default=prompts_module.DEFAULT_FINAL_REPORT_GENERATION_PROMPT,
        description="Prompt template for generating the final report from collected notes and brief.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_FINAL_REPORT_GENERATION],
            "langgraph_type": "prompt",
        },
    )

    summarize_webpage_prompt: str = Field(
        default=prompts_module.DEFAULT_SUMMARIZE_WEBPAGE_PROMPT,
        description="Prompt template for summarizing raw webpage content from external search results.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_RESEARCHER],
            "langgraph_type": "prompt",
        },
    )
