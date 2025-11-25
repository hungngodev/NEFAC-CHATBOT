"""Startup diagnostics for the LlamaIndex ingestion stack."""

from __future__ import annotations

import importlib.util
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

_TRUTHY = {"1", "true", "yes", "on"}


def _enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in _TRUTHY


def _has_module(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


@dataclass
class DependencyStatus:
    name: str
    present: bool
    required: bool
    reason: str
    install_hint: str


def _dependency_matrix() -> List[DependencyStatus]:
    return [
        DependencyStatus(
            name="llama_index",
            present=_has_module("llama_index"),
            required=True,
            reason="Core ingestion pipeline",
            install_hint="pip install llama-index",
        ),
        DependencyStatus(
            name="spacy",
            present=_has_module("spacy"),
            required=True,
            reason="Semantic splitter",
            install_hint="pip install spacy",
        ),
        DependencyStatus(
            name="pandas",
            present=_has_module("pandas"),
            required=True,
            reason="Spreadsheet ingestion",
            install_hint="pip install pandas",
        ),
        DependencyStatus(
            name="youtube_transcript_api",
            present=_has_module("youtube_transcript_api"),
            required=_enabled("ENABLE_YOUTUBE_TRANSCRIPTS", False),
            reason="YouTube transcript ingestion",
            install_hint="pip install youtube-transcript-api",
        ),
        DependencyStatus(
            name="docx",
            present=_has_module("docx"),
            required=False,
            reason="DOCX ingestion",
            install_hint="pip install python-docx",
        ),
        DependencyStatus(
            name="pptx",
            present=_has_module("pptx"),
            required=False,
            reason="PPTX ingestion",
            install_hint="pip install python-pptx",
        ),
        DependencyStatus(
            name="qdrant_client",
            present=_has_module("qdrant_client"),
            required=_enabled("QDRANT_ENABLE", True),
            reason="Qdrant indexing",
            install_hint="pip install qdrant-client",
        ),
        DependencyStatus(
            name="elasticsearch",
            present=_has_module("elasticsearch"),
            required=_enabled("ES_LI_ENABLE", False),
            reason="Elasticsearch indexing",
            install_hint="pip install elasticsearch",
        ),
        DependencyStatus(
            name="neo4j",
            present=_has_module("neo4j"),
            required=_enabled("GRAPH_LI_ENABLE", False),
            reason="Neo4j ingestion",
            install_hint="pip install neo4j",
        ),
    ]


_ENV_REQUIREMENTS: Dict[str, Tuple[Tuple[str, ...], ...]] = {
    "Qdrant": (("QDRANT_ENDPOINT",), ("QDRANT_CLUSTER_ID",)),
    "Elasticsearch": (("ES_HOST",), ("ES_INDEX",)),
    "Neo4j": (("NEO4J_URI",), ("NEO4J_USER", "NEO4J_USERNAME"), ("NEO4J_PASSWORD",)),
}


def check_dependencies() -> List[DependencyStatus]:
    return _dependency_matrix()


def check_environment() -> Dict[str, List[str]]:
    missing: Dict[str, List[str]] = {}
    for service, key_groups in _ENV_REQUIREMENTS.items():
        required = False
        if service == "Qdrant":
            required = _enabled("QDRANT_ENABLE", True)
        elif service == "Elasticsearch":
            required = _enabled("ES_LI_ENABLE", False)
        elif service == "Neo4j":
            required = _enabled("GRAPH_LI_ENABLE", False)

        if not required:
            continue

        missing_keys: List[str] = []
        for group in key_groups:
            if not any(os.getenv(option) for option in group):
                missing_keys.append(" / ".join(group))
        if missing_keys:
            missing[service] = missing_keys

    return missing


_DIAGNOSTICS_CACHE: Dict[str, bool] = {}


def ensure_llamaindex_ready(raise_on_missing: bool | None = None) -> None:
    if _DIAGNOSTICS_CACHE.get("ready"):
        return

    dependency_results = check_dependencies()
    missing_required = [d for d in dependency_results if d.required and not d.present]

    env_missing = check_environment()

    if not dependency_results:
        logger.info("No dependency diagnostics available")

    for status in dependency_results:
        if status.present:
            continue
        level = logging.WARNING
        if status.required:
            level = logging.ERROR
        logger.log(
            level,
            "Dependency '%s' missing (%s). Install via: %s",
            status.name,
            status.reason,
            status.install_hint,
        )

    for service, keys in env_missing.items():
        logger.error(
            "%s configuration incomplete. Missing: %s",
            service,
            ", ".join(keys),
        )

    should_raise = raise_on_missing
    if should_raise is None:
        should_raise = _enabled("INGESTION_FAIL_ON_MISSING", False)

    if should_raise and (missing_required or env_missing):
        raise RuntimeError("Ingestion prerequisites missing; see logs for details")

    if not missing_required and not env_missing:
        _DIAGNOSTICS_CACHE["ready"] = True


def diagnostics_summary() -> Dict[str, object]:
    deps = check_dependencies()
    envs = check_environment()
    return {
        "dependencies": [status.__dict__ for status in deps],
        "environment": envs,
    }


if __name__ == "__main__":
    summary = diagnostics_summary()
    for dep in summary["dependencies"]:
        state = "ok" if dep["present"] else "missing"
        tag = "required" if dep["required"] else "optional"
        print(f"{dep['name']}: {state} ({tag}) - {dep['reason']}")
        if not dep["present"]:
            print(f"  install: {dep['install_hint']}")

    if summary["environment"]:
        print("\nEnvironment issues:")
        for service, keys in summary["environment"].items():
            print(f"- {service}: missing {', '.join(keys)}")
    else:
        print("\nEnvironment looks good.")
