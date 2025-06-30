from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .state import AgentState


class Validation(BaseModel):
    """Validation of the answer against the context."""

    is_valid: bool = Field(
        description="Whether the answer is valid and supported by the context."
    )
    reason: str = Field(description="The reason for the validation result.")


VALIDATION_PROMPT = ChatPromptTemplate.from_template(
    """You are a validator. Given the user's question, the retrieved text, and the answer, 
    determine if the answer fully answers the question using the text. 
    Respond with a JSON object with two fields: 'is_valid' (boolean) and 'reason' (string).

    Question: {question}
    Context: {context}
    Answer: {answer}
    """
)


def validation_agent(state: AgentState, model: ChatOpenAI):
    """
    Validates the generated answer.
    """
    try:
        chain = VALIDATION_PROMPT | model.with_structured_output(Validation)

        validation_result = chain.invoke(
            {
                "question": state.contextualized_query,
                "context": state.documents,
                "answer": state.answer,
            }
        )

        return {"validation": validation_result.dict()}
    except Exception as e:
        return {"error": str(e)}
