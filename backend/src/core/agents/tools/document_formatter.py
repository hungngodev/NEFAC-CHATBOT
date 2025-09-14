import re

from langchain_core.documents import Document


def _safe_meta(doc: Document) -> dict:
    try:
        return dict(getattr(doc, "metadata", {}) or {})
    except Exception:
        return {}


def format_docs(docs: list[Document]) -> str:
    """Format documents using ingestion metadata conventions.

    Ingestion provides base metadata keys like:
    - title, filename, source_url, link, uri
    - file_extension, transcript_type (e.g., "youtube"), start_time/end_time for transcripts
    - summary (optional, may be added by upstream summarizers)
    The document page_content already includes contextualized text.
    """
    if not docs:
        return "No documents available"

    formatted_docs: list[str] = []
    for i, doc in enumerate(docs, start=1):
        meta = _safe_meta(doc)

        title = meta.get("title") or meta.get("source") or meta.get("filename")

        # Prefer explicit source_url, then link, then uri
        base_link = meta.get("source_url") or meta.get("link") or meta.get("uri") or ""

        # Detect youtube transcript and add timestamp if present
        is_youtube = (meta.get("transcript_type") == "youtube") or ("youtube" in (base_link or ""))
        start_time = meta.get("start_time")
        if is_youtube and base_link and isinstance(start_time, (int, float)):
            link = f"{base_link}&t={int(start_time)}s"
        else:
            link = base_link

        # If title still missing, try to derive from page_content's Context line
        if not title and isinstance(doc.page_content, str):
            m = re.search(r"Document:\s*(.+?)(?:\s*\||\n|$)", doc.page_content)
            if m:
                title = m.group(1).strip()
        title = title or "Unknown Source"

        summary = meta.get("summary")

        parts = [f"title: {title}"]
        if summary:
            parts.append(f"summary: {summary}")
        if link:
            parts.append(f"link: {link}")
        parts.append(f"content: {doc.page_content}")

        formatted_docs.append("\n".join(parts))

    return "\n\n".join(formatted_docs)
