from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config.prompts import CONVERSATION_SUMMARY_PROMPT
from src.schemas.core_types import AgentState


def summarizer_agent(state: AgentState, model: ChatOpenAI):
    """
    Summarizes the conversation history.
    """
    try:
        # Convert chat_history to a readable string format for summarization
        formatted_chat_history = "\n".join([f"{msg.type}: {msg.content}" for msg in state.chat_history])

        # If there's an existing summary, include it in the prompt
        if state.history_summary:
            full_history_for_summary = "Existing Summary: {}\n\nNew Conversation:\n{}".format(state.history_summary, formatted_chat_history)
        else:
            full_history_for_summary = formatted_chat_history

        summary_chain = (
            ChatPromptTemplate.from_messages(
                [
                    ("system", CONVERSATION_SUMMARY_PROMPT),
                ]
            )
            | model
        )

        # Invoke the summarization chain
        new_summary = summary_chain.invoke({"chat_history": full_history_for_summary})

        return {"history_summary": new_summary.content}
    except Exception as e:
        return {"error": str(e)}
