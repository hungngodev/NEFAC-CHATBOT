import os
from langchain_community.document_loaders import (DirectoryLoader, PyPDFLoader,
                                                  YoutubeLoader)
from langchain_community.document_loaders.youtube import TranscriptFormat

def youtubeLoader(path, existing_vids):
    if 'yt_urls.txt' not in os.listdir(path):
        print('yt_urls.txt not in os.listdir(path)')
        return [], [], []

    with open(f"{path}/yt_urls.txt", "r") as f:
        URLs = f.readlines()

    new_vids = set()
    new_vids_chunks = []
    duplicate_vids = set()

    for url in URLs:
        # print(url)
        url=url.rstrip()
        if url in existing_vids:
            duplicate_vids.add(url)
        elif url not in existing_vids and url not in new_vids:
            loader = YoutubeLoader.from_youtube_url(
                url,
                add_video_info=False,
                transcript_format=TranscriptFormat.CHUNKS,
                chunk_size_seconds=60, # 60
            )
            new_vids.add(url)
            loaded_chunks=loader.load()
            # print(f"Loaded chunks for URL {url}: {loaded_chunks}")
            new_vids_chunks.extend(loaded_chunks)
            # print("\n\n".join(map(repr, loader.load())))
    # print(f"New Chunks: {new_vids_chunks}, New Documents: {new_vids}, Duplicate Documents: {duplicate_vids}")
    return new_vids_chunks, new_vids, duplicate_vids
