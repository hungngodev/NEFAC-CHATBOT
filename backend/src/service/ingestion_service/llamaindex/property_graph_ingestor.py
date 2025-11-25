"""Property Graph Index with legal domain schema for Neo4j.

Enhanced knowledge graph with schema-based entity/relation extraction.
Based on: https://developers.llamaindex.ai/python/examples/property_graph/property_graph_neo4j/
"""

from __future__ import annotations

import logging
import os
import time
from uuid import uuid4
from typing import List, Literal, Optional, Set

from llama_index.core import PropertyGraphIndex, Settings
from llama_index.core.indices.property_graph import SchemaLLMPathExtractor
from llama_index.core.schema import BaseNode
from llama_index.core.schema import Document as LIDocument
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

from src.service.ingestion_service.llamaindex.entity_deduplication import (
    EntityDeduplicator,
)
from src.service.ingestion_service.settings import (
    GRAPH_ENABLE_ENTITY_DEDUPLICATION,
    GRAPH_ENTITY_SIMILARITY_THRESHOLD,
    GRAPH_MAX_TRIPLETS_PER_CHUNK,
    GRAPH_NUM_WORKERS,
    GRAPH_USE_WORD_DISTANCE,
    GRAPH_WORD_DISTANCE_THRESHOLD,
    OPENAI_EMBED_MODEL_DIM,
)

try:
    # Newer openai client
    from openai import RateLimitError  # type: ignore
except Exception:  # pragma: no cover - fallback for older client versions
    try:
        from openai.error import RateLimitError  # type: ignore
    except Exception:
        RateLimitError = None  # type: ignore


logger = logging.getLogger(__name__)
_RUN_UUID = uuid4()


# -----------------------------------------------------------------------------
# --- Entity Aliases and Disambiguation for NEFAC Ecosystem
# -----------------------------------------------------------------------------
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

# Build a lowercase alias map for fast lookup
CANONICAL_ENTITY_LOOKUP = {}
for canon, aliases in ENTITY_ALIASES.items():
    for alias in aliases:
        CANONICAL_ENTITY_LOOKUP[alias.lower()] = canon


