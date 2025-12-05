import os as _os
from typing import cast

from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from src.config.node_names import QUICK_AGENT_NODE, QUICK_AGENT_TOOLS_NODE
from src.config.settings import Configuration
from src.core.agents.query_translation.query_transformer import query_transformer
from src.core.agents.tools.main import get_all_tools
from src.core.agents.tools.misc_utils import execute_tool_safely, get_today_str
from src.schemas.state import QuickAgentState
from src.utils.debug import get_debug_mode
from src.utils.events import EVENT_FINAL_RESPONSE, emit_custom_event
from src.utils.model_factory import init_model


async def quick_agent(state: QuickAgentState, config: RunnableConfig) -> dict:
    """
    A single-node agent that handles Quick QA requests.
    It uses a custom ReAct loop to analyze, search, and answer.
    """
    configurable = Configuration.from_runnable_config(config)

    tools = await get_all_tools(config)

    llm = init_model(configurable.quick_agent_model, disable_streaming=configurable.disable_streaming, node_name=QUICK_AGENT_NODE)
    llm_with_tools = llm.bind_tools(tools)

    system_prompt = configurable.quick_agent_system_prompt.format(date=get_today_str())

    supervisor_messages = state.get("supervisor_messages", [])
    messages = state.get("messages", [])
    conversation_history = [m for m in messages if not isinstance(m, SystemMessage)]
    llm_input = [SystemMessage(content=system_prompt)] + conversation_history + cast(list, supervisor_messages)

    emit_custom_event(EVENT_FINAL_RESPONSE, {"is_final": True})

    response = await llm_with_tools.ainvoke(llm_input, config)
    # Check for Tool Calls
    if response.tool_calls:
        emit_custom_event(EVENT_FINAL_RESPONSE, {"is_final": False})
        return Command(goto=QUICK_AGENT_TOOLS_NODE, update={"supervisor_messages": [response], "tool_call_iterations": state.get("tool_call_iterations", 0) + 1})

    # No tool calls -> Final Answert
    response.additional_kwargs = {
        "final_documents": state.get("final_documents", []),
        "supervisor_messages": supervisor_messages,
        "is_final_response": True,
    }

    return Command(
        goto=END,
        update={
            "final_report": response.content,
            "messages": [response],
            "supervisor_messages": [response],
        },
    )


async def quick_agent_tools(state: QuickAgentState, config: RunnableConfig) -> dict:
    messages = cast(list, state.get("supervisor_messages", []))
    if not messages:
        messages = cast(list, state.get("messages", []))

    last_message = messages[-1]
    tool_calls = last_message.tool_calls

    all_tools = await get_all_tools(config)
    tool_map = {t.name: t for t in all_tools}

    tool_outputs = []
    collected_documents = []

    for tc in tool_calls:
        name = tc["name"]
        args = tc["args"]
        tool_call_id = tc["id"]

        if name == "InternalDocumentSearch":
            query = args.get("query")

            qt_input = {
                "transformed_query": query,
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
                "_source_tool_call": tc,
            }

            try:
                # Sanitize config to prevent streaming internal events to the frontend
                # Explicitly set callbacks to empty list to suppress event emission
                clean_config = {
                    "configurable": config.get("configurable", {}),
                    "callbacks": [],
                }
                qt_result = await query_transformer.ainvoke(qt_input, clean_config)

                completed_results = qt_result.get("_completed_query_results", [])
                if completed_results:
                    result = completed_results[0]
                    content = f"Internal Document Search Results:\n{result.get('transformed_context', 'No results found.')}"

                    docs = result.get("documents", [])
                    if docs:
                        collected_documents.extend(docs)
                        content += f"\n\n[System Notification]: Extracted {len(docs)} documents and added to final documents."
                else:
                    content = "No results found."

            except Exception as e:
                content = f"Error executing InternalDocumentSearch: {str(e)}"

            tool_outputs.append(ToolMessage(content=content, name=name, tool_call_id=tool_call_id))

        elif name in tool_map:
            tool = tool_map[name]
            content = await execute_tool_safely(tool, args, config)
            tool_outputs.append(ToolMessage(content=str(content), name=name, tool_call_id=tool_call_id))
        else:
            tool_outputs.append(ToolMessage(content=f"Tool {name} not found.", name=name, tool_call_id=tool_call_id))

    return {
        "supervisor_messages": tool_outputs,
        "final_documents": collected_documents,
    }


quick_agent_builder = StateGraph(state_schema=QuickAgentState, input_schema=QuickAgentState, output_schema=QuickAgentState, context_schema=Configuration)

quick_agent_builder.add_node(
    node=QUICK_AGENT_NODE,
    action=quick_agent,
    destinations=[END, QUICK_AGENT_TOOLS_NODE],
    metadata={
        "description": "Quick QA agent for fast, direct answers",
        "type": "agent_node",
        "interaction": "tool_calling",
        "criticality": "high",
        "llm_powered": True,
        "tool_binding": True,
        "expected_duration": "short",
        "max_iterations": 5,
        "dependencies": ["messages", "available_tools"],
        "outputs": ["final_report", "messages"],
    },
)

quick_agent_builder.add_node(
    node=QUICK_AGENT_TOOLS_NODE,
    action=quick_agent_tools,
    destinations=[QUICK_AGENT_NODE],
    metadata={
        "description": "Executes tools for the Quick Agent",
        "type": "tool_execution_node",
        "interaction": "external_apis",
        "criticality": "high",
        "command_based_routing": True,
        "async_execution": True,
        "expected_duration": "variable",
        "tool_types": ["search", "web_scraping", "document_retrieval"],
        "dependencies": ["tool_calls"],
        "outputs": ["tool_results"],
    },
)

quick_agent_builder.add_edge(START, QUICK_AGENT_NODE)
quick_agent_builder.add_edge(QUICK_AGENT_TOOLS_NODE, QUICK_AGENT_NODE)


_RL = int(_os.getenv("GRAPH_RECURSION_LIMIT", "60"))
quick_agent_subgraph = quick_agent_builder.compile(
    debug=get_debug_mode(),
    name="quick_agent_subgraph",
    interrupt_before=None,
    interrupt_after=None,
).with_config({"recursion_limit": _RL})
