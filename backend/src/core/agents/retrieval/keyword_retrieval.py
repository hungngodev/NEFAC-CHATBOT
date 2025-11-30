import os

from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_elasticsearch import BM25Strategy, ElasticsearchStore

elasticsearch_url = os.environ["ES_HOST"]
index_name = os.environ["ES_INDEX"]
print("ES_HOST =", os.environ.get("ES_HOST"))
print("ES_INDEX =", os.environ.get("ES_INDEX"))

bm25_store = ElasticsearchStore(
    index_name=index_name,
    es_url=elasticsearch_url,
    query_field="content",
    strategy=BM25Strategy(),
)

keyword_retriever = bm25_store.as_retriever(search_kwargs={"k": 10})


@tool(description="Performs keyword-based search using BM25.")
def keyword_search(query: str, top_k: int = 10) -> list[Document]:
    documents = keyword_retriever.invoke(query, k=top_k)

    for doc in documents:
        if not hasattr(doc, "metadata") or doc.metadata is None:
            doc.metadata = {}
        doc.metadata["stream_tag"] = "keyword_retrieved_docs"
        doc.metadata["retrieval_method"] = "keyword_search"

    return documents
