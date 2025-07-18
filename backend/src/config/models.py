"""
Centralized model configurations for the NEFAC chatbot application.

This module defines all model configurations used across different nodes
in the LangGraph-based agent system, ensuring consistency and maintainability.
"""

import os
from typing import Literal

# ============================================================================
# MODEL TYPES AND CONSTANTS
# ============================================================================

# Available model providers and their models
OPENAI_MODELS = [
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/gpt-4-turbo",
    "openai/gpt-3.5-turbo",
]

ANTHROPIC_MODELS = [
    "anthropic/claude-3-5-sonnet-20241022",
    "anthropic/claude-3-5-haiku-20241022",
    "anthropic/claude-3-opus-20240229",
]

ALL_MODELS = OPENAI_MODELS + ANTHROPIC_MODELS

# Supported models (alias for backward compatibility)
SUPPORTED_MODELS = ALL_MODELS

# Model type annotation for LangGraph Studio
ModelType = Literal[
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/gpt-4-turbo",
    "openai/gpt-3.5-turbo",
    "anthropic/claude-3-5-sonnet-20241022",
    "anthropic/claude-3-5-haiku-20241022",
    "anthropic/claude-3-opus-20240229",
]

# ============================================================================
# DEFAULT MODEL CONFIGURATIONS
# ============================================================================

# Environment variable defaults
DEFAULT_MODEL_PROVIDER = os.getenv("DEFAULT_MODEL_PROVIDER", "openai")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4")
DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.0"))

# ============================================================================
# NODE-SPECIFIC MODEL CONFIGURATIONS
# ============================================================================

# Generator and validation models (high-quality required)
DEFAULT_GENERATOR_MODEL = "openai/gpt-4o"
DEFAULT_VALIDATION_MODEL = "openai/gpt-4o-mini"

# Summarization model
DEFAULT_SUMMARIZATION_MODEL = "openai/gpt-4o"

# Contextualization and analysis models (speed and efficiency)
DEFAULT_CONTEXTUALIZE_MODEL = "openai/gpt-4o-mini"
DEFAULT_COMPLEXITY_ANALYSIS_MODEL = "openai/gpt-4o-mini"
DEFAULT_INTENT_CLASSIFICATION_MODEL = "openai/gpt-4o-mini"

# Reasoning models (high-quality reasoning required)
DEFAULT_REACT_WORKER_MODEL = "openai/gpt-4o"
DEFAULT_REASONING_MODEL = "openai/gpt-4o"

# Retrieval and query translation models (efficiency focused)
DEFAULT_RETRIEVER_WORKER_MODEL = "openai/gpt-4o-mini"


DEFAULT_QUERY_TRANSFORMER_MODEL = "openai/gpt-4o-mini"
DEFAULT_CONTEXTUAL_STRATEGY_MODEL = "openai/gpt-4o-mini"
DEFAULT_DECOMPOSITION_GENERATE_MODEL = "openai/gpt-4o-mini"
DEFAULT_DECOMPOSITION_ANSWER_MODEL = "openai/gpt-4o-mini"
DEFAULT_DECOMPOSITION_FINAL_MODEL = "openai/gpt-4o-mini"
DEFAULT_FACTUAL_STRATEGY_MODEL = "openai/gpt-4o-mini"
DEFAULT_HYDE_MODEL = "openai/gpt-4o-mini"
DEFAULT_HYDE_FINAL_MODEL = "openai/gpt-4o-mini"
DEFAULT_MULTI_QUERY_MODEL = "openai/gpt-4o-mini"
DEFAULT_STEP_BACK_GENERATE_MODEL = "openai/gpt-4o-mini"
DEFAULT_STEP_BACK_RESPONSE_MODEL = "openai/gpt-4o-mini"

# ============================================================================
# EMBEDDING MODEL CONFIGURATIONS
# ============================================================================

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
