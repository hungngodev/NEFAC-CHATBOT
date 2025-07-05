from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.config.prompts import CONTEXTUAL_STRATEGY_PROMPT
from src.core.agents.tools.document_formatter import format_docs
from src.load_env import load_env

load_env()

model = ChatOpenAI(temperature=0, model=QUERY_TRANSLATION_MODEL_NAME)
contextual_strategy_prompt = ChatPromptTemplate.from_template(CONTEXTUAL_STRATEGY_PROMPT)

generate_contextual_query = contextual_strategy_prompt | model | StrOutputParser()


def get_contextual_strategy_chain(retriever) -> Any:
    return generate_contextual_query | retriever | format_docs
