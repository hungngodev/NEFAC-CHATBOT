from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_core.load import dumps
from langchain_core.load import loads
from load_env import load_env
from llm.utils import format_docs
from llm.constant import PROMPT_MODEL_NAME, BASE_PROMPT

load_env()

prompt_perspectives = ChatPromptTemplate.from_template(
    f"""
You are an AI assistant for the New England First Amendment Coalition (NEFAC).  
Perform a multi-query translation of the user’s question by generating exactly five search queries (one per line) to retrieve diverse, relevant materials—transcripts, summaries, and docs—from our vector store.  

{BASE_PROMPT}

Each query should contain one of the following perspectives:

1. Restate the core question to find precise answers.  
2. Widen the frame to include New England’s free-speech and press-freedom context.  
3. Surface related legal concepts, precedents, or foundational First Amendment principles.  
4. Seek real-world NEFAC case studies, reports, or example applications.  
5. Highlight challenges, debates, or alternative perspectives on the topic.

Original question: {{question}}
"""
)

generate_queries = (
    prompt_perspectives
    | ChatOpenAI(model=PROMPT_MODEL_NAME, temperature=0)
    | StrOutputParser()
    | (lambda x: x.split("\n"))
)


def get_unique_union(documents: list[list]):
    # print("Documents: ", documents)
    """Unique union of retrieved docs"""
    # Flatten list of lists, and convert each Document to string
    flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
    # Get unique documents
    unique_docs = list(set(flattened_docs))
    # print("Unique Docs: ", unique_docs)
    # Return
    return [loads(doc) for doc in unique_docs]


def get_multi_query_chain(retriever):
    """Multi Query Chain"""
    return generate_queries | retriever.map() | get_unique_union | format_docs
