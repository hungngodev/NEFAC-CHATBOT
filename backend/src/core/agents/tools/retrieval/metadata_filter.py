import datetime
from typing import Any, Callable, Dict, List

from langchain_core.documents import Document


def _parse_date_from_metadata(doc_metadata: Dict[str, Any]) -> datetime.date | None:
    doc_date_str = doc_metadata.get("date")
    if doc_date_str:
        try:
            return datetime.datetime.strptime(doc_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


# Assuming these are the Pydantic models for your metadata


def _filter_by_author_name(doc_metadata: Dict[str, Any], filter_value: str) -> bool:
    author = doc_metadata.get("author")
    return bool(author and author.get("name") == filter_value)


def _filter_by_category_name(doc_metadata: Dict[str, Any], filter_value: str) -> bool:
    categories = doc_metadata.get("categories")
    return bool(categories and any(cat.get("name") == filter_value for cat in categories))


def _filter_by_tags(doc_metadata: Dict[str, Any], filter_value: List[str]) -> bool:
    # Checks if any of the document's tags are present in the filter_value list
    tags = doc_metadata.get("tags")
    return bool(tags and any(tag in tags for tag in filter_value))


def _filter_by_date_range(doc_metadata: Dict[str, Any], filter_value: tuple) -> bool:
    doc_date_str = doc_metadata.get("date")
    if not doc_date_str or not isinstance(filter_value, tuple) or len(filter_value) != 2:
        return False
    try:
        doc_date = datetime.datetime.strptime(doc_date_str, "%Y-%m-%d").date()
        start_date = datetime.datetime.strptime(filter_value[0], "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(filter_value[1], "%Y-%m-%d").date()
        return start_date <= doc_date <= end_date
    except ValueError:
        return False


# Mapping of special filter keys to their handler functions
_FILTER_HANDLERS: Dict[str, Callable[[Dict[str, Any], Any], bool]] = {
    "author_name": _filter_by_author_name,
    "category_name": _filter_by_category_name,
    "tags": _filter_by_tags,
    "date_range": _filter_by_date_range,
}


def filter_documents_by_metadata(documents: List[Document], filters: Dict[str, Any]) -> List[Document]:
    """
    Filters a list of LangChain Document objects based on provided metadata filters.
    Filters can be applied to common metadata fields or type-specific metadata fields.

    Args:
        documents: A list of LangChain Document objects.
        filters: A dictionary where keys are metadata field names and values are
                 the desired filter values.

    Returns:
        A new list of Document objects that match all specified filters.
    """
    if not filters:
        return documents

    filtered_docs = []
    for doc in documents:
        doc_metadata = doc.metadata
        all_filters_match = True

        for filter_key, filter_value in filters.items():
            handler = _FILTER_HANDLERS.get(filter_key)
            if handler:
                if not handler(doc_metadata, filter_value):
                    all_filters_match = False
                    break
            else:
                # Direct metadata field match
                if doc_metadata.get(filter_key) != filter_value:
                    all_filters_match = False
                    break

        if all_filters_match:
            filtered_docs.append(doc)

    return filtered_docs


def prioritize_documents_by_metadata(documents: List[Document], priorities: List[Dict[str, Any]]) -> List[Document]:
    """
    Prioritizes a list of LangChain Document objects based on provided metadata rules.
    Each rule can specify a field, a value to match, and a boost score.
    Documents matching higher priority rules will appear earlier in the list.
    Documents are also sorted by a calculated score.

    Args:
        documents: A list of LangChain Document objects.
        priorities: A list of dictionaries, each defining a priority rule.
                    Example: [{"field": "source", "value": "nefac.org", "boost": 10},
                              {"field": "date", "order": "desc"}]

    Returns:
        A new list of Document objects, prioritized according to the rules.
    """
    if not priorities:
        return documents

    scored_docs = []
    for doc in documents:
        score = 0
        doc_metadata = doc.metadata

        for rule in priorities:
            field = rule.get("field")
            value = rule.get("value")
            boost = rule.get("boost", 0)
            order = rule.get("order")

            if field:
                if field == "date" and order:
                    doc_date = _parse_date_from_metadata(doc_metadata)
                    if doc_date:
                        doc.metadata["_date_score"] = doc_date.toordinal()
                    else:
                        doc.metadata["_date_score"] = 0  # Default for invalid dates
                elif doc_metadata.get(field) == value:
                    score += boost

            # Add a base score for sorting if no specific boost is applied
            # This ensures documents with higher initial relevance (e.g., from vector search)
            # are still considered if no metadata priority applies.
            # Assuming a 'relevance_score' might be added by the retriever
            score += doc_metadata.get("relevance_score", 0)

        scored_docs.append((score, doc))

    # Sort documents: first by the calculated score (descending), then by date (if available and ordered)
    # For date, if order is 'desc', higher date_score means higher priority.
    # If order is 'asc', lower date_score means higher priority.
    def sort_key(item):
        score, doc = item
        date_score = doc.metadata.get("_date_score")

        # Default sort by score (descending)
        primary_sort = -score

        # Secondary sort by date if applicable
        secondary_sort = 0
        for rule in priorities:
            if rule.get("field") == "date" and rule.get("order") == "desc" and date_score is not None:
                secondary_sort = -date_score  # Newest first
                break
            elif rule.get("field") == "date" and rule.get("order") == "asc" and date_score is not None:
                secondary_sort = date_score  # Oldest first
                break

        return (primary_sort, secondary_sort)

    scored_docs.sort(key=sort_key)

    return [doc for score, doc in scored_docs]


# Example Usage (for testing purposes)
if __name__ == "__main__":
    # Dummy Document objects with various metadata
    doc1 = Document(
        page_content="This is a document about FOIA.",
        metadata={
            "id": "1",
            "title": "FOIA Basics",
            "filename": "foia_basics.pdf",
            "source_url": "http://example.com/foia.pdf",
            "date": "2023-01-15",
            "mime_type": "application/pdf",
            "file_type_category": "PDF",
            "author": {"name": "John Doe", "slug": "john-doe", "uri": "http://example.com/john-doe"},
            "categories": [{"name": "FOIA", "slug": "foia"}],
            "tags": ["freedom of information", "government"],
            "page_number": 1,
            "relevance_score": 0.8,
        },
    )

    doc2 = Document(
        page_content="An article on open meetings.",
        metadata={
            "id": "2",
            "title": "Open Meetings Act",
            "filename": "open_meetings.html",
            "source_url": "http://example.com/open_meetings.html",
            "date": "2024-03-10",
            "mime_type": "text/html",
            "file_type_category": "Content",
            "author": {"name": "Jane Smith", "slug": "jane-smith", "uri": "http://example.com/jane-smith"},
            "categories": [{"name": "Open Government", "slug": "open-government"}],
            "tags": ["transparency", "meetings"],
            "relevance_score": 0.9,
        },
    )

    doc3 = Document(
        page_content="A YouTube video transcript about public records.",
        metadata={
            "id": "3",
            "title": "Public Records Video",
            "video_id": "xyz123",
            "source_url": "http://youtube.com/watch?v=xyz123",
            "date": "2023-11-01",
            "mime_type": "video/youtube",
            "file_type_category": "YouTube",
            "uploader": "NEFAC Channel",
            "tags": ["public records", "video"],
            "duration": 1200,
            "relevance_score": 0.7,
        },
    )

    doc4 = Document(
        page_content="Another FOIA document.",
        metadata={
            "id": "4",
            "title": "Advanced FOIA",
            "filename": "advanced_foia.pdf",
            "source_url": "http://example.com/advanced_foia.pdf",
            "date": "2023-02-20",
            "mime_type": "application/pdf",
            "file_type_category": "PDF",
            "author": {"name": "John Doe", "slug": "john-doe", "uri": "http://example.com/john-doe"},
            "categories": [{"name": "FOIA", "slug": "foia"}],
            "tags": ["freedom of information"],
            "page_number": 5,
            "relevance_score": 0.85,
        },
    )

    documents = [doc1, doc2, doc3, doc4]

    # Test cases for filter_documents_by_metadata
    print("--- Test Case 1: Filter by mime_type (PDF) ---")
    filters1 = {"mime_type": "application/pdf"}
    result1 = filter_documents_by_metadata(documents, filters1)
    for doc in result1:
        print(f"- {doc.metadata['title']} ({doc.metadata['mime_type']})")
    # Expected: FOIA Basics, Advanced FOIA

    print("\n--- Test Case 2: Filter by category name (FOIA) ---")
    filters2 = {"category_name": "FOIA"}
    result2 = filter_documents_by_metadata(documents, filters2)
    for doc in result2:
        print(f"- {doc.metadata['title']} (Category: {doc.metadata['categories'][0]['name']})")
    # Expected: FOIA Basics, Advanced FOIA

    print("\n--- Test Case 3: Filter by author name (John Doe) ---")
    filters3 = {"author_name": "John Doe"}
    result3 = filter_documents_by_metadata(documents, filters3)
    for doc in result3:
        print(f"- {doc.metadata['title']} (Author: {doc.metadata['author']['name']})")
    # Expected: FOIA Basics, Advanced FOIA

    print("\n--- Test Case 4: Filter by tags (freedom of information) ---")
    filters4 = {"tags": ["freedom of information"]}
    result4 = filter_documents_by_metadata(documents, filters4)
    for doc in result4:
        print(f"- {doc.metadata['title']} (Tags: {doc.metadata['tags']})")
    # Expected: FOIA Basics, Advanced FOIA

    print("\n--- Test Case 5: Combined filters (PDF by John Doe) ---")
    filters5 = {"mime_type": "application/pdf", "author_name": "John Doe"}
    result5 = filter_documents_by_metadata(documents, filters5)
    for doc in result5:
        print(f"- {doc.metadata['title']} (Mime: {doc.metadata['mime_type']}, Author: {doc.metadata['author']['name']})")
    # Expected: FOIA Basics, Advanced FOIA

    print("\n--- Test Case 6: No matching documents ---")
    filters6 = {"mime_type": "image/jpeg"}
    result6 = filter_documents_by_metadata(documents, filters6)
    print(f"Result: {len(result6)} documents")
    # Expected: 0 documents

    print("\n--- Test Case 7: Filter by specific PDF metadata (page_number) ---")
    filters7 = {"mime_type": "application/pdf", "page_number": 1}
    result7 = filter_documents_by_metadata(documents, filters7)
    for doc in result7:
        print(f"- {doc.metadata['title']} (Page: {doc.metadata.get('page_number')})")
    # Expected: FOIA Basics

    print("\n--- Test Case 8: Filter by YouTube metadata (uploader) ---")
    filters8 = {"file_type_category": "YouTube", "uploader": "NEFAC Channel"}
    result8 = filter_documents_by_metadata(documents, filters8)
    for doc in result8:
        print(f"- {doc.metadata['title']} (Uploader: {doc.metadata.get('uploader')})")
    # Expected: Public Records Video

    print("\n--- Test Case 9: Filter by date range (2023 content) ---")
    filters9 = {"date_range": ("2023-01-01", "2023-12-31")}
    result9 = filter_documents_by_metadata(documents, filters9)
    for doc in result9:
        print(f"- {doc.metadata['title']} (Date: {doc.metadata['date']})")
    # Expected: FOIA Basics, Public Records Video, Advanced FOIA

    # Test cases for prioritize_documents_by_metadata
    print("\n--- Test Case 10: Prioritize by source (nefac.org) with boost ---")
    priorities1 = [{"field": "source", "value": "nefac.org", "boost": 5}]
    # Add source to docs for testing
    doc1.metadata["source"] = "nefac.org"
    doc2.metadata["source"] = "external.com"
    doc3.metadata["source"] = "nefac.org"
    doc4.metadata["source"] = "external.com"

    prioritized_docs1 = prioritize_documents_by_metadata(documents, priorities1)
    for doc in prioritized_docs1:
        print(f"- {doc.metadata['title']} (Source: {doc.metadata.get('source')}, Score: {doc.metadata.get('relevance_score')})")
    # Expected: doc1, doc3 (boosted), then doc2, doc4

    print("\n--- Test Case 11: Prioritize by date (descending) ---")
    priorities2 = [{"field": "date", "order": "desc"}]
    prioritized_docs2 = prioritize_documents_by_metadata(documents, priorities2)
    for doc in prioritized_docs2:
        print(f"- {doc.metadata['title']} (Date: {doc.metadata['date']})")
    # Expected: doc2 (2024), then doc3, doc4, doc1 (2023)

    print("\n--- Test Case 12: Prioritize by category (Open Government) with boost and then by date desc ---")
    priorities3: List[Dict[str, Any]] = [{"field": "category_name", "value": "Open Government", "boost": 10}, {"field": "date", "order": "desc"}]
    prioritized_docs3 = prioritize_documents_by_metadata(documents, priorities3)
    for doc in prioritized_docs3:
        categories = doc.metadata.get("categories")
        category_name = categories[0]["name"] if categories else "N/A"
        print(f"- {doc.metadata['title']} (Category: {category_name}, Date: {doc.metadata['date']})")
    # Expected: doc2 (boosted and newest), then others by date desc.
