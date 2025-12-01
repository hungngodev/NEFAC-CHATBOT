import os

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
