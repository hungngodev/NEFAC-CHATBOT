import json
from typing import AsyncGenerator

from src.core.agents.graph import create_graph
from src.core.agents.state import AgentState


async def ask_llm_stream_agentic(query: str, convoHistory: str) -> AsyncGenerator[str, None]:
    """
    Streams the response from the agentic workflow.
    """
    graph = create_graph()
    inputs = AgentState(query=query, chat_history=convoHistory)
    i = 0
    async for event in graph.astream_events(inputs, version="v1"):
        kind = event["event"]
        if kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                yield f"data: {json.dumps({'message': content, 'order': i})}"
        elif kind == "on_tool_end":
            if event["name"] == "retrieval":
                output_data = event["data"].get("output", {})
                docs = output_data.get("documents", [])
                # Filter for documents with the specific stream_tag
                formatted = []
                for d in docs:
                    if d.metadata.get("stream_tag") == "final_retrieved_docs":
                        formatted.append(
                            {
                                "title": d.metadata.get("title"),
                                "summary": d.metadata.get("summary"),
                                "link": d.metadata.get("source"),
                                "type": d.metadata.get("type"),
                            }
                        )
                if formatted:
                    yield f"data: {json.dumps({'context': formatted, 'order': i})}"
        elif kind == "on_chain_stream":  # For reformulated queries from contextualize_q_chain
            if "contextualize_q_chain" in event.get("tags", []) and event["event"] == "on_chat_model_stream":
                r = event["data"]["chunk"].content
                if r:
                    yield f"data: {json.dumps({'reformulated': r, 'order': i})}"
        i += 1
