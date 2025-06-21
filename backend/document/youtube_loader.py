import logging
import os
import random
import time
from urllib.parse import parse_qs, urlparse

import yt_dlp
from langchain_community.document_loaders import YoutubeLoader
from langchain_community.document_loaders.youtube import TranscriptFormat
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from youtube_transcript_api import YouTubeTranscriptApi

from llm.constant import YOUTUBE_MODEL_NAME
from load_env import load_env
from prompts import TRANSCRIPT_CLEANING_PROMPT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_env()

llm = ChatOpenAI(
    model=YOUTUBE_MODEL_NAME,
    temperature=0.1,
    max_tokens=1024,
    api_key=os.getenv("OPENAI_API_KEY"),
)


def clean_text(text):
    """
    Clean an auto-generated YouTube transcript using an LLM.

    Args:
        text (str): Raw transcript text.

    Returns:
        str: Cleaned transcript text.
    """
    # Define the prompt template
    prompt_template = PromptTemplate.from_template(TRANSCRIPT_CLEANING_PROMPT)

    prompt = prompt_template.format(input_text=text)

    try:
        cleaned_text = llm.invoke(prompt).content.strip()
        return cleaned_text
    except Exception as e:
        logger.error(f"Error cleaning text: {str(e)}")
        return text  # Return original text as fallback


def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    try:
        parsed_url = urlparse(url)
        if parsed_url.hostname in ["youtu.be"]:
            return parsed_url.path[1:]
        elif parsed_url.hostname in ["www.youtube.com", "youtube.com"]:
            if parsed_url.path == "/watch":
                return parse_qs(parsed_url.query)["v"][0]
            elif parsed_url.path.startswith("/embed/"):
                return parsed_url.path.split("/")[2]
            elif parsed_url.path.startswith("/v/"):
                return parsed_url.path.split("/")[2]
        return None
    except Exception:
        return None


def check_video_availability(url):
    """Check if YouTube video exists and is accessible"""
    video_id = extract_video_id(url)
    if not video_id:
        return False, "Invalid YouTube URL"

    try:
        # Use yt-dlp to check video availability
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("availability") in [
                "private",
                "premium_only",
                "subscriber_only",
            ]:
                return False, f"Video is {info.get('availability', 'restricted')}"
            return True, "Available"
    except Exception as e:
        if "Private video" in str(e):
            return False, "Private video"
        elif "Video unavailable" in str(e):
            return False, "Video unavailable"
        elif "deleted" in str(e).lower():
            return False, "Video deleted"
        return False, f"Access error: {str(e)}"


