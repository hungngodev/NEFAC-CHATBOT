from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from llm.constant import QUERY_TRANSLATION_MODEL_NAME
from prompts import HYDE_FINAL_PROMPT, HYDE_GENERATION_PROMPT

model = ChatOpenAI(temperature=0, model_name=QUERY_TRANSLATION_MODEL_NAME)

hyde_prompt = ChatPromptTemplate.from_template(HYDE_GENERATION_PROMPT)

hyde_generation = hyde_prompt | model | StrOutputParser()

final_prompt = ChatPromptTemplate.from_template(HYDE_FINAL_PROMPT)


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
