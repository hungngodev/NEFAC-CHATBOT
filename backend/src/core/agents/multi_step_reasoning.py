from typing import List

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from src.core.agents.context_processor import context_processor_agent
from src.core.agents.retrieval import retrieval_agent  # Import the retrieval agent
from src.core.agents.state import AgentState

# Prompt for generating sub-questions
SUB_QUESTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert at breaking down complex questions into smaller, actionable sub-questions. Given the main question and the current context, generate the next logical sub-question to help gather more information. If enough information has been gathered to answer the main question, respond with 'FINAL_ANSWER'.",
        ),
        MessagesPlaceholder(variable_name="history_context"),
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
        MessagesPlaceholder(variable_name="history_context"),
        ("human", "Main Question: {question}\nContext: {context}\nExtracted Information: {extracted_info}\nSummarized Content: {summarized_content}\nCitations: {citations}\nAnswer:"),
    ]
)


def multi_step_reasoning_agent(state: AgentState, model: ChatOpenAI, max_steps: int = 3):
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
            sub_question = sub_question_chain.invoke(
                {
                    "question": state.query,
                    "context": current_context,
                    "history_context": state.history_summary or state.chat_history,
                }
            )

            if sub_question == "FINAL_ANSWER":
                break

            # 2. Retrieve Information for Sub-question
            # Temporarily create a state for the retrieval agent
            retrieval_state_for_sub_q = AgentState(
                query=sub_question,
                chat_history=state.chat_history,  # Keep full chat_history for now, as it's used by other agents
                history_summary=state.history_summary,  # Pass summary
                transformed_query=sub_question,
                retrieval_selection=state.retrieval_selection,
                entities=state.entities,
            )
            retrieval_output = retrieval_agent(retrieval_state_for_sub_q)
            retrieved_docs = retrieval_output.get("documents", [])

            # Process retrieved documents through context_processor_agent
            context_processor_state = AgentState(
                query=state.query,
                chat_history=state.chat_history,
                history_summary=state.history_summary,
                documents=retrieved_docs,
            )
            processed_context = context_processor_agent(context_processor_state)

            all_documents.extend(processed_context.get("documents", []))
            state.extracted_info = processed_context.get("extracted_info")
            state.summarized_content = processed_context.get("summarized_content")
            state.citations = processed_context.get("citations")

            # 3. Synthesize Context
            doc_contents = "\n\n".join([doc.page_content for doc in processed_context.get("documents", [])])
            current_context += f"\n\n--- Retrieved for '{sub_question}' ---\n{doc_contents}"

        # 4. Final Synthesis
        final_synthesis_chain = SYNTHESIS_PROMPT | model | (lambda x: x.content)
        final_answer = final_synthesis_chain.invoke(
            {
                "question": state.query,
                "context": current_context,
                "history_context": state.history_summary or state.chat_history,
                "extracted_info": state.extracted_info,
                "summarized_content": state.summarized_content,
                "citations": state.citations,
            }
        )

        return {"answer": final_answer, "documents": all_documents}

    except Exception as e:
        return {"error": str(e)}
