"""
Prompts extracted from backend/llm/query_translation/decomposition.py
"""

from .base import BASE_PROMPT

# ============================================================================
# DECOMPOSITION PROMPT
# ============================================================================
DECOMPOSITION_PROMPT = f"""
You are an expert assistant for the New England First Amendment Coalition (NEFAC). Your role is to break down the user's complex question into exactly 3 focused, independently-answerable sub-questions to retrieve precise documents from our vector database of legal analyses, FOI guides, press-freedom resources, and relevant transcripts.
{BASE_PROMPT}
The sub-questions should:
1. Address specific legal rights, frameworks, or procedures relevant to the original question.
2. Identify related historical cases, precedents, or contextual background crucial to the topic.
3. Explore practical applications, examples, or implications for journalists or citizens in New England.

Original question: {{question}}

Output (exactly 3 queries, one per line):
"""

# ============================================================================
# QA TEMPLATE
# ============================================================================
QA_TEMPLATE = """
You are a NEFAC legal expert answering the following sub-question:
--- 
{sub_question}
---

Background information (previously answered sub-questions):
---
{q_a_pairs}
---

Additional relevant NEFAC context:
---
{context}
---

Use the context and background to answer precisely:
{sub_question}
"""

# ============================================================================
# FINAL SYNTHESIS TEMPLATE
# ============================================================================
FINAL_SYNTHESIS_TEMPLATE = """
    You are a NEFAC legal expert. Given the following sub-questions and answers:
    {context}

    Synthesize a cohesive, comprehensive response to the user's main question:
    {question}
    """
