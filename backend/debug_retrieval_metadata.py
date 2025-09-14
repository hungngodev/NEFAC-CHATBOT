#!/usr/bin/env python3
"""
Debug script to inspect metadata returned by retrieval components.

Usage:
  python backend/debug_retrieval_metadata.py --query "NEFAC amicus 2023" \
      --vector-k 5 --keyword-k 5 [--use-rerank]

This script avoids the planner LLM. It queries the vector and keyword
retrievers directly and prints out metadata keys to verify that fields
like `title`, `source_url`, etc. are present as expected from ingestion.
Optionally, it can run the ensemble + Cohere rerank path to check
metadata retention after compression.
"""
import argparse
import os
import sys
from typing import List

from langchain.retrievers import EnsembleRetriever
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_core.documents import Document


def _add_backend_to_path() -> None:
    # Ensure this backend folder is on sys.path for `src.*` imports
    backend_root = os.path.dirname(os.path.abspath(__file__))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)


def _print_docs(label: str, docs: List[Document], limit: int = 5) -> None:
    print(f"\n=== {label} (showing up to {limit}) ===")
    for i, d in enumerate(docs[:limit], start=1):
        meta = getattr(d, "metadata", {}) or {}
        keys = list(meta.keys())
        title = meta.get("title") or meta.get("source") or meta.get("filename")
        print(f"[{i}] title={title!r} keys={keys}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--vector-k", type=int, default=5)
    parser.add_argument("--keyword-k", type=int, default=5)
    parser.add_argument("--use-rerank", action="store_true", help="Try ensemble + Cohere rerank as in subgraph")
    args = parser.parse_args()

    _add_backend_to_path()

    # Lazy imports after sys.path tweak
    from src.core.agents.retrieval.keyword_retrieval import keyword_retriever
    from src.core.agents.retrieval.vector_retrieval import vector_retriever

    # Vector-only
    try:
        vdocs = vector_retriever.invoke(args.query, search_kwargs={"k": args.vector_k}) if args.vector_k > 0 else []
        _print_docs("Vector retriever", vdocs)
    except Exception as e:
        print(f"[WARN] Vector retrieval failed: {e}. Retrying with explicit retriever configured for k={args.vector_k}.")
        try:
            from src.core.agents.retrieval.vector_retrieval import vectorstore

            local_retriever = vectorstore.as_retriever(search_kwargs={"k": args.vector_k})
            vdocs = local_retriever.invoke(args.query) if args.vector_k > 0 else []
            _print_docs("Vector retriever (fallback)", vdocs)
        except Exception as e2:
            print(f"[WARN] Secondary vector retrieval attempt failed: {e2}")
            vdocs = []

    # Keyword-only
    try:
        kdocs = keyword_retriever.invoke(args.query, top_k=args.keyword_k) if args.keyword_k > 0 else []
        _print_docs("Keyword retriever", kdocs)
    except Exception as e:
        print(f"[WARN] Keyword retrieval failed: {e}")
        kdocs = []

    # Ensemble + optional rerank
    if args.use_rerank and (args.vector_k > 0 or args.keyword_k > 0):
        try:
            # Mirror the subgraph’s ensemble
            retrievers = []
            weights = []
            if args.keyword_k > 0:
                retrievers.append(keyword_retriever.bind(top_k=args.keyword_k))
                weights.append(0.5)
            if args.vector_k > 0:
                retrievers.append(vector_retriever.bind(k=args.vector_k))
                weights.append(0.5)
            ens = EnsembleRetriever(retrievers=retrievers, weights=weights or None)
            ensemble_docs = ens.invoke(args.query)
            _print_docs("Ensemble (pre-rerank)", ensemble_docs)

            try:
                from langchain_cohere import CohereRerank

                compressor = CohereRerank(model="rerank-english-v3.0")
                ccr = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=ens)
                reranked = ccr.invoke(args.query)
                _print_docs("Ensemble (post-rerank)", reranked)
            except Exception as e:
                print(f"[WARN] Rerank step failed or rate-limited: {e}")
        except Exception as e:
            print(f"[WARN] Ensemble step failed: {e}")


if __name__ == "__main__":
    main()
