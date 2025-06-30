from langchain_core.load import dumps, loads
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.config.prompts import MULTI_QUERY_PERSPECTIVES_PROMPT
from src.core.utils import format_docs
from src.load_env import load_env

load_env()

model = ChatOpenAI(temperature=0, model=QUERY_TRANSLATION_MODEL_NAME)
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
