from typing import Optional

from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.language_models.base import BaseLanguageModel

context_prompt_template = ChatPromptTemplate.from_template(
    """<document>\n{document}\n</document>\nHere is the chunk we want to situate within the whole document\n<chunk>\n{chunk}\n</chunk>\nPlease generate a short succinct context summary to situate this text chunk within the overall document to enhance search retrieval, two or three sentences max. The chunk contains merged content from different document sections, so focus on the main topics and concepts rather than sequential flow. Answer only with the succinct context and nothing else."""
)


def contextualize_chunk(
    whole_document: str,
    chunk: str,
    metadata: Optional[dict],
    chat_model: BaseLanguageModel,
) -> Document:
    prompt = context_prompt_template.format(document=whole_document, chunk=chunk)
    response = chat_model.invoke(prompt)
    context = response if isinstance(response, str) else response.content
    meta = dict(metadata) if metadata else {}
    meta["context"] = context
    return Document(page_content=chunk, metadata=meta)
