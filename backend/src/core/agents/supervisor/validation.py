from typing import Dict, Union

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.schemas.state import AgentState
from src.schemas.supervisor import Validation

VALIDATION_PROMPT = ChatPromptTemplate.from_template(
    """You are a validator. Given the user's question, the retrieved text, and the answer, 
    determine if the answer fully answers the question using the text. 
    Respond with a JSON object with two fields: 'is_valid' (boolean) and 'reason' (string).

    Question: {question}
    Context: {context}
    Answer: {answer}
    """
)


def validation_agent(state: AgentState, model: ChatOpenAI) -> Dict[str, Union[str, Dict[str, Union[bool, str]]]]:
    """
    Validates the generated answer.
    """
    try:
        chain = VALIDATION_PROMPT | model.with_structured_output(Validation)

        result = chain.invoke(
            {
                "question": state.contextualized_query,
                "context": state.documents,
                "answer": state.answer,
            }
        )
        validation_result = Validation(**result)

        return {"validation": validation_result.dict()}
    except Exception as e:
        return {"error": str(e)}
