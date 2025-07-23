"""
YouTube content extractor for NEFAC crawler.
"""

import json
import logging
import random
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests

# Optional YouTube dependencies - handle import errors gracefully
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.proxies import WebshareProxyConfig
except ImportError:
    YouTubeTranscriptApi = None
    WebshareProxyConfig = None

from ..core.config import CrawlerConfig
from ..core.types import ExtractorResult
from .base import BaseExtractor, RequestMixin

logger = logging.getLogger(__name__)


class YouTubeExtractor(BaseExtractor, RequestMixin):
    """Extracts YouTube video information and transcripts."""

    def __init__(self, config: CrawlerConfig):
        super().__init__(config)
        self.youtube_dir = config.output_dir / "youtube"
        self.youtube_dir.mkdir(parents=True, exist_ok=True)
        self.youtube_channel_url = "https://www.youtube.com/@nefac"

        # Configure yt-dlp
        self.ytdl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extractaudio": False,
            "writeinfojson": False,
            "writethumbnail": False,
            "writesubtitles": False,
            "writeautomaticsub": False,
            "skip_download": True,
            "extract_flat": True,
            "playlist_items": "1-1000",
        }

    @property
    def source_name(self) -> str:
        return "youtube_channel"

    def extract(self) -> ExtractorResult:
        """Extract YouTube content - full channel crawl."""
        self._log_extraction_start()

        result = ExtractorResult(documents=[])

        # Check if YouTube dependencies are available
        if not yt_dlp and not YouTubeTranscriptApi:
            error_msg = "YouTube dependencies (yt-dlp, youtube_transcript_api) not available. Install with: pip install yt-dlp youtube_transcript_api"
            logger.error(error_msg)
            result.errors.append(error_msg)
            self._log_extraction_result(result)
            return result

        try:
            youtube_videos = self._extract_youtube_videos()
            # Convert to DocumentInfo format
            for video in youtube_videos:
                # YouTube videos are handled differently but still need DocumentInfo format
                result.metadata["youtube_videos"] = youtube_videos

        except Exception as e:
            error_msg = f"Error in YouTube extraction: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        self._log_extraction_result(result)
        return result

    def _extract_youtube_videos(self) -> List[Dict[str, Any]]:
        """Extract YouTube content - full channel crawl."""
        logger.info("Starting YouTube channel crawl...")

        if not yt_dlp:
            logger.warning("yt-dlp not available, skipping YouTube crawl")
            return []

        try:
            with yt_dlp.YoutubeDL(self.ytdl_opts) as ydl:
                # Extract channel info
                channel_info = ydl.extract_info(self.youtube_channel_url, download=False)

                if not channel_info or "entries" not in channel_info:
                    logger.error("Could not extract channel videos")
                    return []

                videos = channel_info["entries"]
                logger.info(f"Found {len(videos)} videos in channel")

                youtube_documents = []

                for i, video in enumerate(videos, 1):
                    if not video:
                        continue

                    video_url = video.get("url", "")
                    if not video_url:
                        continue

                    logger.info(f"Processing video {i}/{len(videos)}: {video.get('title', 'Unknown')}")

                    try:
                        # Get full metadata
                        full_metadata = self.get_youtube_metadata(video_url)
                        video_id = full_metadata.get("video_id", "")

                        if not video_id:
                            logger.warning(f"Could not get video ID for {video_url}")
                            continue

                        # Get transcript
                        transcript_data = self.get_youtube_transcript(video_id)

                        # Normalize transcript data to consistent format
                        if transcript_data:
                            transcript_data = self.normalize_transcript(transcript_data)

                        # Create document info
                        document_info = {
                            "id": f"youtube_{video_id}",
                            "title": full_metadata.get("title", "Unknown"),
                            "source_url": video_url,
                            "mime_type": "text/plain",
                            "date": full_metadata.get("upload_date", ""),
                            "modified": full_metadata.get("upload_date", ""),
                            "alt_text": "",
                            "description": full_metadata.get("description", ""),
                            "caption": "",
                            "source": "youtube_channel",
                            "file_size": 0,
                            "youtube_metadata": full_metadata,
                            "transcript_available": transcript_data is not None,
                            "video_id": video_id,
                            "channel": full_metadata.get("channel", ""),
                            "channel_id": full_metadata.get("channel_id", ""),
                            "duration": full_metadata.get("duration", 0),
                            "view_count": full_metadata.get("view_count", 0),
                            "like_count": full_metadata.get("like_count", 0),
                            "comment_count": full_metadata.get("comment_count", 0),
                            "tags": full_metadata.get("tags", []),
                            "categories": full_metadata.get("categories", []),
                            "thumbnail": full_metadata.get("thumbnail", ""),
                            "uploader": full_metadata.get("uploader", ""),
                        }

                        # Save transcript if available
                        if transcript_data:
                            transcript_file = self.save_youtube_transcript(video_id, transcript_data, full_metadata)
                            document_info["transcript_file"] = transcript_file
                            document_info["transcript_length"] = len(transcript_data)

                            # Calculate transcript word count
                            total_words = sum(len(entry.get("text", "").split()) for entry in transcript_data)
                            document_info["transcript_word_count"] = total_words

                        youtube_documents.append(document_info)

                        # Rate limiting
                        time.sleep(self.config.youtube_delay)

                    except Exception as e:
                        logger.error(f"Error processing video {video_url}: {e}")
                        continue

                logger.info(f"YouTube crawl completed: {len(youtube_documents)} videos processed")
                return youtube_documents

        except Exception as e:
            logger.error(f"YouTube channel crawl failed: {e}")
            return []

    def normalize_transcript(self, transcript):
        """Normalize transcript entries to consistent dictionary format"""
        normalized = []
        for entry in transcript:
            if hasattr(entry, "text"):
                # Convert object to dict
                normalized.append(
                    {
                        "text": entry.text,
                        "start": entry.start,
                        "duration": entry.duration,
                    }
                )
            elif isinstance(entry, dict):
                # Already a dict, keep as is
                normalized.append(entry)
        return normalized

    def get_youtube_transcript(self, video_id: str, max_retries: int = 3) -> Optional[List[Dict]]:
        """Get transcript for a YouTube video using multiple free methods"""
        if not YouTubeTranscriptApi and not yt_dlp:
            logger.warning("YouTube dependencies not available")
            return None

        # Method 1: YouTube Transcript API (Primary method - most reliable)
        if YouTubeTranscriptApi:
            transcript = self._get_transcript_youtube_api(video_id, max_retries)
            if transcript:
                logger.info(f"Transcript found using YouTube Transcript API for {video_id}")
                return transcript

        # Method 2: yt-dlp subtitle extraction (Secondary method)
        if yt_dlp:
            transcript = self._get_transcript_ytdlp(video_id)
            if transcript:
                logger.info(f"Transcript found using yt-dlp for {video_id}")
                return transcript

        # Method 3: YouTube's internal API endpoints (Fallback)
        transcript = self._get_transcript_alternative_methods(video_id)
        if transcript:
            logger.info(f"Transcript found using YouTube internal API for {video_id}")
            return transcript

        logger.warning(f"No transcript found for video {video_id} using any method")
        return None

    def _get_transcript_youtube_api(self, video_id: str, max_retries: int = 3) -> Optional[List[Dict]]:
        """Get transcript using YouTube Transcript API (primary method)"""
        # Initialize the API client
        ytt_api = None
        if self.config.webshare_username and self.config.webshare_password:
            logger.info("Using Webshare proxy for YouTube requests.")
            try:
                ytt_api = YouTubeTranscriptApi(
                    proxy_config=WebshareProxyConfig(
                        proxy_username=self.config.webshare_username,
                        proxy_password=self.config.webshare_password,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to initialize Webshare proxy: {e}")
                # Fallback to a direct client
                ytt_api = YouTubeTranscriptApi()
        else:
            ytt_api = YouTubeTranscriptApi()

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
                transcript_list = ytt_api.list_transcripts(video_id)

                # Try preferred languages first
                for lang in language_preferences:
                    try:
                        transcript = transcript_list.find_transcript([lang])
                        transcript_data = transcript.fetch()
                        return list(transcript_data)
                    except Exception:
                        continue  # Try next language

                # If no preferred language found, try manual transcripts first
                try:
                    for transcript in transcript_list:
                        if not transcript.is_generated:  # Manual transcripts
                            transcript_data = transcript.fetch()
                            return list(transcript_data)
                except Exception:
                    pass  # Continue to auto-generated

                # Finally, try any auto-generated transcript
                try:
                    for transcript in transcript_list:
                        if transcript.is_generated:  # Auto-generated transcripts
                            transcript_data = transcript.fetch()
                            return list(transcript_data)
                except Exception:
                    pass

            except Exception as e:
                if "no transcripts" in str(e).lower():
                    logger.info(f"No transcripts available for video {video_id}")
                    return None
                elif "could not retrieve" in str(e).lower():
                    logger.warning(f"Could not retrieve transcript for {video_id}, attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        continue
                else:
                    logger.error(f"Unexpected error getting transcript for {video_id}: {e}")
                    return None

        return None

    def _get_transcript_ytdlp(self, video_id: str) -> Optional[List[Dict]]:
        """Get transcript using yt-dlp subtitle extraction"""
        if not yt_dlp:
            return None

        video_url = f"https://www.youtube.com/watch?v={video_id}"

        # Try multiple language preferences
        language_preferences = [
            ["en"],
            ["en-US"],
            ["en-GB"],
            ["en-orig"],
        ]

        for lang_pref in language_preferences:
            try:
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "skip_download": True,
                    "writesubtitles": False,
                    "writeautomaticsub": True,
                    "subtitleslangs": lang_pref,
                    "listsubtitles": False,
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)
                    if "subtitles" in info:
                        for lang, subs in info["subtitles"].items():
                            if subs:
                                # Try to extract subtitle content
                                sub_url = subs[0]["url"]
                                response = requests.get(sub_url, timeout=30)
                                if response.status_code == 200:
                                    return self._parse_vtt_content(response.text)

            except Exception as e:
                logger.debug(f"yt-dlp failed for language {lang_pref}: {e}")
                continue

        logger.warning(f"yt-dlp could not extract transcript for {video_id} with any language preference.")
        return None

    def _get_transcript_alternative_methods(self, video_id: str) -> Optional[List[Dict]]:
        """Get transcript using YouTube's internal API endpoints"""
        try:
            # Try YouTube's internal timedtext API
            url = f"https://www.youtube.com/api/timedtext?v={video_id}&lang=en"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return self._parse_xml_transcript(response.text)
        except Exception as e:
            logger.debug(f"Alternative method failed for {video_id}: {e}")

        return None

    def _parse_xml_transcript(self, xml_content: str) -> Optional[List[Dict]]:
        """Parse XML transcript content"""
        try:
            root = ET.fromstring(xml_content)
            transcript = []

            for text_elem in root.findall(".//text"):
                start = float(text_elem.get("start", 0))
                duration = float(text_elem.get("dur", 0))
                text = text_elem.text or ""

                # Clean up the text
                text = re.sub(r"<[^>]+>", "", text)  # Remove XML tags
                text = text.strip()

                if text:
                    transcript.append(
                        {
                            "text": text,
                            "start": start,
                            "duration": duration,
                        }
                    )

            return transcript if transcript else None

        except Exception as e:
            logger.debug(f"Failed to parse XML transcript: {e}")
            return None

    def _parse_vtt_content(self, vtt_content: str) -> Optional[List[Dict]]:
        """Parse VTT subtitle content"""
        try:
            transcript = []
            lines = vtt_content.split("\n")

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Look for timestamp lines (format: 00:00:00.000 --> 00:00:00.000)
                if "-->" in line:
                    times = line.split(" --> ")
                    if len(times) == 2:
                        start_time = self._parse_vtt_time(times[0])
                        end_time = self._parse_vtt_time(times[1])

                        # Get the text lines that follow
                        text_lines = []
                        i += 1
                        while i < len(lines) and lines[i].strip():
                            text_line = lines[i].strip()
                            if text_line:
                                # Remove VTT formatting
                                text_line = re.sub(r"<[^>]+>", "", text_line)
                                text_lines.append(text_line)
                            i += 1

                        if text_lines:
                            transcript.append(
                                {
                                    "text": " ".join(text_lines),
                                    "start": start_time,
                                    "duration": end_time - start_time,
                                }
                            )

                i += 1

            return transcript if transcript else None

        except Exception as e:
            logger.debug(f"Failed to parse VTT content: {e}")
            return None

    def _parse_vtt_time(self, time_str: str) -> float:
        """Parse VTT time format to seconds"""
        try:
            # Format: 00:00:00.000
            parts = time_str.split(":")
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        except (ValueError, IndexError):
            return 0.0

    def get_youtube_metadata(self, url: str) -> Dict[str, Any]:
        """Get YouTube video metadata using yt-dlp"""
        try:
            opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
            }

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

                return {
                    "video_id": info.get("id", ""),
                    "title": info.get("title", ""),
                    "description": info.get("description", ""),
                    "duration": info.get("duration", 0),
                    "view_count": info.get("view_count", 0),
                    "like_count": info.get("like_count", 0),
                    "comment_count": info.get("comment_count", 0),
                    "uploader": info.get("uploader", ""),
                    "channel": info.get("channel", ""),
                    "channel_id": info.get("channel_id", ""),
                    "upload_date": info.get("upload_date", ""),
                    "tags": info.get("tags", []),
                    "categories": info.get("categories", []),
                    "thumbnail": info.get("thumbnail", ""),
                    "uploader_url": info.get("uploader_url", ""),
                    "availability": info.get("availability", ""),
                    "live_status": info.get("live_status", ""),
                    "release_timestamp": info.get("release_timestamp", ""),
                    "chapters": info.get("chapters", []),
                    "heatmap": info.get("heatmap", {}),
                }

        except Exception as e:
            logger.error(f"Failed to get metadata for {url}: {e}")
            return {}

    def save_youtube_transcript(self, video_id: str, transcript_data: List[Dict], metadata: Dict[str, Any]) -> str:
        """Save YouTube transcript to file"""
        transcript_file = self.youtube_dir / f"{video_id}_transcript.json"

        transcript_info = {
            "video_id": video_id,
            "title": metadata.get("title", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "transcript": transcript_data,
            "metadata": metadata,
            "extracted_at": time.time(),
        }

        try:
            with open(transcript_file, "w", encoding="utf-8") as f:
                json.dump(transcript_info, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved transcript for {video_id} to {transcript_file}")
            return str(transcript_file)

        except Exception as e:
            logger.error(f"Failed to save transcript for {video_id}: {e}")
            return ""
