"""
YouTube Extractor for NEFAC Crawler - Comprehensive YouTube Channel Crawling
"""

import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

# Imports relative to the crawler directory (where run.py is located)
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.core.types import CrawlerSource, DocumentInfo, ExtractorResult
from src.service.crawler.extractors.base import BaseExtractor
from src.service.crawler.utils.common import DateUtils

logger = logging.getLogger(__name__)


class YouTubeExtractor(BaseExtractor):
    """Comprehensive YouTube extractor for NEFAC channel."""

    def __init__(self, config: CrawlerConfig):
        super().__init__(config)

        # Use dedicated YouTube configuration
        self.youtube_config = config.youtube
        self.youtube_channel_url = self.youtube_config.channel_url
        self.youtube_dir = self.config.output_dir / self.youtube_config.output_subdir
        # Don't create directory until we actually have videos to save

        # YouTube processing settings from dedicated config
        self.youtube_delay = self.youtube_config.request_delay
        self.max_videos = self.youtube_config.max_videos
        self.max_concurrent = self.youtube_config.max_concurrent
        self.batch_size = self.youtube_config.batch_size
        self.enable_transcripts = self.youtube_config.enable_transcripts
        self.timeout_seconds = self.youtube_config.timeout_seconds

        # Proxy settings from YouTube config
        self.webshare_username = self.youtube_config.webshare_username
        self.webshare_password = self.youtube_config.webshare_password
        self.http_proxy = self.youtube_config.http_proxy
        self.https_proxy = self.youtube_config.https_proxy
        self.rotating_proxy = self.youtube_config.rotating_proxy

        # Content filtering settings
        self.min_duration = self.youtube_config.min_duration_seconds
        self.max_duration = self.youtube_config.max_duration_seconds
        self.skip_live_streams = self.youtube_config.skip_live_streams
        self.skip_shorts = self.youtube_config.skip_shorts

    @property
    def source_name(self) -> str:
        return CrawlerSource.YOUTUBE.value

    def extract(self) -> ExtractorResult:
        """Extract all videos from NEFAC YouTube channel."""
        logger.info("🎥 Starting NEFAC YouTube channel extraction...")

        # Check dependencies
        if not self._check_dependencies():
            return ExtractorResult(
                documents=[],
                metadata={
                    "error": "Missing required dependencies: yt-dlp, youtube-transcript-api"
                },
            )

        try:
            # Get all videos from channel
            videos = self._get_channel_videos()

            if not videos:
                logger.warning("No videos found in NEFAC YouTube channel")
                return ExtractorResult(documents=[], metadata={"videos_found": 0})

            logger.info(f"Found {len(videos)} videos in NEFAC channel")

            # Process each video
            documents = []
            failed_count = 0

            for i, video in enumerate(videos, 1):
                try:
                    logger.info(
                        f"📹 Processing video {i}/{len(videos)}: {video.get('title', 'Unknown')}"
                    )

                    doc = self._process_video(video)
                    # Ensure we only append DocumentInfo objects, not dictionaries
                    if doc and isinstance(doc, DocumentInfo):
                        documents.append(doc)
                    else:
                        failed_count += 1
                        if doc:
                            logger.warning(
                                f"Skipping non-DocumentInfo object: {type(doc)}"
                            )

                    # Rate limiting to avoid YouTube restrictions - EMERGENCY LONG DELAYS
                    if i < len(videos):
                        # Check if we're in IP ban emergency mode
                        if (
                            hasattr(self, "_consecutive_transcript_failures")
                            and self._consecutive_transcript_failures >= 3
                        ):
                            delay = random.uniform(
                                180.0, 300.0
                            )  # 3-5 minute delays during IP ban
                            logger.warning(
                                f"🚫 IP BAN MODE: Waiting {delay:.1f}s before next video (no transcripts)"
                            )
                        else:
                            delay = random.uniform(
                                self.youtube_delay, self.youtube_delay + 10.0
                            )  # Increased random range
                            logger.debug(
                                f"⏳ Waiting {delay:.1f}s before next video..."
                            )
                        time.sleep(delay)

                except Exception as e:
                    logger.error(
                        f"❌ Failed to process video {video.get('url', 'unknown')}: {e}"
                    )
                    failed_count += 1
                    continue

            logger.info(
                f"✅ YouTube extraction complete: {len(documents)} videos processed, {failed_count} failed"
            )

            return ExtractorResult(
                documents=documents,
                metadata={
                    "channel_url": self.youtube_channel_url,
                    "videos_found": len(videos),
                    "videos_processed": len(documents),
                    "failed_videos": failed_count,
                    "success_rate": len(documents) / len(videos) if videos else 0,
                },
            )

        except Exception as e:
            logger.error(f"❌ YouTube extraction failed: {e}")
            return ExtractorResult(documents=[], metadata={"error": str(e)})

    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available."""
        try:
            pass

            return True
        except ImportError as e:
            logger.error(f"Missing YouTube dependencies: {e}")
            logger.error("Install with: pip install yt-dlp youtube-transcript-api")
            return False

    def _get_channel_videos(self) -> List[Dict[str, Any]]:
        """Get all videos from the NEFAC YouTube channel."""
        try:
            import yt_dlp

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": True,
                "playlist_items": f"1-{self.max_videos}",
                "socket_timeout": self.timeout_seconds,
            }

            # Add proxy if configured
            if self.webshare_username and self.webshare_password:
                proxy_url = f"http://{self.webshare_username}:{self.webshare_password}@p.webshare.io:8080"
                ydl_opts["proxy"] = proxy_url
                logger.info("🔒 Using Webshare proxy for YouTube requests")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"🔍 Extracting video list from {self.youtube_channel_url}")
                channel_info = ydl.extract_info(
                    self.youtube_channel_url, download=False
                )

                if not channel_info or "entries" not in channel_info:
                    logger.error("Could not extract channel video list")
                    return []

                videos = [
                    v for v in channel_info["entries"] if v
                ]  # Filter out None entries
                logger.info(f"📊 Found {len(videos)} videos in channel")

                return videos

        except Exception as e:
            logger.error(f"Failed to get channel videos: {e}")
            return []

    def _process_video(self, video: Dict[str, Any]) -> Optional[DocumentInfo]:
        """Process a single YouTube video."""
        try:
            video_url = video.get("url", "")
            if not video_url:
                logger.warning("Video has no URL, skipping")
                return None

            # Get video ID
            video_id = self._extract_video_id(video_url)
            if not video_id:
                logger.warning(f"Could not extract video ID from {video_url}")
                return None

            # Get comprehensive metadata
            metadata = self._get_video_metadata(video_url)

            # Get transcript if available
            transcript_data = self._get_video_transcript(video_id)

            # Create document
            doc = DocumentInfo(
                id=f"youtube_{video_id}",
                title=metadata.get("title", "Unknown YouTube Video"),
                source_url=video_url,
                mime_type="video/youtube",
                date=self._parse_upload_date(metadata.get("upload_date", "")),
                modified=self._parse_upload_date(metadata.get("upload_date", "")),
                source=self.source_name,
                file_size=0,  # Videos are not downloaded, only metadata
                download_date=DateUtils.get_current_iso_string(),
                description=metadata.get("description", ""),
                caption=json.dumps(
                    {
                        "video_id": video_id,
                        "title": metadata.get("title", ""),
                        "description": metadata.get("description", ""),
                        "duration": metadata.get("duration", 0),
                        "view_count": metadata.get("view_count", 0),
                        "like_count": metadata.get("like_count", 0),
                        "comment_count": metadata.get("comment_count", 0),
                        "upload_date": metadata.get("upload_date", ""),
                        "uploader": metadata.get("uploader", ""),
                        "channel": metadata.get("channel", ""),
                        "channel_id": metadata.get("channel_id", ""),
                        "channel_url": metadata.get("channel_url", ""),
                        "tags": metadata.get("tags", []),
                        "categories": metadata.get("categories", []),
                        "thumbnail": metadata.get("thumbnail", ""),
                        "webpage_url": metadata.get("webpage_url", video_url),
                        "availability": metadata.get("availability", ""),
                        "age_limit": metadata.get("age_limit", 0),
                        "live_status": metadata.get("live_status", ""),
                        "release_timestamp": metadata.get("release_timestamp", ""),
                        "language": metadata.get("language", ""),
                        "subtitles_available": bool(
                            metadata.get("automatic_captions", {})
                        ),
                        "chapters": metadata.get("chapters", []),
                        "transcript_available": transcript_data is not None,
                        "transcript_length": (
                            len(transcript_data) if transcript_data else 0
                        ),
                        "platform": "youtube",
                        "content_type": "video",
                    }
                ),
            )

            # Save transcript if available
            if transcript_data:
                transcript_file = self._save_transcript(
                    video_id, transcript_data, metadata
                )
                logger.info(f"📝 Transcript saved: {transcript_file}")
                # Add transcript information to caption field
                try:
                    caption_data = json.loads(doc.caption) if doc.caption else {}
                    caption_data.update(
                        {
                            "transcript_file": transcript_file,
                            "transcript_word_count": self._count_transcript_words(
                                transcript_data
                            ),
                        }
                    )
                    doc.caption = json.dumps(caption_data)
                except json.JSONDecodeError:
                    # If caption is not valid JSON, create new JSON with transcript info
                    doc.caption = json.dumps(
                        {
                            "transcript_file": transcript_file,
                            "transcript_word_count": self._count_transcript_words(
                                transcript_data
                            ),
                        }
                    )
            else:
                logger.warning(
                    f"❌ No transcript available for video: {metadata.get('title', video_id)}"
                )

            # Save video metadata as JSON file for reference
            metadata_file = self._save_video_metadata(
                video_id, metadata, transcript_data is not None
            )
            logger.debug(f"📊 Metadata saved: {metadata_file}")

            return doc

        except Exception as e:
            logger.error(f"Error processing video: {e}")
            return None

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
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

    def _get_video_metadata(self, video_url: str) -> Dict[str, Any]:
        """Get comprehensive video metadata using yt-dlp."""
        try:
            import yt_dlp

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "socket_timeout": self.timeout_seconds,
            }

            # Add proxy if configured
            if self.webshare_username and self.webshare_password:
                proxy_url = f"http://{self.webshare_username}:{self.webshare_password}@p.webshare.io:8080"
                ydl_opts["proxy"] = proxy_url

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return info if info else {}

        except Exception as e:
            logger.warning(f"Failed to get metadata for {video_url}: {e}")
            return {}

    def _get_video_transcript(
        self, video_id: str, max_retries: int = 2
    ) -> Optional[List[Dict]]:
        """Get video transcript with IP ban detection and emergency skip mode."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api.proxies import (
                GenericProxyConfig,
            )

            # Quick IP ban detection - if we've had multiple consecutive failures, skip transcripts
            if (
                hasattr(self, "_consecutive_transcript_failures")
                and self._consecutive_transcript_failures >= 3
            ):
                logger.warning(
                    f"🚫 EMERGENCY SKIP: Detected IP ban, skipping transcript for {video_id}"
                )
                return None

            # Initialize failure counter if not exists
            if not hasattr(self, "_consecutive_transcript_failures"):
                self._consecutive_transcript_failures = 0

            # Configure API client with proxy if available
            api = None

            # Try rotating proxy first for better IP rotation
            if self.rotating_proxy:
                try:
                    api = YouTubeTranscriptApi(
                        proxy_config=GenericProxyConfig(
                            http_url=self.rotating_proxy,
                            https_url=self.rotating_proxy,
                        )
                    )
                    logger.info("Using rotating proxy for transcript extraction")
                except Exception as e:
                    logger.warning(f"Failed to initialize rotating proxy: {e}")

            # Try Webshare proxy if rotating proxy fails
            if api is None and self.webshare_username and self.webshare_password:
                try:
                    proxy_url = f"http://{self.webshare_username}:{self.webshare_password}@p.webshare.io:8080"
                    api = YouTubeTranscriptApi(
                        proxy_config=GenericProxyConfig(
                            http_url=proxy_url,
                            https_url=proxy_url,
                        )
                    )
                    logger.info("Using Webshare proxy for transcript extraction")
                except Exception as e:
                    logger.warning(f"Failed to initialize Webshare proxy: {e}")

            # Try generic HTTP/HTTPS proxy
            if api is None and (self.http_proxy or self.https_proxy):
                try:
                    api = YouTubeTranscriptApi(
                        proxy_config=GenericProxyConfig(
                            http_url=self.http_proxy,
                            https_url=self.https_proxy or self.http_proxy,
                        )
                    )
                    logger.info("Using generic proxy for transcript extraction")
                except Exception as e:
                    logger.warning(f"Failed to initialize generic proxy: {e}")

            # Fallback to direct client
            if api is None:
                api = YouTubeTranscriptApi()
                logger.info("Using direct connection for transcript extraction")

            # Language preferences
            language_preferences = ["en", "en-US", "en-GB", "en-orig"]

            for attempt in range(max_retries):
                try:
                    # Add delay between attempts for IP ban recovery
                    if attempt > 0:
                        # Exponential backoff with much longer delays for IP ban recovery
                        delay = 300 + (
                            attempt * 300
                        )  # Start at 5 minutes, increase by 5 minutes per attempt
                        logger.debug(
                            f"⏳ IP ban recovery: Waiting {delay}s before retry attempt {attempt}..."
                        )
                        time.sleep(delay)

                    # Get available transcripts
                    transcript_list = api.list(video_id)

                    # Try preferred languages first
                    for lang in language_preferences:
                        try:
                            transcript = transcript_list.find_transcript([lang])
                            result = transcript.fetch()
                            # Success! Reset failure counter
                            self._consecutive_transcript_failures = 0
                            # Handle new API response structure
                            if (
                                result
                                and hasattr(result, "__iter__")
                                and not isinstance(result, str)
                            ):
                                # Convert to list of dictionaries if needed
                                processed_result = []
                                for item in result:
                                    if hasattr(item, "get"):
                                        # It's a dict-like object
                                        processed_result.append(
                                            {
                                                "text": item.get("text", ""),
                                                "start": item.get("start", 0),
                                                "duration": item.get("duration", 0),
                                            }
                                        )
                                    else:
                                        # Handle FetchedTranscriptSnippet objects
                                        processed_result.append(
                                            {
                                                "text": getattr(item, "text", ""),
                                                "start": getattr(item, "start", 0),
                                                "duration": getattr(
                                                    item, "duration", 0
                                                ),
                                            }
                                        )
                                return processed_result
                            return result
                        except Exception:
                            continue

                    # Try manual transcripts
                    for transcript in transcript_list:
                        if not transcript.is_generated:
                            result = transcript.fetch()
                            # Success! Reset failure counter
                            self._consecutive_transcript_failures = 0
                            # Handle new API response structure
                            if (
                                result
                                and hasattr(result, "__iter__")
                                and not isinstance(result, str)
                            ):
                                # Convert to list of dictionaries if needed
                                processed_result = []
                                for item in result:
                                    if hasattr(item, "get"):
                                        # It's a dict-like object
                                        processed_result.append(
                                            {
                                                "text": item.get("text", ""),
                                                "start": item.get("start", 0),
                                                "duration": item.get("duration", 0),
                                            }
                                        )
                                    else:
                                        # Handle FetchedTranscriptSnippet objects
                                        processed_result.append(
                                            {
                                                "text": getattr(item, "text", ""),
                                                "start": getattr(item, "start", 0),
                                                "duration": getattr(
                                                    item, "duration", 0
                                                ),
                                            }
                                        )
                                return processed_result
                            return result

                    # Finally try auto-generated
                    for transcript in transcript_list:
                        if transcript.is_generated:
                            result = transcript.fetch()
                            # Success! Reset failure counter
                            self._consecutive_transcript_failures = 0
                            # Handle new API response structure
                            if (
                                result
                                and hasattr(result, "__iter__")
                                and not isinstance(result, str)
                            ):
                                # Convert to list of dictionaries if needed
                                processed_result = []
                                for item in result:
                                    if hasattr(item, "get"):
                                        # It's a dict-like object
                                        processed_result.append(
                                            {
                                                "text": item.get("text", ""),
                                                "start": item.get("start", 0),
                                                "duration": item.get("duration", 0),
                                            }
                                        )
                                    else:
                                        # Handle FetchedTranscriptSnippet objects
                                        processed_result.append(
                                            {
                                                "text": getattr(item, "text", ""),
                                                "start": getattr(item, "start", 0),
                                                "duration": getattr(
                                                    item, "duration", 0
                                                ),
                                            }
                                        )
                                return processed_result
                            return result

                    return None

                except Exception as e:
                    error_msg = str(e).lower()

                    # Detect IP blocking
                    if (
                        "blocking requests from your ip" in error_msg
                        or "ip has been blocked" in error_msg
                    ):
                        self._consecutive_transcript_failures += 1
                        logger.warning(
                            f"🚫 IP BAN DETECTED ({self._consecutive_transcript_failures}/3 failures) for video {video_id}"
                        )

                        if self._consecutive_transcript_failures >= 3:
                            logger.error(
                                "🚨 EMERGENCY MODE: IP banned, disabling transcript extraction for remaining videos"
                            )
                            return None

                    if "disabled" in error_msg or "unavailable" in error_msg:
                        return None
                    elif attempt == max_retries - 1:
                        self._consecutive_transcript_failures += 1
                        logger.warning(
                            f"Transcript unavailable for video {video_id}: {e}"
                        )
                        return None

            return None

        except ImportError:
            logger.warning("youtube-transcript-api not available")
            return None
        except Exception as e:
            logger.warning(f"Failed to get transcript for {video_id}: {e}")
            return None

    def _save_transcript(
        self, video_id: str, transcript_data: List[Dict], metadata: Dict[str, Any]
    ) -> str:
        """Save transcript to file."""
        try:
            title = metadata.get("title", "Unknown")
            safe_title = re.sub(r"[^\w\s-]", "", title).strip()
            safe_title = re.sub(r"[-\s]+", "-", safe_title)

            filename = f"{safe_title}_{video_id}.txt"
            filepath = self.youtube_dir / filename

            # Create directory only when we have content to save
            self.youtube_dir.mkdir(parents=True, exist_ok=True)

            with open(filepath, "w", encoding="utf-8") as f:
                # Write video metadata header
                f.write(f"YouTube Video: {title}\n")
                f.write(f"Video ID: {video_id}\n")
                f.write(f"URL: {metadata.get('webpage_url', '')}\n")
                f.write(f"Upload Date: {metadata.get('upload_date', '')}\n")
                f.write(f"Duration: {metadata.get('duration', 0)} seconds\n")
                f.write(f"Views: {metadata.get('view_count', 0)}\n")
                f.write("=" * 60 + "\n\n")

                # Write transcript with timestamps
                for entry in transcript_data:
                    start_time = entry.get("start", 0)
                    text = entry.get("text", "")
                    f.write(f"[{start_time:.2f}s] {text}\n")

            return str(filepath.relative_to(self.config.output_dir))

        except Exception as e:
            logger.error(f"Failed to save transcript for {video_id}: {e}")
            return ""

    def _save_video_metadata(
        self, video_id: str, metadata: Dict[str, Any], has_transcript: bool
    ) -> str:
        """Save video metadata as JSON file."""
        try:
            title = metadata.get("title", "Unknown")
            safe_title = re.sub(r"[^\w\s-]", "", title).strip()
            safe_title = re.sub(r"[-\s]+", "-", safe_title)

            filename = f"{safe_title}_{video_id}_metadata.json"
            filepath = self.youtube_dir / filename

            # Create directory only when we have content to save
            self.youtube_dir.mkdir(parents=True, exist_ok=True)

            # Prepare metadata for saving
            save_metadata = {
                "video_id": video_id,
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
                "url": metadata.get("webpage_url", ""),
                "upload_date": metadata.get("upload_date", ""),
                "duration": metadata.get("duration", 0),
                "view_count": metadata.get("view_count", 0),
                "like_count": metadata.get("like_count", 0),
                "comment_count": metadata.get("comment_count", 0),
                "uploader": metadata.get("uploader", ""),
                "channel": metadata.get("channel", ""),
                "channel_id": metadata.get("channel_id", ""),
                "channel_url": metadata.get("channel_url", ""),
                "tags": metadata.get("tags", []),
                "categories": metadata.get("categories", []),
                "thumbnail": metadata.get("thumbnail", ""),
                "has_transcript": has_transcript,
                "extracted_at": DateUtils.get_current_iso_string(),
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(save_metadata, f, indent=2, ensure_ascii=False)

            return str(filepath.relative_to(self.config.output_dir))

        except Exception as e:
            logger.error(f"Failed to save metadata for {video_id}: {e}")
            return ""

    def _count_transcript_words(self, transcript_data: List[Dict]) -> int:
        """Count words in transcript."""
        try:
            total_words = 0
            for entry in transcript_data:
                text = entry.get("text", "")
                total_words += len(text.split())
            return total_words
        except Exception:
            return 0

    def _parse_upload_date(self, upload_date: str) -> str:
        """Parse upload date to ISO format."""
        try:
            if upload_date and len(upload_date) == 8:  # YYYYMMDD format
                year = upload_date[:4]
                month = upload_date[4:6]
                day = upload_date[6:8]
                return f"{year}-{month}-{day}T00:00:00Z"
            else:
                return DateUtils.get_current_iso_string()
        except Exception:
            return DateUtils.get_current_iso_string()
