import json
import os
import sys


def find_index(search_term, metadata_file):
    try:
        with open(metadata_file, "r") as f:
            data = json.load(f)

        if not isinstance(data, list):
            print("Error: Metadata file is not a JSON list.")
            return

        print(f"Searching for '{search_term}' in {len(data)} entries...")

        found = False
        for i, entry in enumerate(data):
            # Search in filename, title, or source_url
            if (search_term in entry.get("filename", "")) or (search_term in entry.get("title", "")) or (search_term in entry.get("source_url", "")):
                print(f"\n✅ Found at index: {i}")
                print(f"ID: {entry.get('id')}")
                print(f"Title: {entry.get('title')}")
                print(f"Filename: {entry.get('filename')}")
                found = True

        if not found:
            print(f"\n❌ '{search_term}' not found in metadata.")

    except FileNotFoundError:
        print(f"Error: File {metadata_file} not found.")
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from {metadata_file}.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Default path to metadata file
    default_path = os.path.join(os.path.dirname(__file__), "src/service/crawler/nefac_documents/metadata/html_metadata.json")

    target = "StudentPressFreedom-Day_wordpress.html"
    if len(sys.argv) > 1:
        target = sys.argv[1]

    find_index(target, default_path)