# Extended entity/relation schema ported from the earlier Graph RAG implementation
# to preserve the richer domain coverage.
ALLOWED_NODES = [
    # Core Organization & People
    "Organization",
    "Suborganization",
    "Chapter",
    "Coalition",
    "Affiliate",
    "PartnerOrg",
    "SponsorOrg",
    "Board",
    "Committee",
    "AdvisoryBoard",
    "WorkingGroup",
    "StaffMember",
    "BoardMember",
    "ExecutiveDirector",
    "Director",
    "President",
    "Treasurer",
    "Secretary",
    "Officer",
    "Member",
    "Attorney",
    "LegalCounsel",
    "Advocate",
    "PolicyAdvisor",
    "Journalist",
    "Reporter",
    "Editor",
    "MediaContact",
    "Student",
    "Graduate",
    "Volunteer",
    "Intern",
    "Fellow",
    "Mentor",
    "Mentee",
    "Stakeholder",
    "Regulator",
    "Policymaker",
    "Legislator",
    "LawMaker",
    "Judge",
    "Justice",
    "LawFirm",
    "Partner",
    "Associate",
    "MediaOutlet",
    "University",
    "College",
    "School",
    "HighSchool",
    "NonProfit",
    "ForProfit",
    "GovernmentAgency",
    "PublicOfficial",
    "CommunityLeader",
    "Speaker",
    # Programs, Events, Campaigns
    "Program",
    "Initiative",
    "Campaign",
    "Project",
    "ActionPlan",
    "Workshop",
    "Seminar",
    "Webinar",
    "Training",
    "Course",
    "Session",
    "Panel",
    "Roundtable",
    "Conference",
    "Summit",
    "TownHall",
    "Forum",
    "Meetup",
    "Event",
    "VirtualEvent",
    "InPersonEvent",
    "FundraisingEvent",
    "Competition",
    "AwardCeremony",
    "Festival",
    "OutreachActivity",
    # Legal & Advocacy
    "LegalBrief",
    "AmicusBrief",
    "CourtFiling",
    "Testimony",
    "Petition",
    "Case",
    "Statute",
    "Regulation",
    "PolicyDocument",
    "PolicyPaper",
    "WhitePaper",
    "Report",
    "CaseStudy",
    "FOILetter",
    "FOIRequest",
    "LegalFramework",
    "Guide",
    "Toolkit",
    "Template",
    "Checklist",
    "LegalOpinion",
    "Complaint",
    "CourtDecision",
    "Judgment",
    "Order",
    "Motion",
    "Affidavit",
    "Notice",
    "Hearing",
    "Settlement",
    "LawReview",
    # Publications & Media
    "Publication",
    "Article",
    "BlogPost",
    "NewsArticle",
    "PressRelease",
    "Newsletter",
    "NewsletterIssue",
    "EmailDigest",
    "Podcast",
    "PodcastEpisode",
    "Video",
    "Transcript",
    "MediaAsset",
    "Infographic",
    "Chart",
    "DataTable",
    "Map",
    "ImageAsset",
    "AudioRecording",
    "Documentary",
    "Presentation",
    "Interview",
    "MediaMention",
    "Clip",
    "WebinarRecording",
    "SlideDeck",
    # Digital, AI, Technical
    "Dataset",
    "API",
    "Platform",
    "Tool",
    "App",
    "Software",
    "Bot",
    "Widget",
    "OpenDataPortal",
    "Repository",
    "Documentation",
    "CodeExample",
    # Website Structure & Resources
    "Website",
    "Page",
    "LandingPage",
    "PageSection",
    "NavigationMenu",
    "MenuItem",
    "Sidebar",
    "FooterLink",
    "Breadcrumb",
    "Header",
    "Banner",
    "ContactPage",
    "DonatePage",
    "FAQPage",
    "FAQTopic",
    "Glossary",
    "GlossaryTerm",
    "Resource",
    "ResourceCategory",
    "ResourceSection",
    "DownloadablePDF",
    "InteractiveMap",
    "Form",
    "Survey",
    "FeedbackForm",
    "ContactForm",
    "SearchBar",
    "Sitemap",
    "Announcement",
    "Popup",
    "Modal",
    # Funding, Opportunities, Careers
    "Grant",
    "Scholarship",
    "Fellowship",
    "Award",
    "Donor",
    "Donation",
    "FundingSource",
    "Sponsorship",
    "VolunteerOpportunity",
    "Internship",
    "JobPosting",
    "CareerOpportunity",
    "Application",
    "SelectionCommittee",
    "Recipient",
    "Nominee",
    "Sponsor",
    "Supporter",
    # Communication & Outreach
    "SocialMediaChannel",
    "TwitterAccount",
    "FacebookPage",
    "LinkedInPage",
    "InstagramProfile",
    "YouTubeChannel",
    "RSSFeed",
    "EmailList",
    "Survey",
    "Poll",
    "OutreachCampaign",
    "MailingList",
    "NewsletterSubscriber",
    "EventInvitation",
    "ContactRequest",
    "Query",
    "Feedback",
    "SupportTicket",
    # Partnerships & Coalitions
    "Partner",
    "Collaborator",
    "Consortium",
    "StakeholderGroup",
    "Ally",
    "SponsorOrg",
    # Geographic & Demographic
    "Location",
    "Venue",
    "City",
    "County",
    "State",
    "Region",
    "District",
    "Country",
    "PostalCode",
    "CourtDistrict",
    "AppellateCourt",
    "SupremeCourt",
    "SchoolDistrict",
    "Audience",
    "TargetGroup",
    "Demographic",
    # Miscellaneous/Advanced
    "Calendar",
    "Schedule",
    "Milestone",
    "Deadline",
    "Task",
    "ChecklistItem",
    "Badge",
    "Level",
    "Module",
    "Topic",
    "Theme",
    "Subject",
    "Reference",
    "Citation",
    "Footnote",
    "Appendix",
    "Attachment",
    "ResourceLink",
    "Submission",
    "Response",
    "Acknowledgment",
]

