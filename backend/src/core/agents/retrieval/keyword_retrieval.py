import os

from langchain_core.runnables import RunnableLambda
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


def _clean_docs(docs):
    for doc in docs:
        # User wants full content, so we don't clean doc.page_content
        # But we MUST remove 'text' from metadata as it duplicates content
        if doc.metadata:
            doc.metadata.pop("text", None)
            doc.metadata.pop("_node_content", None)
    return docs


keyword_retriever = bm25_store.as_retriever(search_kwargs={"k": 10}) | RunnableLambda(_clean_docs)
