import glob
from document.pdf_loader import pdfLoader
from document.youtube_loader import youtubeLoader
import os
import pickle
# TODO: implement for txt files, images, etc. add optional filter params for each category (audience, tag_type, nefac_category) retrieved from frontend

# grab all the documents in the waiting room. use the llm to tag them, append the tags to the txt files in the locations and in the metadata for the db. once done, move them to the finished tagging

def load_all_documents():
    all_documents = set()

    docs_path="docs/*"
    all_paths=[d for d in glob.glob(docs_path) if os.path.isdir(d)] 

    # Load url_to_title and title_to_chunks from pickle files
    try:
        with open('url_to_title.pkl', 'rb') as u2t:
            url_to_title = pickle.load(u2t)
    except FileNotFoundError:
        url_to_title = {}  # Initialize as empty if file not found

    try:
        with open('title_to_chunks.pkl', 'rb') as t2c:
            title_to_chunks = pickle.load(t2c)
    except FileNotFoundError:
        title_to_chunks = {}  # Initialize as empty if file not found

    def load_all_in_path(path,tag_title):
        path_list=glob.glob(path+'/*')
        for folder in path_list:
            tag=folder.split("/")[-1] # docs/by_audience/citizen
            tag_type='audience' if tag_title=='by_audience' else 'nefac_category' if tag_title=='by_content' else 'resource_type' if tag_title=='by_resource' else ''

            new_docs = pdfLoader(folder, title_to_chunks, tag_type, tag)
            all_documents.update(new_docs)

            new_vids = youtubeLoader(folder, title_to_chunks, url_to_title, tag_type, tag)
            all_documents.update(new_vids)
            
    for path in all_paths:
        load_all_in_path(path,path.split("/")[-1]) # docs/by_audience

    return all_documents, url_to_title, title_to_chunks