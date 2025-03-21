import json
import logging
from langchain_community.vectorstores import FAISS
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_openai import OpenAIEmbeddings
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessageChunk
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough, RunnableBranch
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from llm.utils import format_docs
from load_env import load_env
from vector.utils import create_vectorstore_filter
from vector.load import vector_store
from .query_translation.decomposition import get_decomposition_chain
from .query_translation.multi_query import get_multi_query_chain
from .query_translation.rag_fusion import get_rag_fusion_chain
from .query_translation.hyDe import get_hyDe_chain
from .query_translation.step_back import get_step_back_chain
from llm.constant import MODEL_NAME, NUMBER_OF_NEAREST_NEIGHBORS, LAMBDA_MULT, THRESHOLD

load_env()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

store = {}

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

def serialize_aimessagechunk(chunk):
    if isinstance(chunk, AIMessageChunk):
        return chunk.content
    else:
        raise TypeError(
            f"Object of type {type(chunk).__name__} is not correctly formatted for serialization"
        )

# Keep format_docs as metadata-focused, but we won’t use it directly in the message
def format_docs(docs):
    formatted = []
    for doc in docs:
        metadata = doc.metadata
        formatted.append(
            f"Title: {metadata['title']}\n"
            f"Summary: {metadata['summary']}\n"
            f"Link: {metadata['source']}\n"
            f"Type: {metadata['type']}\n"
        )
    return "\n\n".join(formatted)

async def middleware_qa(query, convoHistory, roleFilter="", contentType="", resourceType=""):
    model = ChatOpenAI(model=MODEL_NAME, streaming=True)

    # Step 1: Classification Prompt and Chain (unchanged)
    classify_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", """
Based on the conversation history and the latest user query, determine the user's intent:
- If the user is requesting specific information, documents, resources, or media on any particular topic, classify it as 'document request'.
- If the user is asking a general question, making a statement, or seeking broad explanations, classify it as 'general query'.
Ignore whether the topic is related to NEFAC's focus areas; focus solely on the structure and intent of the query.

Examples:
- "Do you have any information about Excel?" → document request
- "What is the First Amendment?" → general query
- "Tell me about NEFAC's mission." → general query
- "Are there any resources on freedom of speech?" → document request
- "Can you explain freedom of the press?" → general query
- "Do you have documents on data privacy laws?" → document request

Respond with 'document request' or 'general query'.
"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ]
    )
    classify_chain = classify_prompt | ChatOpenAI(temperature=0) | StrOutputParser()

    # Step 2: General Query Prompt and Chain (unchanged)
    general_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", """
You are an AI chatbot for NEFAC, the New England First Amendment Coalition. NEFAC is dedicated to protecting press freedoms and the public's right to know in New England. Provide a helpful response to the user's query based on your knowledge of NEFAC’s mission and activities. Do not retrieve documents.
"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ]
    )
    general_chain = (
        general_prompt
        | model.with_config(tags=["final_answer"])
        | (lambda x: {"answer": x})
    )

    # Step 3: Document Request Path (Updated QA Prompt)
    contextualize_q_system_prompt = """Given a chat history and the latest user question, formulate a standalone question that can be understood without the chat history. Do NOT answer it, just reformulate if needed."""
    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ]
    )
    contextualize_q_chain = (contextualize_q_prompt | model | StrOutputParser()).with_config(
        tags=["contextualize_q_chain"]
    )

    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", """
You are an AI assistant for NEFAC, the New England First Amendment Coalition. The user has asked for documents or resources. Your task is to acknowledge their request and indicate that relevant documents are available, without including the document details in your response.

Instructions:
- Respond with a concise message like: "I have found some relevant documents on [topic]. You can view the details below."
- Replace [topic] with a brief description of what the user asked for (e.g., 'NEFAC’s FOI guides').
- Do NOT include document titles, summaries, or links in your response—they will be provided separately.
- If no documents are relevant (context is empty), say: "I couldn’t find specific documents on [topic]. Can you provide more details?"
- Use the conversation history to refine your response if needed.
- Keep it short and clear.

