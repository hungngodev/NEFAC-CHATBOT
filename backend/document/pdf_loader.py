import glob
from langchain_community.document_loaders import ( PyPDFLoader,
                                                  )

def pdfLoader(path, existing_docs):
    # Load all PDF documents from the directory "docs/"
    all_docs_path = glob.glob(path+"/*")
    new_pages = []
    new_docs = set()
    duplicate_docs = set()
    for doc in all_docs_path:
        doc_title = doc.split("/")[-1]
        if doc_title in existing_docs:
            duplicate_docs.add(doc_title.split(".")[0])
        elif doc.endswith(".pdf") and doc_title not in new_docs:
            new_docs.add(doc_title) # clean up doc title
            loader = PyPDFLoader(doc)
            pages = loader.load_and_split()
            new_pages.extend(pages)
    return new_pages, new_docs, duplicate_docs