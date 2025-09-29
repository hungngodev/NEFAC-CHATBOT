import json
import logging
import os
import random
import time
from typing import Iterable, List

from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_neo4j import Neo4jGraph
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from src.service.ingestion_service.settings import graph_llm_model

logger = logging.getLogger(__name__)


def _batched(iterable: Iterable[Document], size: int) -> Iterable[list[Document]]:
    batch: list[Document] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USER, password=NEO4J_PASSWORD)


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


GRAPH_RAG_CONVERSION_RETRIES = max(
    1,
    _get_env_int(
        "GRAPH_RAG_CONVERSION_RETRIES",
        _get_env_int("GRAPH_LLM_MAX_RETRIES", 2),
    ),
)
GRAPH_RAG_RETRY_WAIT_MIN_SECONDS = max(0.5, _get_env_float("GRAPH_RAG_RETRY_WAIT_MIN_SECONDS", 1.0))
GRAPH_RAG_RETRY_WAIT_MAX_SECONDS = max(
    GRAPH_RAG_RETRY_WAIT_MIN_SECONDS,
    _get_env_float("GRAPH_RAG_RETRY_WAIT_MAX_SECONDS", 20.0),
)


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


def resolve_entity(name: str) -> str:
    """Return canonical entity name, or original if not found in alias map."""
    name_clean = name.strip().lower().replace("-", " ").replace(".", "").replace("_", " ")
    return CANONICAL_ENTITY_LOOKUP.get(name_clean, name)


def pre_disambiguate_entities(docs: List[Document]) -> List[Document]:
    """
    For each Document, replace any known alias (NEFAC, partners, awards, etc.) with its canonical name.
    Attach original mention(s) as property if different.
    """
    logger.info(f"Disambiguating entities for {len(docs)} documents...")

    fixed_docs = []
    for doc in docs:
        meta = dict(getattr(doc, "metadata", {}))
        content = getattr(doc, "page_content", "")
        new_content = content
        found_aliases = []
        for alias, canon in CANONICAL_ENTITY_LOOKUP.items():
            if alias != canon.lower() and alias in content.lower():
                new_content = new_content.replace(alias, canon)
                found_aliases.append(alias)
        if found_aliases:
            meta.setdefault("original_mentions", []).extend(found_aliases)
        fixed_doc = doc.__class__(page_content=new_content, metadata=meta)
        fixed_docs.append(fixed_doc)

    logger.info(f"Entity disambiguation complete for {len(fixed_docs)} documents")
    return fixed_docs


