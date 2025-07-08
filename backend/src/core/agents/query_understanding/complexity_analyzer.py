from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config.constant import COMPLEXITY_ANALYSIS_MODEL_NAME
from src.schemas.core_types import AgentState


class QueryComplexity(BaseModel):
    reasoning_required: bool = Field(description="Indicates if the query requires multi-step legal reasoning to answer (e.g., interpreting statutes or synthesizing guidance).")
    multi_hop_needed: bool = Field(description="Indicates if the query requires connecting information across multiple sources, jurisdictions, or legal domains relevant to NEFAC.org (e.g., federal FOIA rules plus MA state public records law).")
    tool_usage_required: bool = Field(description="Indicates if the query requires external tools, API calls, or database filtering (e.g., FOIA log searches, public records API queries) to answer.")


# Initialize the LLM model
model = ChatOpenAI(model=COMPLEXITY_ANALYSIS_MODEL_NAME)

# Prompt tailored to NEFAC.org’s content and offerings
COMPLEXITY_ANALYSIS_PROMPT = """
You are an expert AI assistant for the NEFAC.org chatbot, which helps the public navigate:
  • The FOI Guide: state-by-state FOIA request processes
  • 30 Minute Skills tutorials (Signal, immigration records, podcasting, etc.)
  • Commentary & Advocacy pieces (legal briefs, reform proposals, Sunshine Week insights)
  • Open Meeting and Public Records Laws for Massachusetts, Rhode Island, Connecticut

For each incoming user query, decide exactly these three boolean flags. Use the following combined guidance, drawing on both NEFAC-specific and general legal-query complexity cues:

1. reasoning_required:
   - True if the query demands multi-step legal reasoning, such as:
     • Interpreting statutory language or regulatory text (e.g., FOIA deadlines, exemptions)
     • Comparing or contrasting case precedents (e.g., "Smith v. Jones")
     • Synthesizing guidelines across different laws (FOIA vs Sunshine law) or commentary pieces
   - **Linguistic cues**:
     • Assess sentence structure, grammar, and vocabulary richness
     • Note complex vs simple question forms: "why", "how", "analyze", "compare", "evaluate", "assess" vs "what", "who", "when", "where"
     • Look for multiple clauses or conjunctions: "and", "but", "however", "although", "because", "since"
     • Identify long sentences or high word counts
   - **Domain cues**:
     • Gauge density of legal terms: law, court, statute, regulation, jurisdiction, precedent, appellate
     • Recognize specialized terms: FOIA, public records, exemption, redaction, open meeting, sunshine law

2. multi_hop_needed:
   - True if answering requires connecting multiple resources or dimensions, such as:
     • Federal FOIA procedures plus state-specific public records laws (MA, RI, CT)
     • Merging open meeting rules with Sunshine Week commentary and NEFAC tutorials
     • Combining advocacy proposals with statutory requirements
   - **Temporal complexity**:
     • Look for time-based references: trend, over time, historical, evolution, change, development
     • Time markers: decade, year, month, recent, past, future, since, until, event dates (e.g., "July 22 30 Minute Skills")
   - **Citation complexity**:
     • Case citations: "Smith v. Jones"
     • Statute references: "42 U.S.C. § 1983"

3. tool_usage_required:
   - True if simple text lookup isn’t enough and you need external tools or data:
     • Filtering FOIA log databases by date or requester attributes
     • Querying public records APIs for aggregated statistics or counts
     • Pulling event archives, CSVs, or tutorial transcripts for analysis
   - Consider if the query asks for:
     • Statistical summaries (e.g., number of requests in a time period)
     • Programmatic access (e.g., download records, export logs)

Output exactly one JSON object with keys: reasoning_required, multi_hop_needed, tool_usage_required. Do not include any other text or fields.
"""


def analyze_complexity_node(state: AgentState) -> QueryComplexity:
    """
    Graph node that runs complexity analysis on tshe incoming AgentState.
    """
    prompt = ChatPromptTemplate(
        [
            ("system", COMPLEXITY_ANALYSIS_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "Query to analyze: {query}"),
        ]
    )
    response = (prompt | model.with_structured_output(QueryComplexity)).invoke({"query": state["contextualized_query"], "chat_history": state["summarized_messages"]})
    return QueryComplexity.model_validate(response)
