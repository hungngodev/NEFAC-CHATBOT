import re
import os
from langchain.docstore.document import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone as LangchainPinecone
import pinecone
from dotenv import load_dotenv
import json
import logging
import pickle
from pathlib import Path
from tqdm import tqdm
from typing import List
from langchain.llms import HuggingFacePipeline
from langchain.prompts import PromptTemplate
from transformers import pipeline as hf_pipeline
import glob
from bs4 import BeautifulSoup
from service.schemas.metadata import ContentMetadata, PDFMetadata, YouTubeMetadata

# Optional dependencies for indexing/graph
try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None
    print("Warning: rank_bm25 not installed. BM25 indexing will be skipped.")
try:
    import networkx as nx
    from networkx import write_gpickle
except ImportError:
    nx = None
    write_gpickle = None
    print("Warning: networkx not installed. Entity graph construction will be skipped.")
# The following imports are optional and may cause linter errors if not installed:
try:
    import pinecone  # Optional: for Pinecone vector DB
except ImportError:
    pinecone = None
    print("Warning: pinecone not installed. Vector DB upload will be skipped.")
try:
    from neo4j import GraphDatabase  # Optional: for Neo4j graph DB
except ImportError:
    GraphDatabase = None
    print("Warning: neo4j-driver not installed. Online graph upload will be skipped.")
try:
    from elasticsearch import Elasticsearch  # Optional: for Elasticsearch BM25
except ImportError:
    Elasticsearch = None
    print("Warning: elasticsearch not installed. Online BM25 upload will be skipped.")

# spaCy for entity extraction
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except Exception as e:
    nlp = None
    print(f"spaCy not available or model not downloaded: {e}")

# Load environment variables
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV")  # e.g., "gcp-starter"
INDEX_NAME = "nefac-docs"

# Initialize Pinecone
if pinecone is not None:
    pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Contextualization Setup ---
# You can change the model name below to any local Llama model you have
LLAMA_MODEL_NAME = "meta-llama/Llama-2-70b-chat-hf"  # Change if needed
try:
    llama_pipe = hf_pipeline("text-generation", model=LLAMA_MODEL_NAME, device=0)
    llm = HuggingFacePipeline(pipeline=llama_pipe)
except Exception as e:
    llm = None
    print(f"Warning: Could not load Llama model '{LLAMA_MODEL_NAME}': {e}")