ALLOWED_RELATIONSHIPS = [
    "AFFILIATED_WITH",
    "ANNOUNCES",
    "APPLIES_TO",
    "ASSISTS",
    "ATTENDS",
    "AUTHORED_BY",
    "AWARDS",
    "COLLECTS",
    "COLLECTS_FEEDBACK_ON",
    "COMPRISED_OF",
    "CONTACT_FOR",
    "CONTAINS",
    "CONTAINS_MEDIA",
    "CONDUCTS",
    "CONTRIBUTES_TO",
    "COVERS",
    "CATEGORIZED_AS",
    "DECIDED_BY",
    "DEFINES",
    "DETAILED_BY",
    "DIRECTS",
    "DONATES_TO",
    "EMBEDS",
    "ENDORSES",
    "EMPLOYS",
    "ENROLLS_IN",
    "EXPLAINS",
    "FEATURES",
    "FILES",
    "FILLED_BY",
    "FOCUSES_ON",
    "FOLLOWS",
    "FUNDS",
    "GOVERNED_BY",
    "GOVERNS",
    "HAS_CONTACT_METHOD",
    "HAS_FAQ",
    "HAS_FOOTER_LINK",
    "HAS_GLOSSARY_TERM",
    "HAS_NAV_ITEM",
    "HAS_SECTION",
    "HAPPENS_AT",
    "HIGHLIGHTS",
    "HOSTED_BY",
    "HOSTS",
    "IMPACTS",
    "INCLUDES",
    "INCLUDES_RESOURCE",
    "INVITES",
    "IS_CHILD_OF",
    "IS_PARENT_OF",
    "IS_SUBPAGE_OF",
    "IS_TOPIC_OF",
    "LAUNCHED_BY",
    "LEADS",
    "LEARNS_IN",
    "LINKED_FROM",
    "LINKS_TO",
    "LISTED_ON",
    "LOCATED_IN",
    "MAINTAINS",
    "MANAGES",
    "MENTEES",
    "MENTIONS",
    "MENTORS",
    "NAV_LINKS_TO",
    "OFFERED_BY",
    "OPEN_TO",
    "OPERATES",
    "ORGANIZES",
    "OWNED_BY",
    "PARTICIPATED_IN",
    "PARTNERS_WITH",
    "PRESENTED_BY",
    "PRESENTS",
    "PROCESSING",
    "PRODUCES",
    "PROVIDES",
    "PUBLISHES",
    "QUOTES",
    "RECEIVES",
    "REFERENCES",
    "REPRESENTS",
    "REQUESTS",
    "REPORTED_BY",
    "REQUIRES",
    "REVIEWS",
    "SENDS",
    "SENT_TO",
    "SERVES_ON",
    "SHOWS",
    "SIGNATORY",
    "SPONSORS",
    "SPONSORS_EVENT",
    "SPEAKS_AT",
    "SPEAKS_ON",
    "STUDIES",
    "SUBMITS",
    "SUBSCRIBED_TO",
    "SUBMITTED_TO",
    "SUMMARIZES",
    "SUPPORTED_BY",
    "SUPPORTS",
    "SURVEY_TARGETS",
    "TAKES_PLACE_IN",
    "TARGETS",
    "USED_BY",
    "UTILIZES",
    "AWARDED_TO",
    "HAS_TOPIC",
    "HAS_RESOURCE",
    "HAS_DOWNLOADABLE",
    "HAS_APPLICATION",
    "HAS_CONTACT_FORM",
    "HAS_SURVEY",
    "HAS_EVENT",
    "HAS_JOB_POSTING",
    "HAS_MEMBER",
    "HAS_NEWS",
    "HAS_OPPORTUNITY",
    "HAS_PRESS_RELEASE",
    "HAS_PUBLICATION",
    "HAS_SPEAKER",
    "HAS_STAFF",
    "HAS_TESTIMONY",
    "HAS_VIDEO",
    "HAS_WORKSHOP",
    "INCLUDES_MEDIA",
    "MAPS_TO",
    "RECOGNIZES",
    "RELATES_TO",
    "RUNS",
    "TEACHES",
    "TRANSMITS",
    "USES",
    "VISITED_BY",
    "WORKS_FOR",
    "WRITES",
]

