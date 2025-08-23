import logging
import sys
from pathlib import Path
from typing import List, Type

sys.path.insert(0, str(Path(__file__).parents[4]))

from tqdm import tqdm

from src.schemas.metadata import BaseMetadata, DocumentMetadata, HTMLMetadata, PDFMetadata, XLSXMetadata, YouTubeMetadata
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.downloaders.common import JSONUtils
from src.service.crawler.downloaders.document_downloader import DocumentDownloader
from src.service.crawler.downloaders.metadata_manager import MetadataManager

logger = logging.getLogger(__name__)


class DownloadValidator:
    """Validates downloaded files against their metadata."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.metadata_manager = MetadataManager(config)
        self.downloader = DocumentDownloader(config)
        self.stats = {"validated": 0, "missing": 0, "corrupted": 0, "size_mismatch": 0}

    def get_metadata_class(self, doc_data: dict) -> Type[BaseMetadata]:
        """Determine the metadata class for a given document data."""
        # This is a simplified version of the categorization in MetadataManager
        source_url = doc_data.get("source_url", "").lower()
        mime_type = doc_data.get("mime_type", "").lower()
        source = doc_data.get("source", "").lower()

        if "pdf" in source_url or "pdf" in mime_type:
            return PDFMetadata
        if "xls" in source_url or "spreadsheet" in mime_type:
            return XLSXMetadata
        if "html" in source_url or "html" in mime_type:
            return HTMLMetadata
        if "youtube" in source:
            return YouTubeMetadata
        return DocumentMetadata

    def load_all_metadata(self) -> List[BaseMetadata]:
        """Load all metadata from JSON files."""
        all_docs = []
        for metadata_file in self.metadata_manager.metadata_dir.glob("*_metadata.json"):
            docs_data = JSONUtils.load_from_file(metadata_file)
            if docs_data:
                for doc_data in docs_data:
                    metadata_class = self.get_metadata_class(doc_data)
                    try:
                        all_docs.append(metadata_class(**doc_data))
                    except Exception as e:
                        logger.warning(f"Could not instantiate metadata for {doc_data.get('id')}: {e}")
        return all_docs

    def validate_all(self):
        """Validate all downloaded files."""
        logger.info("Starting validation of all downloaded files...")
        all_docs = self.load_all_metadata()
        logger.info(f"Found metadata for {len(all_docs)} documents.")

        with tqdm(total=len(all_docs), desc="Validating files", unit="docs") as pbar:
            for doc in all_docs:
                self.validate_document(doc)
                pbar.update(1)

        self.print_summary()

    def validate_document(self, doc: BaseMetadata):
        """Validate a single document."""
        self.stats["validated"] += 1
        file_path_str = getattr(doc, "file_path", None)
        if not file_path_str:
            return

        file_path = self.config.output_dir / file_path_str

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            self.stats["missing"] += 1
            return

        # 1. Check file size against expected size
        expected_size = getattr(doc, "expected_size", None)
        if expected_size is not None and file_path.stat().st_size != expected_size:
            logger.warning(f"File size mismatch for {file_path}. " f"Expected: {expected_size}, Got: {file_path.stat().st_size}")
            self.stats["size_mismatch"] += 1

        # 2. Perform full validation
        if not self.downloader._validate_downloaded_file(file_path, doc):
            logger.warning(f"File is corrupted: {file_path}")
            self.stats["corrupted"] += 1

    def print_summary(self):
        """Print validation summary."""
        print("\n--- Validation Summary ---")
        print(f"Total documents validated: {self.stats['validated']}")
        print(f"  - Missing files: {self.stats['missing']}")
        print(f"  - Corrupted files: {self.stats['corrupted']}")
        print(f"  - File size mismatch: {self.stats['size_mismatch']}")
        print("------------------------\n")


def setup_logging(debug: bool = False, quiet: bool = False) -> None:
    """Setup logging configuration."""
    if quiet:
        level = logging.WARNING
    elif debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", datefmt="%H:%M:%S")


def main():
    """Main entry point."""
    setup_logging()
    config = CrawlerConfig.from_env_file()
    validator = DownloadValidator(config)
    validator.validate_all()


if __name__ == "__main__":
    main()
