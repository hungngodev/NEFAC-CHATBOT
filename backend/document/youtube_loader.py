import os
from langchain_community.document_loaders import YoutubeLoader
from langchain_community.document_loaders.youtube import TranscriptFormat
from document.summary import generate_summary
import yt_dlp

def get_youtube_title(url): # function to scrape the titles of the youtube videos given the link
    ydl_opts = {
        'quiet': True,
        'no_warnings': True, 
        # 'cookies': 'cookies.txt'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Title not found')
            return title
    except Exception as e:
        print(f"Error fetching title for {url}: {str(e)}")
        return "Title not found"

def youtubeLoader(path, title_to_chunks, url_to_title, tag_type, tag):
    if not os.path.isdir(path) or 'yt_urls.txt' not in os.listdir(path):
        print('not a directory or yt_urls.txt not in path', path)
        return set()

    with open(f"{path}/yt_urls.txt", "r") as f:
        URLs = f.readlines()

    new_vids = set()
    for url in URLs:
        url=url.rstrip() # remove \n
        if url not in url_to_title:
            url_to_title[url] = get_youtube_title(url) # get the title if we haven't fetched it yet
            print(url_to_title[url])
        title = url_to_title[url]
        if title in title_to_chunks: # if we have already loaded this video
            if tag not in title_to_chunks[title][0].metadata[tag_type]: # update the tagging for each of the chunks if they don't have this tag yet
                for clip in title_to_chunks[title]:
                    clip.metadata[tag_type].append(tag)
        else:
            loader = YoutubeLoader.from_youtube_url(
                url,
                add_video_info=False,
                transcript_format=TranscriptFormat.CHUNKS,
                chunk_size_seconds=60, # 60
            )
            loaded_clips=loader.load()
            summary = generate_summary(loaded_clips[:-1]) # remove the last minute where information is usually irrelevant to summary
            print("youtube summary",summary)
            for clip in loaded_clips:
                clip.metadata["title"] = title # set the title
                clip.metadata["page"] = clip.metadata["start_seconds"] # update the page metadata for youtube videos
                clip.metadata['audience']=[] # initialize the tagging fields
                clip.metadata['nefac_category'] = []
                clip.metadata['resource_type'] = []
                clip.metadata[tag_type].append(tag) # update the current tag
                clip.metadata['type'] = 'youtube' # mark as youtube video
                clip.metadata['summary'] = summary
            new_vids.add(title)
            title_to_chunks[title] = loaded_clips # store the clips
    return new_vids