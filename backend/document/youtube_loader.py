import os
from langchain_community.document_loaders import (DirectoryLoader, PyPDFLoader,
                                                  YoutubeLoader)
from langchain_community.document_loaders.youtube import TranscriptFormat
import yt_dlp

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

def youtubeLoader(path, title_to_pages, url_to_title, tag_type, tag):
    if 'yt_urls.txt' not in os.listdir(path):
        print('yt_urls.txt not in os.listdir(path)')
        return set(), set()

    with open(f"{path}/yt_urls.txt", "r") as f:
        URLs = f.readlines()
    
    new_vids = set()
    for url in URLs:
        url=url.rstrip()
        if url not in url_to_title:
            url_to_title[url] = get_youtube_title(url)
        title = url_to_title[url]
        if title in title_to_pages:
            if tag not in title_to_pages[title][0].metadata[tag_type]:
                for clip in title_to_pages[title]:
                    clip.metadata[tag_type].append(tag)
        else:
            loader = YoutubeLoader.from_youtube_url(
                url,
                add_video_info=False,
                transcript_format=TranscriptFormat.CHUNKS,
                chunk_size_seconds=60, # 60
            )
            new_vids.add(title)
            loaded_clips=loader.load()
            for clip in loaded_clips:
                clip.metadata["title"] = title
                clip.metadata["page"] = clip.metadata["start_seconds"]
                clip.metadata['audience']=[]
                clip.metadata['nefac_category'] = []
                clip.metadata['resource_type'] = []
                clip.metadata[tag_type].append(tag)
                clip.metadata['type'] = 'youtube'
            title_to_pages[title]=loaded_clips
    return new_vids