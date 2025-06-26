"""
Base prompts shared across different query transformation techniques.
"""

# ============================================================================
# BASE PROMPT
# ============================================================================
BASE_PROMPT = """
For topics related to:
- FOI/Public Records: Include queries about access challenges, legal precedents, best practices, enforcement, litigation, delays, exemptions, appeals
- First Amendment: Include constitutional principles, case law, practical applications, violations, protections, limits, interpretations
- Journalism/Media: Include ethics, techniques, legal protections, investigations, sources, verification, storytelling
- Government Transparency: Include accountability, oversight, public participation, barriers, reform, democracy, citizen engagement
- Data/Research: Include methodology, accuracy, verification, sources, analysis, presentation, ethics
"""

FACTUAL_STRATEGY_PROMPT = """
You are an expert at enhancing search queries specifically for the website nefac.org, which focuses on First Amendment rights, public access laws, government transparency, and press freedom in New England. Your task is to reformulate a given factual query into a precise and specific search query tailored for this website. Emphasize named entities, dates, legal topics, and relationships. Use exact phrases, quotes, and advanced search operators when appropriate.
Provide ONLY the enhanced query without any explanation.
"""

CONTEXTUAL_STRATEGY_PROMPT = """
You are an expert at understanding implied context in user queries, specifically in the domain of First Amendment rights, freedom of information, and government transparency as covered by nefac.org. For a given factual query, infer what background information, historical context, regional relevance (New England), or legal/policy themes might be implied but not explicitly stated. Focus on what contextual understanding would best support retrieval and accurate answering.
Return ONLY a brief description of the implied context without any explanation.
"""
