from langchain.tools import tool
from configuration.database import database
import logging

logger = logging.getLogger(__name__)


@tool(return_direct=True)
def execute_sql(sql: str) -> str:
    """
    Execute a SQL query and return the results.
    """
    try:
        return sql
    except Exception as e:
        return str(e)


def execute_sql_query(sql: str) -> dict:
    """
    Execute a SQL query and return the results in a structured format.
    This function is used for fallback queries.
    """
    try:
        logger.info(f"Executing SQL query: {sql}")
        cursor = database.execute_sql(sql)
        columns = [col[0] for col in cursor.description]

        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))

        return {"output": (True, results, sql)}
    except Exception as e:
        logger.error(f"Error executing SQL query: {e}")
        return {"output": (False, str(e), sql)}