Retrieved documents (for your reference, not to include in the response):
{context}
"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ]
    )

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": NUMBER_OF_NEAREST_NEIGHBORS,
            "lambda_mult": LAMBDA_MULT,
            "score_threshold": THRESHOLD,
            "filter": create_vectorstore_filter(roleFilter, contentType, resourceType, NUMBER_OF_NEAREST_NEIGHBORS)
        },
    ).with_config(tags=["retriever"])

    retriever_chain = {
        'default': RunnableLambda(lambda x: x['question']) | retriever | format_docs,
        'multi_query': get_multi_query_chain(retriever),
        'rag_fusion': get_rag_fusion_chain(retriever),
        'decomposition': get_decomposition_chain(retriever),
        'step_back': get_step_back_chain(retriever),
        'hyde': get_hyDe_chain(retriever)
    }

    classifier_prompt = ChatPromptTemplate.from_template(
        """Analyze the question and choose the best query transformation strategy:
        1. multiquery - ambiguous questions
        2. ragfusion - complex questions
        3. stepback - specific questions needing context
        4. decompose - multi-part questions
        5. hyde - technical questions
        6. default - straightforward questions
        Question: {question}
        Respond ONLY with the method name."""
    )

    query_classifier = (
        classifier_prompt 
        | ChatOpenAI(temperature=0, model="gpt-4")
        | StrOutputParser()
    )

    retrieval_step = (
        contextualize_q_chain 
        | {
            'question': RunnablePassthrough(),
            'method': query_classifier
        }
        | RunnableBranch(
            (lambda x: "multiquery" in x["method"], retriever_chain['multi_query']),
            (lambda x: "decompose" in x["method"], retriever_chain['decomposition']),
            (lambda x: "stepback" in x["method"], retriever_chain['step_back']),
            (lambda x: "hyde" in x["method"], retriever_chain['hyde']),
            (lambda x: "ragfusion" in x["method"], retriever_chain['rag_fusion']),
            retriever_chain['default']
        )
    ).with_config(tags=["full_retrieval_pipeline"])

    retrieval_chain = (
        RunnablePassthrough.assign(context=retrieval_step)
        | qa_prompt
        | model.with_config(tags=["final_answer"])
        | (lambda x: {"answer": x})
    )

    # Step 4: Routing Logic (unchanged)
    router = RunnableBranch(
        (
            lambda x: "document request" in classify_chain.invoke(x).lower(),
            retrieval_chain
        ),
        general_chain
    )

    conversational_chain = RunnableWithMessageHistory(
        router,
        get_session_history,
        input_messages_key="question",
        history_messages_key="chat_history",
        output_messages_key="answer",
    )

    input = {"question": query, "chat_history": convoHistory}
    try:
        i = 0
        async for event in conversational_chain.astream_events(input, config={"configurable": {"session_id": "abc123"}}, version="v1"):
            # Stream the final answer (message only)
            if "final_answer" in event["tags"] and event["event"] == "on_chat_model_stream":               
                chunk_content = serialize_aimessagechunk(event["data"]["chunk"])
                if len(chunk_content) != 0:
                    data_dict = {"message": chunk_content, "order": i}
                    data_json = json.dumps(data_dict)
                    yield f"data: {data_json}\n\n"

            # Stream the reformulated question (unchanged)
            sources_tags = ['seq:step:2', 'main_chain', 'contextualize_q_chain']
            if all(value in event["tags"] for value in sources_tags) and event["event"] == "on_chat_model_stream":
                chunk_content = serialize_aimessagechunk(event["data"]["chunk"])
                if len(chunk_content) != 0:
                    data_dict = {"reformulated": chunk_content, "order": i}
                    data_json = json.dumps(data_dict)
                    yield f"data: {data_json}\n\n"

            # Stream the context (document metadata) - adjusted to ensure it’s sent properly
            sources_tags = ['main_chain', 'retriever']
            if "retriever" in event["tags"] and event["event"] == "on_retriever_end":
                print("WE ENDED UP IN THE DOCUMENT OUTPUT")
                documents = event['data']['output']['documents']
                formatted_documents = []
                seen_documents = set()
                for doc in documents:
                    if doc.metadata["title"] in seen_documents:
                        continue
                    seen_documents.add(doc.metadata["title"])
                    formatted_doc = {
                        'summary': doc.metadata['summary'],
                        'link': doc.metadata['source'],
                        'type': doc.metadata['type'],
                        'title': doc.metadata['title'],
                        'nefac_category': doc.metadata.get('nefac_category', []),
                        'resource_type': doc.metadata.get('resource_type', []),
                        'audience': doc.metadata.get('audience', []),
                        'citation': doc.metadata.get('citation', [])
                    }
                    formatted_documents.append(formatted_doc)
                if formatted_documents:  # Only send if there are documents
                    final_output = {'context': formatted_documents, "order": i}
                    data_json = json.dumps(final_output)
                    yield f"data: {data_json}\n\n"
            if event["event"] == "on_chat_model_end":
                print("Chat model has completed one response.")
            i += 1
    except Exception as e:
        logger.error(f"Error: {e}")
