"""
Document post-processing functions, including filtering and prioritization.
This module consolidates logic from the previously deleted metadata_filter.py.
"""

import datetime

from langchain_core.documents import Document


def _parse_date_from_metadata(doc_metadata: dict[str, str | int | float | bool]) -> datetime.date | None:
    """Safely parse a date from document metadata."""
    doc_date_str = doc_metadata.get("date")
    if doc_date_str and isinstance(doc_date_str, str):
        return datetime.datetime.strptime(doc_date_str, "%Y-%m-%d").date()
    return None


def _matches_filters(doc: Document, filters: dict[str, str | int | float | bool | list[str, tuple]]) -> bool:
    """Check if a single document matches the provided filters."""
    if not filters:
        return True

    doc_metadata = doc.metadata
    for key, value in filters.items():
        # Add more complex filter handlers here if needed
        if doc_metadata.get(key) != value:
            return False
    return True


def _calculate_priority_score(doc: Document, priorities: list[dict[str, str | int | float]]) -> int:
    """Calculate a priority score for a document based on rules."""
    score = 0
    if not priorities:
        return score

    doc_metadata = doc.metadata
    for rule in priorities:
        field = rule.get("field")
        value = rule.get("value")
        boost = rule.get("boost", 0)

        if field and doc_metadata.get(field) == value:
            score += boost

    # Add base relevance score if present
    score += doc_metadata.get("relevance_score", 0)
    return score


def filter_and_prioritize_documents(documents: list[Document], filters: dict[str, str | int | float | bool | list[str, tuple]] = None, priorities: list[dict[str, str | int | float]] = None) -> list[Document]:
    """
    Filters and prioritizes a list of documents in a single pass.

    Args:
        documents: A list of LangChain Document objects.
        filters: A dictionary of metadata fields and values to filter by.
        priorities: A list of rules to boost document scores for prioritization.

    Returns:
        A new list of Document objects, filtered and sorted.
    """
    filters = filters or {}
    priorities = priorities or []

    # 1. Filter documents
    filtered_docs = [doc for doc in documents if _matches_filters(doc, filters)]

    # 2. Score and sort the filtered documents
    if not priorities:
        return filtered_docs

    scored_docs = []
    for doc in filtered_docs:
        score = _calculate_priority_score(doc, priorities)

        # Handle date-based sorting
        date_sort_key = None
        for rule in priorities:
            if rule.get("field") == "date" and rule.get("order"):
                doc_date = _parse_date_from_metadata(doc.metadata)
                if doc_date:
                    # For descending, we want newest first, so a larger ordinal is better.
                    # We negate it for sorting to put higher values first.
                    date_sort_key = -doc_date.toordinal() if rule["order"] == "desc" else doc_date.toordinal()
                break

        scored_docs.append((score, date_sort_key, doc))

    # Sort by score (desc), then by date, then by original order
    scored_docs.sort(key=lambda x: (x[0], x[1] if x[1] is not None else float("inf")), reverse=True)

    return [doc for score, date_key, doc in scored_docs]
