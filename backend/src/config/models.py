"""
Centralized model configurations for the NEFAC chatbot application.

This module defines all model configurations used across different nodes
in the LangGraph-based agent system, ensuring consistency and maintainability.
"""

from typing import Literal

EMBEDDING_MODEL_NAME = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

SERVICE_TIER: Literal["flex", "default", "auto", "priority"] = "flex"
ENABLE_STREAMING: bool = True
DEFAULT_MAX_RETRIES: int = 5

ModelType = Literal[
    "openai:gpt-4o",
    "openai:gpt-4o-mini",
    "openai:gpt-4-turbo",
    "openai:gpt-3.5-turbo",
    "openai:gpt-5.1",
    "openai:gpt-5",
    "openai:gpt-5-mini",
    "openai:gpt-5-nano",
    "anthropic:claude-3-5-sonnet-20241022",
    "anthropic:claude-3-5-haiku-20241022",
    "anthropic:claude-3-opus-20240229",
]
DEFAULT_SUMMARIZATION_MODEL: ModelType = "openai:gpt-5-nano"
DEFAULT_RETRIEVER_WORKER_MODEL: ModelType = "openai:gpt-5-nano"

DEFAULT_RETRIEVAL_PLANNER_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_QUERY_TRANSFORMER_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_CONTEXTUAL_STRATEGY_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_DECOMPOSITION_GENERATE_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_DECOMPOSITION_ANSWER_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_DECOMPOSITION_FINAL_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_FACTUAL_STRATEGY_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_HYDE_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_HYDE_FINAL_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_MULTI_QUERY_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_STEP_BACK_GENERATE_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_STEP_BACK_RESPONSE_MODEL: ModelType = "openai:gpt-5-mini"

DEFAULT_CLARIFY_WITH_USER_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_TRANSFORM_MESSAGES_INTO_RESEARCH_TOPIC_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_COMPRESS_RESEARCH_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_SUPERVISOR_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_RESEARCH_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_FINAL_REPORT_MODEL: ModelType = "openai:gpt-5-mini"
DEFAULT_QUICK_AGENT_MODEL: ModelType = "openai:gpt-5-mini"
