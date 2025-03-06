from configuration.database import TimeOff, Employees
from datetime import datetime, timedelta, date
from langchain.tools import tool
from peewee import fn, SQL, Case
from playhouse.shortcuts import model_to_dict
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Literal, Annotated
from configuration.database import database
import logging
import re

logger = logging.getLogger(__name__)


class TimeOffFilterParams(BaseModel):
    query_type: Literal["time_off"] = Field(
        ...,
        description="Type of filter: `time_off`.",
    )
    type: Literal["past", "present", "future"] = Field(
        "present",
        description="Type of filter: `past`, `present` or `future`.",
    )
    from_date: Optional[str] = Field(
        None,
        description='Start date for filtering by time off start date. Only format "%Y-%m-%d" is supported, or relative terms like "next week", "last month".',
    )
    to_date: Optional[str] = Field(
        None,
        description='End date for filtering by time off end date. Only format "%Y-%m-%d" is supported, or relative terms like "next week", "last month".',
    )
    policy_type: Optional[str] = Field(
        None,
        description="Policy type to filter by (e.g., 'vacation leave', 'sick leave', 'annual leave', 'birthday day off').",
    )
    status: Optional[Literal["pending", "approved", "rejected"]] = Field(
        None,
        description="Status of the time off request.",
    )
    name: Optional[str] = Field(None, description="Employee name to filter by.")
    department: Optional[str] = Field(None, description="Department name to filter by.")
    duration_min: Optional[int] = Field(
        None, description="Minimum duration of time off in days."
    )
    duration_max: Optional[int] = Field(
        None, description="Maximum duration of time off in days."
    )
    return_as_count: Optional[bool] = Field(
        None,
        description="Returns the total number of time off records that match all criteria.",
    )
    count_sort_desc: Optional[bool] = Field(
        None,
        description="If return_as_count is True, sort the count DESC if True or ASC if False.",
    )
    select_columns: Optional[
        List[
            Literal[
                "id",
                "policy_type",
                "start_date",
                "end_date",
                "status",
                "employee_id",
                "department",
                "employee_name",
            ]
        ]
    ] = Field(
        None,
        description="What fields are relevant for grouping when using return_as_count.",
    )


def validate_time_off_params(params):
    """Validate parameters with improved error messages."""
    try:
        extra_fields = {
            k: v for k, v in params.model_dump().items() if k not in params.model_fields
        }
        if len(extra_fields) > 0:
            return False, f"Unrecognized fields: {', '.join(extra_fields.keys())}"

        # Validate policy_type if provided
        if params.policy_type and not isinstance(params.policy_type, str):
            return (
                False,
                f"policy_type must be a string, got {type(params.policy_type)}",
            )

        # Validate duration values if provided
        if params.duration_min is not None and params.duration_min < 1:
            return False, "duration_min must be at least 1"

        if params.duration_max is not None and params.duration_max < 1:
            return False, "duration_max must be at least 1"

        if params.duration_min is not None and params.duration_max is not None:
            if params.duration_min > params.duration_max:
                return (
                    False,
                    f"duration_min ({params.duration_min}) cannot be greater than duration_max ({params.duration_max})",
                )

        # Validate count parameters
        if params.return_as_count is True and not params.select_columns:
            logger.warning(
                "return_as_count is True but no select_columns provided. Will return total count only."
            )

        # Validate select_columns if provided
        valid_columns = [
            "id",
            "policy_type",
            "start_date",
            "end_date",
            "status",
            "employee_id",
            "department",
            "employee_name",
        ]

        if params.select_columns:
            invalid_columns = [
                col for col in params.select_columns if col not in valid_columns
            ]
            if invalid_columns:
                return (
                    False,
                    f"Invalid select_columns: {', '.join(invalid_columns)}. Valid options are: {', '.join(valid_columns)}",
                )

        return True, None
    except Exception as e:
        return False, f"Parameter validation error: {str(e)}"


def build_time_off_base_query(params=None):
    """Build the base query, joining employees and time off tables."""
    fields = []

    # Default query
    if params is None or not params.return_as_count:
        query = TimeOff.select(TimeOff, Employees).join(
            Employees, on=(TimeOff.employee_id == Employees.id), attr="employee"
        )
        query = query.where(Employees.is_active == True)
        return query, fields

    # Handle count queries
    if params.select_columns:
        # Map virtual fields to actual database fields
        field_mapping = {
            "id": TimeOff.id,
            "policy_type": TimeOff.policy_type,
            "start_date": TimeOff.start_date,
            "end_date": TimeOff.end_date,
            "status": TimeOff.status,
            "employee_id": TimeOff.employee_id,
            "department": Employees.department,
            "employee_name": Employees.full_name,
        }

        fields = [
            field_mapping[column]
            for column in params.select_columns
            if column in field_mapping
        ]

    # Build the count query
    if fields:
        query = TimeOff.select(
            *fields, fn.COUNT(TimeOff.id.distinct()).alias("total")
        ).join(Employees, on=(TimeOff.employee_id == Employees.id), attr="employee")
    else:
        query = TimeOff.select(fn.COUNT(TimeOff.id.distinct()).alias("total")).join(
            Employees, on=(TimeOff.employee_id == Employees.id), attr="employee"
        )

    query = query.where(Employees.is_active == True)

    return query, fields


