"""
Selenium-based content extractor for NEFAC crawler.
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.types import CrawlerSource, ExtractorResult
from .base import BaseExtractor

logger = logging.getLogger(__name__)


class SeleniumExtractor(BaseExtractor):
    """Extractor using Selenium for dynamic content."""

    @property
    def source_name(self) -> str:
        return CrawlerSource.SELENIUM_SCRAPER.value

    def extract(self) -> ExtractorResult:
        """Extract content using Selenium scraper."""
        self._log_extraction_start()

        result = ExtractorResult(documents=[])

        try:
            # Run selenium scraper
            selenium_documents = self._run_selenium_scraper()
            # Convert to DocumentInfo format and add to result
            result.metadata["selenium_content"] = selenium_documents

        except Exception as e:
            error_msg = f"Error in Selenium scraper: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        self._log_extraction_result(result)
        return result

    def _run_selenium_scraper(self) -> List[Dict[str, Any]]:
        """Run the Selenium-based scraper to extract text content from web pages."""
        selenium_scraper_path = Path("tools/selenium-scraper/nefac_scraper.py")
        if not selenium_scraper_path.exists():
            logger.warning(f"Selenium scraper not found at {selenium_scraper_path}")
            return []

        try:
            # Run the Selenium scraper
            result = subprocess.run(
                ["python", str(selenium_scraper_path)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=self.config.output_dir,
            )

            if result.returncode != 0:
                logger.error(f"Selenium scraper failed with return code {result.returncode}")
                logger.error(f"Error output: {result.stderr}")
                return []

            logger.info("Selenium scraper completed successfully")
            return self._process_selenium_output()

        except subprocess.TimeoutExpired:
            logger.error("Selenium scraper timed out after 5 minutes")
            return []
        except Exception as e:
            logger.error(f"Error running Selenium scraper: {e}")
            return []

    def _process_selenium_output(self) -> List[Dict[str, Any]]:
        """Process the output from the Selenium scraper."""
        output_dir = self.config.output_dir / "output"
        if not output_dir.exists():
            logger.warning("Selenium output directory not found")
            return []

        processed_files = []

        for txt_file in output_dir.glob("*.txt"):
            try:
                with open(txt_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Basic processing
                word_count = len(content.split())
                file_size = txt_file.stat().st_size

                processed_file = {
                    "title": txt_file.stem,
                    "url": f"file://{txt_file}",
                    "content": content,
                    "file_size": file_size,
                    "word_count": word_count,
                    "extracted_at": txt_file.stat().st_mtime,
                }

                processed_files.append(processed_file)

            except Exception as e:
                logger.error(f"Error processing {txt_file}: {e}")

        # Save metadata for Selenium content
        if processed_files:
            metadata_file = self.config.output_dir / "metadata" / "selenium_metadata.json"
            try:
                from ..utils.common import JSONUtils

                JSONUtils.save_json(processed_files, metadata_file)
                logger.info(f"Saved metadata for {len(processed_files)} Selenium files")
            except Exception as e:
                logger.error(f"Error saving Selenium metadata: {e}")

        return processed_files
        """Extract content using Selenium scraper."""
        logger.info("Starting Selenium-based extraction...")

        extracted_content = []

        try:
            self._setup_driver()

            # Get URLs to scrape
            urls_to_scrape = self._get_scraping_urls()

            for url in urls_to_scrape:
                try:
                    content = self._scrape_page(url)
                    if content:
                        extracted_content.append(content)
                        logger.info(f"Scraped content from: {url}")

                    # Add delay between requests
                    time.sleep(self.page_load_delay)

                except Exception as e:
                    logger.error(f"Failed to scrape {url}: {e}")

        finally:
            self._cleanup_driver()

        logger.info(f"Extracted {len(extracted_content)} items via Selenium")
        return extracted_content

    def _setup_driver(self):
        """Setup Selenium WebDriver."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            # Chrome options
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

            # Initialize driver
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(self.selenium_timeout)

            logger.info("Selenium WebDriver initialized successfully")

        except Exception as e:
            logger.error(f"Failed to setup Selenium driver: {e}")
            raise

    def _cleanup_driver(self):
        """Cleanup Selenium WebDriver."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Selenium WebDriver cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up driver: {e}")

    def _get_scraping_urls(self) -> List[str]:
        """Get URLs that require Selenium scraping."""
        # These could be URLs that are:
        # 1. JavaScript-heavy pages
        # 2. Pages with dynamic content loading
        # 3. Pages requiring interaction (clicking, scrolling)
        # 4. Pages with complex authentication

        urls = []

        # Add specific NEFAC pages that need Selenium
        base_urls = [
            f"{self.config.wordpress_base_url}/resources/",
            f"{self.config.wordpress_base_url}/news/",
            f"{self.config.wordpress_base_url}/training/",
        ]

        for base_url in base_urls:
            try:
                page_urls = self._discover_dynamic_urls(base_url)
                urls.extend(page_urls)
            except Exception as e:
                logger.error(f"Failed to discover URLs for {base_url}: {e}")

        return list(set(urls))  # Remove duplicates

    def _discover_dynamic_urls(self, base_url: str) -> List[str]:
        """Discover URLs from a page that requires JavaScript."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        urls = []

        try:
            self.driver.get(base_url)

            # Wait for page to load
            WebDriverWait(self.driver, self.selenium_timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # Additional wait for dynamic content
            time.sleep(self.page_load_delay)

            # Find all links
            link_elements = self.driver.find_elements(By.TAG_NAME, "a")

            for link in link_elements:
                try:
                    href = link.get_attribute("href")
                    if href and self._is_valid_nefac_url(href):
                        urls.append(href)
                except Exception:
                    continue

            # Handle pagination or "Load More" buttons
            urls.extend(self._handle_pagination())

        except Exception as e:
            logger.error(f"Failed to discover URLs from {base_url}: {e}")

        return urls

    def _handle_pagination(self) -> List[str]:
        """Handle pagination or Load More functionality."""
        from selenium.common.exceptions import NoSuchElementException, TimeoutException
        from selenium.webdriver.common.by import By

        additional_urls = []

        try:
            # Look for "Load More" or pagination buttons
            load_more_selectors = ["button[class*='load-more']", "a[class*='load-more']", ".load-more-button", ".pagination a", "[data-load-more]"]

            for selector in load_more_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            # Scroll to element
                            self.driver.execute_script("arguments[0].scrollIntoView();", element)
                            time.sleep(1)

                            # Click the element
                            element.click()

                            # Wait for new content to load
                            time.sleep(3)

                            # Get new links that appeared
                            new_links = self.driver.find_elements(By.TAG_NAME, "a")
                            for link in new_links:
                                try:
                                    href = link.get_attribute("href")
                                    if href and self._is_valid_nefac_url(href):
                                        additional_urls.append(href)
                                except Exception:
                                    continue

                            break  # Exit after first successful load more

                except (NoSuchElementException, TimeoutException):
                    continue
                except Exception as e:
                    logger.debug(f"Error handling pagination element: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in pagination handling: {e}")

        return additional_urls

    def _is_valid_nefac_url(self, url: str) -> bool:
        """Check if URL is a valid NEFAC URL to scrape."""
        if not url:
            return False

        # Must be NEFAC domain
        if "nefac.org" not in url:
            return False

        # Skip certain file types and external links
        skip_extensions = [".jpg", ".jpeg", ".png", ".gif", ".pdf", ".zip", ".doc", ".docx"]
        if any(url.lower().endswith(ext) for ext in skip_extensions):
            return False

        # Skip admin and technical URLs
        skip_patterns = ["wp-admin", "wp-login", "wp-json", "feed", "xmlrpc"]
        if any(pattern in url.lower() for pattern in skip_patterns):
            return False

        return True

    def _scrape_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape content from a specific page."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        try:
            self.driver.get(url)

            # Wait for page to load
            WebDriverWait(self.driver, self.selenium_timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # Additional wait for dynamic content
            time.sleep(self.page_load_delay)

            # Extract content
            content_data = {"url": url, "title": self._extract_title(), "content": self._extract_main_content(), "meta_description": self._extract_meta_description(), "links": self._extract_internal_links(), "images": self._extract_images(), "extraction_method": "selenium", "timestamp": time.time()}

            return content_data

        except Exception as e:
            logger.error(f"Failed to scrape page {url}: {e}")
            return None

    def _extract_title(self) -> str:
        """Extract page title."""
        from selenium.webdriver.common.by import By

        try:
            title_element = self.driver.find_element(By.TAG_NAME, "title")
            return title_element.get_attribute("innerHTML").strip()
        except Exception:
            try:
                h1_element = self.driver.find_element(By.TAG_NAME, "h1")
                return h1_element.text.strip()
            except Exception:
                return "No title found"

    def _extract_main_content(self) -> str:
        """Extract main content from the page."""
        from selenium.webdriver.common.by import By

        content_selectors = ["main", ".content", ".post-content", ".entry-content", "#content", "article", ".article-content"]

        for selector in content_selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                return element.text.strip()
            except Exception:
                continue

        # Fallback to body content
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            return body.text.strip()
        except Exception:
            return "No content found"

    def _extract_meta_description(self) -> str:
        """Extract meta description."""
        from selenium.webdriver.common.by import By

        try:
            meta_element = self.driver.find_element(By.CSS_SELECTOR, "meta[name='description']")
            return meta_element.get_attribute("content").strip()
        except Exception:
            return ""

    def _extract_internal_links(self) -> List[str]:
        """Extract internal links from the page."""
        from selenium.webdriver.common.by import By

        links = []

        try:
            link_elements = self.driver.find_elements(By.TAG_NAME, "a")

            for link in link_elements:
                try:
                    href = link.get_attribute("href")
                    if href and self._is_valid_nefac_url(href):
                        links.append(href)
                except Exception:
                    continue
        except Exception:
            pass

        return list(set(links))  # Remove duplicates

    def _extract_images(self) -> List[Dict[str, Any]]:
        """Extract images from the page."""
        from selenium.webdriver.common.by import By

        images = []

        try:
            img_elements = self.driver.find_elements(By.TAG_NAME, "img")

            for img in img_elements:
                try:
                    src = img.get_attribute("src")
                    if src:
                        image_data = {"src": src, "alt": img.get_attribute("alt") or "", "title": img.get_attribute("title") or "", "width": img.get_attribute("width"), "height": img.get_attribute("height")}
                        images.append(image_data)
                except Exception:
                    continue
        except Exception:
            pass

        return images
