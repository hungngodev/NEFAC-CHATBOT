# Node names for LangGraph workflows

# memory
MEMORY_SUMMARIZER_NODE = "summarizer_node"

# query_understanding
COMPLEXITY_ANALYZER_ANALYZE_COMPLEXITY_NODE = "analyze_complexity"

# query_translation
QUERY_TRANSFORMER_NODE = "query_transformer"
QUERY_TRANSFORMER_MULTI_QUERY = "multi_query"
QUERY_TRANSFORMER_DECOMPOSITION = "decomposition"
QUERY_TRANSFORMER_STEP_BACK = "step_back"
QUERY_TRANSFORMER_HYDE = "hyde"
QUERY_TRANSFORMER_FACTUAL_STRATEGY = "factual_strategy"
QUERY_TRANSFORMER_CONTEXTUAL_STRATEGY = "contextual_strategy"

CONTEXTUAL_STRATEGY_GENERATE_CONTEXTUAL_QUERY = "generate_contextual_query"
CONTEXTUAL_STRATEGY_RETRIEVE_SUBGRAPH = "retrieve_subgraph"
CONTEXTUAL_STRATEGY_FORMAT_DOCUMENTS = "format_documents"

DECOMPOSITION_GENERATE_SUB_QUESTIONS = "generate_sub_questions"
DECOMPOSITION_ANSWER_SUB_QUESTIONS = "answer_sub_questions"
DECOMPOSITION_FORMAT_ANSWER = "format_answer"
DECOMPOSITION_RETRIEVE_SUBGRAPH = "retrieve_subgraph"
DECOMPOSITION_SYNTHESIZE_FINAL_ANSWER = "synthesize_final_answer"

FACTUAL_STRATEGY_GENERATE_FACTUAL_QUERY = "generate_factual_query"
FACTUAL_STRATEGY_RETRIEVE_SUBGRAPH = "retrieve_subgraph"
FACTUAL_STRATEGY_FORMAT_DOCUMENTS = "format_documents"

HYDE_GENERATE_HYPOTHETICAL_DOCUMENT = "generate_hypothetical_document"
HYDE_RETRIEVE_SUBGRAPH = "retrieve_subgraph"
HYDE_GENERATE_FINAL_RESPONSE = "generate_final_response"

MULTI_QUERY_GENERATE_QUERIES = "generate_queries"
MULTI_QUERY_RETRIEVE_SUBGRAPH = "retrieve_subgraph"
MULTI_QUERY_DEDUPLICATE_DOCUMENTS = "deduplicate_documents"
MULTI_QUERY_FORMAT_DOCUMENTS = "format_documents"

STEP_BACK_GENERATE_AND_DISPATCH = "generate_and_dispatch"
STEP_BACK_RETRIEVE_ORIGINAL = "retrieve_original"
STEP_BACK_RETRIEVE_STEP_BACK = "retrieve_step_back"
STEP_BACK_PROCESS_ORIGINAL_CONTEXT = "process_original_context"
STEP_BACK_PROCESS_STEP_BACK_CONTEXT = "process_step_back_context"
STEP_BACK_GENERATE_FINAL_RESPONSE = "generate_final_response"


# reasoning
REASONING_MULTI_STEP_REASONING = "multi_step_reasoning"
REASONING_REACT_MULTI_STEP_REASONING = "react_multi_step_reasoning"

# retrieval
GRAPH_RETRIEVAL_GRAPH_TOOL_NODE = "graph_tool_node"
KEYWORD_RETRIEVAL_KEYWORD_SEARCH = "keyword_search"

RETRIEVAL_SUBGRAPH_PLANNER = "planner"
RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL = "ensemble_retrieval"
RETRIEVAL_SUBGRAPH_GRAPH_RETRIEVAL = "graph_retrieval"
RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS = "combine_documents"

# supervisor
SUPERVISOR_GENERATOR_AGENT = "generator_agent"
SUPERVISOR_VALIDATION_AGENT = "validation_agent"
SUPERVISOR_NODE = "supervisor"
SUPERVISOR_TOOLS_NODE = "supervisor_tools"

# research agents
RESEARCH_CLARIFY_WITH_USER = "clarify_with_user"
RESEARCH_WRITE_RESEARCH_BRIEF = "write_research_brief"
RESEARCH_SUPERVISOR = "research_supervisor"
RESEARCH_FINAL_REPORT_GENERATION = "final_report_generation"
RESEARCH_RESEARCHER = "researcher"
RESEARCH_RESEARCHER_TOOLS = "researcher_tools"
RESEARCH_COMPRESS_RESEARCH = "compress_research"