def get_transcript_direct(url, max_retries=3):
    """Try to get transcript using YouTube Transcript API directly with enhanced retry mechanism"""
    video_id = extract_video_id(url)
    if not video_id:
        return None, "Invalid video ID"

    # Language preferences in order of preference
    language_preferences = ["en", "en-US", "en-GB", "en-orig"]

    for attempt in range(max_retries):
        try:
            # Add small delay between attempts to avoid rate limiting
            if attempt > 0:
                delay = random.uniform(1, 3) * attempt
                logger.info(f"Retrying transcript fetch after {delay:.1f}s delay (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)

            # Get available transcripts
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try preferred languages first
            for lang in language_preferences:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    transcript_data = transcript.fetch()
                    return transcript_data, f"Transcript found in {lang}"
                except Exception as e:
                    if "no element found" not in str(e).lower():
                        continue  # Try next language
                    else:
                        raise e  # Propagate XML parsing errors for retry

            # If no preferred language found, try manual transcripts first
            try:
                for transcript in transcript_list:
                    if not transcript.is_generated:  # Manual transcripts
                        transcript_data = transcript.fetch()
                        return (
                            transcript_data,
                            f"Manual transcript found in {transcript.language}",
                        )
            except Exception as e:
                if "no element found" not in str(e).lower():
                    pass  # Continue to auto-generated
                else:
                    raise e  # Propagate XML parsing errors for retry

            # Finally try any auto-generated transcript
            try:
                for transcript in transcript_list:
                    if transcript.is_generated:  # Auto-generated transcripts
                        transcript_data = transcript.fetch()
                        return (
                            transcript_data,
                            f"Auto-generated transcript found in {transcript.language}",
                        )
            except Exception as e:
                if "no element found" not in str(e).lower():
                    pass
                else:
                    raise e  # Propagate XML parsing errors for retry

            return None, "No transcripts available"

        except Exception as e:
            error_msg = str(e).lower()
            if "disabled" in error_msg:
                return None, "Transcripts disabled"
            elif "unavailable" in error_msg:
                return None, "Video unavailable"
            elif "private" in error_msg:
                return None, "Video is private"
            elif "no element found" in error_msg and attempt < max_retries - 1:
                logger.warning(f"XML parsing error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                continue  # Retry for XML parsing errors
            elif attempt == max_retries - 1:
                return None, f"Transcript error after {max_retries} attempts: {str(e)}"

    return None, f"Failed after {max_retries} attempts"


def get_transcript_ytdlp(url):
    """Get transcript using yt-dlp as fallback method with enhanced language support"""
    video_id = extract_video_id(url)
    if not video_id:
        return None, "Invalid video ID"

    import json
    import tempfile
    from pathlib import Path

    # Try multiple language preferences
    language_preferences = [
        ["en"],  # English first
        ["en-US"],  # US English
        ["en-GB"],  # UK English
        ["en-orig"],  # Original English
        ["*"],  # Any language available
    ]

    for lang_pref in language_preferences:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "skip_download": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": lang_pref,
                    "subtitlesformat": "json3",  # JSON format for easier parsing
                    "outtmpl": f"{temp_dir}/%(id)s.%(ext)s",
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                # Look for subtitle files
                subtitle_files = list(Path(temp_dir).glob(f"{video_id}.*.json3"))
                if not subtitle_files:
                    continue  # Try next language preference

                # Read and parse the JSON subtitle file
                with open(subtitle_files[0], "r", encoding="utf-8") as f:
                    subtitle_data = json.load(f)

                # Convert to transcript format
                transcript_entries = []
                for event in subtitle_data.get("events", []):
                    if "segs" in event:
                        # Combine all segments in this event
                        text = "".join(seg.get("utf8", "") for seg in event["segs"])
                        if text.strip():
                            transcript_entries.append(
                                {
                                    "text": text.strip(),
                                    "start": event.get("tStartMs", 0) / 1000.0,  # Convert to seconds
                                    "duration": event.get("dDurationMs", 0) / 1000.0,
                                }
                            )

                if transcript_entries:
                    lang_used = lang_pref[0] if lang_pref[0] != "*" else "auto-detected"
                    return (
                        transcript_entries,
                        f"Transcript extracted via yt-dlp ({lang_used})",
                    )

        except Exception as e:
            if lang_pref == language_preferences[-1]:  # Last attempt
                return None, f"yt-dlp extraction failed: {str(e)}"
            continue  # Try next language preference

    return None, "No subtitles found in any supported language"


def get_youtube_metadata(url):
    """Get comprehensive YouTube video metadata using yt-dlp"""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            metadata = {
                "title": info.get("title", "Title not found"),
                "description": info.get("description", ""),
                "duration": info.get("duration", 0),
                "view_count": info.get("view_count", 0),
                "upload_date": info.get("upload_date", ""),
                "uploader": info.get("uploader", ""),
                "channel": info.get("channel", ""),
                "channel_id": info.get("channel_id", ""),
                "tags": info.get("tags", []),
                "categories": info.get("categories", []),
                "language": info.get("language", ""),
                "subtitles_available": bool(info.get("automatic_captions", {})),
                "like_count": info.get("like_count", 0),
                "age_limit": info.get("age_limit", 0),
            }
            return metadata
    except Exception as e:
        logger.error(f"Error fetching metadata for {url}: {str(e)}")
        return {"title": "Title not found"}


def get_youtube_title(url):
    """Get YouTube video title (wrapper for backwards compatibility)"""
    metadata = get_youtube_metadata(url)
    return metadata.get("title", "Title not found")


def create_document_from_transcript(transcript_data, title, url):
    """Create document chunks from transcript data"""
    documents = []
    current_chunk = []
    current_start = 0
    chunk_duration = 60  # 60 seconds per chunk

    for entry in transcript_data:
        start_time = entry["start"]
        text = entry["text"]

        # If we've exceeded the chunk duration, create a new chunk
        if start_time - current_start >= chunk_duration and current_chunk:
            chunk_text = " ".join(current_chunk)
            doc = Document(
                page_content=chunk_text,
                metadata={
                    "title": title,
                    "page": current_start,
                    "type": "youtube",
                    "source": url,
                    "start_seconds": current_start,
                    "end_seconds": start_time,
                },
            )
            documents.append(doc)
            current_chunk = []
            current_start = start_time

        current_chunk.append(text)

    # Add the last chunk if there's content
    if current_chunk:
        chunk_text = " ".join(current_chunk)
        doc = Document(
            page_content=chunk_text,
            metadata={
                "title": title,
                "page": current_start,
                "type": "youtube",
                "source": url,
                "start_seconds": current_start,
            },
        )
        documents.append(doc)

    return documents


def youtubeLoader(url, title_to_chunks, url_to_title):
    # Return new video names
    if url in url_to_title:
        title = url_to_title[url]
        if title in title_to_chunks:
            logger.info(f"Video already processed, skipping: {url}")
            return set()

    logger.info(f"Starting processing for YouTube URL: {url}")

    # Step 1: Check video availability
    logger.info(f"Checking video availability for: {url}")
    is_available, availability_msg = check_video_availability(url)
    if not is_available:
        logger.warning(f"Skipping YouTube video {url}: {availability_msg}")
        return set()

    # Step 2: Get video metadata
    logger.info(f"Fetching video metadata for: {url}")
    video_metadata = get_youtube_metadata(url)
    title = video_metadata.get("title", "Title not found")
    if title == "Title not found":
        logger.warning(f"Could not fetch title for {url}, using URL as title")
        title = url
    else:
        logger.info(f"Video title: {title}")

    # Step 3: Try multiple methods to get transcript
    loaded_clips = []

    # Method 1: Try LangChain YoutubeLoader
    try:
        logger.info(f"Attempting LangChain loader for: {title}")
        loader = YoutubeLoader.from_youtube_url(
            url,
            add_video_info=False,
            transcript_format=TranscriptFormat.CHUNKS,
            chunk_size_seconds=60,
        )
        loaded_clips = loader.load()
        logger.info(f"Successfully loaded {len(loaded_clips)} clips using LangChain loader for: {title}")

    except Exception as e:
        logger.warning(f"LangChain loader failed for {title}: {str(e)}")

        # Method 2: Try direct YouTube Transcript API
        try:
            logger.info(f"Attempting direct transcript API for: {title}")
            transcript_data, transcript_msg = get_transcript_direct(url)
            if transcript_data:
                loaded_clips = create_document_from_transcript(transcript_data, title, url)
                logger.info(f"Successfully loaded {len(loaded_clips)} clips using direct API ({transcript_msg}) for: {title}")
            else:
                logger.warning(f"Direct transcript API failed for {title}: {transcript_msg}")

                # Method 3: Try yt-dlp as final fallback
                try:
                    logger.info(f"Attempting yt-dlp fallback for: {title}")
                    transcript_data, transcript_msg = get_transcript_ytdlp(url)
                    if transcript_data:
                        loaded_clips = create_document_from_transcript(transcript_data, title, url)
                        logger.info(f"Successfully loaded {len(loaded_clips)} clips using yt-dlp ({transcript_msg}) for: {title}")
                    else:
                        logger.warning(f"yt-dlp fallback failed for {title}: {transcript_msg}")
                except Exception as e3:
                    logger.error(f"yt-dlp fallback error for {title}: {str(e3)}")

        except Exception as e2:
            logger.error(f"Direct transcript API error for {title}: {str(e2)}")

            # Method 3: Try yt-dlp as final fallback
            try:
                logger.info(f"Attempting yt-dlp fallback for: {title}")
                transcript_data, transcript_msg = get_transcript_ytdlp(url)
                if transcript_data:
                    loaded_clips = create_document_from_transcript(transcript_data, title, url)
                    logger.info(f"Successfully loaded {len(loaded_clips)} clips using yt-dlp ({transcript_msg}) for: {title}")
                else:
                    logger.warning(f"yt-dlp fallback failed for {title}: {transcript_msg}")
            except Exception as e3:
                logger.error(f"yt-dlp fallback error for {title}: {str(e3)}")

    # Step 4: Process loaded clips if we have any
    if loaded_clips:
        logger.info(f"Processing {len(loaded_clips)} clips for: {title}")

        # Clean and enrich metadata for each clip
        for i, clip in enumerate(loaded_clips, 1):
            logger.debug(f"Processing clip {i}/{len(loaded_clips)} for: {title}")

            clip.metadata.update(
                {
                    "title": title,
                    "type": "youtube",
                    "source": url,
                    "duration": video_metadata.get("duration", 0),
                    "uploader": video_metadata.get("uploader", ""),
                    "channel": video_metadata.get("channel", ""),
                    "upload_date": video_metadata.get("upload_date", ""),
                    "view_count": video_metadata.get("view_count", 0),
                    "tags": video_metadata.get("tags", []),
                    "categories": video_metadata.get("categories", []),
                    "language": video_metadata.get("language", ""),
                }
            )

            if "page" not in clip.metadata:
                clip.metadata["page"] = clip.metadata.get("start_seconds", 0)

            # Clean the text using LLM
            try:
                logger.debug(f"Cleaning text for clip {i}/{len(loaded_clips)} of: {title}")
                cleaned_text = clean_text(clip.page_content)
                logger.debug(f"Original text: {clip.page_content[:100]}...")
                logger.debug(f"Cleaned text: {cleaned_text[:100]}...")
                clip.page_content = cleaned_text
            except Exception as e:
                logger.error(f"Error cleaning text for {title}: {str(e)}, using original text")

        title_to_chunks[title] = loaded_clips
        url_to_title[url] = title
        logger.info(f"Successfully processed YouTube video with transcript: {title}")
        return {title}

    else:
        # No transcript available - create a basic document with video metadata
        logger.info(f"No transcript available for {title}, creating metadata-only document")

        # Create enhanced content using available metadata
        content_parts = [f"YouTube video: {title}", f"URL: {url}"]

        if video_metadata.get("description"):
            # Add first 500 chars of description
            desc = video_metadata["description"][:500]
            if len(video_metadata["description"]) > 500:
                desc += "..."
            content_parts.append(f"Description: {desc}")

        if video_metadata.get("uploader"):
            content_parts.append(f"Channel: {video_metadata['uploader']}")

        if video_metadata.get("duration"):
            duration_min = video_metadata["duration"] // 60
            duration_sec = video_metadata["duration"] % 60
            content_parts.append(f"Duration: {duration_min}m {duration_sec}s")

        if video_metadata.get("tags"):
            tags_str = ", ".join(video_metadata["tags"][:10])  # First 10 tags
            content_parts.append(f"Tags: {tags_str}")

        content_parts.append("Note: No transcript available for this video.")

        # Create a basic document with video information
        basic_doc = Document(
            page_content="\n".join(content_parts),
            metadata={
                "title": title,
                "page": 0,
                "type": "youtube",
                "source": url,
                "transcript_available": False,
                "duration": video_metadata.get("duration", 0),
                "uploader": video_metadata.get("uploader", ""),
                "channel": video_metadata.get("channel", ""),
                "upload_date": video_metadata.get("upload_date", ""),
                "view_count": video_metadata.get("view_count", 0),
                "tags": video_metadata.get("tags", []),
                "categories": video_metadata.get("categories", []),
                "language": video_metadata.get("language", ""),
                "note": "This video does not have transcripts available",
            },
        )

        title_to_chunks[title] = [basic_doc]
        url_to_title[url] = title
        logger.info(f"Created metadata-only document for: {title}")
        return {title}
