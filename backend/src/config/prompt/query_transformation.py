"""
Query transformation prompts for the NEFAC chatbot system.
"""

# ============================================================================
# QUERY TRANSLATION PROMPTS
# ============================================================================

DEFAULT_QUERY_TRANSORMER_PROMPT = """Analyze the question and choose the best query transformation strategy:

You are an assistant for the New England First Amendment Coalition (NEFAC). 
Your task is to generate exactly 5 search queries that will be used to search through a vector database 
containing YouTube video transcripts, summaries, and documents related to NEFAC's work.

Make these queries ABSTRACT and COMPREHENSIVE - think about what information would make you give the BEST possible answer, even if it's not directly mentioned in the question.

IMPORTANT: Be creative and expansive in your search. Consider:
- Historical context and evolution of the topic
- Legal frameworks and precedents
- Best practices and methodologies
- Common challenges and innovative solutions
- Cross-cutting themes that might illuminate the topic
- Expert perspectives and professional advice
- Real-world examples and case studies

For topics related to:
- FOI/Public Records: Include queries about access challenges, legal precedents, best practices, enforcement, litigation, delays, exemptions, appeals
- First Amendment: Include constitutional principles, case law, practical applications, violations, protections, limits, interpretations
- Journalism/Media: Include ethics, techniques, legal protections, investigations, sources, verification, storytelling
- Government Transparency: Include accountability, oversight, public participation, barriers, reform, democracy, citizen engagement
- Data/Research: Include methodology, accuracy, verification, sources, analysis, presentation, ethics

1. multiquery - Use for ambiguous or open-ended questions where multiple interpretations or perspectives are possible. Generate several diverse queries to cover different angles.
2. ragfusion - Use for complex or multifaceted questions that may require combining results from several distinct queries. Useful when a single query is unlikely to retrieve all relevant information.
3. stepback - Use for specific questions that may benefit from broader context or reframing. Reformulate the question to a more general or foundational one to improve retrieval.
4. decompose - Use for multi-part or compound questions. Break the main question into several sub-questions to ensure comprehensive coverage.
5. hyde - Use for technical, hypothetical, or highly specialized questions. Generate a hypothetical answer or document to guide retrieval.
6. factual - Use for straightforward factual questions where precision and specificity are critical. Reformulate the query to emphasize named entities, dates, legal topics, and relationships, using exact phrases and advanced search operators if appropriate.
7. contextual - Use when the question is missing important background, historical, regional (New England), or legal/policy context. Infer and add the implied context to the query to improve retrieval accuracy.
8. multi-step - Use for complex analytical questions requiring step-by-step reasoning. Breaks down complex queries into sequential reasoning steps, each building on previous context and findings.
9. default - Use for simple, direct questions that do not require Any special handling or transformation.

Examples of when to use each method:
- "What are the main challenges to public records access in Vermont?" → factual
- "How has the First Amendment been interpreted in New England courts?" → multiquery
- "Explain the evolution of press freedom laws in the US." → ragfusion
- "What is the process for filing a FOIA request and appealing a denial?" → decompose
- "Can I film police during a protest in Massachusetts?" → stepback
- "What if a journalist hypothetically faces a subpoena for confidential sources?" → hyde
- "What are the legal rights around recording public officials in Massachusetts?" (missing context about public spaces, state law, etc.) → contextual
- "Analyze the impact of recent Supreme Court decisions on student free speech rights in public schools." → multi-step
- "What is NEFAC?" → default
Question: {question}
Respond ONLY with the method name."""

DEFAULT_CONTEXTUAL_STRATEGY_PROMPT = """You are an expert at understanding implied context in user queries, specifically in the domain of First Amendment rights, freedom of information, and government transparency as covered by NEFAC (New England First Amendment Coalition).

Your task is to analyze a factual query and infer what background information, historical context, regional relevance (New England), or legal/policy themes might be implied but not explicitly stated in the query.

**Context Analysis Framework:**
1. **Regional Context**: Consider New England-specific legal frameworks, state variations, and regional precedents
2. **Historical Context**: Identify relevant historical background, legal evolution, and precedential cases
3. **Legal Framework Context**: Understand the broader legal principles and constitutional foundations
4. **Practical Context**: Consider real-world applications and practical implications
5. **Stakeholder Context**: Identify relevant parties, organizations, and interests involved

**Contextual Dimensions to Consider:**
- **Legal Precedents**: Relevant case law and legal foundations
- **Jurisdictional Variations**: State-specific laws and regulations across New England
- **Historical Evolution**: How laws and practices have changed over time
- **Practical Applications**: Real-world implementation and common scenarios
- **Challenges and Barriers**: Common obstacles and limitations
- **Best Practices**: Recommended approaches and successful strategies
- **Stakeholder Perspectives**: Different viewpoints from journalists, citizens, government, legal professionals

**Output Guidelines:**
- Provide a brief, focused description of the implied contextual elements
- Focus on contextual understanding that would best support retrieval and accurate answering
- Do not provide explanations or reasoning, just the contextual insights
- Consider what background knowledge would make the query more complete and searchable

Return ONLY a brief description of the implied context without Any explanation or additional commentary."""

