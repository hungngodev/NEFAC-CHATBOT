"""
Specialized prompts configuration for the NEFAC chatbot system.
"""

from pydantic import BaseModel, Field

import src.config.node_names as node_names_module
import src.config.prompts as prompts_module


class RetrievalConfig(BaseModel):
    """Configuration for specialized prompts and templates."""

    cypher_generation_template: str = Field(
        default=prompts_module.DEFAULT_CYPHER_GENERATION_TEMPLATE,
        description="Template for generating Cypher queries for Neo4j.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.GRAPH_RETRIEVAL_GRAPH_TOOL_NODE],
            "langgraph_type": "prompt",
        },
    )

    graph_qa_prompt: str = Field(
        default=prompts_module.DEFAULT_GRAPH_QA_PROMPT,
        description="QA prompt for answering questions using knowledge graph context.",
        json_schema_extra={
            "langgraph_nodes": [node_names_module.GRAPH_RETRIEVAL_GRAPH_TOOL_NODE],
            "langgraph_type": "prompt",
        },
    )
