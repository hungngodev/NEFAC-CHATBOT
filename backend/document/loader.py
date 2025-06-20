import glob
import os
import shutil
from document.pdf_loader import pdfLoader
from document.youtube_loader import youtubeLoader
import pickle
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define folder paths as placeholders
WAITING_ROOM_PATH = "docs/waiting_room"
FINISHED_PATH = "docs/finished_tagging"
COPY_DESTINATION_PATH = "../frontend/public/docs"  # New destination path for copying


def load_all_documents():
    all_documents = set()
    new_docs = set()

    # Load title_to_chunks from pickle if it exists
    if os.path.exists("title_to_chunks.pkl"):
        with open("title_to_chunks.pkl", "rb") as t2c:
            title_to_chunks = pickle.load(t2c)
    else:
        title_to_chunks = {}  # Initialize as empty if the file does not exist

    if os.path.exists("url_to_title.pkl"):
        with open("url_to_title.pkl", "rb") as u2t:
            url_to_title = pickle.load(u2t)
    else:
        url_to_title = {}

    # Process PDFs
    pdf_files = glob.glob(os.path.join(WAITING_ROOM_PATH, "*.pdf"))
    for pdf_file in pdf_files:
        new_doc = pdfLoader(pdf_file, title_to_chunks)
        all_documents.update(new_doc)
        new_docs.update(new_doc)
        shutil.copy(
            pdf_file, os.path.join(COPY_DESTINATION_PATH, os.path.basename(pdf_file))
        )  # move to frontend for fetching WONT NEED WHEN WE ARE USING NEFAC WEBSITE
        os.rename(pdf_file, os.path.join(FINISHED_PATH, os.path.basename(pdf_file)))

    # Process YouTube URLs
    yt_urls_file = os.path.join(WAITING_ROOM_PATH, "yt_urls.txt")
    finished_urls_file = os.path.join(FINISHED_PATH, "yt_urls.txt")

    # Read all URLs into memory
    urls = []
    if os.path.exists(yt_urls_file):
        with open(yt_urls_file, "r") as waiting_read:
            urls = [line.strip() for line in waiting_read if line.strip()]

    # Log total number of YouTube videos to process
    total_videos = len(urls)
    if total_videos > 0:
        logger.info(f"Starting to process {total_videos} YouTube videos")

    # Process URLs and collect failed ones
    failed_urls = []
    for idx, url in enumerate(urls, 1):
        # Skip empty lines or lines that don't look like URLs
        if not url or not url.startswith("http"):
            logger.warning(f"Skipping invalid URL: {url}")
            continue

        logger.info(f"Processing YouTube video {idx}/{total_videos}: {url}")

        with open(finished_urls_file, "a") as finished:
            try:
                new_vid = youtubeLoader(url, title_to_chunks, url_to_title)
                all_documents.update(new_vid)
                new_docs.update(new_vid)
                finished.write(url + "\n")
                logger.info(f"Successfully processed video {idx}/{total_videos}")
            except Exception as e:
                logger.error(
                    f"Error processing YouTube URL {url} (video {idx}/{total_videos}): {e}"
                )
                failed_urls.append(url)
                continue

    # Log completion status
    if total_videos > 0:
        successful_videos = total_videos - len(failed_urls)
        logger.info(
            f"YouTube video processing complete: {successful_videos}/{total_videos} successful, {len(failed_urls)} failed"
        )

    # Rewrite failed URLs to waiting_room/yt_urls.txt
    with open(yt_urls_file, "w") as waiting_write:
        for url in failed_urls:
            waiting_write.write(url + "\n")

    # Save title_to_chunks to make it available for sequential loading
    with open("title_to_chunks.pkl", "wb") as t2c:
        pickle.dump(title_to_chunks, t2c)
    logger.info("Saved title_to_chunks.pkl for sequential loading")

    return all_documents, url_to_title, title_to_chunks, new_docs
