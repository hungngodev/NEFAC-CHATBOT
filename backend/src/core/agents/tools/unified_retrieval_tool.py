from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg
from langchain_core.tools import tool as lc_tool

from src.core.agents.query_translation.query_transformer import QueryTransformerState, query_internal_documents


@lc_tool(parse_docstring=True)
async def internal_document_search(query: str, config: Annotated[RunnableConfig, InjectedToolArg] = None) -> str:
    """Search internal documents and knowledge base using intelligent retrieval strategies.

    This tool automatically analyzes your query and selects the most appropriate search method:
    basic direct search for simple queries, or advanced transformation strategies (multi-query,
    decomposition, step-back, HyDE, factual enhancement, contextual expansion) for complex queries.
    Use this to find relevant information from the organization's document collection,
    including legal documents, policy papers, reports, and other internal resources.
    The system intelligently chooses between direct retrieval and sophisticated query transformation
    based on query characteristics, providing comprehensive coverage from multiple perspectives
    when needed while maintaining efficiency for straightforward searches.
    Always prioritize this tool for legal, policy, NEFAC-related, or organizational queries before using external search.

    This unified tool automatically:
    1. Analyzes your query complexity and characteristics
    2. Selects the optimal retrieval strategy:
       - Default: Direct search for straightforward queries
       - Multi-query: Multiple perspectives for broader coverage
       - Decomposition: Sub-question analysis for complex topics
       - Step-back: Conceptual framing for foundational understanding
       - HyDE: Hypothetical document generation for semantic matching
       - Factual: Enhanced factual precision and entity focus
       - Contextual: Legal and domain context expansion
    3. Executes the chosen strategy with hybrid retrieval methods
    4. Returns comprehensive, formatted results

    Args:
        query: The search query for internal documents. Be specific and detailed
               for best results. Examples: "First Amendment rights for journalists",
               "FOIA exemptions for law enforcement", "NEFAC v. Department of Justice"

    Returns:
        Formatted search results with strategy information and source metadata.
        Returns comprehensive document excerpts with titles, summaries, and content.
    """
    try:
        # Use the unified query transformer which intelligently selects strategy
        result: QueryTransformerState = await query_internal_documents(query, config)

        # Extract results from the transformation
        transformed_context = result["transformed_context"]
        documents = result["accumulated_documents"]
        method_used = result["method_used"]

        if not transformed_context and not documents:
            return f"No relevant internal documents found for query: '{query}'. Consider rephrasing your query or using web search for external information."

        # Use transformed_context if available (from advanced strategies), otherwise basic formatting
        if transformed_context:
            formatted_result = transformed_context
        else:
            # Fallback formatting if no transformed_context
            from src.core.agents.tools.document_formatter import format_docs

            formatted_result = format_docs(documents)

        # Provide strategy transparency to the user
        strategy_info = ""
        if method_used and method_used != "default":
            strategy_map = {"multiquery": "multi-perspective search", "decompose": "sub-question analysis", "stepback": "conceptual framework search", "hyde": "hypothetical document matching", "factual": "factual precision search", "contextual": "contextual expansion search"}
            strategy_name = strategy_map.get(method_used, method_used)
            strategy_info = f" (using {strategy_name})"

        # Format the final response with clear structure
        response_header = f"📚 Internal Document Search Results{strategy_info} for: '{query}'"
        separator = "\n" + "=" * 80 + "\n"

        return f"{response_header}{separator}{formatted_result}"

    except Exception as e:
        error_msg = f"❌ Error searching internal documents: {str(e)}"
        suggestion = "💡 Try rephrasing your query or use web search for external information."
        return f"{error_msg}\n{suggestion}"