def parse_relative_date(date_value):
    """Parse exact or relative date expressions."""
    if not date_value or not isinstance(date_value, str):
        return None, f"Invalid date value: {date_value}"

    date_value = date_value.lower().strip()
    today = datetime.now().date()

    # Handle exact date formats using strptime
    try:
        # Try YYYY-MM-DD format
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_value):
            return datetime.strptime(date_value, "%Y-%m-%d").date(), None
        else:
            # Invalid date format
            return None, f"Invalid date format. Only YYYY-MM-DD is supported."
    except ValueError as e:
        pass  # Continue to relative date handling

    # Mapping of common relative date expressions
    relative_date_mapping = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "yesterday": today - timedelta(days=1),
        "next week": today + timedelta(weeks=1),
        "last week": today - timedelta(weeks=1),
        "next month": date(
            today.year + (1 if today.month == 12 else 0),
            1 if today.month == 12 else today.month + 1,
            min(
                today.day,
                (
                    28
                    if (today.month % 12) + 1 == 2
                    else 30 if (today.month % 12) + 1 in [4, 6, 9, 11] else 31
                ),
            ),
        ),
        "last month": date(
            today.year - (1 if today.month == 1 else 0),
            12 if today.month == 1 else today.month - 1,
            min(
                today.day,
                (
                    28
                    if today.month - 1 == 2
                    else 30 if today.month - 1 in [4, 6, 9, 11] else 31
                ),
            ),
        ),
        "next year": date(today.year + 1, today.month, today.day),
        "last year": date(today.year - 1, today.month, today.day),
    }

    # Check for matches in our mapping
    if date_value in relative_date_mapping:
        return relative_date_mapping[date_value], None

    # Handle patterns like "in X days/weeks/months" and "X days/weeks/months ago"
    in_pattern = re.match(
        r"in (\d+) (day|days|week|weeks|month|months|year|years)", date_value
    )
    ago_pattern = re.match(
        r"(\d+) (day|days|week|weeks|month|months|year|years) ago", date_value
    )

    if in_pattern or ago_pattern:
        pattern = in_pattern or ago_pattern
        amount = int(pattern.group(1))
        unit = pattern.group(2).rstrip("s")  # Normalize singular/plural

        # Direction is future for "in X", past for "X ago"
        multiplier = 1 if in_pattern else -1

        if unit == "day":
            return today + timedelta(days=amount * multiplier), None
        elif unit == "week":
            return today + timedelta(weeks=amount * multiplier), None
        elif unit == "month":
            # Calculate month offset
            target_month = today.month + (amount * multiplier)
            target_year = today.year + (target_month - 1) // 12
            target_month = ((target_month - 1) % 12) + 1

            # Handle day overflow (e.g., Jan 31 -> Feb 28)
            max_day = (
                28 if target_month == 2 else 30 if target_month in [4, 6, 9, 11] else 31
            )
            target_day = min(today.day, max_day)

            return date(target_year, target_month, target_day), None
        elif unit == "year":
            return (
                date(today.year + (amount * multiplier), today.month, today.day),
                None,
            )

    return None, f"Unrecognized date format: {date_value}"


