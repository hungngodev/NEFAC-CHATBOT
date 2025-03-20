import glob
from document.pdf_loader import pdfLoader
from document.youtube_loader import youtubeLoader
import yt_dlp
import re
import os
# TODO: implement for txt files, images, etc. add optional filter params for each category (audience, resource_type, nefac_category) retrieved from frontend

def get_youtube_title(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': False,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Title not found')
            print(f"Fetched title for {url}: '{title}'")
            return title
    except Exception as e:
        print(f"Error fetching title for {url}: {str(e)}")
        return "Title not found"

def load_all_documents():
    all_pdfs = set()
    all_yt_vids = set() 
    
    # all_pdf_pages = []
    # all_yt_vid_chunks = []

    docs_path="docs/*"
    all_paths=[d for d in glob.glob(docs_path) if os.path.isdir(d)]

    # all_audience = glob.glob(by_audience_path)
    # all_resources = glob.glob(by_resource_type_path)
    # all_content_types = glob.glob(by_nefac_category_path)

    url_to_title={}
    title_to_pages={}

    def load_all_in_path(path):
        path_list=glob.glob(path+'/*')
        for folder in path_list:
            new_docs, dup_docs = pdfLoader(folder, title_to_pages)
            # print(path_list,folder)

            all_pdfs.update(new_docs)

            new_vids, dup_vids = youtubeLoader(folder, title_to_pages)
            all_yt_vids.update(new_vids)

            path_dirs=folder.split("/")
            resource_type=path_dirs[-2]
            resource_category=path_dirs[-1]
            to_change='audience' if resource_type=='by_audience' else 'nefac_category' if resource_type=='by_content' else 'resource_type' if resource_type=='by_resource' else ''
            for doc in new_docs:
                for page in title_to_pages[doc]:
                    page.metadata['title'] = page.metadata['source'].split('/')[-1].split(".")[0]
                    page.metadata[to_change].append(resource_category)

            for dup_doc in dup_docs:
                if resource_category not in title_to_pages[dup_doc][0].metadata[to_change]:
                    for page in title_to_pages[dup_doc]:
                        page.metadata[to_change].append(resource_category)
                    # if 'nefac_category' not in page.metadata:
                    # page.metadata['nefac_category'] = [resource_category] if resource_type=="by_content" else []
                    # if 'resource_type' not in page.metadata:
                    # page.metadata['resource_type'] = [resource_category] if resource_type=="by_resource" else []
                
            for vid in new_vids:
                for clip in title_to_pages[vid]:
                    clean_url = re.sub(r"&t=\d+s", "", clip.metadata["source"])
                    if clean_url not in url_to_title:
                        url_to_title[clean_url] = get_youtube_title(clean_url)
                    clip.metadata["title"] = url_to_title[clean_url]
                    clip.metadata["page"] = clip.metadata["start_seconds"]
                    clip.metadata[to_change].append(resource_category)

            for vid in dup_vids:
                if resource_category not in title_to_pages[vid][0].metadata[to_change]:
                    for clip in title_to_pages[vid]:
                        clip.metadata[to_change].append(resource_category)
                # if 'nefac_category' not in vid.metadata:
                # vid.metadata['nefac_category'] = [resource_category] if resource_type=="by_content" else []
                # if 'resource_type' not in vid.metadata:
                # vid.metadata['resource_type'] = [resource_category] if resource_type=="by_resource" else []

            # for existing_page in all_pdf_pages:
            #     if existing_page.metadata["title"] in dup_docs:
            #         if 'audience' not in existing_page.metadata or existing_page.metadata['audience'] == [] or folder.split("/")[-1] not in existing_page.metadata['audience']:
            #             existing_page.metadata["audience"].append(folder.split("/")[-1])
            #         if 'nefac_category' not in existing_page.metadata:
            #             existing_page.metadata['nefac_category'] = []
            #         if 'resource_type' not in existing_page.metadata:
            #             existing_page.metadata['resource_type'] = []
            
            # for existing_vid in all_yt_vid_chunks:
            #     if existing_vid.metadata["source"] in dup_vids:
            #         if 'page' not in existing_vid.metadata or existing_vid.metadata['page'] == "":
            #             existing_vid.metadata["page"] = existing_vid.metadata["start_seconds"]
            #         if 'audience' not in existing_vid.metadata or existing_vid.metadata['audience'] == [] or folder.split("/")[-1] not in existing_vid.metadata['audience']:
            #             existing_vid.metadata["audience"].append(folder.split("/")[-1])
            #         if 'nefac_category' not in existing_vid.metadata:
            #             existing_vid.metadata['nefac_category'] = []
            #         if 'resource_type' not in existing_vid.metadata:
            #             existing_vid.metadata['resource_type'] = []

            
    for path in all_paths:
        load_all_in_path(path)
    # for page in all_pdf_pages:
    #     page.metadata['type'] = 'pdf'
    # for vid in all_yt_vid_chunks:
    #     vid.metadata['type'] = 'youtube'
    return [page for pdf in all_pdfs for page in title_to_pages[pdf]], [clip for vid in all_yt_vids for clip in title_to_pages[vid]], all_pdfs, all_yt_vids