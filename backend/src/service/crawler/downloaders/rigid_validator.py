"""
Clean, rigid validator for NEFAC crawler - zero tolerance for failures.
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from tqdm import tqdm

from src.schemas.metadata import BaseMetadata, DocumentMetadata, HTMLMetadata, PDFMetadata, XLSXMetadata, YouTubeMetadata
from src.service.crawler.core.config import FILE_TYPE_DIRECTORIES, CrawlerConfig
from src.service.crawler.downloaders.common import JSONUtils
from src.service.crawler.downloaders.document_downloader import DocumentDownloader
from src.service.crawler.downloaders.metadata_manager import MetadataManager

logger = logging.getLogger(__name__)


class ValidationResult:
    """Clean validation result container."""

    def __init__(self):
        self.total_files = 0
        self.total_metadata = 0
        self.perfect_matches = 0
        self.critical_issues = []  # Missing files, corrupted files, download failures
        self.wordpress_issues = []  # Missing _wordpress suffix, filename mismatches
        self.other_issues = []  # Size mismatches, orphaned files, etc.
        self.start_time = None
        self.end_time = None

    @property
    def has_critical_issues(self) -> bool:
        return bool(self.critical_issues)

    @property
    def has_any_issues(self) -> bool:
        return bool(self.critical_issues or self.wordpress_issues or self.other_issues)

    @property
    def success_rate(self) -> float:
        return (self.perfect_matches / self.total_metadata * 100) if self.total_metadata > 0 else 0

    def print_summary(self):
        """Print clean, focused summary."""
        duration = f" ({self.end_time - self.start_time:.1f}s)" if self.start_time and self.end_time else ""

        print(f"\n{'='*60}")
        print("RIGID VALIDATION REPORT")
        print(f"{'='*60}")
        print(f"Files: {self.total_files} | Metadata: {self.total_metadata} | Success: {self.success_rate:.1f}%{duration}")

        if not self.has_any_issues:
            print(f"\n✅ PERFECT SYNC - All {self.perfect_matches} files validated")
            return

        if self.critical_issues:
            print(f"\n❌ CRITICAL ISSUES ({len(self.critical_issues)}):")
            for issue in self.critical_issues[:3]:
                print(f"   {issue}")
            if len(self.critical_issues) > 3:
                print(f"   ... and {len(self.critical_issues) - 3} more")

        if self.wordpress_issues:
            print(f"\n⚠️  WORDPRESS ISSUES ({len(self.wordpress_issues)}):")
            for issue in self.wordpress_issues[:3]:
                print(f"   {issue}")

        if self.other_issues:
            print(f"\n📋 OTHER ISSUES ({len(self.other_issues)}):")
            for issue in self.other_issues[:3]:
                print(f"   {issue}")

        print(f"\n{'='*60}")
        print("💡 Run with --fix-issues to resolve automatically")


class RigidValidator:
    """Clean, focused validator with zero tolerance."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.downloader = DocumentDownloader(config)
        self.metadata_manager = MetadataManager(config)

    def validate(self, fix_issues: bool = False) -> ValidationResult:
        """Main validation entry point."""
        result = ValidationResult()
        result.start_time = time.time()

        # Load data
        metadata_list = self._load_metadata()
        files_dict = self._scan_files()

        result.total_metadata = len(metadata_list)
        result.total_files = len(files_dict)

        # Validate
        self._validate_sync(metadata_list, files_dict, result)
        self._validate_integrity(metadata_list, result)
        self._validate_wordpress(metadata_list, result)

        # Fix if requested
        if fix_issues and result.has_any_issues:
            self._fix_issues(metadata_list, result)

        result.end_time = time.time()
        result.print_summary()
        return result

    def _load_metadata(self) -> List[BaseMetadata]:
        """Load all metadata files."""
        metadata_list = []

        for metadata_file in self.metadata_manager.metadata_dir.glob("*_metadata.json"):
            docs_data = JSONUtils.load_from_file(metadata_file)
            for doc_data in docs_data or []:
                try:
                    metadata_obj = self._create_metadata_object(doc_data)
                    if metadata_obj:
                        metadata_list.append(metadata_obj)
                except Exception as e:
                    logger.warning(f"Invalid metadata {doc_data.get('id')}: {e}")

        return metadata_list

    def _create_metadata_object(self, doc_data: dict) -> Optional[BaseMetadata]:
        """Create metadata object from dict."""
        source_url = doc_data.get("source_url", "").lower()
        mime_type = doc_data.get("mime_type", "").lower()
        source = doc_data.get("source", "").lower()

        if "pdf" in source_url or "pdf" in mime_type:
            return PDFMetadata(**doc_data)
        elif "xls" in source_url or "spreadsheet" in mime_type:
            return XLSXMetadata(**doc_data)
        elif "html" in source_url or "html" in mime_type:
            return HTMLMetadata(**doc_data)
        elif "youtube" in source:
            return YouTubeMetadata(**doc_data)
        else:
            return DocumentMetadata(**doc_data)

    def _scan_files(self) -> Dict[str, Path]:
        """Scan all files in output directories."""
        files = {}

        # Scan all directories
        for ext, dir_name in FILE_TYPE_DIRECTORIES.items():
            dir_path = self.config.output_dir / dir_name
            if dir_path.exists():
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file():
                        rel_path = str(file_path.relative_to(self.config.output_dir))
                        files[rel_path] = file_path

        # Additional directories
        for dir_name in ["html", "youtube", "other"]:
            dir_path = self.config.output_dir / dir_name
            if dir_path.exists():
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file():
                        rel_path = str(file_path.relative_to(self.config.output_dir))
                        files[rel_path] = file_path

        return files

    def _validate_sync(self, metadata_list: List[BaseMetadata], files_dict: Dict[str, Path], result: ValidationResult):
        """Validate file-metadata synchronization."""
        metadata_files = set()

        for doc in metadata_list:
            # For YouTube items without transcripts, we don't require a local file
            try:
                from src.schemas.metadata import YouTubeMetadata as _YTM
            except Exception:
                _YTM = None

            if _YTM and isinstance(doc, _YTM):
                if not getattr(doc, "transcript_available", False):
                    # Skip file existence checks for videos without transcripts
                    continue

            file_path_str = getattr(doc, "file_path", None)
            if not file_path_str:
                expected_path = self.downloader._generate_filepath(doc)
                file_path_str = str(expected_path.relative_to(self.config.output_dir))

            metadata_files.add(file_path_str)

            if file_path_str not in files_dict:
                result.critical_issues.append(f"Missing: {doc.id}")
            else:
                actual_filename = files_dict[file_path_str].name
                expected_filename = getattr(doc, "filename", "")
                if expected_filename and actual_filename != expected_filename:
                    result.wordpress_issues.append(f"Name mismatch: {doc.id}")
                else:
                    result.perfect_matches += 1

        # Find orphaned files
        for file_path_str in files_dict:
            if file_path_str not in metadata_files:
                result.other_issues.append(f"Orphaned: {file_path_str}")

    def _validate_integrity(self, metadata_list: List[BaseMetadata], result: ValidationResult):
        """Validate file integrity."""
        for doc in tqdm(metadata_list, desc="Validating integrity", unit="files", leave=False):
            # Skip integrity check for YouTube items without transcripts
            try:
                from src.schemas.metadata import YouTubeMetadata as _YTM
            except Exception:
                _YTM = None

            if _YTM and isinstance(doc, _YTM) and not getattr(doc, "transcript_available", False):
                continue

            file_path_str = getattr(doc, "file_path", None)
            if not file_path_str:
                continue

            file_path = self.config.output_dir / file_path_str
            if not file_path.exists():
                continue

            # Check size
            file_size = file_path.stat().st_size
            # Relax minimum size for YouTube transcripts
            if file_size < 100:
                if not (_YTM and isinstance(doc, _YTM)):
                    result.critical_issues.append(f"Empty: {doc.id} ({file_size}B)")
                    continue
            if _YTM and isinstance(doc, _YTM) and file_size == 0:
                result.critical_issues.append(f"Empty: {doc.id} ({file_size}B)")
                continue

            # Check expected size
            expected_size = getattr(doc, "expected_size", None)
            if expected_size is not None and expected_size > 0 and file_size != expected_size:
                result.other_issues.append(f"Size mismatch: {doc.id}")

            # Validate content
            try:
                if not self.downloader._validate_downloaded_file(file_path, doc):
                    result.critical_issues.append(f"Corrupted: {doc.id}")
            except Exception:
                result.critical_issues.append(f"Validation failed: {doc.id}")

    def _validate_wordpress(self, metadata_list: List[BaseMetadata], result: ValidationResult):
        """Validate WordPress-specific requirements."""
        for doc in metadata_list:
            source = getattr(doc, "source", "")
            if source in ["wordpress", "wordpress_rest_api"]:
                filename = getattr(doc, "filename", "")
                if filename and "_wordpress" not in filename:
                    result.wordpress_issues.append(f"Missing _wordpress: {doc.id}")

    def _fix_issues(self, metadata_list: List[BaseMetadata], result: ValidationResult):
        """Fix detected issues."""
        logger.info("Fixing issues...")

        # Re-download missing/corrupted files
        docs_to_fix = []
        for issue in result.critical_issues:
            if any(keyword in issue for keyword in ["Missing:", "Empty:", "Corrupted:"]):
                doc_id = issue.split(":")[1].strip().split()[0]
                for doc in metadata_list:
                    if doc.id == doc_id:
                        docs_to_fix.append(doc)
                        break

        for doc in tqdm(docs_to_fix, desc="Fixing files", unit="files", leave=False):
            try:
                self.downloader.download(doc)
            except Exception as e:
                logger.error(f"Failed to fix {doc.id}: {e}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Rigid validator")
    parser.add_argument("--fix", action="store_true", help="Fix issues")
    args = parser.parse_args()

    config = CrawlerConfig.from_env_file()
    validator = RigidValidator(config)
    result = validator.validate(fix_issues=args.fix)

    exit(2 if result.has_critical_issues else 1 if result.has_any_issues else 0)


if __name__ == "__main__":
    main()
