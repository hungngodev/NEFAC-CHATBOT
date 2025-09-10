"""
YouTube Extractor for NEFAC Crawler
- Crawls the single channel configured (default: https://www.youtube.com/@nefac)
- Saves transcript files under output_dir/youtube as plain .txt with only "[time] text" lines
- Returns rich YouTubeMetadata objects; youtube_metadata.json is written by MetadataManager
"""

import json
import logging
import os
import random
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from src.schemas.metadata import YouTubeMetadata
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.core.types import CrawlerSource, ExtractorResult
from src.service.crawler.downloaders.common import DateUtils, FileUtils
from src.service.crawler.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class YouTubeExtractor(BaseExtractor):
    """YouTube extractor that saves transcripts and emits rich metadata."""

    def __init__(self, config: CrawlerConfig):
        super().__init__(config)
        self.youtube_config = config.youtube
        self.youtube_dir = self.config.output_dir / self.youtube_config.output_subdir
        self.youtube_dir.mkdir(parents=True, exist_ok=True)

    @property
    def source_name(self) -> str:
        return CrawlerSource.YOUTUBE.value

    def extract(self) -> ExtractorResult:
        logger.info("YouTube: fetching channel listing: %s", self.youtube_config.channel_url)
        videos = self._get_channel_videos()
        logger.info("YouTube: found %d videos in channel", len(videos))
        documents: List[YouTubeMetadata] = []

        for idx, v in enumerate(videos, start=1):
            try:
                logger.info("YouTube: processing video %d/%d", idx, len(videos))
                doc = self._process_video(v)
                documents.append(doc)
            except Exception as e:
                # fail-fast (skip problematic video) if configured
                if self.youtube_config.skip_on_error:
                    logger.warning("YouTube: skipping video due to error: %s", e)
                    continue
                raise e

            # Politeness delay with slight jitter
            self._apply_rate_limit(idx)

        return ExtractorResult(
            documents=documents,
            metadata={
                "channel_url": self.youtube_config.channel_url,
                "videos_found": len(videos),
                "videos_processed": len(documents),
            },
        )

    def _get_channel_videos(self) -> List[Dict[str, Any]]:
        """Get flat list of channel entries to avoid per-video fetches initially."""
        ydl_opts = self._get_ydl_options()
        ydl_opts.update(
            {
                "extract_flat": True,
                "playlist_items": f"1-{self.youtube_config.max_videos}",
            }
        )

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            channel_info = ydl.extract_info(self.youtube_config.channel_url, download=False)
            entries = channel_info.get("entries", []) if channel_info else []
            return [v for v in entries if v]

    def _process_video(self, video: Dict[str, Any]) -> YouTubeMetadata:
        """Build rich metadata, save transcript .txt, and return YouTubeMetadata."""
        video_url = video.get("url") or video.get("webpage_url")
        if not video_url:
            raise ValueError("Missing video URL in channel entry")

        video_id = self._extract_video_id(video_url) or video.get("id", "")
        if not video_id:
            raise ValueError(f"Could not determine video id for {video_url}")

        # Get detailed metadata (best-effort)
        metadata = self._get_video_metadata(video_url)

        # Fallbacks to flat fields if detailed extraction fails
        title = metadata.get("title") or video.get("title") or f"YouTube Video {video_id}"
        upload_date = metadata.get("upload_date") or video.get("upload_date") or ""
        iso_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}T00:00:00Z" if upload_date and len(upload_date) >= 8 else DateUtils.get_current_iso_string()

        # Try to get transcript
        transcript = self._get_video_transcript(video_id)

        # Save transcript file (only lines with [time] text)
        transcript_rel_path = None
        transcript_word_count = 0
        if transcript:
            transcript_rel_path = self._save_transcript(video_id, title, transcript)
            transcript_word_count = sum(len(e.get("text", "").split()) for e in transcript)

        # Compose filename and file_path using transcript file if available
        if transcript_rel_path:
            file_path = transcript_rel_path
            filename = FileUtils.safe_filename(file_path.split("/")[-1])
            file_size = (self.config.output_dir / file_path).stat().st_size if (self.config.output_dir / file_path).exists() else None
        else:
            # No transcript file created; point to a sensible placeholder in youtube dir
            filename = self._get_safe_filename(title, video_id, ".txt")
            file_path = str((self.youtube_dir / filename).relative_to(self.config.output_dir))
            file_size = None

        # Build YouTubeMetadata
        doc = YouTubeMetadata(
            id=f"youtube_{video_id}",
            title=title,
            filename=filename,
            source_url=metadata.get("webpage_url") or video_url,
            mime_type="video/youtube",
            date=iso_date,
            modified=iso_date,
            file_path=file_path,
            file_size=file_size,
            download_date=DateUtils.get_current_iso_string(),
            crawler_version="3.0",
            source=self.source_name,
            # Rich fields
            description=metadata.get("description") or "",
            video_id=video_id,
            duration=metadata.get("duration") or 0,
            view_count=metadata.get("view_count") or 0,
            like_count=metadata.get("like_count"),
            comment_count=metadata.get("comment_count"),
            uploader=metadata.get("uploader") or metadata.get("channel") or "",
            channel=metadata.get("channel") or "",
            channel_id=metadata.get("channel_id") or "",
            tags=metadata.get("tags") or [],
            categories=metadata.get("categories") or [],
            thumbnail=metadata.get("thumbnail") or "",
            uploader_url=metadata.get("uploader_url"),
            availability=metadata.get("availability"),
            live_status=metadata.get("live_status"),
            release_timestamp=str(metadata.get("release_timestamp")) if metadata.get("release_timestamp") else None,
            chapters=metadata.get("chapters") or {},
            heatmap=metadata.get("heatmap") or {},
            transcript_available=bool(transcript),
            transcript_file=file_path if transcript_rel_path else None,
            transcript_length=sum(len(e.get("text", "")) for e in transcript) if transcript else None,
            transcript_word_count=transcript_word_count if transcript else None,
        )

        # Attach file_path so validator uses the transcript file
        setattr(doc, "file_path", file_path)
        return doc

    def _get_video_metadata(self, video_url: str) -> Dict[str, Any]:
        """Get comprehensive YouTube metadata using yt-dlp; best-effort if blocked."""
        opts = self._get_ydl_options()
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return info or {}
        except Exception:
            # Fallback: minimal metadata
            return {"webpage_url": video_url}

    def _get_video_transcript(self, video_id: str) -> List[Dict]:
        """Get transcript using multiple methods: API -> yt-dlp -> timedtext XML."""
        # Method 1: YouTubeTranscriptApi
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            for lang in ["en", "en-US", "en-GB", "en-orig"]:
                try:
                    t = transcript_list.find_transcript([lang])
                    return self._normalize_transcript(t.fetch())
                except Exception:
                    continue
            for t in transcript_list:
                try:
                    return self._normalize_transcript(t.fetch())
                except Exception:
                    continue
        except Exception:
            pass

        # Method 2: yt-dlp auto-subtitles
        ytdlp_transcript = self._get_transcript_ytdlp(video_id)
        if ytdlp_transcript:
            return ytdlp_transcript

        # Method 3: YouTube timedtext XML
        xml_transcript = self._get_transcript_timedtext_xml(video_id)
        if xml_transcript:
            return xml_transcript

        return []

    def _get_transcript_ytdlp(self, video_id: str) -> List[Dict] | None:
        """Use yt-dlp to download auto-generated subtitles (json3) and parse them."""
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        language_prefs = [["en"], ["en-US"], ["en-GB"], ["en-orig"]]

        for langs in language_prefs:
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    ydl_opts: Dict[str, Any] = {
                        "quiet": True,
                        "no_warnings": True,
                        "skip_download": True,
                        "writeautomaticsub": True,
                        "subtitleslangs": langs,
                        "subtitlesformat": "json3",
                        "outtmpl": f"{temp_dir}/%(id)s.%(ext)s",
                        "extractor_args": {"youtube": {"player_client": ["android"]}},
                        "http_headers": {
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/605.1.15",
                            "Accept-Language": "en-US,en;q=0.9",
                        },
                        "noprogress": True,
                        "retries": 0,
                        "extractor_retries": 0,
                    }

                    # Optional cookiefile support
                    cookiefile = os.getenv("YTDLP_COOKIES_FILE") or os.getenv("YOUTUBE_COOKIES_FILE")
                    if cookiefile and Path(cookiefile).exists():
                        ydl_opts["cookiefile"] = cookiefile

                    # Optional proxy support via Webshare credentials
                    if getattr(self.youtube_config, "webshare_username", None) and getattr(self.youtube_config, "webshare_password", None):
                        ydl_opts["proxy"] = f"http://{self.youtube_config.webshare_username}:{self.youtube_config.webshare_password}@p.webshare.io:8080"

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([video_url])
                        # Look for generated subtitle json3
                        subs = list(Path(temp_dir).glob(f"{video_id}.*.json3"))
                        if not subs:
                            continue
                        with open(subs[0], "r", encoding="utf-8") as f:
                            data = json.load(f)
                        entries: List[Dict] = []
                        for event in data.get("events", []):
                            if "segs" in event:
                                text = "".join(seg.get("utf8", "") for seg in event["segs"]) or ""
                                if text.strip():
                                    entries.append(
                                        {
                                            "text": text.strip(),
                                            "start": event.get("tStartMs", 0) / 1000.0,
                                            "duration": event.get("dDurationMs", 0) / 1000.0,
                                        }
                                    )
                        if entries:
                            return entries
            except Exception:
                continue
        return None

    def _get_transcript_timedtext_xml(self, video_id: str) -> List[Dict] | None:
        """Fetch basic timedtext XML transcript if available."""
        try:
            import requests

            url = f"https://www.youtube.com/api/timedtext?v={video_id}&lang=en"
            r = requests.get(url, timeout=10)
            if r.status_code != 200 or not r.text.strip():
                return None
            # Parse XML
            from xml.etree import ElementTree

            root = ElementTree.fromstring(r.text)
            out: List[Dict] = []
            for el in root.findall(".//text"):
                start = float(el.get("start", 0))
                dur = float(el.get("dur", 0))
                txt = (el.text or "").strip()
                if txt:
                    out.append({"text": txt, "start": start, "duration": dur})
            return out or None
        except Exception:
            return None

    def _save_transcript(self, video_id: str, title: str, transcript: List[Dict]) -> str:
        """Write transcript as plain lines: "[X.XXs] text" and return relative path under output_dir."""
        filename = self._get_safe_filename(title, video_id, ".txt")
        filepath = self.youtube_dir / filename
        self.youtube_dir.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            for entry in transcript:
                start = float(entry.get("start", 0.0))
                text = entry.get("text", "").strip()
                if text:
                    f.write(f"[{start:.2f}s] {text}\n")
        rel = str(filepath.relative_to(self.config.output_dir))
        logger.info("YouTube: saved transcript %s", rel)
        return rel

    def _get_ydl_options(self) -> Dict[str, Any]:
        return {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            # Use Android client to reduce consent/403 issues
            "extractor_args": {"youtube": {"player_client": ["android"]}},
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
                "Accept-Language": "en-US,en;q=0.9",
            },
            "noprogress": True,
            "retries": 0,
            "extractor_retries": 0,
            "socket_timeout": self.config.request_timeout,
        }

    def _extract_video_id(self, video_url: str) -> str:
        parsed = urlparse(video_url)
        host = (parsed.hostname or "").lower()
        if "youtu.be" in host:
            return parsed.path.lstrip("/")
        if "youtube.com" in host:
            if parsed.path == "/watch":
                return parse_qs(parsed.query).get("v", [""])[0]
            parts = parsed.path.split("/")
            return parts[2] if len(parts) > 2 else ""
        return ""

    def _normalize_transcript(self, result) -> List[Dict]:
        return [{"text": x.get("text", ""), "start": float(x.get("start", 0.0)), "duration": float(x.get("duration", 0.0))} for x in result]

    def _get_safe_filename(self, title: str, video_id: str, suffix: str) -> str:
        safe_title = re.sub(r"[^\w\s-]", "", title or "").strip()
        safe_title = re.sub(r"[-\s]+", "-", safe_title) or "youtube-video"
        return f"{safe_title}_{video_id}{suffix}"

    def _apply_rate_limit(self, index: int):
        # Progressive backoff with min/max bounds
        base = max(self.youtube_config.min_delay, self.youtube_config.request_delay)
        cap = self.youtube_config.max_delay
        delay = min(base * (self.youtube_config.backoff_multiplier ** max(0, index // 20)), cap)
        logger.info("YouTube: sleeping for %.1fs", delay)
        time.sleep(delay + random.uniform(0.5, 2.0))
