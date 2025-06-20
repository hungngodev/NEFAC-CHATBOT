from langchain_community.document_loaders import PyPDFLoader
import os


def pdfLoader(pdf_path, title_to_chunks):
    doc_title = (
        os.path.basename(pdf_path)[:-4].strip().replace("_", " ").replace("  ", " ")
    )
    if doc_title in title_to_chunks:
        return set()
    loader = PyPDFLoader(pdf_path)
    pages = loader.load_and_split()
    for page in pages:
        page.metadata["title"] = doc_title
        page.metadata["type"] = "pdf"
        title_to_chunks[doc_title] = pages
    return {doc_title}
