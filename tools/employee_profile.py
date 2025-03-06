from configuration.database import Employees
from datetime import date, datetime
from langchain.tools import tool
from peewee import fn, SQL, Case
from playhouse.shortcuts import model_to_dict
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Literal, Annotated
import logging
from configuration.database import database
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmployeeFilterParams(BaseModel):
    query_type: Literal["employee"] = Field(
        ...,
        description="Type of filter: `employee`.",
    )
    select_columns: Optional[
        List[
            Literal[
                "id",
                "updated_at",
                "full_name",
                "nationality",
                "department",
                "is_manager",
                "location",
                "linkedin",
                "twitter_x",
                "facebook",
                "email",
                "is_active",
                "reports_to",
                "birth_date",
                "client",
            ]
        ]
    ] = Field(
        None,
        description="What fields are relevant?",
    )
    name: Optional[str] = Field(None, description="Name to filter by.")
    department: Optional[List[str]] = Field(
        None,
        description="List of internal organizational departments to filter by (e.g., Engineering, Sales, HR, Finance). This represents the employee's organizational unit.",
    )
    is_manager: Optional[bool] = Field(
        None, description="Boolean flag to filter by managerial status: True:False"
    )
    location: Optional[List[str]] = Field(
        None,
        description="List of locations to filter by.",
    )
    reports_to: Optional[str] = Field(None, description="Manager name to filter by.")
    from_next_birthday: Optional[str] = Field(
        None,
        description='Start date for filtering by next birthday. Format: "YYYY-MM-DD".',
    )
    to_next_birthday: Optional[str] = Field(
        None,
        description='End date for filtering by next birthday. Format: "YYYY-MM-DD".',
    )
    client: Optional[List[str]] = Field(
        None,
        description="List of work assignments to filter by. This can include external clients or internal assignments. Available options: "
        + ", ".join(
            [
                c.client
                for c in Employees.select(Employees.client).distinct()
                if c.client
            ]
        ),
    )
    return_as_count: Optional[bool] = Field(
        None,
        description="Returns the total number of employees that match all criteria.",
    )
    count_sort_desc: Optional[bool] = Field(
        None,
        description="if return_as_count is True sort the count DESC if True or ASC if False.",
    )


def build_employee_base_query(params):
    logger.info("Building base query with params: %s", params)

    # Select specific fields if provided, otherwise select all
    fields = []
    if params.select_columns:
        fields = [
            getattr(Employees, column)
            for column in params.select_columns
            if hasattr(Employees, column)
        ]

    # Build the appropriate query based on whether count is requested
    if params.return_as_count:
        if fields:
            query = Employees.select(
                *fields, fn.COUNT(Employees.id.distinct()).alias("total")
            )
        else:
            query = Employees.select(fn.COUNT(Employees.id.distinct()).alias("total"))
    else:
        query = Employees.select(*fields) if fields else Employees.select()

    # Only include active employees
    query = query.where(Employees.is_active)

    return query, fields


def apply_employee_name_filter(query, params):
    if params.name:
        for name in params.name.split(" "):
            query = query.where(Employees.full_name.contains(name))
    return query


def apply_employee_manager_filter(query, params):
    if params.is_manager is not None:
        query = query.where(Employees.is_manager == params.is_manager)
    return query


def apply_employee_location_filter(query, params):
    if params.location:
        location_list = [loc.lower() for loc in params.location if loc]
        if location_list:
            query = query.where(fn.LOWER(Employees.location).in_(location_list))
    return query


def apply_employee_reports_to_filter(query, params):
    if params.reports_to:
        # Join with the manager's record
        manager_alias = Employees.alias()
        query = query.join(
            manager_alias,
            on=(Employees.reports_to_id == manager_alias.id),
            attr="manager",
        )

        # Filter by manager's name
        for name in params.reports_to.split(" "):
            query = query.where(manager_alias.full_name.contains(name))
    return query


def validate_date_format(date_str):
    """Validate date format and return normalized date."""
    if not date_str:
        return None, "Date string is empty"

    logger.debug(f"Validating date format: {date_str}")

    # Try to parse as YYYY-MM-DD
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        # Check year range
        if date_obj.year < 1900 or date_obj.year > 2100:
            return None, "Invalid year range (1900-2100)"
        logger.debug(f"Parsed as YYYY-MM-DD: {date_str}")
        return date_str, None
    except ValueError:
        pass  # Try next format

    # If no valid format found
    return (
        None,
        f"Invalid date format: {date_str}. Only YYYY-MM-DD format is supported.",
    )


