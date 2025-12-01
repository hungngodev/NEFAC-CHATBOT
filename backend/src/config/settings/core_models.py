"""
Core models configuration for the NEFAC chatbot system.
"""

from typing import Annotated, Any

from pydantic import BaseModel, Field

import src.config.models as models_module
import src.config.node_names as node_names_module


class CoreModelsConfig(BaseModel):
    """Configuration for core model settings."""

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

    summarization_model_max_tokens: int = Field(
        default=512,
        description="Maximum generation tokens for the summarization model.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.MEMORY_SUMMARIZER_NODE],
            "langgraph_type": "number",
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

    model_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional model configuration parameters.",
    )

    # Global switch to disable model streaming; models should not stream
    # and callers should not pass stream flags on invoke/ainvoke.
    disable_streaming: bool = Field(
        default=False,
        description="Disable streaming at the model level; all LLM invocations are non-streaming.",
        json_schema_extra={"langgraph_type": "boolean"},
    )
