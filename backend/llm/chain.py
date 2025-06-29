import json
import logging
from typing import Any, AsyncGenerator, Dict, List

from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain.retrievers.ensemble import EnsembleRetriever
from langchain_cohere import CohereRerank
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessageChunk
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from llm.constant import MODEL_NAME
from llm.query_translation.contextual_strategy import get_contextual_strategy_chain
from llm.query_translation.decomposition import get_decomposition_chain
from llm.query_translation.factual_strategy import get_factual_strategy_chain
from llm.query_translation.hyDe import get_hyDe_chain
from llm.query_translation.multi_query import get_multi_query_chain
from llm.query_translation.rag_fusion import get_rag_fusion_chain
from llm.query_translation.step_back import get_step_back_chain
from load_env import load_env
from prompts import (
    CONTEXTUALIZE_PROMPT,
    FINAL_PROMPT,
    GENERAL_PROMPT,
    INTENT_CLASSIFICATION_PROMPT,
    METHOD_SELECTION_PROMPT,
    RETRIEVAL_METHOD_SELECTION_PROMPT,
)
from schemas import IntentClassification, MethodSelection, RetrievalSelection
from vector.graph_search import graph_rag_retrieve
from vector.hybrid_search import get_bm25_retriever, get_qdrant_retriever

# --- Initialization ---
load_env()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Embedding model (for some retrievers)
embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

# In-memory conversation store
store: Dict[str, ChatMessageHistory] = {}
seen_documents = set()


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]


def serialize_aimessagechunk(chunk: Any) -> str:
    if isinstance(chunk, AIMessageChunk):
        content = chunk.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(item.get("text", str(item)) if isinstance(item, dict) else str(item) for item in content)
        return str(content)
    raise TypeError(f"Unexpected chunk type: {type(chunk)}")


# --- Dynamic retriever builder with weights support ---
def build_retriever(methods: List[str], weights: List[float]):
    retrievers = []
    for part in methods:
        part = part.lower().strip()
        if part == "graph":
            retrievers.append(RunnableLambda(lambda inputs: {"documents": graph_rag_retrieve(inputs["question"])} if isinstance(inputs, dict) and "question" in inputs else {"documents": graph_rag_retrieve(str(inputs))}))
        elif part == "dense":
            retrievers.append(get_qdrant_retriever())
        elif part == "sparse":
            retrievers.append(get_bm25_retriever())
    if not retrievers:
        retrievers.append(get_qdrant_retriever())
        weights = [1.0]
    if len(weights) != len(retrievers):
        weights = [1.0 / len(retrievers)] * len(retrievers)
    base = retrievers[0] if len(retrievers) == 1 else EnsembleRetriever(retrievers=retrievers, weights=weights)
    return ContextualCompressionRetriever(base_compressor=CohereRerank(model="rerank-english-v3.0"), base_retriever=base).with_config(tags=["retriever"])


