import csv
import os
from langchain_openai.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from typing import List, Dict, Any
import logging
import traceback
import sys
from pydantic import BaseModel, Field
from datetime import datetime
from configuration.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("expand-dataset.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# Define the model for alternative questions
class AlternativeQuestions(BaseModel):
    alternatives: List[str] = Field(
        ...,
        description="A list of alternative questions that should produce the same SQL query as the original question",
    )


def read_dataset(file_path: str) -> List[Dict[str, str]]:
    """Read the original dataset CSV file."""
    dataset = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # Use csv.reader to handle complex CSV with quotes properly
            reader = csv.DictReader(f)
            for row in reader:
                dataset.append(row)
        logger.info(f"Read {len(dataset)} rows from {file_path}")
    except Exception as e:
        logger.error(f"Error reading dataset file: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise
    return dataset


def create_question_generator():
    """Create an LLM for generating alternative questions."""
    try:
        chat_model = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=config.OPENAI_KEY,
            temperature=0.7,  # Use some temperature for more diverse alternatives
        )

        # Use structured output for the model to return a list of alternatives
        chat_model = chat_model.with_structured_output(
            AlternativeQuestions, method="json_schema"
        )

        # Create a prompt template
        system_template = """You are an expert at generating alternative ways to ask the same database query question.
Given an original question and its corresponding SQL query, generate {num_alternatives} alternative phrasings of the question that would result in the same SQL query being executed.

The alternatives should:
1. Vary in wording, syntax, and style but maintain the same semantic meaning
2. Include different question formats (direct questions, indirect questions, commands)
3. Use synonyms and different ways of expressing the same concepts
4. Range from formal to informal tone
5. Be realistic questions that a human might ask

ONLY return the alternative questions as a JSON list. Do not include any explanations or the original question.
"""

        prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", system_template),
                (
                    "user",
                    "Original question: {original_question}\nSQL query: {sql_query}\n\nGenerate {num_alternatives} alternative questions that should produce the same SQL result.",
                ),
            ]
        )

        return prompt_template | chat_model
    except Exception as e:
        logger.error(f"Error creating question generator: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


def generate_alternatives(
    dataset: List[Dict[str, str]], generator, num_alternatives: int = 20
) -> List[Dict[str, str]]:
    """Generate alternative questions for each question in the dataset."""
    expanded_dataset = []

    for i, row in enumerate(dataset):
        original_question = row["question"]
        sql_query = row["sql"]

        logger.info(
            f"Processing question {i+1}/{len(dataset)}: {original_question[:50]}..."
        )

        try:
            # Generate alternatives using the LLM
            response = generator.invoke(
                {
                    "original_question": original_question,
                    "sql_query": sql_query,
                    "num_alternatives": num_alternatives,
                }
            )

            alternatives = response.alternatives

            # Add each alternative to the expanded dataset
            for alt in alternatives:
                expanded_dataset.append(
                    {
                        "original-question": original_question,
                        "alternative-question": alt,
                        "sql": sql_query,
                    }
                )

            logger.info(
                f"Generated {len(alternatives)} alternatives for question {i+1}"
            )

        except Exception as e:
            logger.error(f"Error generating alternatives for question {i+1}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Continue with the next question even if this one fails

    logger.info(f"Generated a total of {len(expanded_dataset)} alternative questions")
    return expanded_dataset


def write_expanded_dataset(data: List[Dict[str, str]], file_path: str):
    """Write the expanded dataset to a CSV file."""
    try:
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["original-question", "alternative-question", "sql"],
                quoting=csv.QUOTE_ALL,
            )  # Quote all fields to handle complex SQL queries
            writer.writeheader()
            writer.writerows(data)
        logger.info(f"Wrote {len(data)} rows to {file_path}")
    except Exception as e:
        logger.error(f"Error writing expanded dataset: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


def backup_dataset(file_path: str):
    """Create a backup of the output file if it already exists."""
    if os.path.exists(file_path):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = f"{file_path}.{timestamp}.bak"
        try:
            os.rename(file_path, backup_path)
            logger.info(f"Created backup of existing file: {backup_path}")
        except Exception as e:
            logger.error(f"Error creating backup: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")


def main():
    # Start time measurement
    start_time = datetime.now()
    logger.info("Starting dataset expansion process")

    try:
        # Define file paths
        input_file = "dataset.csv"
        output_file = "dataset-expanded.csv"

        # Create a backup of the output file if it exists
        backup_dataset(output_file)

        # Read the original dataset
        dataset = read_dataset(input_file)

        # Create the question generator
        generator = create_question_generator()

        # Generate alternative questions
        expanded_dataset = generate_alternatives(dataset, generator)

        # Write the expanded dataset
        write_expanded_dataset(expanded_dataset, output_file)

        # Calculate and log elapsed time
        elapsed_time = datetime.now() - start_time
        logger.info(f"Completed dataset expansion in {elapsed_time}")
        logger.info(f"Original dataset size: {len(dataset)} rows")
        logger.info(f"Expanded dataset size: {len(expanded_dataset)} rows")
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
