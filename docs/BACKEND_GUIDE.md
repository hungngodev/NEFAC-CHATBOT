# NEFAC Backend Documentation

## 1. Overview

The NEFAC Backend is a sophisticated **Agentic System** built on **LangGraph** (a LangChain extension). Unlike traditional REST APIs that map URLs to controllers, this system maps **Graph Nodes** to **Agent Functions**. It uses an event-driven, stateful architecture to perform complex, multi-step research tasks ("Deep Research") as well as quick question-answering ("Quick QA").

- **Architecture Style**: Stateful Graph (Supervisor-Worker Pattern).
- **Framework**: LangGraph (`langgraph-api` runtime).
- **Runtime**: Asynchronous Python 3.11+.
- **Main Entry Point**: `src/app/server.py` (Exports the `deep_researcher` graph).
- **Infrastructure**: Dockerized services including Postgres (State), Redis (Queue), Qdrant (Vector), Neo4j (Graph), and Elasticsearch (Keyword).

---

## 2. API Routes & Logic Flow

The backend is served via the **LangGraph API Server** (using `langgraph-cli`). It exposes standard graph operations rather than custom REST endpoints.

### Core Endpoints (LangGraph Standard)

| Method | Path                               | Description                                                          |
| :----- | :--------------------------------- | :------------------------------------------------------------------- |
| `POST` | `/threads`                         | Create a new conversation thread (session).                          |
| `POST` | `/threads/{thread_id}/runs`        | Send a user message to the graph. This triggers the agent execution. |
| `GET`  | `/threads/{thread_id}/state`       | Retrieve the current state of a conversation (messages, documents).  |
| `POST` | `/threads/{thread_id}/runs/stream` | Stream the execution events (tokens, tool calls) in real-time.       |

### Graph Logic Flow (`deep_researcher`)

When a request is sent to `/runs`, the request flows through the `deep_researcher` graph defined in `src/app/server.py`:

1.  **Entry (`START`)**: The request enters the graph.
2.  **`MEMORY_SUMMARIZER_NODE`**:
    - **Function**: `summarizer`
    - **Logic**: Compresses older conversation history to save context window.
    - **Routing**: Decides whether to go to **Quick QA** or **Deep Research** based on `configurable.research_mode`.
3.  **Path A: Quick QA (`QUICK_AGENT_NODE`)**:
    - **Function**: `quick_agent_subgraph`
    - **Logic**: A fast ReAct agent that calls tools (Search, Internal Docs) directly and returns a final answer immediately.

### 2.2 Subgraphs
*   **`research_team`**: Executes `tavily_search` and `InternalDocumentSearch` in parallel.
*   **`quick_agent`**: A single-node ReAct agent that calls tools directly.

### 2.3 Research Subgraph Details (`src/core/agents/research/`)
The `research_team` is a complex subgraph designed for iterative discovery.

| Node | Description | Logic Flow |
| :--- | :--- | :--- |
| `researcher` | **Agent Node**. Decides next steps (Tool Call vs. Finish). | Checks `max_react_tool_calls`. If cap reached -> `compress_research`. Else -> `researcher_tools`. |
| `researcher_tools` | **Tool Executor**. Routes standard tools vs. RAG tools. | `InternalDocumentSearch` -> `query_transformer` (via `Send`). Other tools -> Execute & Loop back to `researcher`. |
| `query_transformer` | **RAG Optimizer**. Expands queries (HyDE, MultiQuery). | `query_transformer` -> `researcher_tools` (returns results as `ToolMessage`). |
| `compress_research` | **Summarizer**. Condenses findings into notes. | `researcher` (when done) -> `compress_research` -> `package_output`. |
| `package_output` | **Formatter**. Formats data for the Supervisor. | `compress_research` -> `package_output` -> `END`. |

**Key Behaviors**:
*   **Parallel Query Processing**: Multiple `InternalDocumentSearch` calls are de-duplicated and sent to `query_transformer` in parallel.
*   **Safety Caps**: Enforces `max_react_tool_calls` (default 10) to prevent infinite loops.
*   **Pending Tool Checks**: Ensures all LLM-generated tool calls receive a response (even if just an error) before the agent proceeds.

4.  **Path B: Deep Research**:
    - **`RESEARCH_CLARIFY_WITH_USER`**: Asks clarifying questions if the user's intent is ambiguous.
    - **`RESEARCH_WRITE_RESEARCH_BRIEF`**: Generates a structured research plan.
    - **`RESEARCH_SUPERVISOR`**: Orchestrates a team of researchers to execute the plan in parallel.
    - **`RESEARCH_FINAL_REPORT_GENERATION`**: Synthesizes all findings into a comprehensive report.
5.  **`CLEANUP_NODE`**: Resets temporary state (like internal supervisor messages) before saving the checkpoint.
6.  **Exit (`END`)**: The final response is returned to the user.

---

## 3. Data Models

State is managed via Pydantic models and `TypedDict` in `src/schemas/state.py`.

