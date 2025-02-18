import glob
from pdf_loader import pdfLoader
from youtube_loader import youtubeLoader

# TODO: implement for txt files, images, etc. save vector store to disk. add optional filter params for each category (audience, resource_type, nefac_category) retrieved from frontend

def load_all_documents():
    all_pdfs = []
    all_pdf_pages = []
    all_yt_vids = []
    all_yt_vid_chunks = []

    by_audience_path = "docs/by_audience/*"
    by_resource_type_path = "docs/by_resource/*"
    by_nefac_category_path = "docs/by_content/*"

    all_audience = glob.glob(by_audience_path)
    all_resources = glob.glob(by_resource_type_path)
    all_content_types = glob.glob(by_nefac_category_path)
    
    for idx, audience_folder in enumerate(all_audience):
        new_pages, new_docs, dup_docs = pdfLoader(audience_folder, all_pdfs)
        all_pdfs.extend(new_docs)
        all_pdf_pages.extend(new_pages)

        new_yt_chunks, new_vids, dup_vids = youtubeLoader(audience_folder, all_yt_vids)
        all_yt_vids.extend(new_vids)
        all_yt_vid_chunks.extend(new_yt_chunks)

        for page in new_pages:
            page.metadata['title'] = page.metadata['source'].split('/')[-1].split(".")[0]
            page.metadata["audience"] = [audience_folder.split("/")[-1]]
            if 'nefac_category' not in page.metadata:
                page.metadata['nefac_category'] = []
            if 'resource_type' not in page.metadata:
                page.metadata['resource_type'] = []
        
        for vid in new_yt_chunks:
            vid.metadata["title"] = vid.metadata["source"].split('=')[1][:-2]
            vid.metadata["audience"] = [audience_folder.split("/")[-1]]
            vid.metadata["page"] = vid.metadata["start_seconds"]
            if 'nefac_category' not in vid.metadata:
                vid.metadata['nefac_category'] = []
            if 'resource_type' not in vid.metadata:
                vid.metadata['resource_type'] = []

        for dup_doc in dup_docs:
            for existing_page in all_pdf_pages:
                if existing_page.metadata["title"] == dup_doc:
                    if 'audience' not in existing_page.metadata or existing_page.metadata['audience'] == [] or audience_folder.split("/")[-1] not in existing_page.metadata['audience']:
                        existing_page.metadata["audience"].append(audience_folder.split("/")[-1])
                    if 'nefac_category' not in existing_page.metadata:
                        existing_page.metadata['nefac_category'] = []
                    if 'resource_type' not in existing_page.metadata:
                        existing_page.metadata['resource_type'] = []
        
        for dup_vid in dup_vids:
            for existing_vid in all_yt_vid_chunks:
                if existing_vid.metadata["title"] == dup_vid:
                    if 'page' not in existing_vid.metadata or existing_vid.metadata['page'] == "":
                        existing_vid.metadata["page"] = existing_vid.metadata["start_seconds"]
                    if 'audience' not in existing_vid.metadata or existing_vid.metadata['audience'] == [] or audience_folder.split("/")[-1] not in existing_vid.metadata['audience']:
                        existing_vid.metadata["audience"].append(audience_folder.split("/")[-1])
                    if 'nefac_category' not in existing_vid.metadata:
                        existing_vid.metadata['nefac_category'] = []
                    if 'resource_type' not in existing_vid.metadata:
                        existing_vid.metadata['resource_type'] = []
            

    for idx, resource_folder in enumerate(all_resources):
        new_pages, new_docs, dup_docs = pdfLoader(resource_folder, all_pdfs)
        all_pdfs.extend(new_docs)
        all_pdf_pages.extend(new_pages)

        new_yt_chunks, new_vids, dup_vids = youtubeLoader(resource_folder, all_yt_vids)
        all_yt_vids.extend(new_vids)
        all_yt_vid_chunks.extend(new_yt_chunks)

        for page in new_pages:
            page.metadata['title'] = page.metadata['source'].split('/')[-1]
            page.metadata["resource_type"] = [resource_folder.split("/")[-1]]

            if 'nefac_category' not in page.metadata:
                page.metadata['nefac_category'] = []
            if 'audience' not in page.metadata:
                page.metadata['audience'] = []

        # set vids "start_seconds" to page number
        for vid in new_yt_chunks:
            vid.metadata["title"] = vid.metadata["source"].split('=')[1][:-2]
            vid.metadata["resource_type"] = [resource_folder.split("/")[-1]]
            vid.metadata["page"] = vid.metadata["start_seconds"]

            if 'nefac_category' not in vid.metadata:
                vid.metadata['nefac_category'] = []
            if 'audience' not in vid.metadata:
                vid.metadata['audience'] = []

        for dup_doc in dup_docs:
            for existing_page in all_pdf_pages:
                if existing_page.metadata["title"] == dup_doc:
                    if 'audience' not in existing_page.metadata:
                        existing_page.metadata["audience"] = []
                    if 'nefac_category' not in existing_page.metadata:
                        existing_page.metadata['nefac_category'] = []
                    if 'resource_type' not in existing_page.metadata or existing_page.metadata['resource_type'] == [] or resource_folder.split("/")[-1] not in existing_page.metadata['resource_type']:
                        existing_page.metadata['resource_type'].append(resource_folder.split("/")[-1])
        
        for dup_vid in dup_vids:
            for existing_vid in all_yt_vid_chunks:
                if existing_vid.metadata["title"] == dup_vid:
                    if 'page' not in existing_vid.metadata or existing_vid.metadata['page'] == "":
                        existing_vid.metadata["page"] = existing_vid.metadata["start_seconds"]
                    if 'audience' not in existing_vid.metadata:
                        existing_vid.metadata["audience"] = []
                    if 'nefac_category' not in existing_vid.metadata:
                        existing_vid.metadata['nefac_category'] = []
                    if 'resource_type' not in existing_vid.metadata or existing_vid.metadata['resource_type'] == [] or resource_folder.split("/")[-1] not in existing_vid.metadata['resource_type']:
                        existing_vid.metadata['resource_type'].append(resource_folder.split("/")[-1])
            
    for idx, content_folder in enumerate(all_content_types):
        new_pages, new_docs, dup_docs = pdfLoader(content_folder, all_pdfs)

        all_pdfs.extend(new_docs)
        all_pdf_pages.extend(new_pages)

        new_yt_chunks, new_vids, dup_vids = youtubeLoader(content_folder, all_yt_vids)
        all_yt_vids.extend(new_vids)
        all_yt_vid_chunks.extend(new_yt_chunks)

        for page in new_pages:
            page.metadata['title'] = page.metadata['source'].split('/')[-1]
            page.metadata["nefac_category"] = [content_folder.split("/")[-1]]
            if 'resource_type' not in page.metadata:
                page.metadata['resource_type'] = []
            if 'audience' not in page.metadata:
                page.metadata['audience'] = []

        # set vids "start_seconds" to page number
        for vid in new_yt_chunks:
            vid.metadata["title"] = vid.metadata["source"].split('=')[1][:-2]
            vid.metadata["nefac_category"] = [content_folder.split("/")[-1]]
            vid.metadata["page"] = vid.metadata["start_seconds"]

            if 'resource_type' not in vid.metadata:
                vid.metadata['resource_type'] = []
            if 'audience' not in vid.metadata:
                vid.metadata['audience'] = []

        for dup_doc in dup_docs:
            for existing_page in all_pdf_pages:
                if existing_page.metadata["title"] == dup_doc:
                    if 'audience' not in existing_page.metadata:
                        existing_page.metadata["audience"] = []
                    if 'nefac_category' not in existing_page.metadata or existing_page.metadata['nefac_category'] == [] or content_folder.split("/")[-1] not in existing_page.metadata['nefac_category']:
                        existing_page.metadata['nefac_category'].append(content_folder.split("/")[-1])
                    if 'resource_type' not in existing_page.metadata:
                        existing_page.metadata['resource_type'] = []
        
        for dup_vid in dup_vids:
            for existing_vid in all_yt_vid_chunks:
                if existing_vid.metadata["title"] == dup_vid:
                    if 'page' not in existing_vid.metadata or existing_vid.metadata['page'] == "":
                        existing_vid.metadata["page"] = existing_vid.metadata["start_seconds"]
                    if 'audience' not in existing_vid.metadata:
                        existing_vid.metadata["audience"] = []
                    if 'nefac_category' not in existing_vid.metadata or existing_vid.metadata['nefac_category'] == [] or content_folder.split("/")[-1] not in existing_vid.metadata['nefac_category']:
                        existing_vid.metadata['nefac_category'].append(content_folder.split("/")[-1])
                    if 'resource_type' not in existing_vid.metadata:
                        existing_vid.metadata['resource_type'] = []

    return all_pdf_pages, all_yt_vid_chunks
