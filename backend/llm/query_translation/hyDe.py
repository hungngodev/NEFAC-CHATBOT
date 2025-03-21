from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

# Define the HyDE document generation chain
hyde_prompt = ChatPromptTemplate.from_template(
    """Please write a scientific paper passage to answer the question
Question: {question}
Passage:"""
)

hyde_generation = hyde_prompt | ChatOpenAI(temperature=0) | StrOutputParser()

# Define the full HyDE RAG pipeline
final_prompt = ChatPromptTemplate.from_template(
    """Answer the following question based on this context:
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
    | ChatOpenAI(temperature=0)
    | StrOutputParser()
    )
    return hyde_rag_chain
