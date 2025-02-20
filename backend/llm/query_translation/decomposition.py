from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from operator import itemgetter
from load_env import load_env
load_env()

# Define all components
llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo")

# 1. Sub-question Generation Chain
decomposition_template = """You are a helpful assistant that generates multiple sub-questions related to an input question. 
The goal is to break down the input into a set of sub-problems that can be answered in isolation.
Generate multiple search queries related to: {question}
Output (3 queries):"""
prompt_decomposition = ChatPromptTemplate.from_template(decomposition_template)
generate_queries_decomposition = (prompt_decomposition | llm | StrOutputParser() | (lambda x: x.split("\n")))

# 2. Individual Question Answering Chain
qa_template = """Here is the question you need to answer:
--- 
{question}
---

Here is any available background question + answer pairs:
---
{q_a_pairs}
---

Here is additional context relevant to the question:
---
{context}
---

Use the above context and background pairs to answer the question: {question}"""
decomposition_prompt = ChatPromptTemplate.from_template(qa_template)

def get_decomposition_chain(retriever):

    rag_chain = (
        {
            "context": itemgetter("question") | retriever,
            "question": itemgetter("question"),
            "q_a_pairs": itemgetter("q_a_pairs")
        }
        | decomposition_prompt
        | llm
        | StrOutputParser()
    )

    # 3. Formatting and Final Synthesis Chain
    final_template = """Here is a set of Q+A pairs:
    {context}

    Use these to synthesize an answer to the question: {question}"""
    final_prompt = ChatPromptTemplate.from_template(final_template)
    final_rag_chain = final_prompt | llm | StrOutputParser()

    # Main Processing Chain
    def format_qa_pair(question, answer):
        return f"Question: {question}\nAnswer: {answer}"

    def process_sub_questions(input_dict):
        main_question = input_dict["question"]
        sub_questions = generate_queries_decomposition.invoke({"question": main_question})
        
        q_a_pairs = []
        for q in sub_questions:
            current_context = "\n---\n".join(q_a_pairs) if q_a_pairs else ""
            answer = rag_chain.invoke({"question": q, "q_a_pairs": current_context})
            q_a_pairs.append(format_qa_pair(q, answer))
        
        return {
            "context": "\n---\n".join(q_a_pairs),
            "question": main_question
        }

    # Final end-to-end chain
    return (
        RunnableLambda(lambda x: {"question": x})
        | RunnableLambda(process_sub_questions)
        | final_rag_chain
    )
