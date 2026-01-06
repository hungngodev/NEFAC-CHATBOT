"""Metadata Filter Tool for pre-retrieval document filtering.

This tool enables filtering documents by metadata attributes BEFORE
vector search, allowing for more precise resource discovery.
"""

import json
import logging
import os
from typing import Any, Dict

from langchain_core.tools import tool
from pydantic import Field

logger = logging.getLogger(__name__)


def parse_filter_key(key: str) -> tuple[str, str]:
    """Parse a filter key into field name and operator.

    Supports suffixes: __eq, __gte, __lte, __contains, __in, __exists

    Args:
        key: Filter key like 'date__gte' or 'category'

    Returns:
        Tuple of (field_name, operator)
    """
    operators = ["__gte", "__lte", "__eq", "__contains", "__in", "__exists", "__ne"]

    for op in operators:
        if key.endswith(op):
            return key[: -len(op)], op[2:]  # Remove __ prefix from operator

    return key, "eq"  # Default to equality


def build_elasticsearch_query(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Build an Elasticsearch query from filter dict.

    Args:
        filters: Dictionary of filters with optional operator suffixes

    Returns:
        Elasticsearch query dict
    """
    must_clauses = []
    filter_clauses = []

    for key, value in filters.items():
        field, operator = parse_filter_key(key)
        metadata_field = f"metadata.{field}"

        if operator == "eq":
            filter_clauses.append({"term": {metadata_field: value}})
        elif operator == "ne":
            must_clauses.append({"bool": {"must_not": {"term": {metadata_field: value}}}})
        elif operator == "gte":
            filter_clauses.append({"range": {metadata_field: {"gte": value}}})
        elif operator == "lte":
            filter_clauses.append({"range": {metadata_field: {"lte": value}}})
        elif operator == "contains":
            must_clauses.append({"match": {metadata_field: value}})
        elif operator == "in":
            if isinstance(value, list):
                filter_clauses.append({"terms": {metadata_field: value}})
            else:
                filter_clauses.append({"terms": {metadata_field: [value]}})
        elif operator == "exists":
            if value:
                filter_clauses.append({"exists": {"field": metadata_field}})
            else:
                must_clauses.append({"bool": {"must_not": {"exists": {"field": metadata_field}}}})

    query: Dict[str, Any] = {"bool": {}}
    if must_clauses:
        query["bool"]["must"] = must_clauses
    if filter_clauses:
        query["bool"]["filter"] = filter_clauses

    return query


@tool
async def metadata_filter_search(
    filters: str = Field(description="JSON string of metadata filters. Use '__gte', '__lte', '__contains', '__in', '__exists' suffixes. " 'Example: \'{"date__gte": "2023-01-01", "category__contains": "FOIA", "source_type__in": ["pdf", "html"]}\''),
    return_full_docs: bool = Field(default=False, description="Whether to return full document content or just metadata summaries"),
    max_results: int = Field(default=20, description="Maximum results (1-100)", ge=1, le=100),
) -> str:
    """Filter documents by metadata attributes before retrieval.

    Use this to narrow down resources by date, category, document type, author, etc.
    This runs BEFORE vector search for precise filtering.

    Supported operators:
    - No suffix or __eq: exact match
    - __gte / __lte: greater/less than or equal (for dates, numbers)
    - __contains: text contains (for partial matching)
    - __in: value in list
    - __exists: field exists (true/false)

    Example filters:
    - {"date__gte": "2023-01-01"} - Documents from 2023 onwards
    - {"category": "FOIA"} - Exact category match
    - {"source_type__in": ["pdf", "html"]} - PDFs or HTML pages
    """
    try:
        filter_dict = json.loads(filters) if isinstance(filters, str) else filters
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON in filters: {e}", "hint": 'Ensure filters is valid JSON, e.g., \'{"category": "FOIA"}\''}, indent=2)

    if not filter_dict:
        return json.dumps({"error": "No filters provided", "hint": 'Provide at least one filter, e.g., filters=\'{"date__gte": "2023-01-01"}\''}, indent=2)

    # Build Elasticsearch query
    es_query = build_elasticsearch_query(filter_dict)

    # Check if Elasticsearch is configured
    es_url = os.getenv("ELASTICSEARCH_URL")
    es_index = os.getenv("ELASTICSEARCH_INDEX", "documents")

    if not es_url:
        # Return mock response for development/testing
        logger.warning("ELASTICSEARCH_URL not set, returning mock response")
        return json.dumps({"status": "mock_response", "message": "Elasticsearch not configured. In production, this would filter documents.", "query_built": es_query, "filters_parsed": filter_dict, "total": 0, "documents": []}, indent=2)

    try:
        # Dynamic import to avoid dependency issues
        from elasticsearch import AsyncElasticsearch

        es_client = AsyncElasticsearch([es_url])

        try:
            # Execute search
            response = await es_client.search(
                index=es_index,
                query=es_query,
                size=max_results,
                _source=["metadata", "page_content"] if return_full_docs else ["metadata"],
            )

            hits = response.get("hits", {}).get("hits", [])
            total = response.get("hits", {}).get("total", {}).get("value", 0)

            # Format results
            documents = []
            for hit in hits:
                source = hit.get("_source", {})
                metadata = source.get("metadata", {})

                doc_result = {
                    "id": hit.get("_id"),
                    "score": hit.get("_score"),
                    "title": metadata.get("title", metadata.get("source", "Unknown")),
                    "url": metadata.get("url", metadata.get("source", "")),
                    "metadata": metadata,
                }

                if return_full_docs:
                    doc_result["content_preview"] = source.get("page_content", "")[:500]

                documents.append(doc_result)

            return json.dumps({"total": total, "returned": len(documents), "filters_applied": filter_dict, "documents": documents}, indent=2)

        finally:
            await es_client.close()

    except ImportError:
        return json.dumps({"error": "Elasticsearch client not installed", "hint": "Install with: pip install elasticsearch"}, indent=2)
    except Exception as e:
        logger.error(f"Elasticsearch error: {e}")
        return json.dumps({"error": f"Search failed: {str(e)}", "query_attempted": es_query}, indent=2)


@tool
async def get_available_facets(field: str = Field(description="Metadata field to get facet values for, e.g., 'category', 'source_type', 'author'"), max_values: int = Field(default=20, description="Maximum number of unique values to return", ge=1, le=100)) -> str:
    """Get available values for a metadata field (faceted search).

    Use this to discover what filter values are available before filtering.
    For example, get all available categories or document types.
    """
    es_url = os.getenv("ELASTICSEARCH_URL")
    es_index = os.getenv("ELASTICSEARCH_INDEX", "documents")

    if not es_url:
        # Return mock response
        mock_facets = {
            "category": ["FOIA", "First Amendment", "Press Freedom", "Legal Guide", "News"],
            "source_type": ["pdf", "html", "markdown", "docx"],
            "state": ["Massachusetts", "Connecticut", "Rhode Island", "Maine", "New Hampshire", "Vermont"],
        }
        return json.dumps({"status": "mock_response", "field": field, "values": mock_facets.get(field, ["(no mock data for this field)"]), "message": "Elasticsearch not configured. These are sample values."}, indent=2)

    try:
        from elasticsearch import AsyncElasticsearch

        es_client = AsyncElasticsearch([es_url])

        try:
            # Aggregation query for unique values
            response = await es_client.search(index=es_index, size=0, aggs={"field_values": {"terms": {"field": f"metadata.{field}.keyword", "size": max_values}}})  # Don't return documents, just aggregations

            buckets = response.get("aggregations", {}).get("field_values", {}).get("buckets", [])

            values = [{"value": b["key"], "count": b["doc_count"]} for b in buckets]

            return json.dumps({"field": field, "total_unique_values": len(values), "values": values}, indent=2)

        finally:
            await es_client.close()

    except Exception as e:
        logger.error(f"Facet query error: {e}")
        return json.dumps({"error": f"Facet query failed: {str(e)}", "field": field}, indent=2)
