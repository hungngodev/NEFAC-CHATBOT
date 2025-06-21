from langchain_core.load import dumps, loads
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from llm.constant import PROMPT_MODEL_NAME
from llm.utils import format_docs
from load_env import load_env
from prompts import MULTI_QUERY_PERSPECTIVES_PROMPT

load_env()

model = ChatOpenAI(temperature=0, model_name=PROMPT_MODEL_NAME)
prompt_perspectives = ChatPromptTemplate.from_template(MULTI_QUERY_PERSPECTIVES_PROMPT)

generate_queries = prompt_perspectives | model | StrOutputParser() | (lambda x: x.split("\n"))


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
