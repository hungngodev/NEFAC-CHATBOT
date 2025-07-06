
# The Contextualizer

The Contextualizer is a critical component at Level 2 of the hierarchical architecture that ensures query reliability and context awareness. It transforms user queries into **standalone, self-contained questions** while integrating conversation history, intent classification, and entity extraction for optimal downstream processing.

## The Problem it Solves: Context-Blindness

Agents and retrieval systems work best when the query they receive is explicit and unambiguous. However, users naturally speak in a conversational manner, often asking follow-up questions that rely on previous context.

**Example:**

1.  **User:** "Tell me about public records laws in Massachusetts."
2.  **User:** "What about for journalists?"

The second query, "What about for journalists?", is meaningless on its own. Without the context of the first question, a retrieval system would have no idea what to search for.

## Core Responsibilities

- **Query Contextualization:** Transforms user queries into standalone, self-contained questions using conversation history
- **Intent Classification:** Determines the type of query (document request, structured graph query, general query, etc.)
- **Entity Extraction:** Identifies and canonicalizes entities mentioned in the query
- **Memory Integration:** Incorporates relevant past interactions for context-aware processing
- **State Management:** Updates the `EnhancedAgentState` with processed query information

## Implementation Details

- **Location:** `src/core/agents/contextualizer/query_understanding.py`
- **Function:** `query_understanding_agent`
- **State Management:** Uses `EnhancedAgentState` with conversation history and memory context
- **LLM Integration:** Multiple specialized prompts for different processing tasks
- **Output:** Contextualized query, intent classification, extracted entities, and structured queries

**Example of Contextualization:**

- **Input History:** ["User: Tell me about public records laws in Massachusetts.", "User: What about for journalists?"]
- **Output `contextualized_query`:** "What are the public records laws in Massachusetts specifically for journalists?"

## Position in the Graph

The Contextualizer node sits immediately after the Supervisor and before any of the worker agents. This ensures that any agent that performs retrieval (both the simple `Retriever Worker` and the `ReAct Worker`) receives a clear, context-aware query to work with, dramatically improving the accuracy and reliability of their results.