DEFAULT_DECOMPOSITION_GENERATE_PROMPT = """You are an expert assistant for the New England First Amendment Coalition (NEFAC). Your role is to break down the user's complex question into exactly 3 focused, independently-answerable sub-questions to retrieve precise documents from our vector database of legal analyses, FOI guides, press-freedom resources, and relevant transcripts.

The sub-questions should:
1. Address specific legal rights, frameworks, or procedures relevant to the original question.
2. Identify related historical cases, precedents, or contextual background crucial to the topic.
3. Explore practical applications, examples, or implications for journalists or citizens in New England.

Original question: {question}

Output (exactly 3 queries, one per line):
"""

DEFAULT_DECOMPOSITION_QA_TEMPLATE = """You are a NEFAC legal expert answering the following sub-question:
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

DEFAULT_DECOMPOSITION_SYNTHESIS_TEMPLATE = """You are a NEFAC legal expert. Given the following sub-questions and answers:
{context}

Synthesize a cohesive, comprehensive response to the user's main question:
{question}
"""

DEFAULT_FACTUAL_STRATEGY_PROMPT = """You are an expert at refining user queries for precise factual retrieval from NEFAC's database of legal analyses, press freedom guides, and government transparency resources.

Your task is to reformulate the user's question to emphasize factual elements, named entities, dates, legal topics, and relationships using exact phrases and precise terminology for optimal retrieval.

Focus on:
- Specific legal terms, statutes, and case names
- Exact dates, time periods, and jurisdictions
- Named entities (people, organizations, locations)
- Precise legal concepts and procedures
- Specific document types or resources

Original question: {question}

Reformulated factual query:"""

DEFAULT_HYDE_GENERATION_PROMPT = """
You are an AI assistant specialized in legal and First Amendment topics for the New England First Amendment Coalition (NEFAC).

To effectively retrieve relevant case studies, legal analyses, press freedom guides, and related NEFAC resources from our vector database, generate a hypothetical, concise, and informative legal passage that could directly address the user's question.

The synthesized passage should:
- Clearly resemble a NEFAC-authored case analysis, legal summary, or practical guidance document.
- Include specific legal terminology, relevant case precedents, or practical implications where applicable.
- Be focused, authoritative, and realistic enough to effectively query our document and transcript database.

User Question: {question}

Synthesized Legal Passage:
"""

DEFAULT_HYDE_FINAL_PROMPT = """
Answer the following question based on the NEFAC-related documents and resources provided below:

{context}

Question: {question}
"""

DEFAULT_MULTI_QUERY_PERSPECTIVES_PROMPT = """
You are an AI assistant for the New England First Amendment Coalition (NEFAC).  
Perform a multi-query translation of the user's question by generating exactly five search queries (one per line) to retrieve diverse, relevant materials—transcripts, summaries, and docs—from our vector store.  

Each query should contain one of the following perspectives:

1. Restate the core question to find precise answers.  
2. Widen the frame to include New England's free-speech and press-freedom context.  
3. Surface related legal concepts, precedents, or foundational First Amendment principles.  
4. Seek real-world NEFAC case studies, reports, or example applications.  
5. Highlight challenges, debates, or alternative perspectives on the topic.

Original question: {question}
"""

DEFAULT_STEP_BACK_GENERATE_PROMPT = """
You are an expert in First Amendment law and public records processes in New England.
Your task is to take a user's question and "step back" to a broader, more answerable legal framing aligned with NEFAC's work.
Here are examples of reformulating specific questions into broader legal inquiries:
"""

DEFAULT_STEP_BACK_RESPONSE_PROMPT = """
Using both the original question and the stepped-back legal context, produce a comprehensive answer based on these sources:

# normal_context (direct retrieval results)
{normal_context}

# step_back_context (retrieved broader context)
{step_back_context}

Original Question: {question}
Answer:
"""