async def middleware_qa(query: str, convoHistory: str) -> AsyncGenerator[str, None]:
    model = ChatOpenAI(model=MODEL_NAME, streaming=True, model_kwargs={"timeout": 180})

    # Full retrieval pipeline, now with linked method and retriever selection
    retrieval_chain = (
        RunnablePassthrough.assign(
            # 1) reformulate
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
            ),
            # 2) choose query method
            method=(ChatPromptTemplate.from_template(METHOD_SELECTION_PROMPT) | model.with_structured_output(MethodSelection, method="function_calling") | StrOutputParser()),
            # 3) choose retriever method(s)
            retrieval_selection=(ChatPromptTemplate.from_template(RETRIEVAL_METHOD_SELECTION_PROMPT) | model.with_structured_output(RetrievalSelection, method="function_calling")),
        )
        # 4) build composite retriever based on method output
        | RunnableLambda(lambda env: {"retriever": build_retriever(env["retrieval_selection"].methods, env["retrieval_selection"].weights)} if isinstance(env, dict) and "retrieval_selection" in env else {"retriever": build_retriever(["dense"], [1.0])})
        # 5) apply translation+retrieval branch
        | RunnableBranch(
            (lambda env: isinstance(env, dict) and "multiquery" in env.get("method", ""), lambda env: get_multi_query_chain(env.get("retriever", None)) if isinstance(env, dict) else None),
            (lambda env: isinstance(env, dict) and "decompose" in env.get("method", ""), lambda env: get_decomposition_chain(env.get("retriever", None)) if isinstance(env, dict) else None),
            (lambda env: isinstance(env, dict) and "stepback" in env.get("method", ""), lambda env: get_step_back_chain(env.get("retriever", None)) if isinstance(env, dict) else None),
            (lambda env: isinstance(env, dict) and "hyde" in env.get("method", ""), lambda env: get_hyDe_chain(env.get("retriever", None)) if isinstance(env, dict) else None),
            (lambda env: isinstance(env, dict) and "ragfusion" in env.get("method", ""), lambda env: get_rag_fusion_chain(env.get("retriever", None)) if isinstance(env, dict) else None),
            (lambda env: isinstance(env, dict) and "factual" in env.get("method", ""), lambda env: get_factual_strategy_chain(env.get("retriever", None)) if isinstance(env, dict) else None),
            (lambda env: isinstance(env, dict) and "contextual" in env.get("method", ""), lambda env: get_contextual_strategy_chain(env.get("retriever", None)) if isinstance(env, dict) else None),
            (lambda env: isinstance(env, dict), lambda env: get_multi_query_chain(env.get("retriever", None)) if isinstance(env, dict) else None),
        )
        | ChatPromptTemplate.from_messages(
            [
                ("system", FINAL_PROMPT),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{question}"),
            ]
        )
        | model.with_config(tags=["final_answer"])
        | (lambda x: {"answer": x})
    )

    # General chain
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

    # Router
    main_chain = RunnablePassthrough.assign(
        intent=(
            ChatPromptTemplate.from_messages(
                [
                    ("system", INTENT_CLASSIFICATION_PROMPT),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{question}"),
                ]
            )
            | model.with_structured_output(IntentClassification, method="function_calling")
        ).with_config(tags=["doc_request_classifier"]),
    ) | RunnableBranch(
        (lambda x: x.get("intent", None) is not None and getattr(x["intent"], "intent", None) == "document request" if isinstance(x, dict) else False, retrieval_chain),
        general_chain,
    )

    # Conversation with history
    conv_chain = RunnableWithMessageHistory(
        main_chain,  # type: ignore
        get_session_history,
        input_messages_key="question",
        history_messages_key="chat_history",
        output_messages_key="answer",
    )

    # Streaming execution
    input_data = {"question": query, "chat_history": convoHistory}
    i = 0
    try:
        async for event in conv_chain.astream_events(input_data, config={"configurable": {"session_id": "abc123"}}, version="v1"):
            if "final_answer" in event.get("tags", []) and event["event"] == "on_chat_model_stream":
                c = serialize_aimessagechunk(event["data"]["chunk"])  # type: ignore
                if c:
                    yield f"data: {json.dumps({'message': c, 'order': i})}\n\n"

            reform_tags = ["seq:step:2", "main_chain", "contextualize_q_chain"]
            if all(t in event.get("tags", []) for t in reform_tags) and event["event"] == "on_chat_model_stream":
                r = serialize_aimessagechunk(event["data"]["chunk"])  # type: ignore
                if r:
                    yield f"data: {json.dumps({'reformulated': r, 'order': i})}\n\n"

            if "retriever" in event.get("tags", []) and event["event"] == "on_retriever_end":
                docs = event["data"]["output"].get("documents", [])  # type: ignore
                formatted, seen = [], set()
                for d in docs:
                    cid = f"{d.metadata.get('title')}:{d.metadata.get('page')}:{hash(d.page_content[:100])}"
                    if cid in seen:
                        continue
                    seen.add(cid)
                    formatted.append(
                        {
                            "title": d.metadata.get("title"),
                            "summary": d.metadata.get("summary"),
                            "link": d.metadata.get("source"),
                            "type": d.metadata.get("type"),
                        }
                    )
                if formatted:
                    yield f"data: {json.dumps({'context': formatted, 'order': i})}\n\n"
                seen_documents.clear()

            i += 1
    except Exception as e:
        logger.error(f"Error: {e}")
        yield f"data: {json.dumps({'message': 'Error processing query', 'order': i})}\n\n"
