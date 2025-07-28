"""
Query transformation configurations for the NEFAC chatbot system.
"""

from typing import Annotated

from pydantic import BaseModel, Field

import src.config.models as models_module
import src.config.node_names as node_names_module
import src.config.prompts as prompts_module


class QueryTransformerConfig(BaseModel):
    """Configuration for core query transformation strategies."""

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


class ContextualStrategyConfig(BaseModel):
    """Configuration for contextual strategy query transformation."""

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


class DecompositionStrategyConfig(BaseModel):
    """Configuration for decomposition strategy query transformation."""

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


class FactualStrategyConfig(BaseModel):
    """Configuration for factual strategy query transformation."""

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


class HydeStrategyConfig(BaseModel):
    """Configuration for HyDE (Hypothetical Document Embeddings) strategy."""

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


class MultiQueryStrategyConfig(BaseModel):
    """Configuration for multi-query strategy."""

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


class StepBackStrategyConfig(BaseModel):
    """Configuration for step-back strategy."""

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