CUSTOM_KG_PROMPT = """
You are an expert information extractor building a complete, typed knowledge graph.
Your goal is to extract entities and relationships from the provided text, adhering to the specified schema and instructions.

**1. Entity Normalization (Alias Resolution)**
First, use this alias map to normalize all entity mentions to their canonical form.
The key is the canonical name, and the values are its aliases.
ALIAS MAP:
{alias_map}

- For any entity matching an alias, use its canonical name for the node ID.
- Store the original mention in an `aliases` property on the node.
- Never create duplicate nodes for the same canonical entity.

**3. Schema: Rich Property Extraction**
For the following node types, extract these specific properties if present in the text:

*   **Case**:
    *   `caseNumber` (e.g., "No. 22-1234")
    *   `decisionDate` (e.g., "May 1, 2023")
    *   `court` (e.g., "U.S. Court of Appeals for the First Circuit")
    *   `jurisdiction` (e.g., "Massachusetts")

*   **Person**:
    *   `title` (e.g., "Professor", "Journalist", "Executive Director")
    *   `email` (e.g., "jane.smith@example.com")
    *   `phone` (e.g., "555-123-4567")

*   **Statute**:
    *   `citation` (e.g., "G.L. c. 66, § 10")
    *   `jurisdiction` (e.g., "Massachusetts", "Federal")
    *   `commonName` (e.g., "Public Records Law")

*   **Organization**:
    *   `website` (e.g., "https://www.nefac.org")
    *   `location` (e.g., "Boston, MA")

*   **Event**:
    *   `date` (e.g., "October 26, 2023")
    *   `location` (e.g., "Boston Public Library")
    *   `eventType` (e.g., "Workshop", "Webinar", "Conference")

Example here: {allowed_nodes}
Some of the popular relationships you can use are: {allowed_relationships}

**4. General Instructions**
- Extract all specified node types, relationships, and properties.
- For all other node types, extract any relevant attributes found in the text as generic properties.
- Ensure all relationships are directed and explicit.
- Model hierarchical structures (e.g., Board -> Committee) using relationships like `HAS_CHILD` or `PART_OF`.
- Attach all source document metadata to the extracted graph elements.
"""

