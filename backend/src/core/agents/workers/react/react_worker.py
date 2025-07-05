from typing import Any, Dict, List

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from src.core.agents.context_processor import context_processor_agent
from src.core.agents.workers.retriever.retrieval import retrieval_agent  # Import the retrieval agent
from src.schemas.state import AgentState

# Prompt for generating sub-questions
SUB_QUESTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert at breaking down complex questions into smaller, actionable sub-questions. Given the main question and the current context, generate the next logical sub-question to help gather more information. If enough information has been gathered to answer the main question, respond with 'FINAL_ANSWER'.",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        (
            "human",
            "Main Question: {question}\nCurrent Context: {context}\nNext Sub-question:",
        ),
    ]
)

# Prompt for synthesizing information
SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert at synthesizing information. Combine the following pieces of context to form a comprehensive answer to the main question. If the context is insufficient, state that.",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "Main Question: {question}\nContext: {context}\nExtracted Information: {extracted_info}\nCitations: {citations}\nAnswer:"),
    ]
)


def multi_step_reasoning_agent(state: AgentState, model: ChatOpenAI, max_steps: int = 3) -> Dict[str, Any]:
    """
    Performs multi-step reasoning by iteratively generating sub-questions, retrieving information,
    and synthesizing context.
    """
    try:
        current_context = ""
        all_documents: List[Document] = []

        for step in range(max_steps):
            # 1. Generate Sub-question
            sub_question_chain = SUB_QUESTION_PROMPT | model | (lambda x: x.content)
            sub_question: str = sub_question_chain.invoke(
                {
                    "question": state.query,
                    "context": current_context,
                    "chat_history": state.chat_history,
                }
            )

            if sub_question == "FINAL_ANSWER":
                break

            # 2. Retrieve Information for Sub-question
            # Temporarily create a state for the retrieval agent
            retrieval_state_for_sub_q = AgentState(
                query=sub_question,
                chat_history=state.chat_history,
                contextualized_query=None,
                intent=None,
                retrieval_method=None,
                retrieval_selection=state.retrieval_selection,
                transformed_query=sub_question,
                documents=[],
                answer=None,
                validation=None,
                entities=state.entities,
                metadata_filters={},
                priorities=[],
                extracted_info=None,
                citations=[],
                structured_query=None,
                statistical_query=None,
                error=None,
            )
            retrieval_output = retrieval_agent(retrieval_state_for_sub_q)
            retrieved_docs = retrieval_output.get("documents", [])

            # Process retrieved documents through context_processor_agent
            # Ensure documents is a list of strings (page_content) or None
            if isinstance(retrieved_docs, list) and len(retrieved_docs) > 0 and hasattr(retrieved_docs[0], "page_content"):
                doc_contents_list = [doc.page_content for doc in retrieved_docs]
            else:
                doc_contents_list = []
            context_processor_state = AgentState(
                query=state.query,
                chat_history=state.chat_history,
                contextualized_query=None,
                intent=None,
                retrieval_method=None,
                retrieval_selection=None,
                transformed_query=None,
                documents=doc_contents_list,
                answer=None,
                validation=None,
                entities=[],
                metadata_filters={},
                priorities=[],
                extracted_info=None,
                citations=[],
                structured_query=None,
                statistical_query=None,
                error=None,
            )
            processed_context = context_processor_agent(context_processor_state)

            all_documents.extend(processed_context.get("documents", []))
            state.extracted_info = processed_context.get("extracted_info")

            state.citations = processed_context.get("citations")

            # 3. Synthesize Context
            doc_contents = "\n\n".join([doc.page_content for doc in processed_context.get("documents", [])])
            current_context += f"\n\n--- Retrieved for '{sub_question}' ---\n{doc_contents}"

        # 4. Final Synthesis
        final_synthesis_chain = SYNTHESIS_PROMPT | model | (lambda x: x.content)
        final_answer: str = final_synthesis_chain.invoke(
            {
                "question": state.query,
                "context": current_context,
                "chat_history": state.chat_history,
                "extracted_info": state.extracted_info,
                "citations": state.citations,
            }
        )

        return {"answer": final_answer, "documents": all_documents}
    except Exception as e:
        return {"error": str(e)}
