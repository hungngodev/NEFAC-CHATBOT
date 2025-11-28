import sys
import argparse
import tiktoken
from pathlib import Path
from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
import concurrent.futures
import logging

def process_file(file_path):
    try:
        reader = SimpleDirectoryReader(input_files=[str(file_path)])
        docs = reader.load_data()
        return docs
    except Exception:
        return []

logging.getLogger("pypdf").setLevel(logging.ERROR)

backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.append(str(backend_path))

from src.service.ingestion_service import settings
PRICING = {
    "gpt-5.1": {"input": 0.625, "output": 5.00},
    "gpt-5": {"input": 0.625, "output": 5.00},
    "gpt-5-mini": {"input": 0.125, "output": 1.00},
    "gpt-5-nano": {"input": 0.025, "output": 0.20},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}

CACHED_INPUT_DISCOUNT = 0.5

SUPPORTED_EXTENSIONS = {
    "pdf": [".pdf"],
    "html": [".html", ".htm"],
    "text": [".txt", ".md", ".markdown"],
    "word": [".docx", ".doc"],
    "excel": [".xlsx", ".xls"],
    "all": [".pdf", ".html", ".htm", ".txt", ".md", ".markdown", ".docx", ".doc", ".xlsx", ".xls"]
}

def get_model_pricing(model_name):
    if hasattr(model_name, "model"):
        name = model_name.model
    else:
        name = str(model_name)
    return PRICING.get(name, {"input": 0.0, "output": 0.0}), name

