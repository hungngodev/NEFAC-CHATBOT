import glob
from langchain_community.document_loaders import ( PyPDFLoader,
                                                  )

def pdfLoader(path, title_to_pages,tag_type,tag):
    # Load all PDF documents from the directory "docs/"
    all_docs_path = glob.glob(path+"/*")

    new_docs = set()
    for doc in all_docs_path:
        doc_title = doc.split("/")[-1]
        if not doc_title.endswith(".pdf"): continue
        else: doc_title=doc_title[:-4].strip().replace('_', ' ').replace('  ', ' ') # Better result using LLM?
        if doc_title in title_to_pages:
            if tag not in title_to_pages[doc_title][0].metadata[tag_type]:
                for page in title_to_pages[doc_title]:
                    page.metadata[tag_type].append(tag)
        else:
            new_docs.add(doc_title)
            loader = PyPDFLoader(doc)
            pages = loader.load_and_split()
            for page in pages:
                page.metadata['title'] = doc_title
                page.metadata['audience']=[]
                page.metadata['nefac_category'] = []
                page.metadata['resource_type'] = []
                page.metadata[tag_type].append(tag)
                page.metadata['type'] = 'pdf'
            title_to_pages[doc_title]=pages
    return new_docs