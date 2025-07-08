from typing import TypedDict

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableBranch
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config.constant import CONTEXTUALIZED_QUERY_MODEL_NAME
from src.schemas.core_types import AgentState

NEED_FOR_CONTEXTUALIZATION_PROMPT = """DETERMINE if the user query requires contextualization based on the chat history.
- If the user query can be understood without the chat history, return False.
- If the user query requires context from the chat history to be understood, return True."""

CONTEXTUALIZE_PROMPT = """Given a chat history and the latest user question, formulate a standalone question that can be understood without the chat history. Do NOT answer it, just reformulate if needed."""


class NeedForContextualization(BaseModel):
    """ """

    requires_contextualization: bool = Field(description="Indicates whether the user query requires contextualization based on the chat history.")


class ContextualizerNodeOutput(TypedDict):
    """
    Output type for the contextualizer node.
    Contains the contextualized query and any extracted information.
    """

    contextualized_query: str = Field(description="The reformulated query that can be understood without the chat history.")


model = ChatOpenAI(model=CONTEXTUALIZED_QUERY_MODEL_NAME)


def contextualizer_node(state: AgentState) -> ContextualizerNodeOutput:
    main_chain = (
        ChatPromptTemplate.from_messages(
            [
                ("system", NEED_FOR_CONTEXTUALIZATION_PROMPT),
                ("human", "{query}"),
            ]
        )
        | model.with_structured_output(NeedForContextualization)
    ) | RunnableBranch(
        (lambda x: x.requires_contextualization, lambda x: {"query": state["user_query"], "chat_history": state["summarized_messages"]}),
        (
            ChatPromptTemplate.from_messages(
                [
                    ("system", CONTEXTUALIZE_PROMPT),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{query}"),
                ]
            )
            | model.with_structured_output(ContextualizerNodeOutput)
        ).with_config(tags=["contextualize_q_chain"]),
        lambda x: ContextualizerNodeOutput(contextualized_query=state["user_query"]),
    )

    return main_chain.invoke(
        {
            "query": state["user_query"],
        }
    )
