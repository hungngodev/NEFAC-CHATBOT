"""
LangGraph retrieval subgraph with a simplified routing strategy.
It uses an Ensemble Retriever for document searches and a separate path for graph retrieval.
"""

import json
import logging
from typing import List, Literal

from langchain.retrievers import EnsembleRetriever
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langgraph.graph import END, StateGraph

from src.core.agents.retrieval.graph_retrieval import graph_tool_node
from src.core.agents.retrieval.keyword_retrieval import keyword_search
from src.core.agents.retrieval.post_processing import filter_and_prioritize_documents
from src.core.agents.retrieval.vector_retrieval import vector_search
from src.schemas.core_types import AgentState

logger = logging.getLogger(__name__)

# --- Retrieval Method Selection Prompt ---
RETRIEVAL_METHOD_SELECTION_PROMPT = """You are an expert at selecting the optimal retrieval strategy for legal queries for NEFAC’s First Amendment resources. Your goal is to choose the best method to answer the user's query.

You have two retrieval methods available:

1.  `graph_search`:
    *   **What it is:** A knowledge graph search (using Neo4j).
    *   **Best for:** Queries about relationships, entities, and structured data. It's excellent for understanding how different entities like people, organizations, and legal cases are connected.

2.  `document_search`:
    *   **What it is:** A hybrid search that combines two techniques:
        *   Keyword search (BM25): For finding exact terms, names, and citations.
        *   Semantic vector search: For finding conceptually related information and answering broader questions.
    *   **Best for:** A wide range of queries, from finding specific documents to exploring general legal concepts.

**Decision Guidelines & Heuristics:**

Carefully analyze the user's query and choose a method based on the following patterns:

*   **Choose `graph_search` if the query contains:**
    *   **Entity & Relationship Patterns:** Look for phrases like `who is`, `what is the relationship between`, `connected to`, `involved in`, etc.
    *   **Examples:**
        *   "What is the connection between the ACLU and cases involving FOIA?"
        *   "Who is John Doe and what organizations is he affiliated with?"
        *   "List all cases decided by the Supreme Court that cite the 'public records law'."

*   **Choose `document_search` if the query contains:**
    *   **Exact-Term Patterns:** Look for specific legal citations (`FOIA`, `Section 230`), laws (`public records law`), or proper names (`Jane Smith`, `ACLU`). While the graph may contain these, document search is better for retrieving the source text.
        *   **Example:** "Find documents discussing Section 230."
    *   **Conceptual Patterns:** Look for broad questions about legal concepts, principles, or approaches.
        *   **Example:** "What are the main legal arguments regarding student speech rights?"
    *   **General Explanatory Questions:** Look for words like `how`, `why`, `explain`, `describe`.
        *   **Example:** "Explain the principle of prior restraint."

**Final Output:**

You must return only a valid JSON object. For `graph_search`, the output should be `{{"method": "graph_search"}}`. For `document_search`, you must also provide weights for the keyword and vector retrievers. The weights must sum to 1.0.

**Example for a relationship query:**
```json
{
  "method": "graph_search"
}
```

**Example for a conceptual query:**
```json
{
  "method": "document_search",
  "weights": {
    "keyword": 0.4,
    "vector": 0.6
  }
}
```
"""


# --- Subgraph State ---
class RetrievalSubgraphState(AgentState):
    """State for the retrieval subgraph."""

    documents: List[Document] = []
    retrieval_method: Literal["document_search", "graph_search"]
    ensemble_weights: List[float] = [0.5, 0.5]
    global_top_k: int = 10


