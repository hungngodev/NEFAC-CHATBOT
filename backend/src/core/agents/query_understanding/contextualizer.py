from typing import TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableBranch, RunnableConfig
from pydantic import BaseModel, Field

from src.config.node_names import CONTEXTUALIZER_CONTEXTUALIZER_NODE
from src.config.settings import Configuration
from src.schemas.core_types import AgentState


class NeedForContextualization(BaseModel):
    """Response model for contextualization need assessment."""

    requires_contextualization: bool = Field(description="Indicates whether the user query requires contextualization based on the chat history.")


class ContextualizerNodeOutput(TypedDict):
    """
    Output type for the contextualizer node.
    Contains the contextualized query and any extracted information.
    """

    contextualized_query: str


def contextualizer_node(state: AgentState, config: RunnableConfig) -> ContextualizerNodeOutput:
    """
    Contextualizer node that uses configuration-based prompts.

    This function uses RunnableConfig for LangGraph Studio compatibility.
    """
    # Get configuration from RunnableConfig
    configuration = Configuration.from_runnable_config(config)

    model = init_chat_model(configuration.contextualize_model)

    main_chain = (
        ChatPromptTemplate.from_messages(
            [
                ("system", configuration.contextualize_need_prompt),
                ("human", "{query}"),
            ]
        )
        | model.with_structured_output(NeedForContextualization)
    ) | RunnableBranch(
        (lambda x: x.requires_contextualization, lambda x: {"query": state["user_query"], "chat_history": state["summarized_messages"]}),
        (
            ChatPromptTemplate.from_messages(
                [
                    ("system", configuration.contextualize_prompt),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{query}"),
                ]
            )
            | model.with_structured_output(ContextualizerNodeOutput)
        ).with_config(tags=[CONTEXTUALIZER_CONTEXTUALIZER_NODE]),
        lambda x: ContextualizerNodeOutput(contextualized_query=state["user_query"]),
    )

    return main_chain.invoke(
        {
            "query": state["user_query"],
        }
    )
