from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.config.prompts import CONTEXTUAL_STRATEGY_PROMPT
from src.core.agents.tools.document_formatter import format_docs
from src.core.agents.tools.retrieval.retrieval_tools import ensemble_retriever_tool
from src.load_env import load_env

load_env()

model = ChatOpenAI(temperature=0, model=QUERY_TRANSLATION_MODEL_NAME)
contextual_strategy_prompt = ChatPromptTemplate.from_template(CONTEXTUAL_STRATEGY_PROMPT)

generate_contextual_query = contextual_strategy_prompt | model | StrOutputParser()


def get_contextual_strategy_chain(retriever=None) -> Runnable:
    """Contextual strategy chain using ensemble retriever with context-aware retrieval."""

    def contextual_retrieval(contextual_query: str) -> str:
        """Retrieve documents using contextual query with ensemble methods."""
        docs = ensemble_retriever_tool.retrieve(query=contextual_query, methods=["dense", "sparse", "graph"], weights=[0.5, 0.25, 0.25], max_documents=8)  # All methods for contextual understanding  # Favor dense for contextual similarity
        return format_docs(docs)

    return generate_contextual_query | contextual_retrieval
