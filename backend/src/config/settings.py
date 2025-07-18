"""
Centralized configuration for the NEFAC chatbot application.

This module defines a unified Configuration class that works with both
LangGraph Studio and the existing workflow system, providing a structured
and type-safe way to handle settings with proper validation.

The Configuration class manages all prompts, models, and node-specific
configurations in a single, cohesive system.
"""

import logging
from typing import Annotated, Any, Dict, Optional

from pydantic import BaseModel, Field

import backend.src.config.models as models_module  # For introspection
import backend.src.config.node_names as node_names_module  # For introspection
import backend.src.config.prompts as prompts_module  # For introspection

logger = logging.getLogger(__name__)

DEFAULT_GENERATION_PROMPT = prompts_module.FINAL_PROMPT


class Configuration(BaseModel):
    """
    Unified configuration for the NEFAC chatbot application.

    This single configuration class works with both LangGraph Studio (for prompt editing)
    and the existing workflow system. It provides centralized access to all node
    configurations with proper validation and type safety.
    """

    query_transformer_model: str = Field(
        default=models_module.DEFAULT_QUERY_TRANSFORMER_MODEL,
        description="Model for query translation and transformation tasks.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.QUERY_TRANSFORMER_NODE],
            "langgraph_type": "model",
        },
    )

    query_transformer_prompt: str = Field(
        default=prompts_module.DEFAULT_QUERY_TRANSORMER_PROMPT,
        description="Prompt for selecting the best query transformation method.",
        json_schema_extra={
            "langgraph_nodes": [
                node_names_module.QUERY_TRANSFORMER_MULTI_QUERY,
                node_names_module.QUERY_TRANSFORMER_DECOMPOSITION,
                node_names_module.QUERY_TRANSFORMER_STEP_BACK,
                node_names_module.QUERY_TRANSFORMER_HYDE,
                node_names_module.QUERY_TRANSFORMER_FACTUAL_STRATEGY,
                node_names_module.QUERY_TRANSFORMER_CONTEXTUAL_STRATEGY,
            ],
            "langgraph_type": "prompt",
        },
    )

    contextual_strategy_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_CONTEXTUAL_STRATEGY_MODEL,
        description="Model for contextualizing the query with relevant knowledge.",
        json_schema_extra={
            "langgraph_nodes": [
                node_names_module.CONTEXTUAL_STRATEGY_GENERATE_CONTEXTUAL_QUERY,
            ]
        },
    )

    contextual_strategy_prompt: str = Field(
        default=prompts_module.DEFAULT_CONTEXTUAL_STRATEGY_PROMPT,
        description="Prompt for the contextual strategy query transformation.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.CONTEXTUAL_STRATEGY_GENERATE_CONTEXTUAL_QUERY],
            "langgraph_type": "prompt",
        },
    )

    decomposition_generate_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_DECOMPOSITION_GENERATE_MODEL,
        description="Model for generating sub-questions in the decomposition strategy.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.DECOMPOSITION_GENERATE_SUB_QUESTIONS],
            "langgraph_type": "model",
        },
    )

    decomposition_answer_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_DECOMPOSITION_ANSWER_MODEL,
        description="Model for answering sub-questions in the decomposition strategy.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.DECOMPOSITION_ANSWER_SUB_QUESTIONS],
            "langgraph_type": "model",
        },
    )

    decomposition_final_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_DECOMPOSITION_FINAL_MODEL,
        description="Model for synthesizing the final answer in the decomposition strategy.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.DECOMPOSITION_SYNTHESIZE_FINAL_ANSWER],
            "langgraph_type": "model",
        },
    )

    decomposition_generate_prompt: str = Field(
        default=prompts_module.DEFAULT_DECOMPOSITION_GENERATE_PROMPT,
        description="Prompt for decomposing complex questions into sub-questions.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.DECOMPOSITION_GENERATE_SUB_QUESTIONS],
            "langgraph_type": "prompt",
        },
    )

    decomposition_qa_template: str = Field(
        default=prompts_module.DEFAULT_DECOMPOSITION_QA_TEMPLATE,
        description="Template for answering individual sub-questions in decomposition.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.DECOMPOSITION_ANSWER_SUB_QUESTIONS],
            "langgraph_type": "prompt",
        },
    )

    decomposition_synthesis_template: str = Field(
        default=prompts_module.DEFAULT_DECOMPOSITION_SYNTHESIS_TEMPLATE,
        description="Template for synthesizing final answer from decomposition sub-questions.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.DECOMPOSITION_SYNTHESIZE_FINAL_ANSWER],
            "langgraph_type": "prompt",
        },
    )

    factual_strategy_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_FACTUAL_STRATEGY_MODEL,
        description="Model for generating factual queries based on the user's question.",
        json_schema_extra={
            "langgraph_nodes": [
                node_names_module.FACTUAL_STRATEGY_GENERATE_FACTUAL_QUERY,
            ]
        },
    )

    factual_strategy_prompt: str = Field(
        default=prompts_module.DEFAULT_FACTUAL_STRATEGY_PROMPT,
        description="Prompt for the factual strategy query transformation.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.FACTUAL_STRATEGY_GENERATE_FACTUAL_QUERY],
            "langgraph_type": "prompt",
        },
    )

    hyde_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_HYDE_MODEL,
        description="Model for HyDE hypothetical document generation node.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.HYDE_GENERATE_HYPOTHETICAL_DOCUMENT],
            "langgraph_type": "model",
        },
    )

    hyde_final_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_HYDE_FINAL_MODEL,
        description="Model for HyDE final response generation node.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.HYDE_GENERATE_FINAL_RESPONSE],
            "langgraph_type": "model",
        },
    )

    hyde_generation_prompt: str = Field(
        default=prompts_module.DEFAULT_HYDE_GENERATION_PROMPT,
        description="Prompt for generating hypothetical documents for HyDE.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.HYDE_GENERATE_HYPOTHETICAL_DOCUMENT],
            "langgraph_type": "prompt",
        },
    )

    hyde_final_prompt: str = Field(
        default=prompts_module.DEFAULT_HYDE_FINAL_PROMPT,
        description="Final prompt for HyDE to generate the answer.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.HYDE_GENERATE_FINAL_RESPONSE],
            "langgraph_type": "prompt",
        },
    )

    multi_query_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_MULTI_QUERY_MODEL,
        description="Model for generating multiple queries from different perspectives.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.MULTI_QUERY_GENERATE_QUERIES],
            "langgraph_type": "model",
        },
    )

    multi_query_perspectives_prompt: str = Field(
        default=prompts_module.DEFAULT_MULTI_QUERY_PERSPECTIVES_PROMPT,
        description="Prompt for generating multiple queries from different perspectives.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.MULTI_QUERY_GENERATE_QUERIES],
            "langgraph_type": "prompt",
        },
    )

    step_back_generate_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_STEP_BACK_GENERATE_MODEL,
        description="Model for generating step-back questions.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.STEP_BACK_GENERATE_AND_DISPATCH],
            "langgraph_type": "model",
        },
    )

    step_back_response_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_STEP_BACK_RESPONSE_MODEL,
        description="Model for generating final responses in the step-back strategy.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.STEP_BACK_GENERATE_FINAL_RESPONSE],
            "langgraph_type": "model",
        },
    )

    step_back_generate_prompt: str = Field(
        default=prompts_module.DEFAULT_STEP_BACK_GENERATE_PROMPT,
        description="System prompt for the step-back query transformation.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.STEP_BACK_GENERATE_AND_DISPATCH],
            "langgraph_type": "prompt",
        },
    )

    step_back_response_prompt: str = Field(
        default=prompts_module.DEFAULT_STEP_BACK_RESPONSE_PROMPT,
        description="Response prompt for the step-back query transformation.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.STEP_BACK_GENERATE_FINAL_RESPONSE],
            "langgraph_type": "prompt",
        },
    )

    contextualize_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_CONTEXTUALIZE_MODEL,
        description="The name of the language model to use for the contextualize node.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.CONTEXTUALIZER_NODE],
            "langgraph_type": "model",
        },
    )

    contextualize_need_prompt: str = Field(
        default=prompts_module.DEFAULT_CONTEXTUALIZE_NEED_PROMPT,
        description="Prompt for determining if the user query requires contextualization based on chat history.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.CONTEXTUALIZER_NODE],
            "langgraph_type": "prompt",
        },
    )

    contextualize_prompt: str = Field(
        default=prompts_module.DEFAULT_CONTEXTUALIZE_PROMPT,
        description="Prompt for contextualizing user queries by incorporating chat history to create standalone questions.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.CONTEXTUALIZER_NODE],
            "langgraph_type": "prompt",
        },
    )

    analyze_complexity_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_COMPLEXITY_ANALYSIS_MODEL,
        description="The name of the language model to use for the analyze_complexity node.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.COMPLEXITY_ANALYZER_ANALYZE_COMPLEXITY_NODE],
            "langgraph_type": "model",
        },
    )

    complexity_analysis_prompt: str = Field(
        default=prompts_module.DEFAULT_COMPLEXITY_ANALYSIS_PROMPT,
        description="Prompt for analyzing query complexity to determine appropriate routing and processing strategies.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.COMPLEXITY_ANALYZER_ANALYZE_COMPLEXITY_NODE],
            "langgraph_type": "prompt",
        },
    )

    intent_classification_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_INTENT_CLASSIFICATION_MODEL,
        description="The name of the language model to use for the intent_classification node.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.INTENT_CLASSIFICATION_NODE],
            "langgraph_type": "model",
        },
    )

    intent_classification_prompt: str = Field(
        default=prompts_module.DEFAULT_INTENT_CLASSIFICATION_PROMPT,
        description="Prompt for classifying user intent to route queries to appropriate processing paths.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.INTENT_CLASSIFICATION_NODE],
            "langgraph_type": "prompt",
        },
    )
    # ========================================================================
    # SPECIALIZED PROMPTS
    # ========================================================================
    cypher_generation_template: str = Field(
        default=prompts_module.DEFAULT_CYPHER_GENERATION_TEMPLATE,
        description="Template for generating Cypher queries for Neo4j.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.GRAPH_RETRIEVAL_GRAPH_TOOL_NODE],
            "langgraph_type": "prompt",
        },
    )

    graph_qa_prompt: str = Field(
        default=prompts_module.DEFAULT_GRAPH_QA_PROMPT,
        description="QA prompt for answering questions using knowledge graph context.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.GRAPH_RETRIEVAL_GRAPH_TOOL_NODE],
            "langgraph_type": "prompt",
        },
    )

    sub_question_prompt: str = Field(
        default=prompts_module.DEFAULT_SUB_QUESTION_PROMPT,
        description="Prompt for generating sub-questions in multi-step reasoning.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.REASONING_MULTI_STEP_REASONING, node_names_module.REASONING_REACT_MULTI_STEP_REASONING],
            "langgraph_type": "prompt",
        },
    )

    # ========================================================================
    # MODEL CONFIGURATIONS
    # ========================================================================

    summarization_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_SUMMARIZATION_MODEL,
        description="The name of the language model to use for summarizing conversation history.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.MEMORY_SUMMARIZER_NODE],
            "langgraph_type": "model",
        },
    )

    generator_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_GENERATOR_MODEL,
        description="The name of the language model to use for the generator node.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.SUPERVISOR_GENERATOR_AGENT],
            "langgraph_type": "model",
        },
    )

    validation_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_VALIDATION_MODEL,
        description="The name of the language model to use for the validation node.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.SUPERVISOR_VALIDATION_AGENT],
            "langgraph_type": "model",
        },
    )

    react_worker_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_REACT_WORKER_MODEL,
        description="The name of the language model to use for the react_worker node.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.REASONING_REACT_MULTI_STEP_REASONING],
            "langgraph_type": "model",
        },
    )

    retriever_worker_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_RETRIEVER_WORKER_MODEL,
        description="The name of the language model to use for the retriever_worker node.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RETRIEVAL_SUBGRAPH_PLANNER, node_names_module.RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL, node_names_module.RETRIEVAL_SUBGRAPH_GRAPH_RETRIEVAL],
            "langgraph_type": "model",
        },
    )

    # ========================================================================
    # ADVANCED CONFIGURATIONS
    # ========================================================================

    temperature: float = Field(
        default=models_module.DEFAULT_TEMPERATURE,
        ge=0.0,
        le=2.0,
        description="Temperature setting for the language model (0.0 to 2.0). Lower values make responses more deterministic.",
        json_schema_extra={
            "langgraph_nodes": [
                node_names_module.SUPERVISOR_GENERATOR_AGENT,
                node_names_module.SUPERVISOR_VALIDATION_AGENT,
                node_names_module.CONTEXTUALIZER_NODE,
                node_names_module.COMPLEXITY_ANALYZER_ANALYZE_COMPLEXITY_NODE,
                node_names_module.INTENT_CLASSIFICATION_NODE,
                node_names_module.REASONING_REACT_MULTI_STEP_REASONING,
                node_names_module.RETRIEVAL_SUBGRAPH_PLANNER,
                node_names_module.RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL,
                node_names_module.RETRIEVAL_SUBGRAPH_GRAPH_RETRIEVAL,
                node_names_module.MULTI_QUERY_GENERATE_QUERIES,
                node_names_module.QUERY_TRANSFORMER_MULTI_QUERY,
                node_names_module.QUERY_TRANSFORMER_DECOMPOSITION,
                node_names_module.QUERY_TRANSFORMER_STEP_BACK,
                node_names_module.QUERY_TRANSFORMER_HYDE,
                node_names_module.QUERY_TRANSFORMER_FACTUAL_STRATEGY,
                node_names_module.QUERY_TRANSFORMER_CONTEXTUAL_STRATEGY,
                node_names_module.STEP_BACK_GENERATE_AND_DISPATCH,
                node_names_module.CONTEXTUAL_STRATEGY_GENERATE_CONTEXTUAL_QUERY,
                node_names_module.HYDE_GENERATE_HYPOTHETICAL_DOCUMENT,
                node_names_module.HYDE_GENERATE_FINAL_RESPONSE,
                node_names_module.DECOMPOSITION_GENERATE_SUB_QUESTIONS,
                node_names_module.DECOMPOSITION_ANSWER_SUB_QUESTIONS,
                node_names_module.DECOMPOSITION_FORMAT_ANSWER,
                node_names_module.DECOMPOSITION_RETRIEVE_SUBGRAPH,
                node_names_module.DECOMPOSITION_SYNTHESIZE_FINAL_ANSWER,
                node_names_module.MEMORY_SUMMARIZER_NODE,
            ]
        },
    )

    # ========================================================================
    # SPECIALIZED MODEL CONFIGURATIONS
    # ========================================================================

    reasoning_model: str = Field(
        default=models_module.DEFAULT_REASONING_MODEL,
        description="Model for complex reasoning and multi-step analysis tasks.",
        json_schema_extra={"langgraph_nodes": [node_names_module.REASONING_MULTI_STEP_REASONING, node_names_module.REASONING_REACT_MULTI_STEP_REASONING]},
    )

    embedding_model: str = Field(
        default=models_module.DEFAULT_EMBEDDING_MODEL,
        description="Model for generating embeddings for retrieval.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL, node_names_module.RETRIEVAL_SUBGRAPH_GRAPH_RETRIEVAL],
        },
    )

    # Advanced settings
    model_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional model configuration parameters.",
    )

    system_prompt: str = Field(
        default=prompts_module.BASE_PROMPT,
        description="The main system prompt for the chatbot's general interactions. This prompt sets the context and behavior for the agent.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.SUPERVISOR_GENERATOR_AGENT, node_names_module.SUPERVISOR_VALIDATION_AGENT],
            "langgraph_type": "prompt",
        },
    )

    validation_prompt: str = Field(
        default=prompts_module.DEFAULT_VALIDATION_PROMPT,
        description="Prompt for validating generated answers against the retrieved context and original question.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.SUPERVISOR_VALIDATION_AGENT],
            "langgraph_type": "prompt",
        },
    )

    synthesis_prompt: str = Field(
        default=prompts_module.DEFAULT_SYNTHESIS_PROMPT,
        description="Prompt for synthesizing information from multiple sources to create comprehensive answers.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.REASONING_MULTI_STEP_REASONING, node_names_module.REASONING_REACT_MULTI_STEP_REASONING],
            "langgraph_type": "prompt",
        },
    )

    generation_prompt: str = Field(
        default=DEFAULT_GENERATION_PROMPT,
        description="Prompt for generating final answers based on context and conversation history.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.SUPERVISOR_GENERATOR_AGENT],
            "langgraph_type": "prompt",
        },
    )

    general_prompt: str = Field(
        default=prompts_module.GENERAL_PROMPT,
        description="Prompt for general questions not requiring document retrieval.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.SUPERVISOR_GENERATOR_AGENT],
            "langgraph_type": "prompt",
        },
    )

    retrieval_planning_prompt: str = Field(
        default=prompts_module.DEFAULT_RETRIEVAL_PLANNING_PROMPT,
        description="Prompt for planning retrieval strategies based on query analysis.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RETRIEVAL_SUBGRAPH_PLANNER],
            "langgraph_type": "prompt",
        },
    )

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    @classmethod
    def from_runnable_config(
        cls,
        config: Optional[Dict[str, Any]] = None,
        default_instance: Optional["Configuration"] = None,
    ) -> "Configuration":
        """
        Create a Configuration instance from a LangGraph RunnableConfig.

        This method is compatible with LangGraph Studio's configuration pattern,
        allowing for dynamic configuration updates while maintaining backward compatibility.

        Args:
            config: Optional configuration dictionary from LangGraph RunnableConfig
            default_instance: Optional default configuration instance to use as base

        Returns:
            Configuration instance with merged settings
        """
        if config is None:
            config = {}

        # Use default instance as base if provided, otherwise use global config
        if default_instance is not None:
            base_config = default_instance.model_dump()
        else:
            base_config = get_configuration().model_dump()

        # Extract configurable parameters from the config dictionary
        configurable = config.get("configurable", {})

        # Merge with base configuration
        merged_config = {**base_config, **configurable}

        # Create new instance with merged configuration
        return cls(**merged_config)


# ========================================================================
# GLOBAL CONFIGURATION INSTANCE
# ========================================================================

# Global configuration instance - lazily initialized
_global_config: Optional[Configuration] = None


def get_configuration() -> Configuration:
    """
    Get the global configuration instance.

    This function provides a singleton pattern for accessing the global configuration,
    ensuring consistent configuration across the application.

    Returns:
        Global Configuration instance
    """
    global _global_config
    if _global_config is None:
        _global_config = Configuration()
    return _global_config
