"""
System prompts configuration for the NEFAC chatbot system.
"""

from pydantic import BaseModel, Field

import src.config.node_names as node_names_module
import src.config.prompts as prompts_module


class SystemPromptsConfig(BaseModel):
    """Configuration for system prompts."""

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

    # Navigator/Librarian Mode Prompts
    navigator_system_prompt: str = Field(
        default=prompts_module.DEFAULT_NAVIGATOR_SYSTEM_PROMPT,
        description="System prompt for librarian mode - navigates to resources instead of generating answers.",
        json_schema_extra={
            "langgraph_type": "prompt",
            "x_oap_ui_config": {"type": "textarea", "label": "Navigator System Prompt"},
        },
    )

    format_navigation_prompt: str = Field(
        default=prompts_module.DEFAULT_FORMAT_NAVIGATION_PROMPT,
        description="Prompt for formatting navigation findings into resource cards.",
        json_schema_extra={
            "langgraph_type": "prompt",
            "x_oap_ui_config": {"type": "textarea", "label": "Format Navigation Prompt"},
        },
    )

    navigation_guide_prompt: str = Field(
        default=prompts_module.DEFAULT_NAVIGATION_GUIDE_PROMPT,
        description="Prompt for generating the final navigation guide output.",
        json_schema_extra={
            "langgraph_type": "prompt",
            "x_oap_ui_config": {"type": "textarea", "label": "Navigation Guide Prompt"},
        },
    )

    navigator_clarify_prompt: str = Field(
        default=prompts_module.DEFAULT_NAVIGATOR_CLARIFY_PROMPT,
        description="Prompt for clarifying user intent in librarian mode.",
        json_schema_extra={
            "langgraph_type": "prompt",
            "x_oap_ui_config": {"type": "textarea", "label": "Navigator Clarify Prompt"},
        },
    )
