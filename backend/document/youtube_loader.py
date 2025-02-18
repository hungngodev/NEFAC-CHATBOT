import os
from langchain_community.document_loaders import (DirectoryLoader, PyPDFLoader,
                                                  YoutubeLoader)
from langchain_community.document_loaders.youtube import TranscriptFormat


def youtubeLoader(path, existing_vids):
    # Load all YouTube videos from list of URLs

    if 'yt_urls.txt' not in os.listdir(path):
        return [], [], []

    with open(f"{path}/yt_urls.txt", "r") as f:
        URLs = f.readlines()

    new_vids = []
    new_vids_chunks = []
    duplicate_vids = []

    for idx, url in enumerate(URLs):
        url_title = url.split('=')[1]
        if url_title in existing_vids:
            duplicate_vids.append(url_title)
        elif url_title not in existing_vids and url_title not in new_vids:
            loader = YoutubeLoader.from_youtube_url(
                url,
                add_video_info=False, # Set to True to include video metadata
                transcript_format=TranscriptFormat.CHUNKS,
                chunk_size_seconds=60,
            )
            new_vids.append(url_title)
            new_vids_chunks.extend(loader.load())
            # print("\n\n".join(map(repr, loader.load())))

    return new_vids_chunks, new_vids, duplicate_vids
