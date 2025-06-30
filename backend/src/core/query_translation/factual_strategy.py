from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.config.prompts import FACTUAL_STRATEGY_PROMPT
from src.core.utils import format_docs
from src.load_env import load_env

load_env()

model = ChatOpenAI(temperature=0, model=QUERY_TRANSLATION_MODEL_NAME)
factual_strategy_prompt = ChatPromptTemplate.from_template(FACTUAL_STRATEGY_PROMPT)

generate_factual_query = factual_strategy_prompt | model | StrOutputParser()


def get_factual_strategy_chain(retriever):
    return generate_factual_query | retriever | format_docs
