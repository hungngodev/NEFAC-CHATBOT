import glob
from langchain_community.document_loaders import PyPDFLoader

def pdfLoader(path, title_to_chunks,tag_type,tag):
    # Load all PDF documents from the directory "docs/"
    all_docs_path = glob.glob(path+"/*")

    new_docs = set()
    for doc_path in all_docs_path:
        doc_title = doc_path.split("/")[-1]
        if not doc_title.endswith(".pdf"): continue
        else: doc_title = doc_title[:-4].strip().replace('_', ' ').replace('  ', ' ') # Better title cleaning result could be obtained using LLM
        if doc_title in title_to_chunks: # if we have already seen this document
            if tag not in title_to_chunks[doc_title][0].metadata[tag_type]: # add the tag to all pages for this document if it doesn't have this tag yet
                for page in title_to_chunks[doc_title]:
                    page.metadata[tag_type].append(tag)
        else:
            loader = PyPDFLoader(doc_path)
            pages = loader.load_and_split()
            for page in pages:
                page.metadata['title'] = doc_title # set the title
                page.metadata['audience']=[] # initialize the tagging fields
                page.metadata['nefac_category'] = []
                page.metadata['resource_type'] = []
                page.metadata[tag_type].append(tag) # add the current tag to the fieldc
                page.metadata['type'] = 'pdf' # mark as a pdf
            new_docs.add(doc_title) # update the new_docs
            title_to_chunks[doc_title] = pages # store the pages
    return new_docs