### 3.1 `AgentState` (Global Context)

Passed between all main nodes.

- `messages` (`list[BaseMessage]`): Full chat history (User, AI, System).
- `final_report` (`str`): The answer to be sent to the user.
- `research_brief` (`str`): The generated plan for the research session.
- `final_documents` (`list[Document]`): List of cited sources retrieved during research.
- `supervisor_messages` (`list`): Internal messages used for agent coordination (hidden from user).

### 3.2 `SupervisorState` (Orchestration Context)

Used within the `RESEARCH_SUPERVISOR` node.

- `research_iterations` (`int`): Safety counter (max 5) to prevent infinite loops.
- `completed_research_results` (`list`): Aggregated findings from workers.
- `supervisor_messages` (`list`): Internal monologue/scratchpad.

### 3.3 `ResearcherState` (Worker Context)

Used by individual researchers.

- `research_topic` (`str`): The specific sub-problem assigned to this researcher.
- `compressed_research` (`str`): Summarized findings from tools.
- `documents` (`list[Document]`): Documents found by this specific researcher.

### 3.4 `QuickAgentState` (Quick QA Context)

Used by the Quick Agent subgraph.

- `tool_call_iterations` (`int`): Counter for ReAct loop steps.
- `final_report` (`str`): The direct answer generated.

### 3.5 `QueryTransformerState` (Retrieval Context)

Used by the Query Transformer subgraph for advanced retrieval.

- `transformed_query` (`str`): The input query.
- `method_used` (`str`): The strategy applied (e.g., "hyde", "multiquery").
- `generated_queries` (`list[str]`): Variations of the query.
- `hypothetical_document` (`str`): Generated hypothetical answer for HyDE.

---

## 4. Middleware & Utilities

### 4.1 Tools (Capabilities)

Located in `src/core/agents/tools/`.

- **`InternalDocumentSearch`**:
  - **Input**: `query` (str).
  - **Logic**: Triggers `query_transformer` -> Retrieval (Qdrant/Neo4j/Elastic) -> Reranking.
  - **Output**: List of `Document` objects.
- **`tavily_search`**:
  - **Input**: `query` (str).
  - **Logic**: Calls Tavily API for live web results.
- **`ResearchComplete`**:
  - **Logic**: Signal to stop research and generate report.

### 4.2 Query Transformer Strategies

Located in `src/core/agents/query_translation/`.

- **HyDE**: Generates a hypothetical answer to improve semantic matching.
- **Multi-Query**: Generates multiple variations of the query to broaden search.
- **Decomposition**: Breaks complex queries into sub-questions.
- **Step-Back**: Generates abstract questions to find grounding context.

### 4.3 Persistence (Middleware)

- **Checkpointer**: `PostgresSaver`.
  - **Function**: Saves the state of the graph after every step to the `checkpoints` table (binary blobs).
  - **TTL**: Configured to delete threads older than 30 days (43200 minutes).
- **Task Queue**: `Redis`.
  - **Function**: Manages concurrent execution and background tasks.

### 4.4 Ingestion Service

Located in `src/service/ingestion_service/`.

- **Workflow**: Loads metadata -> Ingests content -> Stores in Vector/Graph DBs.
- **Stores**:
  - **Qdrant**: Dense vectors for semantic search.
  - **Elasticsearch**: Keyword search.
  - **Neo4j**: Graph RAG for relationship mapping.

---

## 5. Setup & Dependencies

### 5.1 Environment

Defined in `.env` (see `.env.example`).

- `OPENAI_API_KEY`: LLM Provider.
- `TAVILY_API_KEY`: Web Search.
- `POSTGRES_URI`: Database connection (`postgres://...`).
- `REDIS_URI`: Queue connection (`redis://...`).
- `LANGGRAPH_CLOUD_LICENSE_KEY`: (Optional) For LangGraph Cloud features.

### 5.2 Dependencies (`pyproject.toml`)

- **Core**: `langgraph`, `langchain`, `pydantic`.
- **Database**: `langgraph-checkpoint-postgres`, `asyncpg`.
- **Vector/Graph**: `langchain-qdrant`, `langchain-neo4j`, `langchain-elasticsearch`.
- **Parsers**: `unstructured`, `beautifulsoup4`, `pypdf2`.
- **Runtime**: `langgraph-cli`, `langgraph-api`.

### 5.3 Development Setup

**Location**: `backend/`
**Port**: `8123` (API), `2024` (Studio)

1.  **Install Dependencies**:
    ```bash
    cd backend
    poetry install
    ```

2.  **Start Databases**:
    Ensure Docker databases are running:
    ```bash
    cd ../docker
    docker-compose up -d postgres redis qdrant elasticsearch neo4j
    ```

3.  **Start Backend**:
    Run the LangGraph development server (includes LangGraph Studio):
    ```bash
    cd ../backend
    poetry run langgraph dev
    ```
    - **API**: `http://localhost:8123`
    - **Studio**: `http://localhost:2024` (Check terminal output)
