from typing import Dict, List, Optional, TypedDict, Union

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import RunnableConfig

from backend.src.config.settings import Configuration
from backend.src.schemas.core_types import AgentState, Validation


class ValidationAgentOutput(TypedDict):
    validation: Optional[Dict[str, Union[bool, str, float, List[str]]]]
    error: Optional[str]


def validation_agent(state: AgentState, config: RunnableConfig) -> ValidationAgentOutput:
    """
    Validates the generated answer.

    This function uses RunnableConfig for LangGraph Studio compatibility.
    """
    try:
        # Get configuration from RunnableConfig
        configuration = Configuration.from_runnable_config(config)

        model = init_chat_model(configuration.validation_model)

        # Use prompt from configuration (LangGraph Studio compatible)
        validation_prompt_text = configuration.validation_prompt

        validation_prompt = ChatPromptTemplate.from_template(validation_prompt_text)
        chain = validation_prompt | model.with_structured_output(Validation)

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
