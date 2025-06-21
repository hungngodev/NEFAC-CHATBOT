from langchain_core.documents import Document
from langchain_core.load import dumps, loads
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from llm.constant import PROMPT_MODEL_NAME
from llm.utils import format_docs
from load_env import load_env
from prompts import RAG_FUSION_PROMPT

load_env()
model = ChatOpenAI(temperature=0, model_name=PROMPT_MODEL_NAME)
prompt_rag_fusion = ChatPromptTemplate.from_template(RAG_FUSION_PROMPT)

generate_queries = prompt_rag_fusion | model | StrOutputParser() | (lambda x: x.split("\n"))


def reciprocal_rank_fusion(results: list[list], k=60):
    """Reciprocal_rank_fusion that takes multiple lists of ranked documents
    and an optional parameter k used in the RRF formula"""

    # Initialize a dictionary to hold fused scores for each unique document
    fused_scores = {}

    # Iterate through each list of ranked documents
    for docs in results:
        # Iterate through each document in the list, with its rank (position in the list)
        for rank, doc in enumerate(docs):
            # Convert the document to a string format to use as a key (assumes documents can be serialized to JSON)
            doc_str = dumps(doc)
            # If the document is not yet in the fused_scores dictionary, add it with an initial score of 0
            if doc_str not in fused_scores:
                fused_scores[doc_str] = 0
            # Retrieve the current score of the document, if any
            fused_scores[doc_str]
            # Update the score of the document using the RRF formula: 1 / (rank + k)
            fused_scores[doc_str] += 1 / (rank + k)

    # Sort the documents based on their fused scores in descending order to get the final reranked results
    reranked_results = [loads(doc) for doc, score in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)]

    # Return the reranked results as a list of tuples, each containing the document and its fused score
    return reranked_results


def handle_empty_results(results):
    """Handles empty retrieval results by returning a fallback response."""
    if not any(results):  # Check if all retrieved lists are empty
        return [Document(page_content="No relevant documents found.", metadata={})]
    return reciprocal_rank_fusion(results)  # Otherwise, apply RRF


def get_rag_fusion_chain(retriever):
    return generate_queries | retriever.map() | handle_empty_results | format_docs
