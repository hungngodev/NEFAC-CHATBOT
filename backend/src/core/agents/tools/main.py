from langchain_core.messages import MessageLikeRepresentation, filter_messages
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool as lc_tool

from src.config.settings import Configuration, SearchAPI
from src.core.agents.tools.mcp_utils import load_mcp_tools
from src.core.agents.tools.misc_utils import get_config_value
from src.core.agents.tools.search import tavily_search
from src.core.agents.tools.unified_retrieval_tool import internal_document_search
from src.schemas.state import ResearchComplete


##########################
# Tool Utils
##########################
async def get_search_tool(search_api: SearchAPI):
    if search_api == SearchAPI.ANTHROPIC:
        return [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]
    elif search_api == SearchAPI.OPENAI:
        return [{"type": "web_search_preview"}]
    elif search_api == SearchAPI.TAVILY:
        search_tool = tavily_search
        search_tool.metadata = {**(search_tool.metadata or {}), "type": "search", "name": "web_search"}
        return [search_tool]
    elif search_api == SearchAPI.NONE:
        return []


async def get_all_tools(config: RunnableConfig):
    """
    Get all available tools for the agent with proper configuration.

    Returns a list of tools in priority order:
    1. Research completion tool
    2. External search tools (web search)
    3. Internal document search (prioritized for legal/organizational queries)
    4. MCP tools (additional integrations)
    """
    tools = [lc_tool(ResearchComplete)]
    configurable = Configuration.from_runnable_config(config)
    search_api = SearchAPI(get_config_value(configurable.search_api))
    tools.extend(await get_search_tool(search_api))

    # Add unified internal document retrieval tool with proper metadata
    internal_search_tool = internal_document_search.with_config(config)
    # Add metadata to help with tool selection
    internal_search_tool.metadata = {**(internal_search_tool.metadata or {}), "type": "internal_search", "priority": "high", "domain": "legal_organizational"}
    tools.append(internal_search_tool)

    existing_tool_names = {tool.name if hasattr(tool, "name") else tool.get("name", "web_search") for tool in tools}
    mcp_tools = await load_mcp_tools(config, existing_tool_names)
    tools.extend(mcp_tools)
    return tools


def get_notes_from_tool_calls(messages: list[MessageLikeRepresentation]):
    return [tool_msg.content for tool_msg in filter_messages(messages, include_types="tool")]


##########################
# Misc Utils
##########################