def count_tokens(text, model="gpt-4"):
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def main():
    parser = argparse.ArgumentParser(description="Estimate ingestion costs.")
    parser.add_argument("--file", type=str, help="Path to a single file to estimate cost for.")
    args = parser.parse_args()

    print("📊 Estimating Ingestion Costs")
    
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            return
        print(f"📄 Single File: {file_path}")
        files = [file_path]
    else:
        documents_dir = Path(__file__).resolve().parent.parent / "resource" / "nefac_documents"
        print(f"📁 Directory: {documents_dir}")
        print(f"🔍 File Types: {SUPPORTED_EXTENSIONS['all']}")
        
        if not documents_dir.exists():
            print(f"❌ Directory not found: {documents_dir}")
            return

        files = []
        for ext in SUPPORTED_EXTENSIONS["all"]:
            files.extend(list(documents_dir.rglob(f"*{ext}")))
    
    print(f"--------------------------------------------------")
    print("Reading documents... (this may take a moment)")
    print(f"Found {len(files)} files. Processing...")
    
    documents = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = {executor.submit(process_file, f): f for f in files}
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            if (i + 1) % 10 == 0:
                print(f"Processing file {i + 1}/{len(files)}...", end="\r")
            documents.extend(future.result())
            
    print(f"\nFinished processing {len(files)} files.")

    if not documents:
        print("❌ No documents found matching the criteria.")
        return
    
    total_doc_text = "".join([d.text for d in documents])
    total_doc_tokens = count_tokens(total_doc_text)
    
    print(f"📄 Documents Found: {len(documents)}")
    print(f"🔤 Total Document Tokens: {total_doc_tokens:,}")
    print(f"--------------------------------------------------")

    chunk_size = settings.CHUNK_SIZE
    chunk_overlap = settings.CHUNK_OVERLAP
    
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    nodes = splitter.get_nodes_from_documents(documents)
    num_chunks = len(nodes)
    
    print(f"🧩 Chunk Size: {chunk_size}")
    print(f"🧩 Chunk Overlap: {chunk_overlap}")
    print(f"📦 Total Chunks Generated: {num_chunks:,}")
    print(f"--------------------------------------------------")

    total_chunk_tokens = sum([count_tokens(n.text) for n in nodes])
    graph_model_name = "gpt-5-mini"

    contextual_cost = 0
    metadata_cost = 0
    
    if settings.ENABLE_CONTEXTUAL_RETRIEVAL:
        avg_doc_tokens = total_doc_tokens / len(documents) if documents else 0
        
        avg_chunks_per_doc = num_chunks / len(documents) if documents else 1
        contextual_input_tokens = total_doc_tokens * avg_chunks_per_doc
        
        contextual_output_tokens = num_chunks * 150
        
        pricing = PRICING[graph_model_name]
        contextual_cost = ((contextual_input_tokens / 1_000_000) * pricing["input"]) + \
                          ((contextual_output_tokens / 1_000_000) * pricing["output"])
                          
        print(f"--------------------------------------------------")
        print(f"📑 Contextual Retrieval ({graph_model_name})")
        print(f"   • Input Tokens: {contextual_input_tokens:,.0f}")
        print(f"   • Est. Output Tokens: {contextual_output_tokens:,}")
        print(f"   💰 Subtotal: ${contextual_cost:.4f}")

    if settings.ENABLE_METADATA_EXTRACTION:
        metadata_input_tokens = total_chunk_tokens
        metadata_output_tokens = num_chunks * 100
        
        pricing = PRICING[graph_model_name]
        metadata_cost = ((metadata_input_tokens / 1_000_000) * pricing["input"]) + \
                        ((metadata_output_tokens / 1_000_000) * pricing["output"])

        print(f"--------------------------------------------------")
        print(f"🏷️  Metadata Extraction ({graph_model_name})")
        print(f"   • Input Tokens: {metadata_input_tokens:,}")
        print(f"   • Est. Output Tokens: {metadata_output_tokens:,}")
        print(f"   💰 Subtotal: ${metadata_cost:.4f}")

    system_prompt_tokens_per_chunk = 586
    total_system_prompt_tokens = system_prompt_tokens_per_chunk * num_chunks
    
    cached_system_tokens = total_system_prompt_tokens * 0.99
    uncached_system_tokens = total_system_prompt_tokens * 0.01
    
    uncached_user_tokens = total_chunk_tokens
    
    graph_pricing = PRICING[graph_model_name]
    
    graph_input_cost_uncached = ((uncached_system_tokens + uncached_user_tokens) / 1_000_000) * graph_pricing["input"]
    graph_input_cost_cached = (cached_system_tokens / 1_000_000) * (graph_pricing["input"] * CACHED_INPUT_DISCOUNT)
    graph_input_cost = graph_input_cost_uncached + graph_input_cost_cached
    
    estimated_triplets_per_chunk = 5
    estimated_output_tokens_per_chunk = estimated_triplets_per_chunk * 40
    estimated_output_tokens = num_chunks * estimated_output_tokens_per_chunk
    graph_output_cost = (estimated_output_tokens / 1_000_000) * graph_pricing["output"]
    
    total_graph_cost = graph_input_cost + graph_output_cost

    print(f"--------------------------------------------------")
    print(f"🕸️  Graph Extraction ({graph_model_name})")
    print(f"   • System Prompt Tokens: {total_system_prompt_tokens:,} ({int(cached_system_tokens):,} cached)")
    print(f"   • Chunk Text Tokens: {total_chunk_tokens:,} (uncached)")
    print(f"   • Est. Output Tokens: {estimated_output_tokens:,}")
    print(f"   • Input Cost: ${graph_input_cost:.4f} (Saved ${(cached_system_tokens/1_000_000 * graph_pricing['input'] * (1-CACHED_INPUT_DISCOUNT)):.4f} via caching)")
    print(f"   • Output Cost: ${graph_output_cost:.4f}")
    print(f"   💰 Graph Subtotal: ${total_graph_cost:.4f}")

    summary_model_name = "gpt-5-nano"
    summary_pricing = PRICING[summary_model_name]
    
    summary_input_tokens = total_doc_tokens
    summary_output_tokens = len(documents) * 300
    
    summary_input_cost = (summary_input_tokens / 1_000_000) * summary_pricing["input"]
    summary_output_cost = (summary_output_tokens / 1_000_000) * summary_pricing["output"]
    total_summary_cost = summary_input_cost + summary_output_cost
    
    print(f"--------------------------------------------------")
    print(f"📝 Summary Generation ({summary_model_name})")
    print(f"   • Input Tokens: {summary_input_tokens:,}")
    print(f"   • Est. Output Tokens: {summary_output_tokens:,}")
    print(f"   💰 Summary Subtotal: ${total_summary_cost:.4f}")

    embed_model_name = "text-embedding-3-small"
    embed_pricing = PRICING[embed_model_name]
    
    embed_cost = (total_chunk_tokens / 1_000_000) * embed_pricing["input"]
    
    print(f"--------------------------------------------------")
    print(f"🧠 Embedding ({embed_model_name})")
    print(f"   • Total Tokens: {total_chunk_tokens:,}")
    print(f"   💰 Embedding Subtotal: ${embed_cost:.4f}")

    grand_total = total_graph_cost + total_summary_cost + embed_cost + contextual_cost + metadata_cost
    print(f"==================================================")
    print(f"💸 ESTIMATED TOTAL COST: ${grand_total:.4f}")
    print(f"==================================================")
    
    if graph_model_name == "gpt-5-mini":
        print("\n💡 Cost Saving Opportunity:")
        mini_pricing = PRICING["gpt-4o-mini"]
        mini_input_uncached = ((uncached_system_tokens + uncached_user_tokens) / 1_000_000) * mini_pricing["input"]
        mini_input_cached = (cached_system_tokens / 1_000_000) * (mini_pricing["input"] * CACHED_INPUT_DISCOUNT)
        mini_output = (estimated_output_tokens / 1_000_000) * mini_pricing["output"]
        
        mini_contextual = 0
        if settings.ENABLE_CONTEXTUAL_RETRIEVAL:
             mini_contextual = ((contextual_input_tokens / 1_000_000) * mini_pricing["input"]) + \
                               ((contextual_output_tokens / 1_000_000) * mini_pricing["output"])
        
        mini_metadata = 0
        if settings.ENABLE_METADATA_EXTRACTION:
            mini_metadata = ((metadata_input_tokens / 1_000_000) * mini_pricing["input"]) + \
                            ((metadata_output_tokens / 1_000_000) * mini_pricing["output"])

        mini_total = mini_input_uncached + mini_input_cached + mini_output + embed_cost + total_summary_cost + mini_contextual + mini_metadata
        print(f"   If you switch to 'gpt-4o-mini': ${mini_total:.4f} (Save ${(grand_total - mini_total):.4f})")

if __name__ == "__main__":
    main()
