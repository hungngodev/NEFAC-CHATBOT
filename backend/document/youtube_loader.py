import os
from langchain_community.document_loaders import (DirectoryLoader, PyPDFLoader,
                                                  YoutubeLoader)
from langchain_community.document_loaders.youtube import TranscriptFormat

def youtubeLoader(path, title_to_pages):
    if 'yt_urls.txt' not in os.listdir(path):
        print('yt_urls.txt not in os.listdir(path)')
        return [] ,set(), set()

    with open(f"{path}/yt_urls.txt", "r") as f:
        URLs = f.readlines()
    
    new_vids_chunks = []
    new_vids = set()
    duplicate_vids = set()

    for url in URLs:
        # print(url)
        url=url.rstrip()
        if url in title_to_pages:
            duplicate_vids.add(url)
        elif url not in title_to_pages and url not in new_vids:
            loader = YoutubeLoader.from_youtube_url(
                url,
                add_video_info=False,
                transcript_format=TranscriptFormat.CHUNKS,
                chunk_size_seconds=60, # 60
            )
            new_vids.add(url)
            loaded_clips=loader.load()
            # print(f"Loaded chunks for URL {url}: {loaded_chunks}")
            for clip in loaded_clips:
                clip.metadata['audience']=[]
                clip.metadata['nefac_category'] = []
                clip.metadata['resource_type'] = []
                clip.metadata['type'] = 'youtube'
            title_to_pages[url]=loaded_clips
            # print("\n\n".join(map(repr, loader.load())))
    # print(f"New Chunks: {new_vids_chunks}, New Documents: {new_vids}, Duplicate Documents: {duplicate_vids}")
    return new_vids, duplicate_vids


# def pdfLoader(path,title_to_pages):
#     # Load all PDF documents from the directory "docs/"
#     all_docs_path = glob.glob(path+"/*")
#     new_pages = []
#     new_docs = set()
#     duplicate_docs = set()
#     for doc in all_docs_path:
#         doc_title = doc.split("/")[-1] # contains .pdf
#         if doc_title in title_to_pages:
#             duplicate_docs.add(doc_title)
#         elif doc.endswith(".pdf") and doc_title not in new_docs:
#             new_docs.add(doc_title) # clean up doc title
#             loader = PyPDFLoader(doc)
#             pages = loader.load_and_split()
#             new_pages.extend(pages)
#             for page in new_pages:
#                 page.metadata['audience']=[]
#                 page.metadata['nefac_category'] = []
#                 page.metadata['resource_type'] = []
#             title_to_pages[doc_title]=new_pages
#     return new_pages, new_docs, duplicate_docs