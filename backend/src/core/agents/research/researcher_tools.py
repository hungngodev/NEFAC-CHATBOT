from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Send

from src.config.node_names import QUERY_TRANSFORMER_NODE, RESEARCH_COMPRESS_RESEARCH, RESEARCH_RESEARCHER
from src.config.settings import Configuration
from src.core.agents.research.utils import emit_research_status
from src.core.agents.tools.main import get_all_tools
from src.core.agents.tools.misc_utils import execute_tool_safely, safe_get
from src.core.agents.tools.search import anthropic_websearch_called, openai_websearch_called
from src.schemas.state import ResearcherState


def _is_tool_message(msg) -> bool:
    if isinstance(msg, ToolMessage):
        return True
    if isinstance(msg, dict):
        role = msg.get("role") or msg.get("type")
        return role == "tool"
    return safe_get(msg, "type") == "tool"


def _assistant_tool_calls(msg) -> list[dict]:
    calls = safe_get(msg, "tool_calls")
    if calls:
        return calls
    ak = safe_get(msg, "additional_kwargs", {}) or {}
    return ak.get("tool_calls") or []


def _last_ai_with_tool_calls(messages: list):
    if not messages:
        return None, []
    for idx in range(len(messages) - 1, -1, -1):
        tc = _assistant_tool_calls(messages[idx])
        if tc:
            return idx, tc
    return None, []


def _pending_tool_call_ids(messages: list[object]) -> set[str]:
    if not messages:
        return set()
    last_idx, tool_calls = _last_ai_with_tool_calls(messages)
    if last_idx is None or not tool_calls:
        return set()
    expected = {str(call.get("id")) for call in tool_calls if isinstance(call, dict) and call.get("id")}
    if not expected:
        return set()
    observed = set()
    # collect contiguous ToolMessages after that assistant
    for m in messages[last_idx + 1 :]:
        if not _is_tool_message(m):
            break
        tcid = safe_get(m, "tool_call_id")
        if tcid:
            observed.add(str(tcid))
    return expected - observed


