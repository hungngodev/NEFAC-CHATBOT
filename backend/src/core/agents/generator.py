from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from src.config.prompts import FINAL_PROMPT, GENERAL_PROMPT
from src.core.agents.state import AgentState


def generator_agent(state: AgentState, model: ChatOpenAI):
    """
    Generates the final answer.
    """
    try:
        # Prepare context: combine summary and session memory
        history_context = state.history_summary or ""
        if state.session_memory:
            memory_text = "\n".join([str(item) for item in state.session_memory])
            history_context = f"{history_context}\nSession Memory:\n{memory_text}"

        if state.intent == "document request":
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", FINAL_PROMPT),
                    MessagesPlaceholder(variable_name="history_context"),
                    ("human", "{question}"),
                ]
            )
            chain = prompt | model
            answer = chain.invoke(
                {
                    "question": state.contextualized_query,
                    "context": state.documents,
                    "history_context": history_context,
                    "extracted_info": state.extracted_info,
                    "summarized_content": state.summarized_content,
                    "citations": state.citations,
                }
            )
        else:
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", GENERAL_PROMPT),
                    MessagesPlaceholder(variable_name="history_context"),
                    ("human", "{question}"),
                ]
            )
            chain = prompt | model
            answer = chain.invoke(
                {
                    "question": state.contextualized_query,
                    "history_context": history_context,
                    "extracted_info": state.extracted_info,
                    "summarized_content": state.summarized_content,
                    "citations": state.citations,
                }
            )

        return {"answer": answer.content}
    except Exception as e:
        return {"error": str(e)}
