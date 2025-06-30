from typing import Any, Dict

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config.constant import MODEL_NAME
from src.core.agents.state import AgentState

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
            extracted_data.append({"title": doc.metadata.get("title"), "source_url": doc.metadata.get("source_url"), "page_content_snippet": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content})

        # In a more advanced scenario, an LLM would be used here to extract structured info
        # based on a predefined schema or user's intent.
        # For now, this is a basic example.

        return {"extracted_info": extracted_data, "documents": documents}
    except Exception as e:
        return {"error": f"Error during information extraction: {e}", "documents": state.documents}


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


def context_summarization_tool(state: AgentState) -> Dict[str, Any]:
    """
    Summarizes lengthy retrieved documents or passages to fit within the LLM's context window.
    """
    try:
        documents = state.documents
        if not documents:
            return {"summarized_content": "No documents to summarize.", "documents": []}

        summarized_docs = []
        for doc in documents:
            # Only summarize if the document content is long
            if len(doc.page_content) > 500:  # Arbitrary length for summarization
                summary = summarization_chain.invoke({"document_content": doc.page_content})
                summarized_docs.append(Document(page_content=summary, metadata=doc.metadata))
            else:
                summarized_docs.append(doc)  # Keep original if short

        return {"summarized_content": summarized_docs, "documents": summarized_docs}
    except Exception as e:
        return {"error": f"Error during context summarization: {e}", "documents": state.documents}


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
            citation_info = {
                "title": doc.metadata.get("title", "N/A"),
                "source_url": doc.metadata.get("source_url", "N/A"),
                "page_number": doc.metadata.get("page_number", "N/A"),
                "document_id": doc.metadata.get("id", "N/A"),
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

    # Step 2: Context Summarization
    summarized_result = context_summarization_tool(state)
    if summarized_result.get("error"):
        return summarized_result
    state.summarized_content = summarized_result.get("summarized_content")

    # Step 3: Citation/Source Attribution
    citation_result = citation_attribution_tool(state)
    if citation_result.get("error"):
        return citation_result
    state.citations = citation_result.get("citations")

    return {"documents": state.documents, "extracted_info": state.extracted_info, "summarized_content": state.summarized_content, "citations": state.citations}
