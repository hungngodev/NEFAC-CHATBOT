"""
Supervisor configurations for the NEFAC chatbot system.
"""

from typing import Annotated

from pydantic import BaseModel, Field

import src.config.models as models_module
import src.config.node_names as node_names_module
import src.config.prompts as prompts_module


class SupervisorConfig(BaseModel):
    """Configuration for the supervisor component."""

    supervisor_model: Annotated[
        models_module.ModelType,
        {"__template_metadata__": {"kind": "llm"}},
    ] = Field(
        default=models_module.DEFAULT_SUPERVISOR_MODEL,
        description="Model for the supervisor to route queries.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_SUPERVISOR],
            "langgraph_type": "model",
        },
    )

    lead_supervisor_prompt: str = Field(
        default=prompts_module.DEFAULT_SUPERVISOR_PROMPT,
        description="Prompt given to the supervisor/lead researcher to coordinate research.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.RESEARCH_WRITE_RESEARCH_BRIEF],
            "langgraph_type": "prompt",
        },
    )