# --- Nodes ---
def route_retrieval_node(state: RetrievalSubgraphState, llm) -> dict:
    """Routes to the appropriate retrieval tool based on the query."""
    query = state.transformed_query
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", RETRIEVAL_METHOD_SELECTION_PROMPT),
            ("human", "Query: {query}"),
        ]
    )
    chain = prompt | llm
    plan_json = chain.invoke({"query": query})
    try:
        plan = json.loads(plan_json.content)
        method = plan.get("method")
        logger.info(f"Retrieval method selected: {method}")
        if method not in ["graph_search", "document_search"]:
            logger.warning("Invalid retrieval method selected. Falling back to document_search.")
            method = "document_search"

        if method == "document_search":
            weights = plan.get("weights", {})
            keyword_weight = weights.get("keyword", 0.5)
            vector_weight = weights.get("vector", 0.5)
            return {"retrieval_method": method, "ensemble_weights": [keyword_weight, vector_weight]}
        else:
            return {"retrieval_method": method}

    except (json.JSONDecodeError, AttributeError):
        logger.error(f"Failed to decode retrieval plan JSON: {plan_json.content}. Falling back to document_search.")
        return {"retrieval_method": "document_search", "ensemble_weights": [0.5, 0.5]}


def ensemble_retrieval_node(state: RetrievalSubgraphState) -> dict:
    """Retrieves documents using an ensemble of keyword and vector search."""
    logger.info("Performing ensemble retrieval (keyword + vector search).")
    query = state.transformed_query
    weights = state.get("ensemble_weights", [0.5, 0.5])
    ensemble_retriever = EnsembleRetriever(retrievers=[keyword_search, vector_search], weights=weights)
    documents = ensemble_retriever.invoke(query)
    return {"documents": documents}


def graph_retrieval_node(state: RetrievalSubgraphState) -> dict:
    """Retrieves documents using graph search."""
    logger.info("Performing graph retrieval.")
    documents = graph_tool_node.invoke(state.transformed_query, state=state)
    return {"documents": documents}


def post_process_node(state: RetrievalSubgraphState) -> dict:
    """Filters and prioritizes documents after retrieval."""
    processed_docs = filter_and_prioritize_documents(state.documents, state.get("metadata_filters"), state.get("priorities"))
    return {"documents": processed_docs}


def rerank_node(state: RetrievalSubgraphState) -> dict:
    """Reranks the final set of documents and applies the global top_k."""
    query = state.transformed_query
    documents = state.documents
    global_top_k = state.get("global_top_k", 10)

    if not documents:
        return {"documents": []}

    try:
        compressor = CohereRerank(model="rerank-english-v3.0")

        class IdentityRetriever(BaseRetriever):
            def _get_relevant_documents(self, query: str, **kwargs) -> List[Document]:
                return documents

            def invoke(self, input: str, **kwargs) -> List[Document]:
                return documents

        identity_retriever = IdentityRetriever()
        compression_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=identity_retriever)

        reranked_docs = compression_retriever.invoke(query)
        final_docs = reranked_docs[:global_top_k]
        logger.info(f"Reranked and sliced to final {len(final_docs)} documents.")
        return {"documents": final_docs}
    except Exception as e:
        logger.warning(f"Reranking failed: {e}. Returning top_k documents without reranking.")
        return {"documents": documents[:global_top_k]}


# --- Graph Definition ---
def create_retrieval_subgraph(llm):
    """Creates the retrieval subgraph with simplified routing."""
    workflow = StateGraph(RetrievalSubgraphState)

    workflow.add_node("router", lambda state: route_retrieval_node(state, llm))
    workflow.add_node("ensemble_retrieval", ensemble_retrieval_node)
    workflow.add_node("graph_retrieval", graph_retrieval_node)
    workflow.add_node("post_process", post_process_node)
    workflow.add_node("rerank", rerank_node)

    workflow.set_entry_point("router")

    workflow.add_conditional_edges(
        "router",
        lambda state: state.get("retrieval_method"),
        {
            "graph_search": "graph_retrieval",
            "document_search": "ensemble_retrieval",
        },
    )

    workflow.add_edge("graph_retrieval", END)
    workflow.add_edge("ensemble_retrieval", "post_process")
    workflow.add_edge("post_process", "rerank")
    workflow.add_edge("rerank", END)

    return workflow.compile()