def apply_employee_birthday_filter(query, params):
    """Apply birthday filtering using complete dates."""
    if params.from_next_birthday or params.to_next_birthday:
        try:
            # Validate and parse the dates
            from_date, from_error = None, None
            to_date, to_error = None, None

            if params.from_next_birthday:
                from_date, from_error = validate_date_format(params.from_next_birthday)
                if from_error:
                    raise ValueError(f"From birthday: {from_error}")

            if params.to_next_birthday:
                to_date, to_error = validate_date_format(params.to_next_birthday)
                if to_error:
                    raise ValueError(f"To birthday: {to_error}")

            # Extract month and day from birth_date column and input dates
            birth_month = fn.CAST(fn.strftime("%m", Employees.birth_date), "INTEGER")
            birth_day = fn.CAST(fn.strftime("%d", Employees.birth_date), "INTEGER")

            # Initialize date components
            from_month, from_day = None, None
            to_month, to_day = None, None

            if from_date:
                # Parse month and day from normalized date string (YYYY-MM-DD format)
                try:
                    date_parts = from_date.split("-")
                    _, from_month, from_day = map(int, date_parts)
                    logger.debug(
                        f"From date parsed as month: {from_month}, day: {from_day}"
                    )
                except Exception as e:
                    logger.error(f"Error parsing from_date '{from_date}': {e}")
                    raise ValueError(
                        f"Invalid from_date format: {from_date}. Only YYYY-MM-DD format is supported."
                    )

            if to_date:
                # Parse month and day from normalized date string (YYYY-MM-DD format)
                try:
                    date_parts = to_date.split("-")
                    _, to_month, to_day = map(int, date_parts)
                    logger.debug(f"To date parsed as month: {to_month}, day: {to_day}")
                except Exception as e:
                    logger.error(f"Error parsing to_date '{to_date}': {e}")
                    raise ValueError(
                        f"Invalid to_date format: {to_date}. Only YYYY-MM-DD format is supported."
                    )

            # Determine if we're crossing a year boundary
            crossing_year = False
            if from_month is not None and to_month is not None:
                crossing_year = from_month > to_month or (
                    from_month == to_month and from_day > to_day
                )

            logger.debug(
                f"Processing birthday filter with from_month={from_month}, from_day={from_day}, to_month={to_month}, to_day={to_day}, crossing_year={crossing_year}"
            )

            # Apply the appropriate date filter logic
            if crossing_year and from_month is not None and to_month is not None:
                # For dates that cross year boundary (e.g. November to February)
                query = query.where(
                    (
                        (birth_month > from_month)
                        | (birth_month < to_month)
                        | ((birth_month == from_month) & (birth_day >= from_day))
                        | ((birth_month == to_month) & (birth_day <= to_day))
                    )
                )
            else:
                # For dates within the same year
                if from_month is not None:
                    query = query.where(
                        (birth_month > from_month)
                        | ((birth_month == from_month) & (birth_day >= from_day))
                    )

                if to_month is not None:
                    query = query.where(
                        (birth_month < to_month)
                        | ((birth_month == to_month) & (birth_day <= to_day))
                    )

        except ValueError as e:
            logger.exception("Invalid date format: %s", e)
            raise ValueError(f"Birthday filter error: {e}")
        except Exception as e:
            logger.exception("Error in birthday filter: %s", e)
            raise ValueError(f"Birthday filter error: {e}")

    return query


def apply_employee_department_filter(query, params):
    """Apply department filter to query.

    Filters by the employee's organizational department (e.g., Engineering, Sales).
    Department represents where an employee belongs in the organization structure.
    """
    if params.department:
        department_list = [dept.lower() for dept in params.department if dept]
        if department_list:
            query = query.where(fn.LOWER(Employees.department).in_(department_list))
    return query


def apply_employee_client_filter(query, params):
    """Apply client filter to query.

    Filters by the employee's work assignment, which can be:
    - External clients (e.g., Apollo, Marketing)
    - Internal assignments (e.g., Internal)
    Client represents what/who an employee is working for/with.
    """
    if params.client:
        client_list = [client.lower() for client in params.client if client]
        if client_list:
            query = query.where(fn.LOWER(Employees.client).in_(client_list))
    return query


def format_employee_results(query, fields, params):
    """Format query results."""
    try:
        if params.return_as_count and fields and len(fields) > 0:
            # If we're grouping by fields, ensure proper grouping and ordering
            query = query.group_by(*fields)

            if params.count_sort_desc:
                query = query.order_by(fn.COUNT(Employees.id.distinct()).desc())
            else:
                query = query.order_by(fn.COUNT(Employees.id.distinct()))

        return str(query)

    except Exception as e:
        logger.exception("Error formatting results: %s", e)
        return str(query)


def params_preprocess(params):
    """Preprocess and normalize parameters."""
    # Validate select columns
    if params.select_columns:
        select_key_renamed = {"country": "location", "twitter": "twitter_x"}
        params.select_columns = [
            select_key_renamed[c] if c in select_key_renamed else c
            for c in params.select_columns
        ]

        # Verify columns exist in the model
        invalid_columns = [
            column for column in params.select_columns if not hasattr(Employees, column)
        ]

        if invalid_columns:
            invalid_columns_str = ", ".join(invalid_columns)
            raise ValueError(f"Invalid column(s): {invalid_columns_str}")

    # Normalize string and list values
    for key, value in params.model_dump().items():
        if isinstance(value, list) and value is not None:
            # Normalize list values
            clean_values = [
                str(v).strip().lower() for v in value if v and str(v).strip()
            ]
            params.__setattr__(key, clean_values or None)

        elif isinstance(value, str) and value is not None:
            # Normalize string values
            params.__setattr__(key, str(value).strip().lower() or None)

    return params


# @tool(args_schema=EmployeeFilterParams, return_direct=True)
def get_employees(params: EmployeeFilterParams) -> Union[List[dict], str]:
    """
    Get employees based on filter parameters.
    """
    try:
        # Preprocess parameters
        params = params_preprocess(params)

        # Build base query
        query, fields = build_employee_base_query(params)

        # Apply filters in sequence
        filters = [
            apply_employee_name_filter,
            apply_employee_manager_filter,
            apply_employee_location_filter,
            apply_employee_reports_to_filter,
            apply_employee_birthday_filter,
            apply_employee_client_filter,
            apply_employee_department_filter,
        ]

        for filter_fn in filters:
            try:
                query = filter_fn(query, params)
            except Exception as e:
                filter_name = filter_fn.__name__.replace("apply_employee_", "")
                logger.exception("Error applying %s filter: %s", filter_name, e)
                return False, f"Error in {filter_name} filter: {e}", ""

        # Format and return results
        return format_employee_results(query, fields, params)

    except Exception as e:
        logger.exception("Error getting employees: %s", e)
        return False, f"Error retrieving employee data: {e}", ""
