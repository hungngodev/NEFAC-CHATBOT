import glob
from langchain_community.document_loaders import ( PyPDFLoader,
                                                  )

def pdfLoader(path, title_to_pages):
    # Load all PDF documents from the directory "docs/"
    all_docs_path = glob.glob(path+"/*")
    new_pages = []
    new_docs = set()
    duplicate_docs = set()
    for doc in all_docs_path:
        doc_title = doc.split("/")[-1] # contains .pdf
        if doc_title in title_to_pages:
            duplicate_docs.add(doc_title)
        elif doc.endswith(".pdf") and doc_title not in new_docs:
            new_docs.add(doc_title) # clean up doc title
            loader = PyPDFLoader(doc)
            pages = loader.load_and_split()
            new_pages.extend(pages)
            for page in new_pages:
                page.metadata['audience']=[]
                page.metadata['nefac_category'] = []
                page.metadata['resource_type'] = []
                page.metadata['type'] = 'pdf'
            title_to_pages[doc_title]=new_pages
    return new_docs, duplicate_docs