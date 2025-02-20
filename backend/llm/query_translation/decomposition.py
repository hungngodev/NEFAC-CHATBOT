from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain.schema.runnable import RunnableParallel, RunnableLambda
from operator import itemgetter

# Decomposition Prompt
decomposition_prompt = ChatPromptTemplate.from_template(
    """You are a helpful assistant that generates multiple sub-questions related to an input question. 
The goal is to break down the input into a set of sub-problems / sub-questions that can be answered in isolation.
Generate multiple search queries related to: {question}
Output (3 queries):"""
)

# LLM
llm = ChatOpenAI(model_name="gpt-4", temperature=0)

# Output Parser
output_parser = StrOutputParser()

# Function to format Q+A pairs
def format_qa_pair(question, answer):
    return f"Question: {question}\nAnswer: {answer}"

# Chain to generate sub-questions
generate_queries_chain = decomposition_prompt | llm | output_parser | (lambda x: x.split("\n"))

# Answering Prompt
answering_prompt = ChatPromptTemplate.from_template(
    """Here is the question you need to answer:
    \n --- \n {question} \n --- \n
    Here is any available background question + answer pairs:
    \n --- \n {q_a_pairs} \n --- \n
    Here is additional context relevant to the question: 
    \n --- \n {context} \n --- \n
    Use the above context and any background question + answer pairs to answer the question: {question}"""
)

def process_sub_questions(inputs, retriever):
    """Retrieves context and answers sub-questions sequentially"""
    sub_questions = generate_queries_chain.invoke({"question": inputs["question"]})
    q_a_pairs = ""

    for sub_q in sub_questions:
        rag_chain = (
            {"context": itemgetter("question") | retriever, "question": sub_q, "q_a_pairs": q_a_pairs} 
            | answering_prompt
            | llm
            | output_parser
        )
        answer = rag_chain.invoke({"question": sub_q, "q_a_pairs": q_a_pairs})
        q_a_pairs += f"\n---\n{format_qa_pair(sub_q, answer)}"

    return {"q_a_pairs": q_a_pairs}

def get_decomposition_chain(retriever):
    """Final Chain"""
    return RunnableParallel(
        {
            "question": itemgetter("question"),
            "q_a_pairs": RunnableLambda(lambda x: process_sub_questions(x, retriever))
        }
    ) | answering_prompt | llm | output_parser
