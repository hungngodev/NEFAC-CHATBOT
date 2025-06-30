from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from prompts import FINAL_PROMPT, GENERAL_PROMPT

from .state import AgentState


def generator_agent(state: AgentState, model: ChatOpenAI):
    """
    Generates the final answer.
    """
    try:
        if state.intent == "document request":
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", FINAL_PROMPT),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{question}"),
                ]
            )
            chain = prompt | model
            answer = chain.invoke(
                {
                    "question": state.contextualized_query,
                    "context": state.documents,
                    "chat_history": state.chat_history,
                    "extracted_info": state.extracted_info,
                    "summarized_content": state.summarized_content,
                    "citations": state.citations,
                }
            )
        else:
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", GENERAL_PROMPT),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{question}"),
                ]
            )
            chain = prompt | model
            answer = chain.invoke(
                {
                    "question": state.contextualized_query,
                    "chat_history": state.chat_history,
                    "extracted_info": state.extracted_info,
                    "summarized_content": state.summarized_content,
                    "citations": state.citations,
                }
            )

        return {"answer": answer.content}
    except Exception as e:
        return {"error": str(e)}