def apply_time_off_date_filters(query, params):
    """Apply date filters with improved handling of relative dates."""
    try:
        # Parse and validate dates
        from_date, to_date = None, None
        current_date = datetime.now().date()
        error_message = None

        if params.from_date:
            from_date, error = parse_relative_date(params.from_date)
            if error:
                return False, f"Invalid from_date: {error}", ""

        if params.to_date:
            to_date, error = parse_relative_date(params.to_date)
            if error:
                return False, f"Invalid to_date: {error}", ""

        # Apply type-based filters (past/present/future)
        if params.type == "present":
            query = query.where(
                (fn.date(TimeOff.start_date) <= fn.date("now"))
                & (fn.date(TimeOff.end_date) >= fn.date("now"))
            )
        elif params.type == "past":
            query = query.where(fn.date(TimeOff.end_date) < fn.date("now"))
        elif params.type == "future":
            query = query.where(fn.date(TimeOff.start_date) > fn.date("now"))

        # Apply date range filters if specified
        if from_date and to_date:
            # Ensure from_date is not after to_date
            if from_date > to_date:
                from_date, to_date = to_date, from_date
                logger.warning(
                    f"Swapped from_date and to_date since from_date ({from_date}) was after to_date ({to_date})"
                )

            # Filter time off periods that overlap with the specified date range
            try:
                query = query.where(
                    # Time off starts within range OR ends within range OR spans the entire range
                    (
                        (fn.date(TimeOff.start_date) >= from_date)
                        & (fn.date(TimeOff.start_date) <= to_date)
                    )
                    | (
                        (fn.date(TimeOff.end_date) >= from_date)
                        & (fn.date(TimeOff.end_date) <= to_date)
                    )
                    | (
                        (fn.date(TimeOff.start_date) <= from_date)
                        & (fn.date(TimeOff.end_date) >= to_date)
                    )
                )
            except Exception as e:
                logger.error(f"Error in date range filter: {e}")
                logger.error(f"Query before adding range filter: {query}")
                return False, f"Error in date range filter: {e}", str(query)
        else:
            # Apply individual date filters if specified
            try:
                if from_date:
                    query = query.where(fn.date(TimeOff.start_date) >= from_date)
                if to_date:
                    query = query.where(fn.date(TimeOff.end_date) <= to_date)
            except Exception as e:
                logger.error(f"Error in individual date filter: {e}")
                logger.error(f"Query before adding date filter: {query}")
                return False, f"Error in individual date filter: {e}", str(query)

        # Apply duration filters if specified
        if params.duration_min is not None or params.duration_max is not None:
            # Calculate duration in days
            try:
                duration_expr = (
                    fn.julianday(TimeOff.end_date)
                    - fn.julianday(TimeOff.start_date)
                    + 1
                )

                if params.duration_min is not None:
                    query = query.where(duration_expr >= params.duration_min)

                if params.duration_max is not None:
                    query = query.where(duration_expr <= params.duration_max)
            except Exception as e:
                logger.error(f"Error in duration filter: {e}")
                logger.error(f"Query before adding duration filter: {query}")
                return False, f"Error in duration filter: {e}", str(query)

    except ValueError as e:
        return False, f"Date filtering error: {e}", ""
    except Exception as e:
        logger.error(f"Unexpected error in date filtering: {e}")
        logger.error(f"Query state: {query}")
        return False, f"Unexpected error in date filtering: {e}", str(query)

    return query


def apply_time_off_policy_filter(query, params):
    """Apply policy type and status filters."""
    try:
        if params.policy_type:
            policy_value = params.policy_type.lower()
            # Check for pattern matches, not just exact matches
            if policy_value in ["vacation", "vacation leave"]:
                query = query.where(fn.LOWER(TimeOff.policy_type).contains("vacation"))
            elif policy_value in ["sick", "sick leave"]:
                query = query.where(fn.LOWER(TimeOff.policy_type).contains("sick"))
            elif policy_value in ["annual", "annual leave"]:
                query = query.where(fn.LOWER(TimeOff.policy_type).contains("annual"))
            elif policy_value in ["birthday", "birthday leave", "birthday day off"]:
                query = query.where(fn.LOWER(TimeOff.policy_type).contains("birthday"))
            else:
                # Generic case for other policy types
                query = query.where(
                    fn.LOWER(TimeOff.policy_type).contains(policy_value)
                )

        if params.status:
            query = query.where(TimeOff.status == params.status)
    except Exception as e:
        return False, f"Error in policy filtering: {e}", ""

    return query


def apply_time_off_name_filter(query, params):
    """Apply name filter with better error handling."""
    try:
        if params.name:
            for name_part in params.name.split(" "):
                if name_part.strip():
                    query = query.where(Employees.full_name.contains(name_part.strip()))
    except Exception as e:
        return False, f"Error in name filtering: {e}", ""

    return query


def apply_time_off_department_filter(query, params):
    """Apply department filter with improved case handling."""
    try:
        if params.department:
            # Support partial department name matching
            query = query.where(
                fn.LOWER(Employees.department).contains(params.department.lower())
            )
    except Exception as e:
        return False, f"Error in department filtering: {e}", ""

    return query


def format_time_off_results(query, params=None, fields=None):
    """Format query results."""
    try:
        if params and params.return_as_count and fields and len(fields) > 0:
            # If we're grouping by fields, ensure proper grouping and ordering
            query = query.group_by(*fields)

            if params.count_sort_desc:
                query = query.order_by(fn.COUNT(TimeOff.id.distinct()).desc())
            else:
                query = query.order_by(fn.COUNT(TimeOff.id.distinct()))

        return str(query)

    except Exception as e:
        logger.exception("Error formatting results: %s", e)
        return str(query)


