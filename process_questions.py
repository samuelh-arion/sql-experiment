import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from agent import (
    create_pydantic_agent,
    create_sql_agent,
    create_sql_evaluation_agent,
    process_agent,
)
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            f'processing_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def evaluate_sql_equivalence(
    sql_evaluation_agent, original_sql, generated_sql, question
):
    """Evaluate if the generated SQL is equivalent to the original SQL in the context of the question."""
    try:
        evaluation_input = {
            "input": json.dumps(
                {"question": question, "query1": original_sql, "query2": generated_sql}
            )
        }
        evaluation_results = process_agent(sql_evaluation_agent, evaluation_input)

        # Log detailed evaluation results
        logger.info(f"SQL Evaluation Results for question: {question}")
        logger.info(f"Original SQL: {original_sql}")
        logger.info(f"Generated SQL: {generated_sql}")
        logger.info(f"Evaluation: {evaluation_results}")

        return evaluation_results.get("is_equivalent", False)
    except Exception as e:
        logger.error(f"Error during SQL evaluation: {str(e)}")
        return False


def process_single_question(question, sql_query):
    """Process a single question using both agents and evaluate results."""
    results = {
        "question": question,
        "original_sql": sql_query,
        "pydantic_agent": None,
        "sql_agent": None,
        "pydantic_agent_correct": False,
        "sql_agent_correct": False,
        "error": None,
    }

    try:
        # Initialize agents
        pydantic_agent = create_pydantic_agent()
        sql_agent = create_sql_agent()
        sql_evaluation_agent = create_sql_evaluation_agent()

        # Process with pydantic agent
        try:
            pydantic_results = process_agent(pydantic_agent, question)
            if isinstance(pydantic_results, dict) and "sql" in pydantic_results:
                results["pydantic_agent"] = pydantic_results["sql"]
            else:
                results["pydantic_agent"] = str(pydantic_results)
        except Exception as e:
            logger.error(f"Error in pydantic agent processing: {str(e)}")
            results["pydantic_agent"] = None
            results["error"] = f"Pydantic agent error: {str(e)}"

        # Process with SQL agent
        try:
            sql_results = sql_agent.invoke({"input": question})
            results["sql_agent"] = sql_results["output"]
        except Exception as e:
            logger.error(f"Error in SQL agent processing: {str(e)}")
            results["sql_agent"] = None
            results["error"] = f"SQL agent error: {str(e)}"

        # Only evaluate if both agents produced results
        if results["pydantic_agent"] and results["sql_agent"]:
            try:
                # Evaluate both agents against original SQL
                results["pydantic_agent_correct"] = evaluate_sql_equivalence(
                    sql_evaluation_agent, sql_query, results["pydantic_agent"], question
                )
                results["sql_agent_correct"] = evaluate_sql_equivalence(
                    sql_evaluation_agent, sql_query, results["sql_agent"], question
                )
            except Exception as e:
                logger.error(f"Error in SQL evaluation: {str(e)}")
                results["error"] = f"Evaluation error: {str(e)}"

    except Exception as e:
        logger.error(f"Error processing question: {question}")
        logger.error(f"Error details: {str(e)}")
        results["error"] = str(e)

    return results


def process_questions_parallel():
    """Process all questions from the dataset in parallel."""
    # Read the dataset
    df = pd.read_csv("dataset.csv")

    # Create a ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all questions for processing
        future_to_question = {
            executor.submit(process_single_question, row["question"], row["sql"]): row[
                "question"
            ]
            for _, row in df.iterrows()
        }

        # Process results as they complete
        results = []
        for future in as_completed(future_to_question):
            question = future_to_question[future]
            try:
                result = future.result()
                results.append(result)
                logger.info(f"Completed processing question: {question}")
            except Exception as e:
                logger.error(f"Error processing question: {question}")
                logger.error(f"Error details: {str(e)}")
                results.append(
                    {
                        "question": question,
                        "original_sql": "",
                        "pydantic_agent": None,
                        "sql_agent": None,
                        "pydantic_agent_correct": False,
                        "sql_agent_correct": False,
                        "error": str(e),
                    }
                )

    # Save results to a file
    output_file = f"results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Results saved to {output_file}")
    return results


if __name__ == "__main__":
    logger.info("Starting parallel question processing")
    results = process_questions_parallel()
    logger.info("Completed parallel question processing")
