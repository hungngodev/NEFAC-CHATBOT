from typing import ClassVar, Literal

from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from backend.src.config.node_names import INTENT_CLASSIFICATION_NODE
from backend.src.config.settings import Configuration
from backend.src.schemas.core_types import AgentState


class IntentClassification(BaseModel):
    """Enhanced intent classification"""

    model_config: ClassVar[ConfigDict] = ConfigDict(use_enum_values=True)
    intent: Literal["info", "general"] = Field(description="Classify the user's intent. If they are asking for information that could be found in NEFAC's documents, classify as 'info'. Otherwise, classify as 'general'.")


def intent_classification_node(state: AgentState, config: RunnableConfig) -> IntentClassification:
    """
    Classify the user's intent based on the query.
    Uses a language model to classify the intent.

    This function uses RunnableConfig for LangGraph Studio compatibility.
    """
    # Get configuration from RunnableConfig
    configuration = Configuration.from_runnable_config(config)

    model = init_chat_model(configuration.intent_classification_model)

    # Use prompt from configuration (LangGraph Studio compatible)
    intent_prompt = configuration.intent_classification_prompt

    main_chain = ChatPromptTemplate.from_messages(
        [
            ("system", intent_prompt),
            ("human", "{query}"),
        ]
    ).with_config(
        tags=[INTENT_CLASSIFICATION_NODE]
    ) | model.with_structured_output(IntentClassification)

    return main_chain.invoke(
        {
            "query": state["user_query"],
        }
    )
