from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState
from langmem.short_term import RunningSummary, summarize_messages

from src.config.settings import Configuration
from src.schemas.state import AgentState


class LLMInputState(AgentState):
    summarized_messages: list[AnyMessage]
    context: dict[str, Any]


class SummaryState(MessagesState):
    summary: RunningSummary | None


def summarization_node(state: SummaryState, config: Configuration) -> SummaryState:
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.summarizer_model)

    summarization_result = summarize_messages(
        state["messages"],
        running_summary=state.get("summary"),
        model=llm.bind(max_tokens=128),
        max_tokens=256,
        max_tokens_before_summary=256,
        max_summary_tokens=128,
    )
    response = llm.invoke(summarization_result.messages)
    state_update = {"messages": [response]}
    if summarization_result.running_summary:
        state_update["summary"] = summarization_result.running_summary
    return state_update


# Create an alias for the summarizer
summarizer = summarization_node
