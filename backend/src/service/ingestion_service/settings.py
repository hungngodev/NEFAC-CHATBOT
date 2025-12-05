import logging
import os

from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI

from src.config.models import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL_NAME
from src.utils.env import load_env as load_env_from_root

load_env_from_root()
logger = logging.getLogger(__name__)

DEFAULT_MODEL_PROVIDER = "openai"
ENABLE_CONTEXTUAL_RETRIEVAL = True
ENABLE_METADATA_EXTRACTION = True
GRAPH_MODE = "property"
CHUNK_SIZE = 384
CHUNK_OVERLAP = 38

GRAPH_RATE_LIMIT_BACKOFF = 3.0
GRAPH_RATE_LIMIT_RETRIES = 4
GRAPH_MAX_TRIPLETS_PER_CHUNK = 4
GRAPH_NUM_WORKERS = 1
GRAPH_ENABLE_ENTITY_DEDUPLICATION = True
GRAPH_ENTITY_SIMILARITY_THRESHOLD = 0.9
GRAPH_USE_WORD_DISTANCE = True
GRAPH_WORD_DISTANCE_THRESHOLD = 2

CONTEXT_FORMAT = "Context: {context}\n\nChunk: {chunk}"
WORKFLOW_ENABLE_VALIDATION = True

SEMANTIC_SPLITTER_AUTO_DOWNLOAD = True


SEMANTIC_SPLITTER_LANGUAGE = "en"
SEMANTIC_SPLITTER_SPACY_MODEL = "en_core_web_lg"
SEMANTIC_SPLITTER_INITIAL_THRESHOLD = 0.5
SEMANTIC_SPLITTER_APPEND_THRESHOLD = 0.6
SEMANTIC_SPLITTER_MERGE_THRESHOLD = 0.6
SEMANTIC_SPLITTER_MAX_CHUNK = 384

SERVICE_TIER = "flex"

Settings.llm = OpenAI(
    model="gpt-5-nano",
    max_retries=30,
    timeout=900.0,
    additional_kwargs={"service_tier": SERVICE_TIER},
    api_key=os.getenv("OPENAI_API_KEY"),
)
graph_llm_model = OpenAI(
    model="gpt-5-nano",
    max_retries=30,
    timeout=900.0,
    additional_kwargs={"service_tier": SERVICE_TIER},
    api_key=os.getenv("OPENAI_API_KEY"),
)


Settings.embed_model = OpenAIEmbedding(
    model=EMBEDDING_MODEL_NAME,
    dimensions=EMBEDDING_DIMENSIONS,
)


ENTITY_ALIASES = {
    "NEFAC": [
        "NEFAC",
        "New England First Amendment Coalition",
        "N.E.F.A.C.",
        "Nefac",
        "Kneefac",
        "Knee Fac",
        "NEFEC",
        "NEFA Coalition",
        "First Amendment Coalition of New England",
        "The Coalition",
        "The New England Coalition",
    ],
    "NEFAI": [
        "NEFAI",
        "New England First Amendment Institute",
        "First Amendment Institute",
        "Negri Institute",
        "Gloria L. Negri First Amendment Institute",
    ],
    "MNPA": [
        "MNPA",
        "Massachusetts Newspaper Publishers Association",
        "Massachusetts Newspaper Assoc.",
        "Mass Newspaper Publishers",
    ],
    "NENPA": [
        "NENPA",
        "New England Newspaper & Press Association",
        "New England Newspaper Association",
        "New England Press Association",
    ],
    "ACLU": [
        "ACLU",
        "American Civil Liberties Union",
        "ACLU of Massachusetts",
        "ACLU of NH",
        "ACLU of CT",
        "ACLU Massachusetts",
    ],
    "RCFP": [
        "RCFP",
        "Reporters Committee for Freedom of the Press",
        "Reporters Committee",
    ],
    "SPJ": [
        "SPJ",
        "Society of Professional Journalists",
        "SPJ New England",
        "SPJ Foundation",
    ],
    "GLAD": [
        "GLAD",
        "GLBTQ Legal Advocates & Defenders",
        "Gay and Lesbian Advocates and Defenders",
    ],
    "APRA": ["APRA", "Access to Public Records Act", "Rhode Island APRA", "RI APRA"],
    "FOI": ["FOI", "Freedom of Information", "Public Records Law", "Right to Know"],
    "FOIA": ["FOIA", "Freedom of Information Act", "Federal FOIA"],
    "SLAPP": [
        "SLAPP",
        "Strategic Lawsuit Against Public Participation",
        "anti-SLAPP",
        "SLAPP suit",
        "SLAPP law",
        "Anti-SLAPP law",
    ],
    "Sunshine Week": [
        "Sunshine Week",
        "Sunshine Week initiative",
        "National Sunshine Week",
    ],
    "WBUR": ["WBUR", "WBUR-FM"],
    "WCVB": ["WCVB", "WCVB-TV"],
    "GBH": ["GBH", "WGBH", "GBH News"],
    "CT Mirror": ["CT Mirror", "Connecticut Mirror"],
    "VT Digger": ["VT Digger", "VTDigger", "VTDigger.org"],
    "Union Leader": ["Union Leader", "New Hampshire Union Leader"],
    "Nackey S. Loeb School": ["Nackey S. Loeb School", "Loeb School"],
}

CANONICAL_ENTITY_LOOKUP = {}
for canon, aliases in ENTITY_ALIASES.items():
    for alias in aliases:
        CANONICAL_ENTITY_LOOKUP[alias.lower()] = canon

ALLOWED_NODES = [
    "Person",
    "Organization",
    "Program",
    "Event",
    "Document",
    "MediaAsset",
    "LegalCase",
    "LawOrPolicy",
    "Location",
    "WebPage",
    "Dataset",
    "FundingSource",
    "Board",
    "Committee",
    "SocialProfile",
    "Topic",
    "Concept",
    "Statute",
    "LegislativeBill",
    "Court",
    "Judge",
]

ALLOWED_RELATIONSHIPS = [
    "WORKS_FOR",
    "SERVES_ON",
    "PARTNERS_WITH",
    "HOSTED_BY",
    "TAKES_PLACE_IN",
    "LOCATED_IN",
    "AUTHORED_BY",
    "WRITES",
    "PUBLISHES",
    "FILES",
    "DECIDED_BY",
    "CITES",
    "REFERENCES",
    "CHALLENGES",
    "FUNDS",
    "ANNOUNCES",
    "HAS_PAGE",
    "HAS_SECTION",
    "LINKS_TO",
    "HAS_PROFILE",
    "CONCERNS",
    "REGULATES",
    "ENFORCES",
    "OPPOSES",
    "OPPOSES",
    "SUPPORTS",
]

EXCLUDED_METADATA_KEYS = [
    "file_path",
    "file_size",
    "processing_timestamp",
    "mime_type",
    "chunk_index",
    "total_chunks",
    "chunk_size",
    "chunk_word_count",
    "start_char",
    "end_char",
    "id",
    "filename",
    "source_url",
    "link",
    "uri",
    "slug",
    "modified",
    "transcript_type",
    "has_timestamps",
    "start_time",
    "end_time",
    "duration",
    "sheet_index",
    "total_sheets",
    "description",
    "summary",
    "abstract",
]
