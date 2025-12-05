import asyncio
import os
from typing import Annotated, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg
from langchain_core.tools import tool as lc_tool
from tavily import AsyncTavilyClient

from src.config.settings import Configuration, SearchAPI
from src.core.agents.tools.misc_utils import get_api_key_for_model, get_today_str
from src.schemas.state import Summary
from src.utils.model_factory import init_model

TAVILY_SEARCH_DESCRIPTION = "A search engine optimized for comprehensive, accurate, and trusted results. " "Useful for when you need to answer questions about current events."


async def summarize_webpage(model: BaseChatModel, webpage_content: str, config: RunnableConfig) -> str:
    try:
        configurable = Configuration.from_runnable_config(config)
        summary = await asyncio.wait_for(
            model.ainvoke(
                [
                    HumanMessage(
                        content=configurable.summarize_webpage_prompt.format(
                            webpage_content=webpage_content,
                            date=get_today_str(),
                        )
                    )
                ]
            ),
            timeout=60.0,
        )
        return f"""<summary>\n{summary.summary}\n</summary>\n\n<key_excerpts>\n{summary.key_excerpts}\n</key_excerpts>"""
    except (asyncio.TimeoutError, Exception) as e:
        print(f"Failed to summarize webpage: {str(e)}")
        return webpage_content


@lc_tool(description=TAVILY_SEARCH_DESCRIPTION)
async def tavily_search(queries: list[str], max_results: Annotated[int, InjectedToolArg] = 5, topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general", config: RunnableConfig = None) -> str:
    search_results = await tavily_search_async(queries, max_results=max_results, topic=topic, include_raw_content=True, config=config)
    formatted_output = "Search results: \n\n"
    unique_results = {}
    for response in search_results:
        for result in response["results"]:
            url = result["url"]
            if url not in unique_results:
                unique_results[url] = {**result, "query": response["query"]}
    configurable = Configuration.from_runnable_config(config)
    max_char_to_include = 50_000
    get_api_key_for_model(configurable.summarization_model, config)
    summarization_model = init_model(configurable.summarization_model, disable_streaming=configurable.disable_streaming).with_structured_output(Summary).with_retry(stop_after_attempt=configurable.max_structured_output_retries)

    async def noop():
        return None

    summarization_tasks = [
        (
            noop()
            if not result.get("raw_content")
            else summarize_webpage(
                summarization_model,
                result["raw_content"][:max_char_to_include],
                config,
            )
        )
        for result in unique_results.values()
    ]
    summaries = await asyncio.gather(*summarization_tasks)
    summarized_results = {url: {"title": result["title"], "content": result["content"] if summary is None else summary} for url, result, summary in zip(unique_results.keys(), unique_results.values(), summaries)}
    for i, (url, result) in enumerate(summarized_results.items()):
        formatted_output += f"\n\n--- SOURCE {i+1}: {result['title']} ---\n"
        formatted_output += f"URL: {url}\n\n"
        formatted_output += f"SUMMARY:\n{result['content']}\n\n"
        formatted_output += "\n\n" + "-" * 80 + "\n"
    if summarized_results:
        return formatted_output
    else:
        return "No valid search results found. Please try different search queries or use a different search API."


async def tavily_search_async(search_queries, max_results: int = 5, topic: Literal["general", "news", "finance"] = "general", include_raw_content: bool = True, config: RunnableConfig = None):
    tavily_async_client = AsyncTavilyClient(api_key=get_tavily_api_key(config))
    search_tasks = []
    for query in search_queries:
        search_tasks.append(tavily_async_client.search(query, max_results=max_results, include_raw_content=include_raw_content, topic=topic))
    search_docs = await asyncio.gather(*search_tasks)
    return search_docs


def get_tavily_api_key(config: RunnableConfig):
    should_get_from_config = os.getenv("GET_API_KEYS_FROM_CONFIG", "false")
    if should_get_from_config.lower() == "true":
        api_keys = config.get("configurable", {}).get("apiKeys", {})
        if not api_keys:
            return None
        return api_keys.get("TAVILY_API_KEY")
    else:
        return os.getenv("TAVILY_API_KEY")


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


def anthropic_websearch_called(response):
    try:
        usage = response.response_metadata.get("usage")
        if not usage:
            return False
        server_tool_use = usage.get("server_tool_use")
        if not server_tool_use:
            return False
        web_search_requests = server_tool_use.get("web_search_requests")
        if web_search_requests is None:
            return False
        return web_search_requests > 0
    except (AttributeError, TypeError):
        return False


def openai_websearch_called(response):
    tool_outputs = response.additional_kwargs.get("tool_outputs")
    if tool_outputs:
        for tool_output in tool_outputs:
            if tool_output.get("type") == "web_search_call":
                return True
    return False
