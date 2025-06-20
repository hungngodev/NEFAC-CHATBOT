from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from llm.constant import PROMPT_MODEL_NAME, BASE_PROMPT


model = ChatOpenAI(temperature=0, model_name=PROMPT_MODEL_NAME)

hyde_prompt = ChatPromptTemplate.from_template(
    f"""
You are an AI assistant specialized in legal and First Amendment topics for the New England First Amendment Coalition (NEFAC).

To effectively retrieve relevant case studies, legal analyses, press freedom guides, and related NEFAC resources from our vector database, generate a hypothetical, concise, and informative legal passage that could directly address the user's question.
{BASE_PROMPT} 

The synthesized passage should:
- Clearly resemble a NEFAC-authored case analysis, legal summary, or practical guidance document.
- Include specific legal terminology, relevant case precedents, or practical implications where applicable.
- Be focused, authoritative, and realistic enough to effectively query our document and transcript database.

User Question: {{question}}

Synthesized Legal Passage:
"""
)

hyde_generation = hyde_prompt | ChatOpenAI(temperature=0) | StrOutputParser()

final_prompt = ChatPromptTemplate.from_template(
    """
Answer the following question based on the NEFAC-related documents and resources provided below:

{context}

Question: {question}
"""
)


def get_hyDe_chain(retriever):
    """Get the HyDE chain."""
    hyde_rag_chain = (
    # Generate hypothetical document
    {"context": hyde_generation | retriever, "question": lambda x: x["question"]}
    | final_prompt
    | model
    | StrOutputParser()
    )
    return hyde_rag_chain
