from datetime import datetime
from typing import List, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config.constant import MODEL_NAME
from src.core.agents.tools.retrieval.memory_search import add_memory_to_pinecone, retrieve_memory_from_pinecone
from src.schemas.core_types import (
    AgentState,
    CitationAttributionOutput,
    ContextSummarizationOutput,
    DocumentCitation,
    ExtractedInformation,
    InformationExtractionOutput,
    SessionMemoryEntry,
    create_citation,
    create_extracted_info,
    create_memory_entry,
)
from src.schemas.core_types import (
    ContextProcessorOutput as CentralizedContextProcessorOutput,
)

# --- LLM Setup ---
llm = ChatOpenAI(temperature=0, model=MODEL_NAME)


# Legacy compatibility
ContextProcessorOutput = CentralizedContextProcessorOutput


class ContextProcessorOutput(TypedDict):
    documents: List[Document]
    extracted_info: Optional[List[ExtractedInformation]]
    summarized_content: Optional[List[Document]]
    citations: Optional[List[DocumentCitation]]
    session_memory: Optional[List[SessionMemoryEntry]]
    error: Optional[str]


# --- Information Extraction Tool ---
def information_extraction_tool(state: AgentState) -> InformationExtractionOutput:
    """
    Extracts specific entities, facts, or relationships from retrieved documents.
    """
    try:
        documents = state.documents
        if not documents:
            return {"extracted_info": None, "documents": []}

        # Extract structured information using the new types
        extracted_data = []
        for doc in documents:
            if isinstance(doc, Document):
                snippet = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content

                # Create structured extracted information
                extracted_info = create_extracted_info(
                    title=doc.metadata.get("title"), source_url=doc.metadata.get("source_url"), content_snippet=snippet, entities=[], key_facts=[snippet], confidence_score=0.8, extraction_method="basic_metadata"  # Could be enhanced with NER  # Basic fact extraction  # Default confidence
                )
                extracted_data.append(extracted_info)

                # Store in memory if session exists
                if hasattr(state, "session_id") and state.session_id:
                    fact = f"Title: {doc.metadata.get('title')} | Source: {doc.metadata.get('source_url')} | Snippet: {snippet}"
                    add_memory_to_pinecone(state.session_id, fact, metadata={"type": "fact", "title": doc.metadata.get("title"), "source_url": doc.metadata.get("source_url")})
            else:
                # Handle non-Document objects
                extracted_info = create_extracted_info(content_snippet=str(doc), extraction_method="string_conversion")
                extracted_data.append(extracted_info)

        return {"extracted_info": extracted_data, "documents": documents}
    except Exception as e:
        return {"error": f"Error during information extraction: {e}", "documents": getattr(state, "documents", [])}


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


def context_summarization_tool(state: AgentState) -> ContextSummarizationOutput:
    """
    Summarizes lengthy retrieved documents or passages to fit within the LLM's context window.
    """
    try:
        documents = state.documents
        if not documents:
            return {"summarized_content": "No documents to summarize.", "documents": []}

        summarized_docs = []
        for doc in documents:
            if isinstance(doc, Document):
                # Only summarize if the document content is long
                if len(doc.page_content) > 500:  # Arbitrary length for summarization
                    summary = summarization_chain.invoke({"document_content": doc.page_content})
                    summarized_docs.append(Document(page_content=summary, metadata=doc.metadata))
                else:
                    summarized_docs.append(doc)  # Keep original if short
            else:
                summarized_docs.append(doc)  # If doc is a string, just append as-is

        return {"summarized_content": summarized_docs, "documents": summarized_docs}
    except Exception as e:
        return {"error": f"Error during context summarization: {e}", "documents": state.documents}


# --- Citation/Source Attribution Tool ---
def citation_attribution_tool(state: AgentState) -> CitationAttributionOutput:
    """
    Identifies and provides the source (document title, URL, page number) for generated answers.
    This tool primarily processes the documents to make source information readily available.
    """
    try:
        documents = state.documents
        if not documents:
            return {"citations": [], "documents": []}

        citations = []
        for doc in documents:
            if isinstance(doc, Document):
                # Create structured citation using the new types
                citation = create_citation(
                    title=doc.metadata.get("title", "Unknown Document"),
                    source_url=doc.metadata.get("source_url", ""),
                    page_number=doc.metadata.get("page_number"),
                    document_id=doc.metadata.get("id", ""),
                    citation_type="document",
                    access_date=datetime.now(),
                    authors=doc.metadata.get("authors", []),
                    relevance_score=doc.metadata.get("relevance_score"),
                )
            else:
                # Handle non-Document objects
                citation = create_citation(title=str(doc)[:50] + "..." if len(str(doc)) > 50 else str(doc), source_url="", citation_type="text_snippet")
            citations.append(citation)

        return {"citations": citations, "documents": documents}
    except Exception as e:
        return {"error": f"Error during citation attribution: {e}", "documents": getattr(state, "documents", [])}


# --- Main Context Processor Agent ---
def context_processor_agent(state: AgentState) -> ContextProcessorOutput:
    """
    Main agent for processing and augmenting retrieved context.
    Delegates to specific tools based on the workflow needs.
    """
    # This agent would typically be orchestrated by a higher-level agent (e.g., Orchestrator Agent)
    # to decide which tools to apply based on the overall task.
    # For demonstration, we'll apply all of them sequentially.

    # Step 1: Information Extraction
    extracted_result = information_extraction_tool(state)
    if extracted_result.get("error"):
        return extracted_result
    state.extracted_info = extracted_result.get("extracted_info")

    # Step 2: Context Summarization
    summarization_result = context_summarization_tool(state)
    if summarization_result.get("error"):
        return summarization_result
    state.summarized_content = summarization_result.get("summarized_content")

    # Step 3: Citation/Source Attribution
    citation_result = citation_attribution_tool(state)
    if citation_result.get("error"):
        return citation_result
    state.citations = citation_result.get("citations")

    # Retrieve top relevant session memory from Pinecone and add to state
    session_memory_entries = []
    if hasattr(state, "session_id") and state.session_id:
        raw_memory = retrieve_memory_from_pinecone(state.session_id, state.query, top_k=5)

        # Convert raw memory to structured SessionMemoryEntry objects
        for i, memory_item in enumerate(raw_memory):
            if isinstance(memory_item, dict):
                memory_entry = create_memory_entry(
                    memory_id=memory_item.get("id", f"mem_{i}"),
                    content=memory_item.get("content", str(memory_item)),
                    user_id=state.user_id if hasattr(state, "user_id") else "unknown",
                    session_id=state.session_id,
                    memory_type=memory_item.get("type", "interaction"),
                    relevance_score=memory_item.get("score", 0.5),
                )
                session_memory_entries.append(memory_entry)

        state.session_memory = session_memory_entries

    return {"documents": state.documents, "extracted_info": state.extracted_info, "summarized_content": state.summarized_content, "citations": state.citations, "session_memory": session_memory_entries}
