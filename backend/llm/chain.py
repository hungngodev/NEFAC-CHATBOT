from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

# validation
from validation import SearchResponse
from langchain_core.runnables import RunnablePassthrough

from vector.utils import create_vectorstore_filter, vector_store, format_docs

async def custom_QA_structured(_, info, query, roleFilter=None, contentType=None, resourceType=None):
    
    prompt_template = """
        Use the following context to answer the query.

        Sources:
        {context}

        Instructions:
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
        - Source links must match exactly the original source links.
        - Put the path of the source in the 'link' field.
        - Format the output as JSON in the following structure: 

        {{
            "results": [
                {{
                    "title": "Title of the source",
                    "link": "source path",
                    "summary": "Details answering the query.",
                    "citations": [
                        {{"id": "1", "context": "Relevant quote used in summary"}}
                    ]
                }},
                ...
            ]
        }}

        Question: {question}
    """
    
    if roleFilter is None and contentType is None and resourceType is None:
        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10, "lambda_mult": 0.25, "score_threshold": 0.75},
        )
    else:
        filter_func = create_vectorstore_filter(roleFilter, contentType, resourceType)  
        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": 10,
                "lambda_mult": 0.25,
                "filter": filter_func
            },
        )

    QA_CHAIN_PROMPT = PromptTemplate.from_template(prompt_template) # prompt_template defined above
    model = ChatOpenAI(model='gpt-4o')
    structured_llm = model.with_structured_output(SearchResponse)

    qa_chain = (
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
        }
        | QA_CHAIN_PROMPT
        | structured_llm
        
    )
    response = qa_chain.invoke(query)
        
    return response.results

async def middleware_qa(_, info, query, convoHistory, roleFilter=None, contentType=None, resourceType=None):
    print("convo history: ", convoHistory)  
    prompt_template = """

        Role: You are an AI chatbot for NEFAC, new england first amendment coalition. You are an expert in providing relevant NEFAC only resources.
       
        Task: 
        Given retrieved NEFAC resources, your task is to determine whether you have enough information, or too much confusing information, to answer the query. 
        If not enough resources were found, ask the user for more information.
        If a lot of unrelated resources were found, ask the user to specify the type of resource they are looking for.
        If you seem comfortable with the information, return the number 1.
        Generally speaking, here are some examples of information you might want to ask the user for:
            - Is the user looking for specific resources, or general resources?
            - Is the user looking for information regarding a specific US state?
            - Is the user looking for information regarding a specific law or court case?

        For example, if the user is looking for mentors, you would want to ask the user about the specific area of expertise or state the user is looking for.

        Sources:
        {context}

        Conversation History:
        {convoHistory}

        Instructions:
        - If you have enough information to answer the query, simply return the number 1.
        - If you need more information to answer the query, ask the user relevant follow up questions to aid in your response.
        - If you have too much conflicting information to answer the query, ask the user to specify the type of resource they are looking for.
        - If you are unsure, ask the user for more information.
        - Use the conversation history to guide your response.
        - Do not ask more than 2 follow up questions. Therefore, if you already asked 2 questions (as shown in conversation history), return the number 1.


        Question: {question}
    """
    
    if roleFilter is None and contentType is None and resourceType is None:
        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10, "lambda_mult": 0.25, "score_threshold": 0.75},
        )
    else:
        filter_func = create_vectorstore_filter(roleFilter, contentType, resourceType)  
        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": 10,
                "lambda_mult": 0.25,
                "filter": filter_func
            },
        )

    QA_CHAIN_PROMPT = PromptTemplate.from_template(prompt_template) # prompt_template defined above
    model = ChatOpenAI(model='o1-mini')

    qa_chain = (
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
            "convoHistory": RunnablePassthrough(),
        }
        | QA_CHAIN_PROMPT
        | model
        
    )
    response = qa_chain.invoke(query)
    print("chat response: ", response)
    return response.content





