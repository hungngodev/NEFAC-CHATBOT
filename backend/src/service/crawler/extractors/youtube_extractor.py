"""
YouTube Extractor for NEFAC Crawler - Fail-Fast Version
"""

import json
import random
import re
import time
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from src.schemas.metadata import YouTubeMetadata
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.core.types import CrawlerSource, ExtractorResult
from src.service.crawler.downloaders.common import DateUtils
from src.service.crawler.extractors.base import BaseExtractor


class YouTubeExtractor(BaseExtractor):
    """Fail-fast YouTube extractor."""

    def __init__(self, config: CrawlerConfig):
        super().__init__(config)
        self.youtube_config = config.youtube
        self.youtube_dir = self.config.output_dir / self.youtube_config.output_subdir

    @property
    def source_name(self) -> str:
        return CrawlerSource.YOUTUBE.value

    def extract(self) -> ExtractorResult:
        videos = self._get_channel_videos()
        documents = [self._process_video(v) for v in videos]
        return ExtractorResult(
            documents=documents,
            metadata={
                "channel_url": self.youtube_config.channel_url,
                "videos_found": len(videos),
                "videos_processed": len(documents),
                "success_rate": len(documents) / len(videos) if videos else 0,
            },
        )

    def _get_channel_videos(self) -> List[Dict[str, Any]]:
        ydl_opts = self._get_ydl_options()
        ydl_opts.update({"extract_flat": True, "playlist_items": f"1-{self.youtube_config.max_videos}"})
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            channel_info = ydl.extract_info(self.youtube_config.channel_url, download=False)
            return [v for v in channel_info["entries"] if v]

    def _process_video(self, video: Dict[str, Any]) -> YouTubeMetadata:
        video_url = video["url"]
        video_id = self._extract_video_id(video_url)
        metadata = self._get_video_metadata(video_url)
        transcript = self._get_video_transcript(video_id)
        doc = self._create_document(video_id, video_url, metadata, transcript)
        if transcript:
            transcript_file = self._save_transcript(video_id, transcript, metadata)
            self._update_document_caption(doc, transcript_file, transcript)
        self._save_metadata(video_id, metadata, bool(transcript))
        return doc

    def _create_document(self, video_id: str, video_url: str, metadata: Dict[str, Any], transcript: List[Dict]) -> YouTubeMetadata:
        upload_date = metadata.get("upload_date", "")
        iso_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}T00:00:00Z" if upload_date else DateUtils.get_current_iso_string()
        transcript_word_count = sum(len(entry["text"].split()) for entry in transcript) if transcript else 0
        return YouTubeMetadata(
            id=f"youtube_{video_id}",
            title=metadata.get("title", "Unknown YouTube Video"),
            source_url=video_url,
            mime_type="video/youtube",
            date=iso_date,
            modified=iso_date,
            source=self.source_name,
            file_size=0,
            download_date=DateUtils.get_current_iso_string(),
            description=metadata.get("description", ""),
            video_id=video_id,
            duration=metadata.get("duration", 0),
            view_count=metadata.get("view_count", 0),
            uploader=metadata.get("uploader", ""),
            channel=metadata.get("channel", ""),
            channel_id=metadata.get("channel_id", ""),
            tags=metadata.get("tags", []),
            categories=metadata.get("categories", []),
            thumbnail=metadata.get("thumbnail", ""),
            transcript_available=bool(transcript),
            transcript_word_count=transcript_word_count,
            caption=json.dumps(
                {
                    "video_id": video_id,
                    "title": metadata.get("title", ""),
                    "description": metadata.get("description", ""),
                    "duration": metadata.get("duration", 0),
                    "view_count": metadata.get("view_count", 0),
                    "upload_date": metadata.get("upload_date", ""),
                    "uploader": metadata.get("uploader", ""),
                    "channel": metadata.get("channel", ""),
                    "channel_id": metadata.get("channel_id", ""),
                    "tags": metadata.get("tags", []),
                    "categories": metadata.get("categories", []),
                    "thumbnail": metadata.get("thumbnail", ""),
                    "webpage_url": video_url,
                    "transcript_available": bool(transcript),
                    "transcript_length": len(transcript) if transcript else 0,
                }
            ),
        )

    def _get_video_metadata(self, video_url: str) -> Dict[str, Any]:
        with yt_dlp.YoutubeDL(self._get_ydl_options()) as ydl:
            return ydl.extract_info(video_url, download=False)

    def _get_video_transcript(self, video_id: str) -> List[Dict]:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        transcript = transcript_list.find_transcript(["en", "en-US"])
        return self._normalize_transcript(transcript.fetch()) if transcript else []

    def _save_transcript(self, video_id: str, transcript: List[Dict], metadata: Dict[str, Any]) -> str:
        filename = self._get_safe_filename(metadata["title"], video_id, ".txt")
        filepath = self.youtube_dir / filename
        self.youtube_dir.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"YouTube Video: {metadata['title']}\nVideo ID: {video_id}\nURL: {metadata['webpage_url']}\n")
            f.write("=" * 60 + "\n\n")
            for entry in transcript:
                f.write(f"[{entry['start']:.2f}s] {entry['text']}\n")
        return str(filepath.relative_to(self.config.output_dir))

    def _save_metadata(self, video_id: str, metadata: Dict[str, Any], has_transcript: bool) -> str:
        filename = self._get_safe_filename(metadata["title"], video_id, "_metadata.json")
        filepath = self.youtube_dir / filename
        self.youtube_dir.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({**metadata, "has_transcript": has_transcript, "extracted_at": DateUtils.get_current_iso_string()}, f, indent=2)
        return str(filepath.relative_to(self.config.output_dir))

    def _get_ydl_options(self) -> Dict[str, Any]:
        return {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": self.youtube_config.timeout_seconds,
        }

    def _extract_video_id(self, video_url: str) -> str:
        parsed = urlparse(video_url)
        if "youtu.be" in parsed.hostname:
            return parsed.path[1:]
        if "youtube.com" in parsed.hostname:
            if parsed.path == "/watch":
                return parse_qs(parsed.query)["v"][0]
            return parsed.path.split("/")[2]
        return ""

    def _normalize_transcript(self, result) -> List[Dict]:
        return [{"text": x["text"], "start": x["start"], "duration": x["duration"]} for x in result]

    def _get_safe_filename(self, title: str, video_id: str, suffix: str) -> str:
        safe_title = re.sub(r"[^\w\s-]", "", title).strip()
        safe_title = re.sub(r"[-\s]+", "-", safe_title)
        return f"{safe_title}_{video_id}{suffix}"

    def _update_document_caption(self, doc: YouTubeMetadata, transcript_file: str, transcript: List[Dict]):
        caption_data = json.loads(doc.caption)
        caption_data.update(
            {
                "transcript_file": transcript_file,
                "transcript_word_count": sum(len(entry["text"].split()) for entry in transcript),
            }
        )
        doc.caption = json.dumps(caption_data)

    def _apply_rate_limit(self):
        delay = random.uniform(self.youtube_config.request_delay, self.youtube_config.request_delay + 20)
        time.sleep(delay)
