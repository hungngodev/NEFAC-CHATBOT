"""
WordPress REST API extractor for NEFAC documents - fail-fast and simplified with tqdm.
"""

import os
from pathlib import Path
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from requests.auth import HTTPBasicAuth
from tqdm import tqdm

from src.schemas.metadata import BaseMetadata, PDFMetadata
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.core.types import ExtractorResult
from src.service.crawler.extractors.base import BaseExtractor


class WordPressExtractor(BaseExtractor):
    WORDPRESS_API_BASE = "https://nefac.org/wp-json/wp/v2/"

    def __init__(self, config: CrawlerConfig):
        super().__init__(config)
        self.wp_username = os.getenv("WORDPRESS_USERNAME")
        self.wp_password = os.getenv("WORDPRESS_PASSWORD")
        self.use_auth = bool(self.wp_username and self.wp_password)
        if self.use_auth:
            self.auth = HTTPBasicAuth(self.wp_username, self.wp_password)
        else:
            self.auth = None

    @property
    def source_name(self) -> str:
        return "wordpress_rest_api"

    def extract(self) -> ExtractorResult:
        documents = []
        documents.extend(self._extract_content("posts"))
        documents.extend(self._extract_content("pages"))
        documents.extend(self._extract_content("news"))
        documents.extend(self._extract_media())
        return ExtractorResult(documents=documents)

    def _get(self, endpoint: str, params: Dict = None) -> List[Dict]:
        page = 1
        all_items = []
        while True:
            query = {"per_page": 100, "page": page}
            if params:
                query.update(params)
            url = urljoin(self.WORDPRESS_API_BASE, endpoint)
            response = self.session.get(url, params=query, auth=self.auth, timeout=30)
            if response.status_code != 200:
                raise requests.exceptions.RequestException(f"Failed request {url}: {response.status_code}")
            items = response.json()
            if not items:
                break
            all_items.extend(items)
            if len(items) < 100:
                break
            page += 1
        return all_items

    def _extract_content(self, content_type: str) -> List[BaseMetadata]:
        items = self._get(content_type)
        documents = []
        for item in tqdm(items, desc=f"Extracting {content_type}", unit="item"):
            doc = self._create_html_document(item, content_type)
            documents.append(doc)
        return documents

    def _extract_media(self) -> List[BaseMetadata]:
        items = self._get("media")
        documents = []
        for item in tqdm(items, desc="Extracting media", unit="file"):
            doc = self._create_media_document(item)
            documents.append(doc)
        return documents

    def _create_html_document(self, item: Dict, content_type: str) -> BaseMetadata:
        content = self._rendered(item.get("content"))
        title = self._rendered(item.get("title"))
        if not title:
            title = f"{content_type.title()} {item.get('id')}"
        source_url = item.get("link")
        if not source_url:
            raise ValueError(f"Missing link for {content_type} {item.get('id')}")
        slug = item.get("slug") or str(item.get("id"))
        filename = f"{slug}.html"
        metadata = {"content": content, "excerpt": self._rendered(item.get("excerpt")), "content_type": content_type, "slug": slug, "status": item.get("status", "")}
        return self._create_document_info(id_value=str(item["id"]), title=title.strip(), filename=filename, source_url=source_url, mime_type="text/html", date=item.get("date", ""), modified=item.get("modified", ""), metadata=metadata)

    def _create_media_document(self, item: Dict) -> BaseMetadata | PDFMetadata:
        source_url = item.get("source_url")
        if not source_url:
            raise ValueError(f"Missing source_url for media {item.get('id')}")
        mime_type = item.get("mime_type", "")
        title_dict = item.get("title", {})
        title = title_dict.get("rendered") if isinstance(title_dict, dict) else str(title_dict)
        if not title:
            filename = Path(urlparse(source_url).path).name
            title = Path(filename).stem if filename else f"Media {item.get('id')}"
        filename = Path(urlparse(source_url).path).name or f"media_{item.get('id')}"
        media_details = item.get("media_details", {})
        file_size = media_details.get("filesize", 0) if isinstance(media_details, dict) else 0
        additional_fields = {"description": self._rendered(item.get("description")), "caption": self._rendered(item.get("caption")), "file_size": file_size, "modified": item.get("modified", "")}
        if mime_type == "application/pdf":
            return PDFMetadata(id=str(item["id"]), title=title.strip(), filename=filename, source_url=source_url, mime_type=mime_type, date=item.get("date", ""), source=self.__class__.__name__.replace("Extractor", "").lower(), **additional_fields)
        else:
            return BaseMetadata(id=str(item["id"]), title=title.strip(), filename=filename, source_url=source_url, mime_type=mime_type, date=item.get("date", ""), source=self.__class__.__name__.replace("Extractor", "").lower(), **additional_fields)

    def _rendered(self, field) -> str:
        if isinstance(field, dict):
            return field.get("rendered", "")
        if field is None:
            return ""
        return str(field)
