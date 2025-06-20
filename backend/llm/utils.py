import logging
from typing import List
from langchain_core.documents import Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_docs(docs: List[Document]) -> str:
    """Format documents with default values for missing metadata."""
    formatted_docs: List[str] = []
    for i, doc in enumerate(docs):
        metadata = doc.metadata
        title = metadata.get('title', 'Unknown Source')
        source_url = metadata.get('source', '')
        doc_type = metadata.get('type', 'unknown')
        timestamp = metadata.get('page', None)
        
        # Store metadata for potential source creation
        metadata ={
            "source_id": i+1,
            "title": title,
            "type": doc_type,
            "link": f"{source_url}&t={timestamp}s" if doc_type == 'youtube' and timestamp else source_url,
            "timestamp_seconds": timestamp if doc_type == 'youtube' else None,
            "summary": metadata.get('summary', None)
        }
        
        # Format the document with the new metadata
        formatted_doc = "\n".join([
            f"content: {doc.page_content}",
            f"title: {metadata['title']}",
            f"type: {metadata['type']}",
            f"link: {metadata['link']}",
            f"timestamp_seconds: {metadata['timestamp_seconds']}",
            f"summary: {metadata['summary']}"
        ])
        
        formatted_docs.append(formatted_doc)
    
    return "\n\n".join(formatted_docs) if formatted_docs else "No documents available"