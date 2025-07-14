from typing import List

from langchain_core.documents import Document
from langchain_core.load import dumps, loads
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, Send, StateGraph

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.config.prompts import BASE_PROMPT
from src.core.agents.retrieval.subgraph import RetrievalSubgraphState, retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.core_types import AgentState

MULTI_QUERY_PERSPECTIVES_PROMPT = f"""
You are an AI assistant for the New England First Amendment Coalition (NEFAC).  
Perform a multi-query translation of the user’s question by generating exactly five search queries (one per line) to retrieve diverse, relevant materials—transcripts, summaries, and docs—from our vector store.  

{BASE_PROMPT}

Each query should contain one of the following perspectives:

1. Restate the core question to find precise answers.  
2. Widen the frame to include New England’s free-speech and press-freedom context.  
3. Surface related legal concepts, precedents, or foundational First Amendment principles.  
4. Seek real-world NEFAC case studies, reports, or example applications.  
5. Highlight challenges, debates, or alternative perspectives on the topic.

Original question: {{question}}
"""

llm = ChatOpenAI(model=QUERY_TRANSLATION_MODEL_NAME)


# --- Subgraph State ---
class MultiQueryState(AgentState):
    """State for the multi-query subgraph."""

    generated_queries: List[str] = []


# --- Nodes ---
def generate_queries_node(state: MultiQueryState) -> MultiQueryState:
    """
    Generates multiple queries and returns a list of Send objects
    to trigger parallel retrieval for each query.
    """
    question = state["contextualized_query"]
    prompt = ChatPromptTemplate.from_template(MULTI_QUERY_PERSPECTIVES_PROMPT)
    chain = prompt | llm | StrOutputParser() | (lambda x: x.split("\n"))

    generated_queries = chain.invoke({"question": question})
    generated_queries = [q.strip() for q in generated_queries if q.strip()]

    # For each query, Send it to the retrieval subgraph
    # Each invocation will have its own `retrieval_query`
    return {"generated_queries": generated_queries}


def deduplicate_documents_node(state: RetrievalSubgraphState) -> MultiQueryState:
    """
    Deduplicates documents from the multiple parallel retrieval runs.
    The results from the Send operations are automatically collected in the state.
    """
    # The `retrieved_documents_lists` will contain the output of each retrieval subgraph invocation
    retrieved_documents_lists = state["final_documents"]

    flattened_docs_str = []

    for doc in retrieved_documents_lists:
        if isinstance(doc, Document):
            flattened_docs_str.append(dumps(doc))

    unique_docs_str = list(set(flattened_docs_str))

    unique_documents = []
    for doc_str in unique_docs_str:
        doc = loads(doc_str)
        if isinstance(doc, Document):
            unique_documents.append(doc)
    return {"final_documents": unique_documents}


def format_documents_node(state: MultiQueryState) -> AgentState:
    """Formats the final list of documents into a single string."""
    formatted_string = format_docs(state["final_documents"])
    # The final output of any query translation subgraph is the transformed query/result
    return {"final_context": formatted_string}


workflow = StateGraph(MultiQueryState)

workflow.add_node("generate_queries", generate_queries_node)
workflow.add_node("retrieve_subgraph", retrieval_subgraph)
workflow.add_node("deduplicate_documents", deduplicate_documents_node)
workflow.add_node("format_documents", format_documents_node)
workflow.set_entry_point("generate_queries")


def route_from_generate_queries(state: MultiQueryState) -> List[Send]:
    """Route to multiple retrieval subgraph invocations based on generated queries."""
    queries = state["generated_queries"]
    sends = [Send("retrieve_subgraph", {"retrieval_query": q}) for q in queries]
    return sends


# After generation, we fan-out to the retrieval subgraph
workflow.add_conditional_edges(
    "generate_queries",
    route_from_generate_queries,
)

# After all parallel retrieval runs are complete, they are joined at the next node
workflow.add_edge("retrieve_subgraph", "deduplicate_documents")
workflow.add_edge("deduplicate_documents", "format_documents")
workflow.add_edge("format_documents", END)
multi_query = workflow.compile()
