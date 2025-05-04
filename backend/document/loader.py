import glob
import os
import shutil
from document.pdf_loader import pdfLoader
from document.youtube_loader import youtubeLoader
import pickle

# Define folder paths as placeholders
WAITING_ROOM_PATH = "backend/docs/waiting_room"
FINISHED_PATH = "backend/docs/finished_tagging"
COPY_DESTINATION_PATH = "../frontend/public/docs"  # New destination path for copying

def load_all_documents():
    all_documents = set()
    new_docs = set()

    # Load title_to_chunks from pickle if it exists
    if os.path.exists('title_to_chunks.pkl'):
        with open('title_to_chunks.pkl', 'rb') as t2c:
            title_to_chunks = pickle.load(t2c)
    else:
        title_to_chunks = {}  # Initialize as empty if the file does not exist

    if os.path.exists('url_to_title.pkl'):
        with open('url_to_title.pkl', 'rb') as u2t:
            url_to_title = pickle.load(u2t)
    else:
        url_to_title = {}

    # Ensure finished and copy destination directories exist
    os.makedirs(FINISHED_PATH, exist_ok=True)
    os.makedirs(COPY_DESTINATION_PATH, exist_ok=True)

    # Process PDFs
    pdf_files = glob.glob(os.path.join(WAITING_ROOM_PATH, "*.pdf"))
    for pdf_file in pdf_files:
        new_doc = pdfLoader(pdf_file, title_to_chunks)
        all_documents.update(new_doc)
        new_docs.update(new_doc)
        # Copy to the new destination path
        shutil.copy(pdf_file, os.path.join(COPY_DESTINATION_PATH, os.path.basename(pdf_file)))
        # Move to finished folder
        os.rename(pdf_file, os.path.join(FINISHED_PATH, os.path.basename(pdf_file)))

    # Process YouTube URLs (each URL in its own .txt file)
    txt_files = glob.glob(os.path.join(WAITING_ROOM_PATH, "*.txt"))
    for txt_file in txt_files:
        with open(txt_file, "r") as f:
            url = f.read().strip()
        new_vid = youtubeLoader(url, title_to_chunks, url_to_title)
        all_documents.update(new_vid)
        new_docs.update(new_vid)
        # Copy to the new destination path
        shutil.copy(txt_file, os.path.join(COPY_DESTINATION_PATH, os.path.basename(txt_file)))
        # Move to finished folder
        os.rename(txt_file, os.path.join(FINISHED_PATH, os.path.basename(txt_file)))
        # Append URL to yt_urls.txt in FINISHED_PATH
        with open(os.path.join(FINISHED_PATH, "yt_urls.txt"), "a") as yt_file:
            yt_file.write(url + "\n")  # Append the URL with a newline

    return all_documents, url_to_title, title_to_chunks, new_docs