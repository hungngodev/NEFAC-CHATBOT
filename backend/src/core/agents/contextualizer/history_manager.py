from typing import Dict, List, Union

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from src.config.constant import (
    HISTORY_THRESHOLD,
    MESSAGES_TO_KEEP,
    MESSAGES_TO_SUMMARIZE,
    MODEL_NAME,
)
from src.schemas.core_types import AgentState

# --- LLM Setup for Summarization ---
llm = ChatOpenAI(temperature=0, model=MODEL_NAME)

summarization_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert at summarizing conversations. Your task is to distill the key information from the following messages into a concise summary. This summary will serve as a contextual foundation for a subsequent conversation, ensuring that important details are retained. Focus on capturing the main points, decisions, and questions raised during the conversation.",
        ),
        MessagesPlaceholder(variable_name="messages_to_summarize"),
    ]
)

summarization_chain = summarization_prompt | llm | StrOutputParser()


def history_manager_agent(state: AgentState) -> Dict[str, Union[str, int, float, bool, None]]:
    """
    Manages the chat history to prevent it from growing too long.
    If the history exceeds a threshold, it summarizes the oldest messages.
    """
    try:
        chat_history = state.get("chat_history", [])
        if len(chat_history) > HISTORY_THRESHOLD:
            # Summarize the oldest messages
            messages_to_summarize = chat_history[:MESSAGES_TO_SUMMARIZE]
            summary = summarization_chain.invoke({"messages_to_summarize": messages_to_summarize})

            # Keep the most recent messages
            recent_messages = chat_history[-MESSAGES_TO_KEEP:]

            # Create the new condensed history
            new_history: List[BaseMessage] = [SystemMessage(content=f"This is a summary of the previous conversation: {summary}")]
            new_history.extend(recent_messages)

            return {"chat_history": new_history}

        # If history is not too long, do nothing
        return {"chat_history": chat_history}

    except Exception:
        # In case of an error, it's safer to return the original history
        # to avoid breaking the conversation flow.
        return {"chat_history": state.get("chat_history", [])}
