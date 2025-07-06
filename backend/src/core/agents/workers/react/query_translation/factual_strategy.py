from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.config.prompts import FACTUAL_STRATEGY_PROMPT
from src.core.agents.tools.document_formatter import format_docs
from src.core.agents.tools.retrieval.retrieval_tools import ensemble_retriever_tool
from src.load_env import load_env

load_env()

model = ChatOpenAI(temperature=0, model=QUERY_TRANSLATION_MODEL_NAME)
factual_strategy_prompt = ChatPromptTemplate.from_template(FACTUAL_STRATEGY_PROMPT)

generate_factual_query = factual_strategy_prompt | model | StrOutputParser()


def get_factual_strategy_chain(retriever=None) -> Runnable:
    """Factual strategy chain using ensemble retriever with fact-focused retrieval."""

    def factual_retrieval(factual_query: str) -> str:
        """Retrieve documents using factual query with emphasis on precise information."""
        docs = ensemble_retriever_tool.retrieve(query=factual_query, methods=["sparse", "dense", "graph"], weights=[0.5, 0.3, 0.2], max_documents=8)  # Prioritize sparse for exact facts  # Favor sparse for factual precision
        return format_docs(docs)

    return generate_factual_query | factual_retrieval
