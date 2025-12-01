from typing import Annotated, Any

from pydantic import BaseModel, Field, model_validator

import src.config.models as models_module


class QuickAgentConfig(BaseModel):
    """Configuration for the Quick Agent."""

    quick_agent_model: Annotated[
        models_module.ModelType,
        Field(
            description="The model to use for the Quick Agent.",
            metadata={"x_oap_ui_config": {"type": "model_select", "label": "Quick Agent Model"}},
        ),
    ] = models_module.DEFAULT_QUICK_AGENT_MODEL

    quick_agent_system_prompt: str = Field(
        default=models_module.DEFAULT_QUICK_AGENT_SYSTEM_PROMPT,
        description="The system prompt for the Quick Agent.",
        metadata={"x_oap_ui_config": {"type": "prompt_editor", "label": "Quick Agent System Prompt"}},
    )

    @model_validator(mode="before")
    @classmethod
    def set_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("quick_agent_system_prompt") is None:
                data["quick_agent_system_prompt"] = models_module.DEFAULT_QUICK_AGENT_SYSTEM_PROMPT
        return data
