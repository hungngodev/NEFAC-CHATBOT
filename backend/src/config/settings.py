"""
Centralized configuration for the NEFAC chatbot application.

This module defines a unified Configuration class that works with both
LangGraph Studio and the existing workflow system, providing a structured
and type-safe way to handle settings with proper validation.

The Configuration class manages all prompts, models, and node-specific
configurations in a single, cohesive system.
"""

import os
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

import backend.src.config.models as models_module  # For introspection
import backend.src.config.node_names as node_names_module  # For introspection
import backend.src.config.prompts as prompts_module  # For introspection


class SearchAPI(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    TAVILY = "tavily"
    NONE = "none"


class MCPConfig(BaseModel):
    url: Optional[str] = Field(
        default=None,
        optional=True,
    )
    """The URL of the MCP server"""
    tools: Optional[List[str]] = Field(
        default=None,
        optional=True,
    )
    """The tools to make available to the LLM"""
    auth_required: Optional[bool] = Field(
        default=False,
        optional=True,
    )
    """Whether the MCP server requires authentication"""


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
        default=prompts_module.FINAL_PROMPT,
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
    # RESEARCHER METHODS
    # ========================================================================
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
    # Research Configuration
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
    # Model Configuration
    summarization_model: str = Field(default="openai:gpt-4.1-nano", metadata={"x_oap_ui_config": {"type": "text", "default": "openai:gpt-4.1-nano", "description": "Model for summarizing research results from Tavily search results"}})
    summarization_model_max_tokens: int = Field(default=8192, metadata={"x_oap_ui_config": {"type": "number", "default": 8192, "description": "Maximum output tokens for summarization model"}})
    research_model: str = Field(default="openai:gpt-4.1", metadata={"x_oap_ui_config": {"type": "text", "default": "openai:gpt-4.1", "description": "Model for conducting research. NOTE: Make sure your Researcher Model supports the selected search API."}})
    research_model_max_tokens: int = Field(default=10000, metadata={"x_oap_ui_config": {"type": "number", "default": 10000, "description": "Maximum output tokens for research model"}})
    compression_model: str = Field(default="openai:gpt-4.1-mini", metadata={"x_oap_ui_config": {"type": "text", "default": "openai:gpt-4.1-mini", "description": "Model for compressing research findings from sub-agents. NOTE: Make sure your Compression Model supports the selected search API."}})
    compression_model_max_tokens: int = Field(default=8192, metadata={"x_oap_ui_config": {"type": "number", "default": 8192, "description": "Maximum output tokens for compression model"}})
    final_report_model: str = Field(default="openai:gpt-4.1", metadata={"x_oap_ui_config": {"type": "text", "default": "openai:gpt-4.1", "description": "Model for writing the final report from all research findings"}})
    final_report_model_max_tokens: int = Field(default=10000, metadata={"x_oap_ui_config": {"type": "number", "default": 10000, "description": "Maximum output tokens for final report model"}})

    # Research Agent Prompts
    # ========================================================================
    clarify_with_user_prompt: str = Field(
        default=prompts_module.DEFAULT_CLARIFY_WITH_USER_INSTRUCTIONS,
        description="Prompt for the clarification agent to determine if user clarification is needed before research.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_CLARIFY_WITH_USER],
            "langgraph_type": "prompt",
        },
    )

    transform_messages_into_research_topic_prompt: str = Field(
        default=prompts_module.DEFAULT_TRANSFORM_MESSAGES_INTO_RESEARCH_TOPIC_PROMPT,
        description="Prompt for transforming conversation messages into a research topic.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_WRITE_RESEARCH_BRIEF],
            "langgraph_type": "prompt",
        },
    )

    lead_researcher_prompt: str = Field(
        default=prompts_module.DEFAULT_LEAD_RESEARCHER_PROMPT,
        description="Prompt for the lead researcher supervisor agent.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_SUPERVISOR],
            "langgraph_type": "prompt",
        },
    )

    research_system_prompt: str = Field(
        default=prompts_module.DEFAULT_RESEARCH_SYSTEM_PROMPT,
        description="System prompt for individual research agents.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_RESEARCHER],
            "langgraph_type": "prompt",
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

    final_report_generation_prompt: str = Field(
        default=prompts_module.DEFAULT_FINAL_REPORT_GENERATION_PROMPT,
        description="Prompt for generating the final research report.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_FINAL_REPORT_GENERATION],
            "langgraph_type": "prompt",
        },
    )

    summarize_webpage_prompt: str = Field(
        default=prompts_module.DEFAULT_SUMMARIZE_WEBPAGE_PROMPT,
        description="Prompt for summarizing webpage content during research.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_RESEARCHER_TOOLS],
            "langgraph_type": "prompt",
        },
    )

    # MCP server configuration
    mcp_config: Optional[MCPConfig] = Field(default=None, optional=True, metadata={"x_oap_ui_config": {"type": "mcp", "description": "MCP server configuration"}})
    mcp_prompt: Optional[str] = Field(default=None, optional=True, metadata={"x_oap_ui_config": {"type": "text", "description": "Any additional instructions to pass along to the Agent regarding the MCP tools that are available to it."}})

    @classmethod
    def from_runnable_config(cls, config: Optional[RunnableConfig] = None) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())
        values: dict[str, Any] = {field_name: os.environ.get(field_name.upper(), configurable.get(field_name)) for field_name in field_names}
        return cls(**{k: v for k, v in values.items() if v is not None})

    class Config:
        arbitrary_types_allowed = True
