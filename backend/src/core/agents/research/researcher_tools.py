import asyncio

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Send

from src.config.node_names import QUERY_TRANSFORMER_NODE, RESEARCH_COMPRESS_RESEARCH, RESEARCH_RESEARCHER
from src.config.settings import Configuration
from src.core.agents.tools.main import get_all_tools
from src.core.agents.tools.search import anthropic_websearch_called, openai_websearch_called
from src.schemas.state import ResearcherState


async def execute_tool_safely(tool, args, config):
    try:
        return await tool.ainvoke(args, config)
    except Exception as e:
        return f"Error executing tool: {str(e)}"


async def researcher_tools(state: ResearcherState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    most_recent_message = researcher_messages[-1]

    # Process query transformer results if available
    completed_query_results = state.get("_completed_query_results", [])

    if completed_query_results:
        query_tool_messages = []

        for query_result in completed_query_results:
            source_tool_call = query_result.get("_source_tool_call", {})
            transformed_context = query_result.get("transformed_context", "")
            method_used = query_result.get("method_used", "default")

            if source_tool_call and transformed_context:
                strategy_map = {"multiquery": "multi-perspective search", "decompose": "sub-question analysis", "stepback": "conceptual framework search", "hyde": "hypothetical document matching", "factual": "factual precision search", "contextual": "contextual expansion search"}

                strategy_info = f" (using {strategy_map.get(method_used, method_used)})" if method_used != "default" else ""
                response_header = f"Internal Document Search Results{strategy_info}"
                formatted_result = f"{response_header}\n{'='*80}\n{transformed_context}"

                query_tool_messages.append(ToolMessage(content=formatted_result, name="InternalDocumentSearch", tool_call_id=source_tool_call.get("id", "unknown")))

        return Command(
            goto=RESEARCH_RESEARCHER,
            update={
                "researcher_messages": query_tool_messages,
                "_completed_query_results": [],
            },
        )

    # Early exit if no tool calls were made
    if not most_recent_message.tool_calls and not (openai_websearch_called(most_recent_message) or anthropic_websearch_called(most_recent_message)):
        return Command(goto=RESEARCH_COMPRESS_RESEARCH)

    # Check for internal document search calls
    tool_calls = most_recent_message.tool_calls
    internal_search_calls = [tool_call for tool_call in tool_calls if tool_call["name"] == "InternalDocumentSearch"]
    other_tool_calls = [tool_call for tool_call in tool_calls if tool_call["name"] != "InternalDocumentSearch"]

    # Delegate internal document search calls to query transformer
    if internal_search_calls:
        query_transformer_sends = [
            Send(
                QUERY_TRANSFORMER_NODE,
                {
                    "transformed_query": tool_call["args"]["query"],
                    "method_used": "default",
                    "transformed_context": "",
                    "generated_queries": [],
                    "sub_questions": [],
                    "step_back_question": "",
                    "hypothetical_document": "",
                    "retrieval_query": "",
                    "retrieval_plan": {},
                    "graph_documents": [],
                    "document_search_documents": [],
                    "documents": [],
                    "accumulated_documents": [],
                    "_source_tool_call": tool_call,
                },
            )
            for tool_call in internal_search_calls
        ]

        # Execute other tools if any
        other_tool_outputs = []
        if other_tool_calls:
            tools = await get_all_tools(config)
            tools_by_name = {tool.name if hasattr(tool, "name") else tool.get("name", "web_search"): tool for tool in tools}
            coros = [execute_tool_safely(tools_by_name[tool_call["name"]], tool_call["args"], config) for tool_call in other_tool_calls]
            observations = await asyncio.gather(*coros)
            other_tool_outputs = [ToolMessage(content=observation, name=tool_call["name"], tool_call_id=tool_call["id"]) for observation, tool_call in zip(observations, other_tool_calls)]

        return Command(
            goto=query_transformer_sends,
            update={
                "researcher_messages": researcher_messages + other_tool_outputs,
            },
        )

    # Standard tool execution for non-internal-search tools
    tools = await get_all_tools(config)
    tools_by_name = {tool.name if hasattr(tool, "name") else tool.get("name", "web_search"): tool for tool in tools}
    coros = [execute_tool_safely(tools_by_name[tool_call["name"]], tool_call["args"], config) for tool_call in tool_calls]
    observations = await asyncio.gather(*coros)
    tool_outputs = [ToolMessage(content=observation, name=tool_call["name"], tool_call_id=tool_call["id"]) for observation, tool_call in zip(observations, tool_calls)]

    if state.get("tool_call_iterations", 0) >= configurable.max_react_tool_calls or any(tool_call["name"] == "ResearchComplete" for tool_call in most_recent_message.tool_calls):
        return Command(goto=RESEARCH_COMPRESS_RESEARCH, update={"researcher_messages": tool_outputs})

    return Command(goto=RESEARCH_RESEARCHER, update={"researcher_messages": tool_outputs})
