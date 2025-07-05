from typing import Any, Dict

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

from src.config.constant import MODEL_NAME
from src.schemas.state import AgentState

# --- LLM Setup ---
llm = ChatOpenAI(temperature=0, model=MODEL_NAME)


# --- Information Extraction Tool ---
def information_extraction_tool(state: AgentState) -> Dict[str, Any]:
    """
    Extracts specific entities, facts, or relationships from retrieved documents.
    """
    try:
        documents = state.documents
        if not documents:
            return {"extracted_info": "No documents to extract information from.", "documents": []}

        # Example: Extracting titles and sources from documents
        extracted_data = []
        for doc in documents:
            if isinstance(doc, Document):
                extracted_data.append({"title": doc.metadata.get("title"), "source_url": doc.metadata.get("source_url"), "page_content_snippet": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content})
            else:
                extracted_data.append({"title": None, "source_url": None, "page_content_snippet": str(doc)[:200] + "..." if len(str(doc)) > 200 else str(doc)})

        # In a more advanced scenario, an LLM would be used here to extract structured info
        # based on a predefined schema or user's intent.
        # For now, this is a basic example.

        return {"extracted_info": extracted_data, "documents": documents}
    except Exception as e:
        return {"error": f"Error during information extraction: {e}", "documents": state.documents}


# --- Context Summarization Tool ---


# --- Citation/Source Attribution Tool ---
def citation_attribution_tool(state: AgentState) -> Dict[str, Any]:
    """
    Identifies and provides the source (document title, URL, page number) for generated answers.
    This tool primarily processes the documents to make source information readily available.
    """
    try:
        documents = state.documents
        if not documents:
            return {"citations": "No documents to generate citations from.", "documents": []}

        citations = []
        for doc in documents:
            if isinstance(doc, Document):
                citation_info = {
                    "title": doc.metadata.get("title", "N/A"),
                    "source_url": doc.metadata.get("source_url", "N/A"),
                    "page_number": doc.metadata.get("page_number", "N/A"),
                    "document_id": doc.metadata.get("id", "N/A"),
                }
            else:
                citation_info = {
                    "title": "N/A",
                    "source_url": "N/A",
                    "page_number": "N/A",
                    "document_id": "N/A",
                }
            citations.append(citation_info)

        return {"citations": citations, "documents": documents}
    except Exception as e:
        return {"error": f"Error during citation attribution: {e}", "documents": state.documents}


# --- Main Context Processor Agent ---
def context_processor_agent(state: AgentState) -> Dict[str, Any]:
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

    # Step 2: Citation/Source Attribution
    citation_result = citation_attribution_tool(state)
    if citation_result.get("error"):
        return citation_result
    state.citations = citation_result.get("citations")

    return {"documents": state.documents, "extracted_info": state.extracted_info, "citations": state.citations}
