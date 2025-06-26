from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from llm.constant import QUERY_TRANSLATION_MODEL_NAME
from llm.utils import format_docs
from load_env import load_env
from prompts.base import CONTEXTUAL_STRATEGY_PROMPT

load_env()

model = ChatOpenAI(temperature=0, model=QUERY_TRANSLATION_MODEL_NAME)
contextual_strategy_prompt = ChatPromptTemplate.from_template(
    CONTEXTUAL_STRATEGY_PROMPT
)

generate_contextual_query = contextual_strategy_prompt | model | StrOutputParser()


def get_contextual_strategy_chain(retriever):
    return generate_contextual_query | retriever | format_docs
