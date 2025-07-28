"""
Settings module for NEFAC chatbot configuration.

This module provides organized configuration classes for different
aspects of the NEFAC chatbot system.
"""

from src.config.settings.base import MCPConfig, SearchAPI
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

from .configuration import Configuration

__all__ = [
    "SearchAPI",
    "MCPConfig",
    "SupervisorConfig",
    "QueryTransformerConfig",
    "ContextualStrategyConfig",
    "DecompositionStrategyConfig",
    "FactualStrategyConfig",
    "HydeStrategyConfig",
    "MultiQueryStrategyConfig",
    "StepBackStrategyConfig",
    "RetrievalConfig",
    "CoreModelsConfig",
    "SystemPromptsConfig",
    "ResearchConfig",
    "ResearchModelsConfig",
    "Configuration",
]
