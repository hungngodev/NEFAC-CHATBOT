from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from src.config.node_names import (
    QUERY_TRANSFORMER_NODE,
    RESEARCH_COMPRESS_RESEARCH,
    RESEARCH_RESEARCHER,
    RESEARCH_RESEARCHER_TOOLS,
)
from src.config.settings import Configuration
from src.core.agents.query_translation.query_transformer import query_transformer
from src.core.agents.research.compress_research import compress_research
from src.core.agents.research.researcher_tools import researcher_tools
from src.core.agents.tools.main import get_all_tools
from src.core.agents.tools.misc_utils import get_api_key_for_model, get_today_str
from src.schemas.state import ResearcherOutputState, ResearcherState


async def researcher(state: ResearcherState, config: RunnableConfig) -> dict:
    configurable = Configuration.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    tools = await get_all_tools(config)
    if len(tools) == 0:
        raise ValueError("No tools found to conduct research: Please configure either your search API or add MCP tools to your configuration.")
    research_model_config = {"model": configurable.research_model, "max_tokens": configurable.research_model_max_tokens, "api_key": get_api_key_for_model(configurable.research_model, config), "tags": ["langsmith:nostream"]}
    configurable_model = init_chat_model(configurable.research_model).bind(**research_model_config)
    researcher_system_prompt = configurable.research_system_prompt.format(mcp_prompt=configurable.mcp_prompt or "", date=get_today_str())
    research_model = configurable_model.bind_tools(tools).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(research_model_config)
    response = await research_model.ainvoke([SystemMessage(content=researcher_system_prompt)] + researcher_messages)
    return {"researcher_messages": [response], "tool_call_iterations": state.get("tool_call_iterations", 0) + 1}


researcher_builder = StateGraph(state_schema=ResearcherState, output_schema=ResearcherOutputState, config_schema=Configuration)

researcher_builder.add_node(
    node=RESEARCH_RESEARCHER,
    action=researcher,
    metadata={
        "description": "Main researcher agent that conducts research using available tools",
        "type": "agent_node",
        "interaction": "tool_calling",
        "criticality": "high",
        "llm_powered": True,
        "tool_binding": True,
        "expected_duration": "medium",
        "max_iterations": "configurable",
        "dependencies": ["research_topic", "available_tools"],
        "outputs": ["researcher_messages", "tool_calls"],
    },
)

researcher_builder.add_node(
    node=RESEARCH_RESEARCHER_TOOLS,
    destinations=[RESEARCH_RESEARCHER, END, QUERY_TRANSFORMER_NODE, RESEARCH_COMPRESS_RESEARCH],
    action=researcher_tools,
    metadata={
        "description": "Executes research tools and processes tool call results",
        "type": "tool_execution_node",
        "interaction": "external_apis",
        "criticality": "high",
        "command_based_routing": True,
        "async_execution": True,
        "expected_duration": "variable",
        "tool_types": ["search", "web_scraping", "document_retrieval"],
        "dependencies": ["tool_calls", "research_context"],
        "outputs": ["tool_results", "processed_data", "routing_decision"],
    },
)

researcher_builder.add_node(
    node=RESEARCH_COMPRESS_RESEARCH,
    action=compress_research,
    metadata={
        "description": "Compresses and summarizes research findings for output",
        "type": "processing_node",
        "interaction": "internal",
        "criticality": "medium",
        "llm_powered": True,
        "summarization": True,
        "expected_duration": "short",
        "dependencies": ["tool_results", "research_data"],
        "outputs": ["compressed_results", "research_summary"],
    },
)

researcher_builder.add_node(
    node=QUERY_TRANSFORMER_NODE,
    action=query_transformer,
    metadata={
        "description": "Transforms and optimizes research queries using multiple strategies",
        "type": "query_processing_node",
        "interaction": "internal_routing",
        "criticality": "high",
        "llm_powered": True,
        "strategy_selection": True,
        "expected_duration": "medium",
        "query_strategies": ["contextual", "decomposition", "hyde", "factual", "multi_query", "step_back"],
        "dependencies": ["research_query", "context"],
        "outputs": ["transformed_context", "optimized_query"],
    },
)

# Graph flow with conditional routing
researcher_builder.add_edge(START, RESEARCH_RESEARCHER)
researcher_builder.add_edge(RESEARCH_RESEARCHER, RESEARCH_RESEARCHER_TOOLS)
researcher_builder.add_edge(RESEARCH_RESEARCHER_TOOLS, RESEARCH_RESEARCHER)
researcher_builder.add_edge(QUERY_TRANSFORMER_NODE, RESEARCH_RESEARCHER_TOOLS)
researcher_builder.add_edge(RESEARCH_COMPRESS_RESEARCH, END)

researcher_subgraph = researcher_builder.compile(
    debug=True,
    name="individual_researcher_graph",
    interrupt_before=None,
    interrupt_after=None,
)
