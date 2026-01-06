"""Tool management for NEFAC chatbot agents.

Provides tools for both research mode (answer generation) and librarian mode (navigation).
"""

from langchain_core.messages import MessageLikeRepresentation, filter_messages
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool as lc_tool

from src.config.settings import Configuration, SearchAPI
from src.core.agents.tools.mcp_utils import load_mcp_tools
from src.core.agents.tools.misc_utils import get_config_value
from src.core.agents.tools.search import tavily_search
from src.schemas.navigation_state import NavigationComplete
from src.schemas.state import InternalDocumentSearch, ResearchComplete


async def get_search_tool(search_api: SearchAPI):
    """Get web search tool based on configured API."""
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


async def get_navigation_tools():
    """Get tools for librarian navigation mode."""
    from src.core.agents.tools.metadata_filter import get_available_facets, metadata_filter_search
    from src.core.agents.tools.section_linker import create_section_link, list_document_sections
    from src.core.agents.tools.sitemap_navigator import sitemap_get_hierarchy, sitemap_search

    return [
        sitemap_search,
        sitemap_get_hierarchy,
        metadata_filter_search,
        get_available_facets,
        create_section_link,
        list_document_sections,
    ]


async def get_all_tools(config: RunnableConfig):
    """Get all tools for the agent based on configuration.

    In librarian_mode: Returns navigation tools for resource discovery
    In research_mode: Returns research tools for answer generation
    """
    configurable = Configuration.from_runnable_config(config)

    if configurable.librarian_mode:
        # Librarian mode: Navigation tools for resource discovery
        tools = [lc_tool(NavigationComplete)]

        # Add navigation-specific tools
        navigation_tools = await get_navigation_tools()
        tools.extend(navigation_tools)

        # Also include InternalDocumentSearch for hybrid scenarios
        # In librarian mode, it returns ResourceCards instead of raw chunks
        tools.append(lc_tool(InternalDocumentSearch))
    else:
        # Research mode: Traditional answer-generating tools
        tools = [lc_tool(ResearchComplete), lc_tool(InternalDocumentSearch)]

    # Add web search tools (useful in both modes)
    search_api = SearchAPI(get_config_value(configurable.search_api))
    tools.extend(await get_search_tool(search_api))

    # Add MCP tools
    existing_tool_names = {tool.name if hasattr(tool, "name") else tool.get("name", "web_search") for tool in tools}
    mcp_tools = await load_mcp_tools(config, existing_tool_names)
    tools.extend(mcp_tools)

    return tools


def get_notes_from_tool_calls(messages: list[MessageLikeRepresentation]):
    """Extract notes from tool call messages."""
    return [tool_msg.content for tool_msg in filter_messages(messages, include_types="tool")]
