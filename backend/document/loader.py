import glob
from document.pdf_loader import pdfLoader
from document.youtube_loader import youtubeLoader
import yt_dlp
import re

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
    
    all_pdf_pages = []
    all_yt_vid_chunks = []

    by_audience_path = "docs/by_audience/*"
    by_resource_type_path = "docs/by_resource/*"
    by_nefac_category_path = "docs/by_content/*"

    all_audience = glob.glob(by_audience_path)
    all_resources = glob.glob(by_resource_type_path)
    all_content_types = glob.glob(by_nefac_category_path)

    url_to_title={}

    def load_all_in_path(path_list):
        print("Loading Paths",path_list)
        for audience_folder in path_list:
            new_pages, new_docs, dup_docs = pdfLoader(audience_folder, all_pdfs)

            all_pdfs.update(new_docs)
            all_pdf_pages.extend(new_pages)

            new_yt_chunks, new_vids, dup_vids = youtubeLoader(audience_folder, all_yt_vids)
            all_yt_vids.update(new_vids)
            all_yt_vid_chunks.extend(new_yt_chunks)

            for page in new_pages:
                page.metadata['title'] = page.metadata['source'].split('/')[-1].split(".")[0]
                page.metadata["audience"] = [audience_folder.split("/")[-1]]
                if 'nefac_category' not in page.metadata:
                    page.metadata['nefac_category'] = []
                if 'resource_type' not in page.metadata:
                    page.metadata['resource_type'] = []
                
            for vid in new_yt_chunks:
                clean_url = re.sub(r"&t=\d+s", "", vid.metadata["source"])
                if clean_url not in url_to_title:
                    url_to_title[clean_url] = get_youtube_title(clean_url)
                vid.metadata["title"] = url_to_title[clean_url]
                vid.metadata["audience"] = [audience_folder.split("/")[-1]]
                vid.metadata["page"] = vid.metadata["start_seconds"]
                if 'nefac_category' not in vid.metadata:
                    vid.metadata['nefac_category'] = []
                if 'resource_type' not in vid.metadata:
                    vid.metadata['resource_type'] = []


            for existing_page in all_pdf_pages:
                if existing_page.metadata["title"] in dup_docs:
                    if 'audience' not in existing_page.metadata or existing_page.metadata['audience'] == [] or audience_folder.split("/")[-1] not in existing_page.metadata['audience']:
                        existing_page.metadata["audience"].append(audience_folder.split("/")[-1])
                    if 'nefac_category' not in existing_page.metadata:
                        existing_page.metadata['nefac_category'] = []
                    if 'resource_type' not in existing_page.metadata:
                        existing_page.metadata['resource_type'] = []
            
            for existing_vid in all_yt_vid_chunks:
                if existing_vid.metadata["source"] in dup_vids:
                    if 'page' not in existing_vid.metadata or existing_vid.metadata['page'] == "":
                        existing_vid.metadata["page"] = existing_vid.metadata["start_seconds"]
                    if 'audience' not in existing_vid.metadata or existing_vid.metadata['audience'] == [] or audience_folder.split("/")[-1] not in existing_vid.metadata['audience']:
                        existing_vid.metadata["audience"].append(audience_folder.split("/")[-1])
                    if 'nefac_category' not in existing_vid.metadata:
                        existing_vid.metadata['nefac_category'] = []
                    if 'resource_type' not in existing_vid.metadata:
                        existing_vid.metadata['resource_type'] = []
            
                
    load_all_in_path(all_audience)

    load_all_in_path(all_resources)

    load_all_in_path(all_content_types)

    # print('ALL CHUNKS',all_yt_vid_chunks)
    for page in all_pdf_pages:
        page.metadata['type'] = 'pdf'
    for vid in all_yt_vid_chunks:
        vid.metadata['type'] = 'youtube'
    return all_pdf_pages, all_yt_vid_chunks, all_pdfs, all_yt_vids