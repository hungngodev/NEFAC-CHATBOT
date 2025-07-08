from langchain_openai import ChatOpenAI
from langmem.short_term import SummarizationNode

from backend.src.config.constant import SUMMARY_MODEL_NAME

model = ChatOpenAI(model=SUMMARY_MODEL_NAME)

summarization_node = SummarizationNode(
    model=model.bind(max_tokens=256),
    max_tokens=256,
    max_tokens_before_summary=256,
    max_summary_tokens=128,
)
