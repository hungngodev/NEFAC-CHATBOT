import glob
from document.pdf_loader import pdfLoader
from document.youtube_loader import youtubeLoader
import os
# TODO: implement for txt files, images, etc. add optional filter params for each category (audience, tag_type, nefac_category) retrieved from frontend

def load_all_documents():
    all_pdfs = set()
    all_yt_vids = set() 

    docs_path="docs/*"
    all_paths=[d for d in glob.glob(docs_path) if os.path.isdir(d)] 

    url_to_title={}
    title_to_pages={}

    def load_all_in_path(path):
        path_list=glob.glob(path+'/*')
        for folder in path_list:
            path_dirs=folder.split("/") # docs/by_audience/citizen
            tag_type_name=path_dirs[-2]
            tag=path_dirs[-1] 
            tag_type='audience' if tag_type_name=='by_audience' else 'nefac_category' if tag_type_name=='by_content' else 'resource_type' if tag_type_name=='by_resource' else ''

            new_docs = pdfLoader(folder, title_to_pages, tag_type,tag)
            # print(path_list,folder)

            all_pdfs.update(new_docs)

            new_vids = youtubeLoader(folder, title_to_pages, url_to_title, tag_type,tag)
            all_yt_vids.update(new_vids)
            
    for path in all_paths:
        load_all_in_path(path)
        
    return [page for pdf in all_pdfs for page in title_to_pages[pdf]], [clip for vid in all_yt_vids for clip in title_to_pages[vid]], all_pdfs, all_yt_vids