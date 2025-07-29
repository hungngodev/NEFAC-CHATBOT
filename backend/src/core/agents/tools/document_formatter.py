from langchain_core.documents import Document


def format_docs(docs: list[Document]) -> str:
    """Format documents with default values for missing metadata."""
    formatted_docs: list[str] = []
    for i, doc in enumerate(docs):
        original_metadata = doc.metadata
        title = original_metadata.get("title", "Unknown Source")
        source_url = original_metadata.get("source", "")
        doc_type = original_metadata.get("type", "unknown")
        timestamp = original_metadata.get("page", None)

        # Store metadata for potential source creation
        metadata = {
            "source_id": i + 1,
            "title": title,
            "type": doc_type,
            "link": (f"{source_url}&t={timestamp}s" if doc_type == "youtube" and timestamp else source_url),
            "timestamp_seconds": timestamp if doc_type == "youtube" else None,
            "summary": original_metadata.get("summary", None),
        }

        # Format the document with the new metadata
        formatted_doc = "\n".join(
            [
                f"title: {metadata['title']}",
                f"summary: {metadata['summary']}",
                f"content: {doc.page_content}",
            ]
        )

        formatted_docs.append(formatted_doc)

    return "\n\n".join(formatted_docs) if formatted_docs else "No documents available"