allowed_nodes = [
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

allowed_relationships = [
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
    "HAS_GL0SSARY_TERM",
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
    "MODERATES",
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
custom_prompt_template = """
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

**Input Text:**
{input}
"""

custom_prompt = ChatPromptTemplate.from_template(custom_prompt_template)


def sanitize_metadata_for_neo4j(metadata: dict) -> dict:
    """
    Clean document metadata to only include primitive types that Neo4j can handle.
    Neo4j properties can only be: strings, numbers, booleans, or arrays of these types.
    """
    sanitized = {}

    for key, value in metadata.items():
        if value is None:
            continue
        elif isinstance(value, (str, int, float, bool)):
            # Primitive types are fine
            sanitized[key] = value
        elif isinstance(value, list):
            # Handle lists - only keep if all elements are primitives
            if all(isinstance(item, (str, int, float, bool)) for item in value):
                sanitized[key] = value
            else:
                # Convert complex list items to strings
                sanitized[key] = [str(item) for item in value]
        elif isinstance(value, dict):
            # Convert complex objects to JSON strings
            try:
                sanitized[f"{key}_json"] = json.dumps(value)
            except (TypeError, ValueError):
                sanitized[f"{key}_str"] = str(value)
        else:
            # Convert any other type to string
            sanitized[f"{key}_str"] = str(value)

    return sanitized


def clean_documents_for_neo4j(documents: List[Document]) -> List[Document]:
    """
    Create new document instances with sanitized metadata for Neo4j compatibility.
    """
    logger.info(f"Cleaning {len(documents)} documents for Neo4j...")

    cleaned_docs = []
    for doc in documents:
        clean_metadata = sanitize_metadata_for_neo4j(doc.metadata)
        cleaned_doc = Document(page_content=doc.page_content, metadata=clean_metadata)
        cleaned_docs.append(cleaned_doc)

    logger.info(f"Document cleaning complete for {len(cleaned_docs)} documents")
    return cleaned_docs


def graph_rag_ingest(documents: List[Document]) -> int:
    """
    Graph RAG ingestion with systematic progress tracking.
    Returns the number of graph documents created/ingested.
    """
    if not documents:
        logger.warning("No documents provided for graph RAG ingestion")
        return 0

    logger.info(f"Starting Graph RAG ingestion for {len(documents)} documents")

    try:
        # Step 1: Clean documents for Neo4j compatibility
        logger.info("Step 1/4: Cleaning documents for Neo4j compatibility")
        docs_cleaned = clean_documents_for_neo4j(documents)

        # Step 2: Apply entity disambiguation
        logger.info("Step 2/4: Applying entity disambiguation")
        docs_canonical = pre_disambiguate_entities(docs_cleaned)

        # Step 3: Initialize graph transformer
        logger.info("Step 3/4: Initializing graph transformer")
        model_name = f"{graph_llm_model.model}" if hasattr(graph_llm_model, "model") else str(graph_llm_model)
        logger.info(f"Using {model_name} for graph document conversion")

        transformer = LLMGraphTransformer(
            llm=graph_llm_model,
            node_properties=True,
            relationship_properties=True,
            prompt=custom_prompt.partial(
                alias_map=str(ENTITY_ALIASES),
                allowed_nodes=str(allowed_nodes),
                allowed_relationships=str(allowed_relationships),
            ),
        )

        total_graph_docs = 0
        failed_docs = 0
        delay = float(os.getenv("GRAPH_RAG_BATCH_DELAY", "2.0"))
        jitter = float(os.getenv("GRAPH_RAG_BATCH_JITTER", "0.5"))

        @retry(
            wait=wait_exponential(
                min=GRAPH_RAG_RETRY_WAIT_MIN_SECONDS,
                max=GRAPH_RAG_RETRY_WAIT_MAX_SECONDS,
            ),
            stop=stop_after_attempt(GRAPH_RAG_CONVERSION_RETRIES),
        )
        def _convert_single(doc: Document) -> list:
            return transformer.convert_to_graph_documents([doc])

        logger.info("Step 4/4: Converting documents to graph format one by one")

        for doc_index, doc in enumerate(docs_canonical, start=1):
            try:
                logger.info("Document %d: converting to graph format", doc_index)
                graph_docs_single = _convert_single(doc)
                total_graph_docs += len(graph_docs_single)
                logger.info(
                    "Document %d: converted %d graph documents (running total=%d)",
                    doc_index,
                    len(graph_docs_single),
                    total_graph_docs,
                )

                graph.add_graph_documents(
                    graph_docs_single,
                    baseEntityLabel=True,
                    include_source=True,
                )
                if delay > 0:
                    sleep_time = delay + (random.random() * jitter if jitter > 0 else 0)
                    time.sleep(sleep_time)
            except RetryError as retry_error:
                last_exc = retry_error.last_attempt.exception() if retry_error.last_attempt else retry_error
                logger.error(
                    "Document %d failed during graph conversion after %d attempts: %s",
                    doc_index,
                    GRAPH_RAG_CONVERSION_RETRIES,
                    last_exc,
                )
                failed_docs += 1
                continue
            except Exception as batch_error:
                logger.error("Document %d failed during graph conversion/ingest: %s", doc_index, batch_error)
                raise

        if total_graph_docs:
            try:
                graph.query(
                    """
                    MATCH (s:Source)
                    OPTIONAL MATCH (d1:Document {title: s.sourcedocument})
                    OPTIONAL MATCH (d2:Document {title: s.sourcedocumenttitle})
                    WITH s, coalesce(d1, d2) AS d
                    WHERE d IS NOT NULL
                    MERGE (s)-[:SOURCE_OF]->(d)
                    """
                )
            except Exception as link_error:
                logger.warning(f"Provenance linking skipped/failed: {link_error}")

        if failed_docs:
            logger.warning(
                "Graph RAG ingestion skipped %d documents after repeated conversion failures",
                failed_docs,
            )

        logger.info(
            "Graph RAG ingestion complete for %d documents (%d graph documents ingested)",
            len(documents),
            total_graph_docs,
        )
        return total_graph_docs
    except Exception as e:
        logger.error(f"Graph RAG ingestion failed: {e}")
        raise
