import json
import logging
from typing import Any, AsyncGenerator, Dict

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessageChunk
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from llm.constant import (
    LAMBDA_MULT,
    MODEL_NAME,
    NUMBER_OF_NEAREST_NEIGHBORS,
    THRESHOLD,
)
from load_env import load_env
from prompts import (
    CONTEXTUALIZE_PROMPT,
    GENERAL_PROMPT,
    INTENT_CLASSIFICATION_PROMPT,
    METHOD_SELECTION_PROMPT,
    RETRIEVAL_PROMPT,
)
from vector.load import vector_store

from .query_translation.decomposition import get_decomposition_chain
from .query_translation.hyDe import get_hyDe_chain
from .query_translation.multi_query import get_multi_query_chain
from .query_translation.rag_fusion import get_rag_fusion_chain
from .query_translation.step_back import get_step_back_chain

load_env()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

store: Dict[str, ChatMessageHistory] = {}
seen_documents = set()


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]


def serialize_aimessagechunk(chunk: Any) -> str:
    if isinstance(chunk, AIMessageChunk):
        return chunk.content
    else:
        raise TypeError(f"Object of type {type(chunk).__name__} is not correctly formatted for serialization")


async def middleware_qa(
    query: str,
    convoHistory: str,
) -> AsyncGenerator[str, None]:
    # ============================================================================
    # INITIALIZATION MODEL
    # ============================================================================
    model = ChatOpenAI(model=MODEL_NAME, streaming=True)

    # ============================================================================
    # RETRIEVER SETUP
    # ============================================================================
    retriever = RunnableLambda(
        lambda question: vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": NUMBER_OF_NEAREST_NEIGHBORS,
                "lambda_mult": LAMBDA_MULT,
                "score_threshold": THRESHOLD,
            },
        ).invoke(question)
    ).with_config(tags=["retriever"])

    # ============================================================================
    # FULL RETRIEVAL PIPELINE
    # ============================================================================
    retrieval_chain = (
        RunnablePassthrough.assign(
            context=(
                (
                    ChatPromptTemplate.from_messages(
                        [
                            ("system", CONTEXTUALIZE_PROMPT),
                            MessagesPlaceholder(variable_name="chat_history"),
                            ("human", "{question}"),
                        ]
                    )
                    | model
                    | StrOutputParser()
                ).with_config(tags=["contextualize_q_chain"])
                | {"question": RunnablePassthrough(), "method": (ChatPromptTemplate.from_template(METHOD_SELECTION_PROMPT) | model | StrOutputParser())}
                | RunnableBranch(
                    (lambda x: "multiquery" in str(x.get("method", "")) if isinstance(x, dict) else "", get_multi_query_chain(retriever)),
                    (lambda x: "decompose" in str(x.get("method", "")) if isinstance(x, dict) else "", get_decomposition_chain(retriever)),
                    (lambda x: "stepback" in str(x.get("method", "")) if isinstance(x, dict) else "", get_step_back_chain(retriever)),
                    (lambda x: "hyde" in str(x.get("method", "")) if isinstance(x, dict) else "", get_hyDe_chain(retriever)),
                    (lambda x: "ragfusion" in str(x.get("method", "")) if isinstance(x, dict) else "", get_rag_fusion_chain(retriever)),
                    (get_multi_query_chain(retriever)),
                )
            ).with_config(tags=["full_retrieval_pipeline"])
        )
        | ChatPromptTemplate.from_messages(
            [
                ("system", RETRIEVAL_PROMPT),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{question}"),
            ]
        )
        | model.with_config(tags=["final_answer"])
        | (lambda x: {"answer": x})
    )

    # ============================================================================
    # GENERAL CHAIN (for non-document requests)
    # ============================================================================
    general_chain = (
        ChatPromptTemplate.from_messages(
            [
                ("system", GENERAL_PROMPT),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{question}"),
            ]
        )
        | model.with_config(tags=["final_answer"])
        | (lambda x: {"answer": x})
    )

    # ============================================================================
    # MAIN ROUTER
    # ============================================================================
    router = RunnableBranch(
        (
            lambda x: "document request"
            in (
                ChatPromptTemplate.from_messages(
                    [
                        ("system", INTENT_CLASSIFICATION_PROMPT),
                        MessagesPlaceholder(variable_name="chat_history"),
                        ("human", "{question}"),
                    ]
                )
                | model
                | StrOutputParser()
            )
            .with_config(tags=["doc_request_classifier"])
            .invoke(x)
            .lower(),
            retrieval_chain,
        ),
        general_chain,
    )

    # ============================================================================
    # CONVERSATIONAL CHAIN WITH HISTORY
    # ============================================================================
    conversational_chain = RunnableWithMessageHistory(
        router,
        get_session_history,
        input_messages_key="question",
        history_messages_key="chat_history",
        output_messages_key="answer",
    )

    # ============================================================================
    # STREAMING EXECUTION
    # ============================================================================
    input_data = {"question": query, "chat_history": convoHistory}

    try:
        i = 0
        async for event in conversational_chain.astream_events(input_data, config={"configurable": {"session_id": "abc123"}}, version="v1"):
            # Handle final answer streaming
            if "final_answer" in event.get("tags", []) and event["event"] == "on_chat_model_stream":
                chunk_content = serialize_aimessagechunk(event["data"]["chunk"])  # type: ignore
                if len(chunk_content) != 0:
                    data_dict = {"message": chunk_content, "order": i}
                    data_json = json.dumps(data_dict)
                    yield f"data: {data_json}\n\n"

            # Handle reformulated question streaming
            sources_tags = ["seq:step:2", "main_chain", "contextualize_q_chain"]
            if all(value in event.get("tags", []) for value in sources_tags) and event["event"] == "on_chat_model_stream":
                chunk_content = serialize_aimessagechunk(event["data"]["chunk"])  # type: ignore
                if len(chunk_content) != 0:
                    data_dict = {"reformulated": chunk_content, "order": i}
                    data_json = json.dumps(data_dict)
                    yield f"data: {data_json}\n\n"

            # Handle document retrieval
            if "retriever" in event.get("tags", []) and event["event"] == "on_retriever_end":
                logger.info("WE ENDED UP IN THE DOCUMENT OUTPUT")
                documents = event["data"]["output"]["documents"]
                formatted_documents = []
                curr_seen_documents = set()

                for doc in documents:
                    chunk_id = f"{doc.metadata.get('title', 'unknown')}:{doc.metadata.get('page', '0')}:{hash(doc.page_content[:100])}"
                    if chunk_id in curr_seen_documents:
                        continue
                    curr_seen_documents.add(chunk_id)

                    formatted_doc = {
                        "summary": doc.metadata.get("summary", ""),
                        "link": doc.metadata.get("source", ""),
                        "type": doc.metadata.get("type", ""),
                        "title": doc.metadata.get("title", ""),
                        "timestamp_seconds": (doc.metadata.get("page", None) if doc.metadata.get("type", "") == "youtube" else None),
                    }
                    formatted_documents.append(formatted_doc)

                if formatted_documents:
                    final_output = {"context": formatted_documents, "order": i}
                    data_json = json.dumps(final_output)
                    yield f"data: {data_json}\n\n"
                seen_documents.clear()

            i += 1

    except Exception as e:
        logger.error(f"Error in middleware_qa: {e}")
        error_chunk = {
            "message": "An error occurred while processing your query.",
            "order": 1,
        }
        logger.info(f"Yielding error chunk: {error_chunk}")
        yield f"data: {json.dumps(error_chunk)}\n\n"
