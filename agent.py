from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain.agents import AgentExecutor
from langchain_openai.chat_models import ChatOpenAI
from langchain.agents.tool_calling_agent.base import create_tool_calling_agent
from configuration.config import config
from tools.employee_profile import get_employees, EmployeeFilterParams
from tools.employee_time_off import get_time_off, TimeOffFilterParams
from tools.execute_sql import execute_sql
from typing import Union, Annotated, Dict, Any, Literal
from pydantic import BaseModel, Field
from langchain.globals import set_debug
import logging
import traceback
import sys
from prompts import PYDANTIC_PROMPT, SQL_PROMPT, SQL_EVALUATION_PROMPT
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


class InvalidQuery(BaseModel):
    query_type: Literal["invalid"] = Field(..., description="The query type is invalid")


class PydanticResponse(BaseModel):
    response: Union[EmployeeFilterParams, TimeOffFilterParams, InvalidQuery] = Field(
        ..., description="The response from the agent, containing query parameters"
    )


class SQLEvaluationResponse(BaseModel):
    is_equivalent: bool = Field(
        ...,
        description="Whether the two SQL queries would produce functionally equivalent results for answering the original question",
    )


def create_pydantic_agent():
    # Initialize the language model
    chat_model = ChatOpenAI(
        model="gpt-4o-mini", api_key=config.OPENAI_KEY, temperature=0, max_tokens=1000
    )
    chat_model = chat_model.with_structured_output(
        PydanticResponse, method="json_schema"
    )
    return (
        ChatPromptTemplate.from_messages(
            [("system", PYDANTIC_PROMPT), ("user", "{input}")]
        )
        | chat_model
    )


def create_sql_agent():
    # Initialize the language model
    chat_model = ChatOpenAI(
        model="gpt-4o-mini", api_key=config.OPENAI_KEY, temperature=0, max_tokens=1000
    )

    # Create a simple prompt template
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SQL_PROMPT),
            ("user", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )
    tools = [execute_sql]

    # Create the agent using create_tool_calling_agent
    agent = create_tool_calling_agent(chat_model, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    return agent_executor


def create_sql_evaluation_agent():
    # Initialize the language model
    chat_model = ChatOpenAI(model="gpt-4o", api_key=config.OPENAI_KEY, temperature=0)
    chat_model = chat_model.with_structured_output(
        SQLEvaluationResponse, method="json_schema"
    )
    return (
        ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    SQL_EVALUATION_PROMPT,
                ),
                ("user", "{input}"),
            ]
        )
        | chat_model
    )


def process_agent(agent, question):
    response = agent.invoke({"input": question})

    if hasattr(response, "response"):
        response = response.response
    logger.info(f"Response: {response}")

    if isinstance(response, EmployeeFilterParams):
        return get_employees(response)
    elif isinstance(response, TimeOffFilterParams):
        return get_time_off(response)
    elif isinstance(response, InvalidQuery):
        return {"error": "Invalid query"}
    elif isinstance(response, SQLEvaluationResponse):
        return {
            "is_equivalent": response.is_equivalent,
        }
    else:
        return response


if __name__ == "__main__":
    # Create and use the agent
    logger.info("Initializing agents...")
    pydantic_agent = create_pydantic_agent()
    sql_agent = create_sql_agent()
    logger.info("Agents initialized successfully")

    while True:
        question = input("Enter a question: ")
        logger.info(f"Received question: {question}")

        # Process with pydantic agent
        logger.debug("Processing question with pydantic agent")
        try:
            pydantic_results = process_agent(pydantic_agent, question)
            print("\nEmployee/Time Off Query Results:", pydantic_results)

            sql_results = sql_agent.invoke({"input": question})
            print("\nSQL Query Results:", sql_results["output"])
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            print(f"\nError occurred: {str(e)}")
