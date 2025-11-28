"""
Centralized model configurations for the NEFAC chatbot application.

This module defines all model configurations used across different nodes
in the LangGraph-based agent system, ensuring consistency and maintainability.
"""

from typing import Literal

# ============================================================================
# MODEL TYPES AND CONSTANTS
# ============================================================================

# Available model providers and their models
EMBEEDING_MODEL_NAME = "text-embedding-3-small"
EMBEEDING_DIMENSIONS = 1536

# Model type annotation for LangGraph Studio
ModelType = Literal[
    "openai:gpt-4o",
    "openai:gpt-4o-mini",
    "openai:gpt-4-turbo",
    "openai:gpt-3.5-turbo",
    "openai:gpt-5",
    "openai:gpt-5-mini",
    "openai:gpt-5-nano",
    "anthropic:claude-3-5-sonnet-20241022",
    "anthropic:claude-3-5-haiku-20241022",
    "anthropic:claude-3-opus-20240229",
]
# ============================================================================
# NODE-SPECIFIC MODEL CONFIGURATIONS
# ============================================================================

# Generator and validation models (high-quality required)
DEFAULT_GENERATOR_MODEL = "openai:gpt-5-mini"
DEFAULT_VALIDATION_MODEL = "openai:gpt-5-mini"

# Summarization model
DEFAULT_SUMMARIZATION_MODEL = "openai:gpt-5-nano"


DEFAULT_RETRIEVER_WORKER_MODEL = "openai:gpt-4o-mini"


DEFAULT_QUERY_TRANSFORMER_MODEL = "openai:gpt-4o"
DEFAULT_CONTEXTUAL_STRATEGY_MODEL = "openai:gpt-4o"
DEFAULT_DECOMPOSITION_GENERATE_MODEL = "openai:gpt-4o"
DEFAULT_DECOMPOSITION_ANSWER_MODEL = "openai:gpt-4o"
DEFAULT_DECOMPOSITION_FINAL_MODEL = "openai:gpt-4o"
DEFAULT_FACTUAL_STRATEGY_MODEL = "openai:gpt-4o"
DEFAULT_HYDE_MODEL = "openai:gpt-4o"
DEFAULT_HYDE_FINAL_MODEL = "openai:gpt-4o"
DEFAULT_MULTI_QUERY_MODEL = "openai:gpt-4o"
DEFAULT_STEP_BACK_GENERATE_MODEL = "openai:gpt-4o"
DEFAULT_STEP_BACK_RESPONSE_MODEL = "openai:gpt-4o"

DEFAULT_CLARIFY_WITH_USER_MODEL = "openai:gpt-5-nano"
DEFAULT_TRANSFORM_MESSAGES_INTO_RESEARCH_TOPIC_MODEL = "openai:gpt-5"
DEFAULT_COMPRESS_RESEARCH_MODEL = "openai:gpt-5-mini"
DEFAULT_SUPERVISOR_MODEL = "openai:gpt-5"
DEFAULT_RESEARCH_MODEL = "openai:gpt-5"
DEFAULT_FINAL_REPORT_MODEL = "openai:gpt-5"

# ============================================================================
# EMBEDDING MODEL CONFIGURATIONS
# ============================================================================

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
