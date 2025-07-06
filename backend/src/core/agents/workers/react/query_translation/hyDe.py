from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.config.prompts import HYDE_FINAL_PROMPT, HYDE_GENERATION_PROMPT
from src.core.agents.tools.document_formatter import format_docs
from src.core.agents.tools.retrieval.retrieval_tools import ensemble_retriever_tool
from src.load_env import load_env

load_env()

model = ChatOpenAI(temperature=0, model=QUERY_TRANSLATION_MODEL_NAME)

hyde_prompt = ChatPromptTemplate.from_template(HYDE_GENERATION_PROMPT)

hyde_generation = hyde_prompt | model | StrOutputParser()

final_prompt = ChatPromptTemplate.from_template(HYDE_FINAL_PROMPT)


def get_hyDe_chain(retriever=None) -> Runnable:
    """HyDE chain using ensemble retriever with hypothetical document generation."""

    def hyde_retrieval(hypothetical_doc: str) -> str:
        """Retrieve documents based on hypothetical document."""
        docs = ensemble_retriever_tool.retrieve(query=hypothetical_doc, methods=["dense", "sparse"], weights=[0.7, 0.3], max_documents=8)  # Dense for semantic similarity, sparse for key terms  # Favor dense for hypothetical document matching
        return format_docs(docs)

    hyde_rag_chain = (
        # Generate hypothetical document and retrieve
        {"context": hyde_generation | hyde_retrieval, "question": lambda x: x["question"]}
        | final_prompt
        | model
        | StrOutputParser()
    )
    return hyde_rag_chain
