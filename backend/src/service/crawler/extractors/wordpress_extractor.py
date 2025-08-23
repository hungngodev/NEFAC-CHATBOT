"""
WordPress REST API extractor for NEFAC documents - fail-fast, robust with retries and tqdm.
"""

import os
import time
from pathlib import Path
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from tqdm import tqdm
from urllib3.util.retry import Retry

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
        self.auth = HTTPBasicAuth(self.wp_username, self.wp_password) if self.use_auth else None

        # configure session retries
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # summary counts
        self.summary_counts = {
            "posts": {"HTML": 0, "PDF": 0, "XLSX": 0, "XLS": 0, "CSV": 0, "DOC": 0, "DOCS": 0},
            "pages": {"HTML": 0, "PDF": 0, "XLSX": 0, "XLS": 0, "CSV": 0, "DOC": 0, "DOCS": 0},
            "news": {"HTML": 0, "PDF": 0, "XLSX": 0, "XLS": 0, "CSV": 0, "DOC": 0, "DOCS": 0},
            "media": {"PDF": 0, "XLSX": 0, "XLS": 0, "CSV": 0, "DOC": 0, "DOCS": 0},
        }

    @property
    def source_name(self) -> str:
        return "wordpress_rest_api"

    def extract(self) -> ExtractorResult:
        documents = []
        # extract posts/pages/news
        for content_type in ["posts", "pages", "news"]:
            items = self._extract_content(content_type)
            documents.extend(items)
            self.summary_counts[content_type]["HTML"] = len(items)

        # extract media
        media_items = self._extract_media()
        documents.extend(media_items)

        # print per-type summary
        print("\nExtraction Summary:")
        for ctype, counts in self.summary_counts.items():
            print(f"{ctype.capitalize()}:")
            for k, v in counts.items():
                if v > 0:
                    print(f"  {k}: {v}")

        # calculate total counts across all types
        total_counts = {"HTML": 0, "PDF": 0, "XLSX": 0, "XLS": 0, "CSV": 0, "DOC": 0, "DOCS": 0}
        for counts in self.summary_counts.values():
            for k, v in counts.items():
                total_counts[k] += v

        print("\nTotal Counts Across All Types:")
        for k, v in total_counts.items():
            if v > 0:
                print(f"  {k}: {v}")

        return ExtractorResult(documents=documents)

    def _get(self, endpoint: str, params: Dict = None) -> List[Dict]:
        """Fetch all items with retry/backoff and WP pagination headers."""
        all_items = []
        page = 1

        while True:
            query = {"per_page": 100, "page": page}
            if params:
                query.update(params)

            url = urljoin(self.WORDPRESS_API_BASE, endpoint)

            try:
                response = self.session.get(url, params=query, auth=self.auth, timeout=30)
            except requests.exceptions.RequestException as e:
                print(f"Request failed for page {page}, retrying: {e}")
                time.sleep(2**page)  # exponential backoff
                continue

            if response.status_code == 400:  # end of pages
                break
            if response.status_code != 200:
                raise requests.exceptions.RequestException(f"Failed request {url}: {response.status_code}")

            items = response.json()
            if not items:
                break

            all_items.extend(items)

            total_pages = int(response.headers.get("X-WP-TotalPages", 0))
            if page >= total_pages:
                break

            page += 1
            time.sleep(0.1)  # small delay to reduce connection drops

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
        allowed_extensions = [".pdf", ".xlsx", ".xls", ".csv", ".doc", ".docs"]
        for item in tqdm(items, desc="Extracting media", unit="file"):
            source_url = item.get("source_url", "").lower()
            if not any(source_url.endswith(ext) for ext in allowed_extensions):
                continue
            doc = self._create_media_document(item)
            documents.append(doc)

            # update counts
            for ext in allowed_extensions:
                if source_url.endswith(ext):
                    self.summary_counts["media"][ext.strip(".").upper()] += 1
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

        metadata = {
            "content": content,
            "excerpt": self._rendered(item.get("excerpt")),
            "content_type": content_type,
            "slug": slug,
            "status": item.get("status", ""),
        }

        return self._create_document_info(
            id_value=str(item["id"]),
            title=title.strip(),
            filename=filename,
            source_url=source_url,
            mime_type="text/html",
            date=item.get("date", ""),
            modified=item.get("modified", ""),
            metadata=metadata,
        )

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

        additional_fields = {
            "description": self._rendered(item.get("description")),
            "caption": self._rendered(item.get("caption")),
            "modified": item.get("modified", ""),
        }

        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            return PDFMetadata(
                id=str(item["id"]),
                title=title.strip(),
                filename=filename,
                source_url=source_url,
                mime_type=mime_type,
                date=item.get("date", ""),
                source=self.__class__.__name__.replace("Extractor", "").lower(),
                **additional_fields,
            )
        else:
            return BaseMetadata(
                id=str(item["id"]),
                title=title.strip(),
                filename=filename,
                source_url=source_url,
                mime_type=mime_type,
                date=item.get("date", ""),
                source=self.__class__.__name__.replace("Extractor", "").lower(),
                **additional_fields,
            )

    def _rendered(self, field) -> str:
        if isinstance(field, dict):
            return field.get("rendered", "")
        if field is None:
            return ""
        return str(field)
