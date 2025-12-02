from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState
from langmem.short_term import RunningSummary, summarize_messages

from src.config.node_names import MEMORY_SUMMARIZER_NODE
from src.config.settings import Configuration
from src.utils.model_factory import init_model


class SummaryState(MessagesState):
    summary: RunningSummary | None


def summarizer(state: SummaryState, config: RunnableConfig | None = None) -> SummaryState:
    """Update running conversation summary without generating a chat reply.

    This node maintains short-term memory using langmem's summarization utilities.
    It should not produce an assistant message or answer the user. It only updates
    the running summary in the graph state when needed.
    """

    configuration = Configuration.from_runnable_config(config)
    # Bind summarization-specific token limit from configuration
    summarization_llm = init_model(configuration.summarization_model, disable_streaming=configuration.disable_streaming, node_name=MEMORY_SUMMARIZER_NODE)
    summarization_model = summarization_llm.bind(max_tokens=configuration.summarization_model_max_tokens)

    summarization_result = summarize_messages(
        state["messages"],
        running_summary=state.get("summary"),
        model=summarization_model,
        max_tokens=configuration.summarization_model_max_tokens,
        max_tokens_before_summary=configuration.summarization_model_max_tokens,
        max_summary_tokens=min(128, configuration.summarization_model_max_tokens),
    )

    # Do not call the chat model here and do not append any messages.
    # Only update the running summary and expose summarized messages for downstream nodes.
    state_update: dict[str, Any] = {"summarized_messages": summarization_result.messages}
    if summarization_result.running_summary:
        state_update["summary"] = summarization_result.running_summary

    return state_update