def params_preprocess(params):
    """Preprocess and normalize the filter parameters."""
    # Handle string values
    for key, value in params.model_dump().items():
        if isinstance(value, str) and value is not None:
            # Clean and normalize the value
            clean_value = value.strip()
            if key not in ["from_date", "to_date", "type"] and clean_value:
                clean_value = clean_value.lower()

            params.__setattr__(key, clean_value if clean_value else None)
        elif isinstance(value, list) and value is not None and key == "select_columns":
            # Ensure select_columns are valid
            valid_columns = [
                "id",
                "policy_type",
                "start_date",
                "end_date",
                "status",
                "employee_id",
                "department",
                "employee_name",
            ]
            filtered_columns = [col for col in value if col in valid_columns]
            params.__setattr__(key, filtered_columns or None)

    # Special handling for return_as_count without select_columns
    if params.return_as_count and not params.select_columns:
        logger.info(
            "return_as_count=True without select_columns, defaulting to count by policy_type"
        )
        params.select_columns = ["policy_type"]

    # Special handling for policy_type to standardize common terms
    if params.policy_type:
        policy_map = {
            "vacation": "vacation leave",
            "sick": "sick leave",
            "annual": "annual leave",
            "birthday": "birthday day off",
            "personal": "personal leave",
            "bereavement": "bereavement leave",
            "parental": "parental leave",
            "maternity": "maternity leave",
            "paternity": "paternity leave",
        }

        for key, mapped_value in policy_map.items():
            if key in params.policy_type.lower():
                params.policy_type = mapped_value
                break

    return params


# @tool(args_schema=TimeOffFilterParams, return_direct=True)
def get_time_off(params: TimeOffFilterParams) -> Union[List[dict], str]:
    """
    Retrieve a list of employees who are (or will be) out of the office, or are working, based on the filter criteria.

    Use this tool when you need to:
    - Identify employees who are currently out of the office.
    - Find employees who have scheduled time off for specific reasons (e.g., vacation, sick leave).
    - Determine who will be out of the office during a specific period.
    - Find time off requests of specific durations.
    - Get aggregated counts of time off requests by policy type, status, etc.

    Examples:
    - Is Fernando working today? -> (policy_type=None)
    - Who is out of the office today? -> (policy_type=None)
    - Who had a birthday leave last month? -> (policy_type=Birthday Day Off)
    - Who will be on vacation for more than 5 days? -> (policy_type=Vacation Leave, duration_min=5)
    - Who has approved time off next month? -> (type=future, from_date=next month)
    - How many employees have time off by department? -> (return_as_count=True, select_columns=[department])
    - Count of approved vs pending vacation requests? -> (return_as_count=True, select_columns=[status], policy_type=Vacation Leave)
    """
    try:
        # Log the input parameters
        logger.info(f"Processing time off request with params: {params}")

        # Preprocess parameters
        params = params_preprocess(params)
        logger.info(f"Preprocessed params: {params}")

        # Validate parameters
        valid, error_msg = validate_time_off_params(params)
        if not valid:
            logger.error(f"Parameter validation error: {error_msg}")
            return False, error_msg, ""

        # Build base query
        try:
            query, fields = build_time_off_base_query(params)
            logger.debug(f"Base query built with {len(fields) if fields else 0} fields")
        except Exception as e:
            error_msg = f"Error building base query: {str(e)}"
            logger.exception(error_msg)
            return False, error_msg, ""

        # Apply filters
        filters = [
            apply_time_off_date_filters,
            apply_time_off_policy_filter,
            apply_time_off_name_filter,
            apply_time_off_department_filter,
        ]

        for filter_fn in filters:
            try:
                logger.debug(f"Applying filter: {filter_fn.__name__}")
                result = filter_fn(query, params)

                if isinstance(result, tuple):  # Error case
                    logger.error(
                        f"Filter {filter_fn.__name__} returned error: {result[1]}"
                    )
                    return result

                query = result
            except Exception as e:
                error_msg = f"Error applying filter {filter_fn.__name__}: {str(e)}"
                logger.exception(error_msg)
                return False, error_msg, str(query)

        # Format results
        try:
            return format_time_off_results(query, params, fields)
        except Exception as e:
            error_msg = f"Error formatting results: {str(e)}"
            logger.exception(error_msg)
            return False, error_msg, str(query)

    except Exception as e:
        error_msg = f"Error retrieving time off data: {str(e)}"
        logger.exception(error_msg)
        return False, error_msg, ""