async def researcher_tools(state: ResearcherState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    most_recent_message = researcher_messages[-1] if researcher_messages else None
    tool_call_iterations = state.get("tool_call_iterations", 0)

    # Calculate loop variables for progress tracking
    state.get("research_iterations", 0)
    getattr(configurable, "max_researcher_iterations", 3)
    max(1, configurable.max_react_tool_calls)

    async def run_tool_calls(tool_calls: list[dict]) -> tuple[list[ToolMessage], list[str]]:
        """Execute recognized tools and return (tool_messages, answered_ids_delta).

        Skips tool calls already answered to avoid duplicate ToolMessages.
        """
        if not tool_calls:
            return [], []
        tools = await get_all_tools(config)
        tools_by_name = {safe_get(tool, "name", safe_get(safe_get(tool, "metadata", {}), "get", lambda *_: None)("name") or "web_search"): tool for tool in tools}
        already_answered = set(state.get("_answered_tool_call_ids", []))
        outputs: list[ToolMessage] = []
        new_answered: list[str] = []
        for tc in tool_calls:
            name = tc.get("name")
            tcid = tc.get("id", "unknown")
            if tcid in already_answered:
                continue
            if name in tools_by_name:
                # Emit progress update for tool execution

                status_msg = f"Executing {name}..."
                if name == "InternalDocumentSearch":
                    status_msg = "Doing internal document search..."
                elif name and ("search" in name.lower() or "tavily" in name.lower()):
                    query_arg = tc.get("args", {}).get("query", "")
                    if len(query_arg) > 30:
                        query_arg = query_arg[:30] + "..."
                    status_msg = f"Searching online for: {query_arg}"

                emit_research_status(status=status_msg)
                observation = await execute_tool_safely(tools_by_name[name], tc.get("args", {}), config)
                outputs.append(ToolMessage(content=observation, name=name, tool_call_id=tcid))
                new_answered.append(tcid)
            else:
                outputs.append(
                    ToolMessage(
                        content=f"Unsupported tool '{name}' not available; proceeding without execution.",
                        name=name,
                        tool_call_id=tcid,
                    )
                )
                new_answered.append(tcid)
        return outputs, new_answered

    # Hard cap guard: if over the cap, do not dispatch or execute tools —
    # instead, reply to any pending tool_call_ids with a cap-reached ToolMessage,
    # then route to compression.
    if tool_call_iterations >= configurable.max_react_tool_calls:
        pending_ids = _pending_tool_call_ids(researcher_messages)
        cap_messages: list[ToolMessage] = []
        if most_recent_message:
            tool_calls = _assistant_tool_calls(most_recent_message)
            for tc in tool_calls:
                tcid = tc.get("id")
                if not tcid or tcid not in pending_ids:
                    continue
                name = tc.get("name") or "tool"
                cap_messages.append(
                    ToolMessage(
                        content=("Max tool-call iterations reached; skipping further execution for this tool. " "Proceeding to summarize current findings."),
                        name=name,
                        tool_call_id=tcid,
                    )
                )
        if cap_messages:
            return Command(
                goto=RESEARCH_COMPRESS_RESEARCH,
                update={
                    "researcher_messages": cap_messages,
                    "_answered_tool_call_ids": list(pending_ids),
                },
            )
        # No pending tool calls to satisfy — go straight to compress
        return Command(goto=RESEARCH_COMPRESS_RESEARCH)

    # Process query transformer results if available
    completed_query_results = state.get("_completed_query_results", [])

    if completed_query_results:
        query_tool_messages: list[ToolMessage] = []
        collected_documents = []
        strategy_map = {
            "multiquery": "multi-perspective search",
            "decompose": "sub-question analysis",
            "stepback": "conceptual framework search",
            "hyde": "hypothetical document matching",
            "factual": "factual precision search",
            "contextual": "contextual expansion search",
        }
        for query_result in completed_query_results:
            source_tool_call = query_result.get("_source_tool_call", {})
            transformed_context = query_result.get("transformed_context", "")
            method_used = query_result.get("method_used", "default")
            docs = query_result.get("documents", [])

            if docs:
                collected_documents.extend(docs)

            if source_tool_call and transformed_context:
                strategy_info = f" (using {strategy_map.get(method_used, method_used)})" if method_used != "default" else ""
                header = f"Internal Document Search Results{strategy_info}"
                content = f"{header}\n{'='*80}\n{transformed_context}"

                if docs:
                    content += f"\n\n[System Notification]: Extracted {len(docs)} documents and added to researcher state."

                query_tool_messages.append(
                    ToolMessage(
                        content=content,
                        name="InternalDocumentSearch",
                        tool_call_id=source_tool_call.get("id", "unknown"),
                    )
                )
        return Command(
            goto=RESEARCH_RESEARCHER,
            update={
                # Append only the new ToolMessages (delta)
                "researcher_messages": query_tool_messages,
                # Clear consumed results using override semantics
                "_completed_query_results": {"type": "override", "value": []},
                # Update documents in state
                "documents": collected_documents,
            },
        )

    # Early exit if no tool calls were made
    if not most_recent_message or (not most_recent_message.tool_calls and not (openai_websearch_called(most_recent_message) or anthropic_websearch_called(most_recent_message))):
        return Command(goto=RESEARCH_COMPRESS_RESEARCH)

    # Check for internal document search calls
    tool_calls = most_recent_message.tool_calls
    internal_search_calls = [tool_call for tool_call in tool_calls if tool_call["name"] == "InternalDocumentSearch"]
    other_tool_calls = [tool_call for tool_call in tool_calls if tool_call["name"] != "InternalDocumentSearch"]

    # Delegate internal document search calls to query transformer
    if internal_search_calls:
        # Deduplicate queries within this turn (case/whitespace normalized)
        def _norm_query(q: str) -> str:
            return " ".join((q or "").strip().lower().split())

        deduped_internal_calls = []
        seen = set()
        for tc in internal_search_calls:
            nq = _norm_query(tc.get("args", {}).get("query", ""))
            if nq and nq not in seen:
                seen.add(nq)
                deduped_internal_calls.append(tc)

        # Enforce per-turn cap for internal search
        cap = max(2, int(configurable.max_internal_search_calls_per_turn))
        to_dispatch_calls = deduped_internal_calls[:cap]
        overflow_calls = deduped_internal_calls[cap:]

        emit_research_status(status=f"Dispatching {len(to_dispatch_calls)} queries to transformer...")

        query_transformer_sends = [
            Send(
                QUERY_TRANSFORMER_NODE,
                {
                    "transformed_query": tc["args"]["query"],
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
                },
            )
            for tc in to_dispatch_calls
        ]
        other_tool_outputs, new_ids = await run_tool_calls(other_tool_calls)
        # Build overflow ToolMessages to satisfy API requirements without executing them now
        overflow_messages: list[ToolMessage] = []
        for tc in overflow_calls:
            overflow_messages.append(
                ToolMessage(
                    content=(f"Deferred InternalDocumentSearch due to per-turn cap ({cap}). " "If still needed, propose this query again in a later iteration."),
                    name="InternalDocumentSearch",
                    tool_call_id=tc.get("id", "unknown"),
                )
            )
        # Append only new tool replies (delta) after the assistant tool_calls
        return Command(
            goto=query_transformer_sends,
            update={
                "researcher_messages": other_tool_outputs + overflow_messages,
                **({"_answered_tool_call_ids": new_ids + [tc.get("id", "unknown") for tc in overflow_calls]} if (new_ids or overflow_calls) else {}),
            },
        )

    # Standard tool execution for non-internal-search tools
    tool_outputs, new_ids = await run_tool_calls(tool_calls)

    if state.get("tool_call_iterations", 0) >= configurable.max_react_tool_calls or any(tool_call["name"] == "ResearchComplete" for tool_call in most_recent_message.tool_calls):
        update_payload: dict[str, Any] = {"researcher_messages": tool_outputs}
        if new_ids:
            update_payload["_answered_tool_call_ids"] = new_ids
        return Command(goto=RESEARCH_COMPRESS_RESEARCH, update=update_payload)

    update_payload = {"researcher_messages": tool_outputs}
    if new_ids:
        update_payload["_answered_tool_call_ids"] = new_ids

    emit_research_status(status="Analyzing tool outputs...")

    return Command(goto=RESEARCH_RESEARCHER, update=update_payload)
