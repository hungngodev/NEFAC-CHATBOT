from typing import List

from langchain_core.documents import Document
from langchain_core.load import dumps, loads
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.config.prompts import MULTI_QUERY_PERSPECTIVES_PROMPT
from src.core.agents.tools.document_formatter import format_docs
from src.core.agents.tools.retrieval.retrieval_tools import ensemble_retriever_tool
from src.load_env import load_env

load_env()

model = ChatOpenAI(temperature=0, model=QUERY_TRANSLATION_MODEL_NAME)
prompt_perspectives = ChatPromptTemplate.from_template(MULTI_QUERY_PERSPECTIVES_PROMPT)

generate_queries = prompt_perspectives | model | StrOutputParser() | (lambda x: x.split("\n"))


def get_unique_union(documents: List[List[Document]]) -> List[Document]:
    """
    Unique union of retrieved documents with proper type safety.
    Deduplicates documents based on their serialized content.
    """
    try:
        # Flatten list of lists, and convert each Document to string for deduplication
        flattened_docs = []
        for sublist in documents:
            for doc in sublist:
                if isinstance(doc, Document):
                    flattened_docs.append(dumps(doc))
                else:
                    # Handle edge case where non-Document objects might be present
                    continue

        # Get unique documents by converting to set and back
        unique_docs = list(set(flattened_docs))

        # Convert back to Document objects
        result_docs = []
        for doc_str in unique_docs:
            try:
                doc = loads(doc_str)
                if isinstance(doc, Document):
                    result_docs.append(doc)
            except Exception:
                # Skip malformed documents
                continue

        return result_docs
    except Exception:
        # Fallback: return flattened list without deduplication
        result = []
        for sublist in documents:
            for doc in sublist:
                if isinstance(doc, Document):
                    result.append(doc)
        return result


def get_multi_query_chain(retriever=None) -> Runnable:
    """Multi-query chain using ensemble retriever with perspective diversification."""

    def multi_query_retrieval(queries: List[str]) -> List[Document]:
        """Retrieve documents for multiple perspective queries."""
        all_docs = []
        for query in queries:
            if query.strip():  # Skip empty queries
                docs = ensemble_retriever_tool.retrieve(query=query.strip(), methods=["dense", "sparse", "graph"], weights=[0.5, 0.25, 0.25], max_documents=8)  # All methods for comprehensive perspectives  # Favor dense for perspective diversity
                all_docs.append(docs)
        return get_unique_union(all_docs)

    return generate_queries | multi_query_retrieval | format_docs