contextual_prompt = PromptTemplate.from_template(
    """<document>\n{document}\n</document>\nHere is the chunk we want to situate within the whole document\n<chunk>\n{chunk}\n</chunk>\nPlease give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""
)

def contextualize_chunk(llm, document, chunk):
    if llm is None:
        # Fallback: just return the chunk
        return "", chunk
    prompt = contextual_prompt.format(document=document, chunk=chunk)
    try:
        context = llm(prompt, max_new_tokens=100)
        if isinstance(context, str):
            context = context.strip()
        elif isinstance(context, list):
            context = context[0].strip()
        else:
            context = str(context).strip()
        contextualized_chunk = context + ' ' + chunk
        return context, contextualized_chunk
    except Exception as e:
        print(f"Contextualization failed: {e}")
        return "", chunk

def transcript_loader(path: str) -> list[Document]:
    """
    Loads a timestamped transcript file and converts it into a list of Document objects.
    Each line with a timestamp becomes a Document with 'start' in its metadata.
    """
    documents = []
    with open(path, 'r') as file:
        lines = file.readlines()

    doc_title = path.split('/')[-1].replace('.txt', '').replace('_', ' ')

    for line in lines:
        # Regex to find a timestamp like [123.45s]
        match = re.match(r'\[(\d+\.\d+)s\]\s*(.*)', line)
        if match:
            start_time = float(match.group(1))
            content = match.group(2).strip()
            
            if content:
                # Create a document for each valid line
                doc = Document(
                    page_content=content,
                    metadata={
                        'source': doc_title,
                        'type': 'youtube',
                        'start_seconds': start_time,
                        'citation': f"Timestamp: {int(start_time // 60)}m {int(start_time % 60)}s"
                    }
                )
                documents.append(doc)
    return documents

def pdf_loader(path: str, entry_metadata: dict) -> list[Document]:
    """
    Loads a PDF, splitting it by page and adding metadata for citations.
    Includes all metadata fields from the metadata entry.
    """
    from langchain_community.document_loaders import PyPDFLoader
    loader = PyPDFLoader(path)
    pages = loader.load_and_split()
    doc_title = path.split('/')[-1].replace('.pdf', '').replace('_', ' ')
    for page in pages:
        # Merge all metadata fields from entry_metadata
        page.metadata.update(entry_metadata)
        page.metadata['source'] = doc_title
        page.metadata['type'] = 'pdf'
        page.metadata['citation'] = f"Page {page.metadata.get('page', 0) + 1}"
    return pages

def adaptive_chunk_documents(documents, doc_type, strategy=None):
    """
    Chunks documents using the best method for the type/strategy.
    """
    if strategy is None:
        # Auto-select based on doc_type
        if doc_type == "pdf":
            strategy = "recursive"
        elif doc_type == "youtube":
            strategy = "timestamp_group"
        elif doc_type == "xlsx":
            strategy = "row"
        else:
            strategy = "recursive"

    if strategy == "recursive":
        splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name="gpt-4",
            chunk_size=400,
            chunk_overlap=0,
            separators=["\n\n", "\n", " ", ""],
        )
        return splitter.split_documents(documents)

    elif strategy == "semantic":
        # This is slower and more expensive, but more precise
        try:
            from langchain_text_splitters import SemanticChunker
        except ImportError:
            raise ImportError("SemanticChunker requires a newer version of langchain-text-splitters. Please update if needed.")
        splitter = SemanticChunker(OpenAIEmbeddings(model="text-embedding-3-large"))
        return splitter.split_documents(documents)

    elif strategy == "timestamp_group" and doc_type == "youtube":
        # Group transcript lines into ~400-char blocks, preserving first timestamp
        grouped = []
        current = []
        current_len = 0
        for doc in documents:
            text = doc.page_content
            if current_len + len(text) > 400 and current:
                # Create a chunk
                chunk_text = " ".join([d.page_content for d in current])
                metadata = current[0].metadata.copy()
                grouped.append(Document(page_content=chunk_text, metadata=metadata))
                current = []
                current_len = 0
            current.append(doc)
            current_len += len(text)
        if current:
            chunk_text = " ".join([d.page_content for d in current])
            metadata = current[0].metadata.copy()
            grouped.append(Document(page_content=chunk_text, metadata=metadata))
        return grouped

    elif strategy == "row" and doc_type == "xlsx":
        # Placeholder: implement row-based chunking for spreadsheets
        raise NotImplementedError("Row-based chunking for XLSX is not implemented yet.")

    else:
        raise ValueError(f"Unknown chunking strategy: {strategy}")

def load_youtube_transcripts_and_metadata(metadata_path, transcripts_dir) -> list[Document]:
    """
    Loads YouTube transcript text and metadata from crawler outputs.
    Returns a list of Document objects with all metadata fields from the metadata entry.
    """
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata_list = json.load(f)
    results = []
    for entry in metadata_list:
        transcript_file = entry.get("transcript_file")
        if not transcript_file:
            continue
        transcript_path = os.path.join(transcripts_dir, os.path.basename(transcript_file))
        if not os.path.exists(transcript_path):
            continue
        with open(transcript_path, "r", encoding="utf-8") as tf:
            transcript_text = tf.read()
        # Merge all metadata fields from entry
        doc_metadata = dict(entry)
        doc_metadata['type'] = 'youtube'
        doc_metadata['source'] = entry.get('title', transcript_file)
        results.append(Document(
            page_content=transcript_text,
            metadata=doc_metadata
        ))
    return results

def html_loader(path: str, page_url: str, entry_metadata: dict) -> list[Document]:
    """
    Loads HTML/text content, chunks by headings/paragraphs, and adds citation metadata as 'page_url#anchor' if anchor exists, else just 'page_url'.
    Only uses existing anchors (id or name). Does not modify HTML.
    Includes all metadata fields from the metadata entry.
    """
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
        tag.decompose()
    elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'])
    chunks = []
    for el in elements:
        text = el.get_text(separator=' ', strip=True)
        if not text:
            continue
        anchor = el.get('id') or el.get('name')
        if anchor:
            citation = f"{page_url}#{anchor}"
        else:
            citation = page_url
        doc_title = os.path.basename(path).replace('.html', '').replace('_', ' ')
        # Merge all metadata fields from entry_metadata
        chunk_metadata = dict(entry_metadata)
        chunk_metadata.update({
            'source': doc_title,
            'type': 'html',
            'citation': citation
        })
        chunks.append(Document(
            page_content=text,
            metadata=chunk_metadata
        ))
    return chunks

def process_and_load_to_db(path: str, file_type: str, chunking_strategy: str = None):
    """
    Unified ingestion pipeline for PDF, YouTube, HTML, and Images.
    For YouTube, reads transcripts and metadata from crawler outputs.
    Loads, chunks, contextualizes, saves, and indexes documents, and builds BM25 and entity graph.
    """
    logger.info(f"Starting processing for {path} of type {file_type}")
    if file_type == "pdf":
        documents = pdf_loader(path)
        with open(path, "rb") as f:
            import PyPDF2
            reader = PyPDF2.PdfReader(f)
            full_document_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif file_type == "youtube":
        metadata_path = "service/crawler/nefac_documents/metadata/youtube_metadata.json"
        transcripts_dir = "service/crawler/nefac_documents/youtube"
        yt_docs = load_youtube_transcripts_and_metadata(metadata_path, transcripts_dir)
        documents = []
        for doc in yt_docs:
            from langchain_core.documents import Document
            documents.append(Document(page_content=doc["text"], metadata=doc["metadata"]))
        full_document_text = "\n".join(doc.page_content for doc in documents)
    elif file_type == "html":
        documents = html_loader(path, path)
        with open(path, "r", encoding="utf-8") as f:
            full_document_text = f.read()
    elif file_type == "image":
        documents = image_loader(path)
        full_document_text = "[IMAGE CONTENT NOT EXTRACTED]"
    else:
        logger.error(f"Unsupported file type: {file_type}")
        return
    if not documents:
        logger.warning(f"No documents loaded from {path}. Skipping.")
        return
    logger.info(f"Loaded {len(documents)} document pages/sections from {path}")
    # --- Contextualization Step ---
    contextualized_documents = []
    for doc in tqdm(documents, desc="Contextualizing chunks"):
        context, contextualized_chunk = contextualize_chunk(llm, full_document_text, doc.page_content)
        doc.metadata["contextualization"] = context
        doc.metadata["original_chunk"] = doc.page_content
        doc.page_content = contextualized_chunk
        contextualized_documents.append(doc)
    # Prepare output directories
    Path("docs/lexical_index").mkdir(parents=True, exist_ok=True)
    Path("docs/graph").mkdir(parents=True, exist_ok=True)
    chunk_jsonl_path = "docs/lexical_index/chunks.jsonl"
    entity_jsonl_path = "docs/graph/entities.jsonl"
    chunk_records = []
    with open(chunk_jsonl_path, "w", encoding="utf-8") as chunk_f, open(entity_jsonl_path, "w", encoding="utf-8") as entity_f:
        for doc in tqdm(contextualized_documents, desc="Indexing chunks and extracting entities"):
            chunk_record = {
                "title": doc.metadata.get("title", ""),
                "text": doc.page_content,
                "metadata": doc.metadata
            }
            chunk_f.write(json.dumps(chunk_record, ensure_ascii=False) + "\n")
            chunk_records.append(chunk_record)
            if nlp is not None:
                spacy_doc = nlp(doc.page_content)
                entities = [
                    {"text": ent.text, "label": ent.label_}
                    for ent in spacy_doc.ents
                ]
                entity_record = {
                    "title": doc.metadata.get("title", ""),
                    "entities": entities,
                    "metadata": doc.metadata
                }
                entity_f.write(json.dumps(entity_record, ensure_ascii=False) + "\n")
    logger.info(f"Saved chunk texts for BM25/TF-IDF to {chunk_jsonl_path}")
    logger.info(f"Saved entity extraction results to {entity_jsonl_path}")
    build_bm25_index(chunk_jsonl_path)
    build_entity_graph(entity_jsonl_path)
    # --- Upload to Online Databases ---
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    if nx is not None:
        try:
            if hasattr(nx, "read_gpickle"):
                G = nx.read_gpickle("docs/graph/entity_graph.gpickle")
                upload_graph_to_neo4j(G, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
            else:
                print("networkx.read_gpickle not available. Skipping Neo4j upload.")
        except Exception as e:
            print(f"Neo4j upload skipped: {e}")
    ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
    ES_INDEX = os.getenv("ES_INDEX", "nefac-bm25")
    upload_chunks_to_elasticsearch(chunk_records, ES_HOST, ES_INDEX)
    logger.info(f"Completed ingestion and indexing for {path}")
    return len(contextualized_documents)

# --- BM25 Indexing ---
def build_bm25_index(chunk_jsonl_path="docs/lexical_index/chunks.jsonl", output_path="docs/lexical_index/bm25_index.pkl"):
    if BM25Okapi is None:
        print("rank_bm25 not installed. Please install it to use BM25 indexing.")
        return
    documents = []
    metadatas = []
    with open(chunk_jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            documents.append(record["text"])
            metadatas.append(record["metadata"])
    tokenized_corpus = [doc.split() for doc in documents]
    bm25 = BM25Okapi(tokenized_corpus)
    with open(output_path, "wb") as out:
        pickle.dump({"bm25": bm25, "metadatas": metadatas, "documents": documents}, out)
    print(f"BM25 index saved to {output_path}")

# --- Entity Graph ---
def build_entity_graph(entity_jsonl_path="docs/graph/entities.jsonl", output_path="docs/graph/entity_graph.gpickle"):
    if nx is None or write_gpickle is None:
        print("networkx not installed. Please install it to use entity graph construction.")
        return
    G = nx.Graph()
    with open(entity_jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            entities = record.get("entities", [])
            entity_nodes = [(ent["text"], ent["label"]) for ent in entities]
            for node in entity_nodes:
                G.add_node(node[0], label=node[1])
            for i in range(len(entity_nodes)):
                for j in range(i+1, len(entity_nodes)):
                    G.add_edge(entity_nodes[i][0], entity_nodes[j][0])
    write_gpickle(G, output_path)
    print(f"Entity graph saved to {output_path}")

def upload_graph_to_neo4j(graph, uri, user, password):
    if GraphDatabase is None:
        print("neo4j-driver not installed. Skipping Neo4j upload.")
        return
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            # Optional: clear existing graph
            session.run("MATCH (n) DETACH DELETE n")
            # Add nodes
            for node, data in graph.nodes(data=True):
                session.run("MERGE (e:Entity {name: $name, label: $label})", name=node, label=data.get("label", ""))
            # Add edges
            for src, dst in graph.edges():
                session.run("""
                    MATCH (a:Entity {name: $src}), (b:Entity {name: $dst})
                    MERGE (a)-[:CO_OCCURS_WITH]->(b)
                """, src=src, dst=dst)
        driver.close()
        print("Knowledge graph uploaded to Neo4j.")
    except Exception as e:
        print(f"Neo4j upload failed: {e}")

def upload_chunks_to_elasticsearch(chunks, es_host, index_name):
    if Elasticsearch is None:
        print("elasticsearch not installed. Skipping BM25 upload.")
        return
    try:
        es = Elasticsearch([es_host])
        # Create index if not exists
        if not es.indices.exists(index=index_name):
            es.indices.create(index=index_name)
        # Index each chunk
        for chunk in chunks:
            doc = {
                "text": chunk["text"],
                "title": chunk["title"],
                "metadata": chunk["metadata"]
            }
            es.index(index=index_name, document=doc)
        print(f"Uploaded {len(chunks)} chunks to Elasticsearch index '{index_name}'.")
    except Exception as e:
        print(f"Elasticsearch upload failed: {e}")

def process_all_metadata():
    """
    Iterates over all metadata files in service/crawler/nefac_documents/metadata/ and processes all document types.
    Enforces Pydantic schema validation for all metadata entries.
    Removes all image processing.
    """
    metadata_dir = "service/crawler/nefac_documents/metadata/"
    # Map metadata files to types and schemas
    metadata_map = {
        "documents_metadata.json": ("pdf", PDFMetadata),
        "youtube_metadata.json": ("youtube", YouTubeMetadata),
        "content_metadata.json": ("html", ContentMetadata),
    }
    for meta_file, (doc_type, schema) in metadata_map.items():
        meta_path = os.path.join(metadata_dir, meta_file)
        if not os.path.exists(meta_path):
            logger.warning(f"Metadata file {meta_path} not found. Skipping.")
            continue
        logger.info(f"Processing metadata file: {meta_path} as type {doc_type}")
        with open(meta_path, "r", encoding="utf-8") as f:
            try:
                entries = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load {meta_path}: {e}")
                continue
        if doc_type == "youtube":
            # Validate all YouTube entries at once, skipping invalid ones
            valid_entries = []
            for entry in tqdm(entries, desc=f"Validating {doc_type} entries"):
                try:
                    validated_entry = schema(**entry)
                    valid_entries.append(validated_entry)
                except Exception as e:
                    logger.error(f"Schema validation failed for {doc_type} entry: {e}. Skipping entry: {entry}")
            if not valid_entries:
                logger.warning(f"No valid YouTube metadata entries found. Skipping.")
                continue
            metadata_path = os.path.join(metadata_dir, "youtube_metadata.json")
            transcripts_dir = "service/crawler/nefac_documents/youtube"
            documents = load_youtube_transcripts_and_metadata(metadata_path, transcripts_dir)
            if not documents:
                logger.warning(f"No documents loaded from {metadata_path}. Skipping.")
                continue
            logger.info(f"Loaded {len(documents)} YOUTUBE sections from {metadata_path}")
            # --- Contextualization Step ---
            contextualized_documents = []
            full_document_text = '\n'.join(doc.page_content for doc in documents)
            for doc in tqdm(documents, desc="Contextualizing chunks"):
                context, contextualized_chunk = contextualize_chunk(llm, full_document_text, doc.page_content)
                doc.metadata["contextualization"] = context
                doc.metadata["original_chunk"] = doc.page_content
                doc.page_content = contextualized_chunk
                contextualized_documents.append(doc)
            # Prepare output directories
            Path("docs/lexical_index").mkdir(parents=True, exist_ok=True)
            Path("docs/graph").mkdir(parents=True, exist_ok=True)
            chunk_jsonl_path = "docs/lexical_index/chunks.jsonl"
            entity_jsonl_path = "docs/graph/entities.jsonl"
            chunk_records = []
            with open(chunk_jsonl_path, "a", encoding="utf-8") as chunk_f, open(entity_jsonl_path, "a", encoding="utf-8") as entity_f:
                for doc in tqdm(contextualized_documents, desc="Indexing chunks and extracting entities"):
                    chunk_record = {
                        "title": doc.metadata.get("title", ""),
                        "text": doc.page_content,
                        "metadata": doc.metadata
                    }
                    chunk_f.write(json.dumps(chunk_record, ensure_ascii=False) + "\n")
                    chunk_records.append(chunk_record)
                    if nlp is not None:
                        spacy_doc = nlp(doc.page_content)
                        entities = [
                            {"text": ent.text, "label": ent.label_}
                            for ent in spacy_doc.ents
                        ]
                        entity_record = {
                            "title": doc.metadata.get("title", ""),
                            "entities": entities,
                            "metadata": doc.metadata
                        }
                        entity_f.write(json.dumps(entity_record, ensure_ascii=False) + "\n")
            logger.info(f"Saved chunk texts for BM25/TF-IDF to {chunk_jsonl_path}")
            logger.info(f"Saved entity extraction results to {entity_jsonl_path}")
            build_bm25_index(chunk_jsonl_path)
            build_entity_graph(entity_jsonl_path)
            # --- Upload to Online Databases ---
            NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
            NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
            if nx is not None:
                try:
                    if hasattr(nx, "read_gpickle"):
                        G = nx.read_gpickle("docs/graph/entity_graph.gpickle")
                        upload_graph_to_neo4j(G, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
                    else:
                        print("networkx.read_gpickle not available. Skipping Neo4j upload.")
                except Exception as e:
                    print(f"Neo4j upload skipped: {e}")
            ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
            ES_INDEX = os.getenv("ES_INDEX", "nefac-bm25")
            upload_chunks_to_elasticsearch(chunk_records, ES_HOST, ES_INDEX)
            logger.info(f"Completed ingestion and indexing for {metadata_path}")
            continue  # Only process YouTube once
        for entry in tqdm(entries, desc=f"Processing {doc_type} entries"):
            # Validate entry with Pydantic schema
            try:
                validated_entry = schema(**entry)
            except Exception as e:
                logger.error(f"Schema validation failed for {doc_type} entry: {e}. Skipping entry: {entry}")
                continue
            if doc_type == "pdf":
                filename = validated_entry.filename
                if not filename:
                    continue
                abs_path = os.path.join("service/crawler/nefac_documents/documents", filename)
                if not abs_path or not isinstance(abs_path, str):
                    continue
                if not os.path.exists(abs_path):
                    logger.warning(f"PDF file {abs_path} not found. Skipping.")
                    continue
                documents = pdf_loader(abs_path, validated_entry.dict())
            elif doc_type == "html":
                filename = validated_entry.filename
                page_url = validated_entry.link
                if not filename or not page_url:
                    continue
                abs_path = os.path.join("service/crawler/nefac_documents/content", filename)
                if not abs_path or not isinstance(abs_path, str):
                    continue
                if not os.path.exists(abs_path):
                    logger.warning(f"HTML file {abs_path} not found. Skipping.")
                    continue
                documents = html_loader(abs_path, page_url, validated_entry.dict())
            else:
                logger.warning(f"Unknown doc_type {doc_type} in {meta_file}")
                continue
            if not documents:
                logger.warning(f"No documents loaded from {abs_path if doc_type != 'youtube' else meta_path}. Skipping.")
                continue
            logger.info(f"Loaded {len(documents)} {doc_type.upper()} sections from {abs_path if doc_type != 'youtube' else meta_path}")
            # --- Contextualization Step ---
            contextualized_documents = []
            full_document_text = '\n'.join(doc.page_content for doc in documents)
            for doc in tqdm(documents, desc="Contextualizing chunks"):
                context, contextualized_chunk = contextualize_chunk(llm, full_document_text, doc.page_content)
                doc.metadata["contextualization"] = context
                doc.metadata["original_chunk"] = doc.page_content
                doc.page_content = contextualized_chunk
                contextualized_documents.append(doc)
            # Prepare output directories
            Path("docs/lexical_index").mkdir(parents=True, exist_ok=True)
            Path("docs/graph").mkdir(parents=True, exist_ok=True)
            chunk_jsonl_path = "docs/lexical_index/chunks.jsonl"
            entity_jsonl_path = "docs/graph/entities.jsonl"
            chunk_records = []
            with open(chunk_jsonl_path, "a", encoding="utf-8") as chunk_f, open(entity_jsonl_path, "a", encoding="utf-8") as entity_f:
                for doc in tqdm(contextualized_documents, desc="Indexing chunks and extracting entities"):
                    chunk_record = {
                        "title": doc.metadata.get("title", ""),
                        "text": doc.page_content,
                        "metadata": doc.metadata
                    }
                    chunk_f.write(json.dumps(chunk_record, ensure_ascii=False) + "\n")
                    chunk_records.append(chunk_record)
                    if nlp is not None:
                        spacy_doc = nlp(doc.page_content)
                        entities = [
                            {"text": ent.text, "label": ent.label_}
                            for ent in spacy_doc.ents
                        ]
                        entity_record = {
                            "title": doc.metadata.get("title", ""),
                            "entities": entities,
                            "metadata": doc.metadata
                        }
                        entity_f.write(json.dumps(entity_record, ensure_ascii=False) + "\n")
            logger.info(f"Saved chunk texts for BM25/TF-IDF to {chunk_jsonl_path}")
            logger.info(f"Saved entity extraction results to {entity_jsonl_path}")
            build_bm25_index(chunk_jsonl_path)
            build_entity_graph(entity_jsonl_path)
            # --- Upload to Online Databases ---
            NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
            NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
            if nx is not None:
                try:
                    if hasattr(nx, "read_gpickle"):
                        G = nx.read_gpickle("docs/graph/entity_graph.gpickle")
                        upload_graph_to_neo4j(G, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
                    else:
                        print("networkx.read_gpickle not available. Skipping Neo4j upload.")
                except Exception as e:
                    print(f"Neo4j upload skipped: {e}")
            ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
            ES_INDEX = os.getenv("ES_INDEX", "nefac-bm25")
            upload_chunks_to_elasticsearch(chunk_records, ES_HOST, ES_INDEX)
            logger.info(f"Completed ingestion and indexing for {abs_path if doc_type != 'youtube' else meta_path}")

# Add a main entry point for CLI usage
if __name__ == "__main__":
    process_all_metadata() 