import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_docs(docs):
    return "\n\n".join(f"content:{doc.page_content}\nsource:{doc.metadata['source']}\npage:{doc.metadata['page']}\ntitle:{doc.metadata['title']}\nnefac_categories:{doc.metadata['nefac_category']}\nresource_types:{doc.metadata['resource_type']}\naudiences:{doc.metadata['audience']}\n" for doc in docs)

