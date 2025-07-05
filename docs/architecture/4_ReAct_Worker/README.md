
# The ReAct Worker

The ReAct Worker is the most sophisticated component at Level 3 of the hierarchical architecture, designed to handle complex, multi-step queries requiring advanced reasoning. It implements a **multi-step reasoning pattern** that breaks down complex problems into manageable sub-questions, iteratively gathering and synthesizing information to provide comprehensive answers.

## Core Responsibilities

- **Complex Query Processing:** Handles queries requiring multi-step analysis and reasoning
- **Sub-Question Generation:** Intelligently breaks down complex queries into logical sub-questions
- **Iterative Information Gathering:** Uses retrieval tools to gather information for each sub-question
- **Context Synthesis:** Combines information from multiple retrieval steps into coherent context
- **Adaptive Reasoning:** Adjusts reasoning strategy based on gathered information
- **Comprehensive Answer Generation:** Synthesizes all findings into a complete, well-structured response

## Implementation Details

- **Location:** `src/core/agents/workers/react/react_worker.py`
- **Function:** `multi_step_reasoning_agent`
- **State Management:** Uses `EnhancedAgentState` with conversation history and retrieval selection
- **Reasoning Pattern:** Implements iterative sub-question generation and information synthesis
- **Maximum Steps:** Configurable limit (default: 3) to prevent infinite loops while ensuring thorough analysis
- **Tool Integration:** Leverages the Retriever Worker for information gathering at each reasoning step
- **Context Processing:** Uses context processor for extracting structured information and citations
- **Final Synthesis:** Combines all gathered information into a comprehensive final answer

## Multi-Step Reasoning Process

### Step 1: Sub-Question Generation
- Analyzes the main question and current context
- Generates the next logical sub-question to gather missing information
- Determines when sufficient information has been collected ("FINAL_ANSWER")

### Step 2: Information Retrieval
- Creates temporary state for the sub-question
- Invokes the Retriever Worker with the sub-question
- Processes retrieved documents through the context processor

### Step 3: Context Synthesis
- Integrates new information with existing context
- Maintains structured information and citations
- Prepares context for next iteration or final synthesis

## Example Workflow

For a query like "Compare the public records laws in Massachusetts and Rhode Island," the ReAct Worker might follow these steps:

1.  **Thought:** I need to find information about the public records laws in Massachusetts.
2.  **Action:** Call the `retrieval_tool` with the query "public records laws in Massachusetts."
3.  **Observation:** Receive a set of documents about Massachusetts public records laws.
4.  **Thought:** Now I need to find information about the public records laws in Rhode Island.
5.  **Action:** Call the `retrieval_tool` with the query "public records laws in Rhode Island."
6.  **Observation:** Receive a set of documents about Rhode Island public records laws.
7.  **Thought:** I now have information about both states. I have enough information to answer the user's query.
8.  **Finish:** Exit the loop and pass the collected documents to the Final Answer Synthesizer.

This ability to break down a problem and iteratively gather information makes the ReAct Worker an essential component for handling the most complex user queries.
