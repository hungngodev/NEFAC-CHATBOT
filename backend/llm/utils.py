import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_docs(docs):
    """Format documents with default values for missing metadata."""
    formatted_docs = []
    
    for doc in docs:
        # Safely extract metadata with defaults
        metadata = {
            "source": doc.metadata.get("source", "N/A"),
            "page": doc.metadata.get("page", "N/A"),
            "title": doc.metadata.get("title", "N/A"),
            "nefac_category": doc.metadata.get("nefac_category", []),
            "resource_type": doc.metadata.get("resource_type", []),
            "audience": doc.metadata.get("audience", [])
        }
        
        # Format the document
        formatted_doc = "\n".join([
            f"content: {doc.page_content}",
            f"source: {metadata['source']}",
            f"page: {metadata['page']}",
            f"title: {metadata['title']}",
            f"nefac_category: {metadata['nefac_category']}",
            f"resource_type: {metadata['resource_type']}",
            f"audience: {metadata['audience']}"
        ])
        
        formatted_docs.append(formatted_doc)
    
    return "\n\n".join(formatted_docs) if formatted_docs else "No documents available"