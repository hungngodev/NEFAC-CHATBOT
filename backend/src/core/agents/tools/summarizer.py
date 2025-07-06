from typing import List, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config.constant import MODEL_NAME
from src.schemas.core_types import AgentState

# --- LLM Setup ---
llm = ChatOpenAI(temperature=0, model=MODEL_NAME)

# --- Context Summarization Tool ---
summarization_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a helpful assistant that summarizes documents."),
        (
            "human",
            """Please summarize the following document:

{document_content}

Summary:""",
        ),
    ]
)
summarization_chain = summarization_prompt | llm | StrOutputParser()


class SummarizerAgentOutput(TypedDict):
    documents: List[Document]
    error: Optional[str]


def summarizer_agent(state: AgentState) -> SummarizerAgentOutput:
    """
    Summarizes lengthy retrieved documents or passages to fit within the LLM's context window.
    """
    try:
        documents = state.get("documents", [])
        if not documents:
            return {"documents": []}

        summarized_docs = []
        for doc in documents:
            if isinstance(doc, Document) and len(doc.page_content) > 500:
                summary = summarization_chain.invoke({"document_content": doc.page_content})
                summarized_docs.append(Document(page_content=summary, metadata=doc.metadata))
            else:
                summarized_docs.append(doc)

        return {"documents": summarized_docs}
    except Exception as e:
        return {"error": f"Error during context summarization: {e}"}