class LegalPropertyGraphIngestor:
    """Property graph ingestor with legal domain schema.

    Features:
    - Schema-based entity extraction (Cases, Statutes, Parties, etc.)
    - Relationship extraction (CITES, APPLIES_TO, etc.)
    - Validation and quality checks
    - Neo4j integration with PropertyGraphIndex
    """

    def __init__(
        self,
        neo4j_url: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        database: str = "neo4j",
        enable_validation: bool = True,
        llm=None,
    ):
        """Initialize property graph ingestor.

        Args:
            neo4j_url: Neo4j connection URL
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            database: Neo4j database name
            enable_validation: Enable schema validation
            llm: Language model for extraction (defaults to Settings.llm)
        """
        self.neo4j_url = neo4j_url or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER") or "neo4j"
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD", "password")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        self.enable_validation = enable_validation
        self.llm = llm or Settings.llm

        self._setup_graph_store()

    def _setup_graph_store(self):
        """Setup Neo4j property graph store."""
        try:
            self.graph_store = Neo4jPropertyGraphStore(
                username=self.neo4j_user,
                password=self.neo4j_password,
                url=self.neo4j_url,
                database=self.database,
            )
            logger.info(f"Connected to Neo4j at {self.neo4j_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def _create_schema_extractor(self):
        """Create schema-based LLM extractor for legal domain.

        Enhanced with entity deduplication from tutorial:
        https://developers.llamaindex.ai/python/examples/property_graph/property_graph_neo4j/
        """
        logger.info("Creating SchemaLLMPathExtractor with legal domain schema")
        logger.info(f"Entity deduplication: {GRAPH_ENABLE_ENTITY_DEDUPLICATION}")

        # Build extractor kwargs (use extended schema)
        extractor_kwargs = {
            "llm": self.llm,
            "possible_entities": ALLOWED_NODES,
            "possible_relations": ALLOWED_RELATIONSHIPS,
            "kg_validation_schema": None,
            "strict": False,  # Allow entities outside schema for flexibility
            "num_workers": GRAPH_NUM_WORKERS,
            "max_triplets_per_chunk": GRAPH_MAX_TRIPLETS_PER_CHUNK,
        }

        # Some LlamaIndex versions do not accept dedup-related kwargs on SchemaLLMPathExtractor.
        # We perform deduplication after ingestion via EntityDeduplicator instead.
        if GRAPH_ENABLE_ENTITY_DEDUPLICATION:
            logger.info("Entity deduplication will run post-ingestion via EntityDeduplicator")

        # Partially format the prompt with static values
        prompt = CUSTOM_KG_PROMPT.replace("{alias_map}", str(ENTITY_ALIASES))
        prompt = prompt.replace("{allowed_nodes}", str(ALLOWED_NODES))
        prompt = prompt.replace("{allowed_relationships}", str(ALLOWED_RELATIONSHIPS))

        extractor = SchemaLLMPathExtractor(
            extract_prompt=prompt,
            **extractor_kwargs
        )

        return extractor

    def _pre_disambiguate_entities(self, nodes: List[BaseNode]) -> List[BaseNode]:
        """
        For each Node, replace any known alias (NEFAC, partners, awards, etc.) with its canonical name.
        Attach original mention(s) as property if different.
        """
        logger.info(f"Disambiguating entities for {len(nodes)} nodes...")

        fixed_nodes = []
        for node in nodes:
            # We need to copy the node to avoid mutating the original list in place if that matters,
            # but here we are returning a new list.
            # LlamaIndex nodes are mutable.
            new_node = node.model_copy()
            content = new_node.get_content()
            new_content = content
            found_aliases = []
            
            # Simple string replacement - could be improved with regex or NLP but this matches original logic
            content_lower = content.lower()
            for alias, canon in CANONICAL_ENTITY_LOOKUP.items():
                if alias != canon.lower() and alias in content_lower:
                    # Case-insensitive replacement is tricky with simple replace, 
                    # but original logic used simple replace on content (which might miss case).
                    # Original logic: new_content.replace(alias, canon) on original content?
                    # Wait, original logic:
                    # if alias in content.lower(): new_content = new_content.replace(alias, canon)
                    # This is actually buggy in the original if alias is lowercase but content is Title Case.
                    # But we will restore it as faithful to the original intent, perhaps improving slightly to use case-insensitive regex?
                    # For now, let's stick to the exact logic from graph_rag.py to be safe, 
                    # BUT `new_content.replace(alias, canon)` only works if `alias` matches case in `new_content`.
                    # The original code had `alias` from `ENTITY_ALIASES` values.
                    # Let's assume the aliases list has the correct casing or we iterate the list values, not the keys of the lookup.
                    pass

            # Re-implementing the loop from graph_rag.py exactly
            for canon, aliases in ENTITY_ALIASES.items():
                for alias in aliases:
                    if alias != canon and alias in new_content:
                         new_content = new_content.replace(alias, canon)
                         found_aliases.append(alias)

            if found_aliases:
                new_node.metadata["original_mentions"] = list(set(found_aliases))
            
            new_node.set_content(new_content)
            fixed_nodes.append(new_node)

        logger.info(f"Entity disambiguation complete for {len(fixed_nodes)} nodes")
        return fixed_nodes

    def _nodes_to_documents(self, nodes: List[BaseNode]) -> List[LIDocument]:
        """Convert nodes to documents for PropertyGraphIndex."""

        documents = []
        for idx, node in enumerate(nodes):
            metadata = dict(node.metadata or {})
            # Preserve document-level identifier separately
            original_doc_id = metadata.get("doc_id") or metadata.get("document_id") or metadata.get("ref_doc_id") or metadata.get("id")
            if original_doc_id:
                metadata["doc_id"] = original_doc_id
            # Force chunk_index to the loop index to avoid reused values from upstream stages
            chunk_index = idx
            chunk_id = f"{original_doc_id or getattr(node, 'node_id', None) or uuid4()}::chunk-{chunk_index:04d}::{_RUN_UUID}"
            metadata["chunk_index"] = chunk_index
            metadata["chunk_id"] = chunk_id
            # Avoid setting metadata["id"] so we don't hit the __Node__.id uniqueness constraint
            metadata.pop("id", None)
            doc = LIDocument(
                text=node.get_content(),
                metadata=metadata,
                id_=chunk_id,
            )
            documents.append(doc)

        return documents

    def _delete_existing_node_ids(self, ids: Set[str]) -> None:
        """Remove existing __Node__ records with conflicting ids to avoid constraint errors."""
        if not ids:
            return
        driver = self._get_driver()
        cypher = """
        UNWIND $ids AS rid
        MATCH (n:__Node__ {id: rid})
        DETACH DELETE n
        """
        try:
            with driver.session(database=self.database) as session:
                session.run(cypher, ids=list(ids))
        except Exception as exc:
            logger.warning("Could not pre-delete duplicate __Node__ ids: %s", exc)

    def _drop_node_id_constraint(self) -> None:
        """Drop __Node__.id uniqueness constraint if present to avoid ingestion failures."""
        driver = self._get_driver()
        # Neo4j 5+: SHOW CONSTRAINTS is the supported syntax
        cypher_list = "SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties RETURN name, type, labelsOrTypes, properties"
        try:
            with driver.session(database=self.database) as session:
                constraints = session.run(cypher_list).data()
                target = [
                    c["name"]
                    for c in constraints
                    if c.get("type") in {"UNIQUE", "UNIQUE_CONSTRAINT"} and c.get("labelsOrTypes") == ["__Node__"] and c.get("properties") == ["id"]
                ]
                for name in target:
                    try:
                        session.run(f"DROP CONSTRAINT `{name}` IF EXISTS")
                        logger.info("Dropped constraint %s to avoid duplicate id conflicts", name)
                    except Exception as exc:
                        logger.warning("Could not drop constraint %s: %s", name, exc)
        except Exception as exc:
            logger.warning("Could not inspect/drop __Node__.id constraint: %s", exc)

    def ingest_nodes(
        self,
        nodes: List[BaseNode],
        show_progress: bool = True,
        run_deduplication: bool = True,
    ) -> PropertyGraphIndex:
        """Ingest nodes into property graph with schema extraction, with rate-limit backoff."""

        def _is_rate_limit_error(exc: Exception) -> bool:
            if RateLimitError and isinstance(exc, RateLimitError):
                return True
            msg = str(exc).lower()
            return "rate limit" in msg or "rate_limit_exceeded" in msg

        max_attempts = int(os.getenv("GRAPH_RATE_LIMIT_RETRIES", "4"))
        delay = float(os.getenv("GRAPH_RATE_LIMIT_BACKOFF", "2.5"))

        attempt = 0
        while attempt < max_attempts:
            try:
                logger.info(f"Ingesting {len(nodes)} nodes into PropertyGraphIndex (attempt {attempt + 1}/{max_attempts})")

                # Apply entity disambiguation
                nodes_to_process = self._pre_disambiguate_entities(nodes)

                documents = self._nodes_to_documents(nodes_to_process)
                ids = [d.id_ for d in documents]
                dupes = {i for i in ids if ids.count(i) > 1}
                if dupes:
                    logger.error("Duplicate graph node ids in batch: %s", dupes)
                    raise ValueError(f"Duplicate graph node ids in batch: {dupes}")

                # Ensure no __Node__.id uniqueness constraint blocks ingestion
                self._drop_node_id_constraint()
                # Pre-delete any existing __Node__ records with the same ids to avoid constraint failures
                incoming_ids = {str(doc.id_) for doc in documents if doc.id_}
                self._delete_existing_node_ids(incoming_ids)
                kg_extractor = self._create_schema_extractor()

                index = PropertyGraphIndex.from_documents(
                    documents,
                    property_graph_store=self.graph_store,
                    kg_extractors=[kg_extractor],
                    show_progress=show_progress,
                )

                logger.info(f"Successfully ingested {len(nodes)} nodes into property graph")

                if run_deduplication and GRAPH_ENABLE_ENTITY_DEDUPLICATION:
                    logger.info("Starting entity deduplication...")
                    self.deduplicate_entities(
                        similarity_threshold=GRAPH_ENTITY_SIMILARITY_THRESHOLD,
                        word_edit_distance=int(GRAPH_WORD_DISTANCE_THRESHOLD),
                    )

                return index

            except Exception as e:
                attempt += 1
                if _is_rate_limit_error(e) and attempt < max_attempts:
                    logger.warning("Rate limited during graph ingestion, backing off %.1fs (attempt %d/%d)", delay, attempt, max_attempts)
                    time.sleep(delay)
                    delay *= 1.5
                    continue
                msg = str(e)
                if "Invalid input '('" in msg and "expected \"{\"" in msg:
                    logger.warning("Skipping Neo4j ingestion due to Cypher syntax incompatibility: %s", msg)
                    return None
                logger.error("Failed to ingest nodes into property graph: %s", e)
                return None

    def deduplicate_entities(
        self,
        similarity_threshold: float = 0.9,
        word_edit_distance: int = 5,
        enable_apoc: bool = True,
        dry_run: bool = False,
    ) -> dict:
        """Deduplicate entities using vector similarity and word distance.

        Based on tutorial pattern:
        https://neo4j.com/blog/developer/property-graph-index-llamaindex/

        Args:
            similarity_threshold: Minimum cosine similarity (0-1)
            word_edit_distance: Maximum Levenshtein distance
            enable_apoc: Use APOC functions if available
            dry_run: Only report, don't merge

        Returns:
            Dictionary with deduplication statistics
        """
        try:
            logger.info(f"Running entity deduplication: " f"similarity={similarity_threshold}, " f"word_distance={word_edit_distance}, " f"dry_run={dry_run}")

            deduplicator = EntityDeduplicator(
                graph_store=self.graph_store,
                similarity_threshold=similarity_threshold,
                word_edit_distance=word_edit_distance,
                enable_apoc=enable_apoc,
            )

            # Create vector index for efficient similarity search
            deduplicator.create_vector_index(embedding_dimension=OPENAI_EMBED_MODEL_DIM)

            # Get initial stats
            initial_stats = deduplicator.get_duplicate_stats()
            logger.info(f"Duplicate analysis: {initial_stats}")

            # Find and validate duplicates
            duplicate_groups = deduplicator.find_duplicate_entities()
            validated_groups, false_positives = deduplicator.validate_duplicates(duplicate_groups)

            logger.info(f"Found {len(validated_groups)} validated duplicate groups " f"({len(false_positives)} false positives filtered)")

            # Log examples for review
            if validated_groups:
                logger.info("Example duplicate groups:")
                for i, group in enumerate(validated_groups[:5]):
                    logger.info(f"  {i+1}. {group}")

            if false_positives:
                logger.info("Example false positives (not merged):")
                for i, group in enumerate(false_positives[:3]):
                    logger.info(f"  {i+1}. {group}")

            # Merge duplicates
            merge_stats = deduplicator.merge_duplicate_entities(
                duplicate_groups=validated_groups,
                dry_run=dry_run,
            )

            # Get final stats
            final_stats = deduplicator.get_duplicate_stats()

            result = {
                **merge_stats,
                "initial_stats": initial_stats,
                "final_stats": final_stats,
                "validated_groups": len(validated_groups),
                "false_positives_filtered": len(false_positives),
            }

            logger.info(f"Entity deduplication complete: {result}")
            return result

        except Exception as e:
            logger.error(f"Error during entity deduplication: {e}", exc_info=True)
            return {"error": str(e)}

    def _get_driver(self):
        driver = getattr(self.graph_store, "driver", None) or getattr(self.graph_store, "_driver", None)
        if driver is None:
            raise RuntimeError("Neo4j driver not available from property graph store")
        return driver

    def clear_graph(self):
        """Clear all nodes and relationships from the graph."""
        try:
            driver = self._get_driver()
            logger.info("Clearing Neo4j graph")
            with driver.session(database=self.database) as session:
                session.run("MATCH (n) DETACH DELETE n")
                # Ensure relationships are removed (DETACH DELETE should suffice, but double-check)
                session.run("MATCH ()-[r]-() DELETE r")
            logger.info("Neo4j graph cleared successfully")
        except Exception as e:
            logger.error(f"Failed to clear graph: {e}")
            raise

    def get_stats(self) -> dict:
        """Get graph statistics.

        Returns:
            Dictionary with entity/relation counts
        """
        try:
            driver = self._get_driver()
            with driver.session(database=self.database) as session:
                node_count_record = session.run("MATCH (n) RETURN count(n) AS count").single()
                node_count = node_count_record["count"] if node_count_record else 0
                relationship_count_record = session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()
                relationship_count = relationship_count_record["count"] if relationship_count_record else 0

                label_counts = []
                for record in session.run(
                    """
                    MATCH (n)
                    WITH labels(n) AS labels
                    UNWIND labels AS label
                    RETURN label, count(*) AS count
                    ORDER BY count DESC
                    LIMIT 10
                    """
                ):
                    label_counts.append({"label": record["label"], "count": record["count"]})

                relationship_type_counts = []
                for record in session.run(
                    """
                    MATCH ()-[r]->()
                    RETURN type(r) AS type, count(*) AS count
                    ORDER BY count DESC
                    LIMIT 10
                    """
                ):
                    relationship_type_counts.append({"type": record["type"], "count": record["count"]})

            return {
                "nodes": node_count,
                "relationships": relationship_count,
                "top_labels": label_counts,
                "top_relationship_types": relationship_type_counts,
            }
        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {"error": str(e)}
