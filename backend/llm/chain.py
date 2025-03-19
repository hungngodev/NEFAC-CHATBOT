import json
import logging

from langchain.vectorstores import FAISS
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessageChunk
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (ChatPromptTemplate, MessagesPlaceholder,
                                    PromptTemplate)
from langchain_core.runnables import RunnablePassthrough, RunnableBranch, RunnableLambda
from langchain_core.runnables.history import RunnableWithMessageHistory
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

# retriever = vector_store.as_retriever(
#             search_type="similarity",
#             search_kwargs={"k": 10, "lambda_mult": 0.25, "score_threshold": 0.75},
#         ).with_config(tags=["retriever"])
# decompose = get_decomposition_chain(retriever).invoke("NEFAC resources related to the First Amendment")
# logger.info(f"Decompose: {decompose}")

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

async def middleware_qa(query, convoHistory, roleFilter=None, contentType=None, resourceType=None):
    model = ChatOpenAI(model=MODEL_NAME, streaming=True)  # Enable streaming here
    
    contextualize_q_system_prompt = """Given a chat history and the latest user question \
    which might reference context in the chat history, formulate a standalone question \
    which can be understood without the chat history. Do NOT answer the question, \
    just reformulate it if needed and otherwise return it as is."""
    
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

    qa_system_prompt = """
        Role: You are an AI chatbot for NEFAC, new england first amendment coalition. You are an expert in providing relevant NEFAC only resources.

        Task: 
        Given retrieved NEFAC resources, your task is to determine whether you have enough information, or too much confusing information, to answer the query. 
        If not enough resources were found, ask the user for more information.
        If a lot of unrelated resources were found, ask the user to specify the type of resource they are looking for.
        If you seem comfortable with the information, answer the query with the relevant resources.
        Generally speaking, here are some examples of information you might want to ask the user for:
            - Is the user looking for specific resources, or general resources?
            - Is the user looking for information regarding a specific US state?
            - Is the user looking for information regarding a specific law or court case?

        For example, if the user is looking for mentors, you would want to ask the user about the specific area of expertise or state the user is looking for.

        Sources:
        {context}

        Instructions:
        - If you need more information in the Sources to answer the query, ask the user relevant follow up questions to aid in your response.
        - If you have too much conflicting information to answer the query, ask the user to specify the type of resource they are looking for.
        - If you are unsure, ask the user for more information.
        - Use the conversation history to guide your response.
        - Do not ask more than 2 follow up questions. Therefore, if you already asked 2 questions (as shown in conversation history), answer the query with the information you have so far and the below structure.
        - But if you don't have enough information in the Sources, clarify with the user that you need more information to answer the query.
        
        IF YOU HAVE ENOUGH INFORMATION IN THE SOURCE, ANSWER THE QUERY WITH THE FOLLOWING CRITERIA:
        - You are an AI search engine for NEFAC, new england first amendment coalition. Sometimes NEFAC gets mistaken with Kneefact in youtube transcripts, so be aware.
        - You are an expert in the providing relevant NEFAC only resources.
        - Generate a list of unique relevant sources from the context as a search engine.
        - If the source is not relevant to the query, do not include it in the list.
        - Titles can be slightly modified for readability.
        - If the query is searching for a person, mentor, or people, mention specific names of people with expertise in the relevant areas.
        - If the query regards a specific state, find sources relevant to that specific state.
        - If the query is not state-specific or regards a general resource, find general resources.
        - Do not hallucianate or make up any resources that arent explicitely given to you above. 
        - Summarize each returned source content in a way that answers the query.
        - Do not include duplicate resources.
        - Sources should be unique.
    """
    
    qa_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", qa_system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}"),
    ])
    
    
    if roleFilter is None and contentType is None and resourceType is None:
        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": NUMBER_OF_NEAREST_NEIGHBORS, "lambda_mult": LAMBDA_MULT, "score_threshold": THRESHOLD},
        ).with_config(tags=["retriever"])
    else:
        filter_func = create_vectorstore_filter(roleFilter, contentType, resourceType)
        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": NUMBER_OF_NEAREST_NEIGHBORS,
                "lambda_mult": LAMBDA_MULT,
                "score_threshold": THRESHOLD,
                "filter": filter_func
            },
        ).with_config(tags=["retriever"])
        
    retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10, "lambda_mult": 0.25, "score_threshold": 0.75},
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
    """Analyze the following question and choose the best query transformation strategy:
    1. multiquery - for ambiguous questions needing multiple perspectives
    2. ragfusion - for complex questions needing combined search strategies
    3. stepback - for specific questions needing broader context
    4. decompose - for multi-part questions needing breakdown
    5. hyde - for technical questions needing hypothetical examples
    6. default - for straightforward questions needing direct answers
    
    Question: {question}
    
    Respond ONLY with the method name from the list above."""
    )

    # Define the classifier chain
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

    rag_chain = (
        RunnablePassthrough.assign(context=retrieval_step)
        | qa_prompt
        | model
        | (lambda x: {"answer": x})
    ).with_config(
        tags=["main_chain"]
    )

    conversational_rag_chain = RunnableWithMessageHistory(
        rag_chain,
        get_session_history,
        input_messages_key="question",
        history_messages_key="chat_history",
        output_messages_key="answer",
    )
    input = {"question": query}
    # print("History: ", get_session_history("abc123"))
    try:
        i = 0
        async for event in conversational_rag_chain.astream_events(input, config={"configurable": {"session_id": "abc123"}}, version="v1"):
            # Only get the answer
            # print("Event: ", event)
            sources_tags = ['seq:step:3', 'main_chain']
            if all(value in event["tags"] for value in sources_tags) and 'full_retrieval_pipeline' not in event['tags'] and event["event"] == "on_chat_model_stream":
                # logger.info(f"Event: {event['tags']}")
                chunk_content = serialize_aimessagechunk(event["data"]["chunk"])
                if len(chunk_content) != 0:
                    data_dict = {"message": chunk_content, "order": i}
                    data_json = json.dumps(data_dict)
                    yield f"data: {data_json}\n\n"

            # Get the reformulated question
            sources_tags = ['seq:step:2', 'main_chain', 'contextualize_q_chain']
            if all(value in event["tags"] for value in sources_tags) and event["event"] == "on_chat_model_stream":
                chunk_content = serialize_aimessagechunk(event["data"]["chunk"])
                if len(chunk_content) != 0:
                    data_dict = {"reformulated": chunk_content, "order": i}
                    data_json = json.dumps(data_dict)
                    yield f"data: {data_json}\n\n"
                
            # Get the context
            sources_tags = ['main_chain', 'retriever']
            if all(value in event["tags"] for value in sources_tags) and event["event"] == "on_retriever_end":
                documents = event['data']['output']['documents']
                # Create a new list to contain the formatted documents
                formatted_documents = []
                # Iterate over each document in the original list
                for doc in documents:
                    # logger.info(f"Document: {doc}")
                    # Create a new dictionary for each document with the required format
                    # print("Doc: ", doc)
                    formatted_doc = {
                        'summary': doc.page_content,
                        'link': doc.metadata['source'],
                        'type': doc.metadata['type'],
                        'title': doc.metadata['title'],
                        'nefac_categorie': doc.metadata['nefac_category'],
                        'resource_type': doc.metadata['resource_type'],
                        'audience': doc.metadata['audience'],
                        'citation': []
                    }
                    # Add the formatted document to the final list
                    formatted_documents.append(formatted_doc)

                # Create the final dictionary with the key "context"
                final_output = {'context': formatted_documents,"order": i}

                # Convert the dictionary to a JSON string
                data_json = json.dumps(final_output)
                yield f"data: {data_json}\n\n"
            if event["event"] == "on_chat_model_end":
                print("Chat model has completed one response.")
            i +=1
    except Exception as e:
        logger.error(f"Error: {e}")