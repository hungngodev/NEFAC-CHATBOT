# import glob
# from langchain_community.document_loaders import PyPDFLoader
# from document.summary import generate_summary

# def pdfLoader(path, title_to_chunks, tag_type, tag):
#     all_docs_path = glob.glob(path + "/*.pdf")
#     new_docs = set()
#     for doc_path in all_docs_path:
#         doc_title = doc_path.split("/")[-1][:-4].strip().replace('_', ' ').replace('  ', ' ')
#         if doc_title in title_to_chunks:
#             if tag not in title_to_chunks[doc_title][0].metadata[tag_type]:
#                 for page in title_to_chunks[doc_title]:
#                     page.metadata[tag_type].append(tag)
#         else:
#             loader = PyPDFLoader(doc_path)
#             pages = loader.load_and_split()
#             summary = generate_summary(pages)
#             print("page summary",summary)
#             for page in pages:
#                 page.metadata['title'] = doc_title
#                 page.metadata['audience'] = []
#                 page.metadata['nefac_category'] = []
#                 page.metadata['resource_type'] = []
#                 page.metadata[tag_type].append(tag)
#                 page.metadata['type'] = 'pdf'
#                 page.metadata['summary'] = summary
#             new_docs.add(doc_title)
#             title_to_chunks[doc_title] = pages
#     return new_docs
import glob
from langchain_community.document_loaders import PyPDFLoader
from document.summary import generate_summary, generate_tags
import os

def pdfLoader(pdf_path, title_to_chunks):
    doc_title = os.path.basename(pdf_path)[:-4].strip().replace('_', ' ').replace('  ', ' ')
    if doc_title in title_to_chunks:
        return set()  # Skip if already processed
    loader = PyPDFLoader(pdf_path)
    pages = loader.load_and_split()
    summary = generate_summary(pages)
    tags = generate_tags(summary)
    for page in pages:
        page.metadata['title'] = doc_title
        page.metadata['audience'] = tags.get('audience', [])
        page.metadata['nefac_category'] = tags.get('nefac_category', [])
        page.metadata['resource_type'] = tags.get('resource_type', [])
        page.metadata['type'] = 'pdf'
        page.metadata['summary'] = summary
    title_to_chunks[doc_title] = pages
    return {doc_title}