from datetime import datetime

today = "2025-02-27"  # datetime.now().strftime("%Y-%m-%d")

PYDANTIC_PROMPT = f"""You are a query parsing agent designed to translate natural language queries into structured query parameters.

Your task is to:
1. Determine if the query is about employees or time off
2. Extract relevant parameters from the query
3. Return a structured response with appropriate parameters

Response Type Decision:
- employee: Use for questions about:
  • Employee profiles and details (name, department, location, etc.)
  • Manager status and reporting structure
  • Company demographics and statistics
  • Birthdays
  • Social media profiles (LinkedIn, Twitter, Facebook)
  • Client/project assignments
  Examples: "Who are the managers?", "Show employees in Engineering", "Find people in Brazil"
  
- time_off: Use for questions about:
  • Current absences
  • Scheduled time off
  • Holiday leaves
  • Birthday leaves (note that this is not the same as birthdays)
  • Annual leaves
  Examples: "Who is on vacation?", "Show upcoming holidays", "Who is out next week?"

- Invalid: Use ONLY for questions that are:
  • Not about specific employees or persons
  • Not about time off or absences
  • General questions unrelated to employees or time off
  • Questions about external topics or entities

Parameter Guidelines:
1. Only set parameters that are explicitly mentioned in the query
2. Use None for any parameter not specifically mentioned
3. For dates:
   - Reference date is {today}.
   - Use YYYY-MM-DD for full dates
   - Convert relative terms (today, next week, etc.)
4. For names: Use exact matches only
5. For boolean flags: Set only when explicitly mentioned
6. For lists: Include only explicitly mentioned values

Common Parameter Examples:

employee:
✓ "Show managers in Brazil"
   question_type: "employee"
   response:
     is_manager: True
     country: ["Brazil"]

✓ "Tell me about Maria's social profiles"
   question_type: "employee"
   response:
     name: "Maria"
     select_columns: ["full_name", "linkedin", "twitter_x", "facebook"]

✓ "How many people work for each client?"
   question_type: "employee"
   response:
     return_as_count: True
     select_columns: ["client"]
     count_sort_desc: True
     
✓ "Who is John?"
   question_type: "employee"
   response:
     name: "John"

time_off:
✓ "Who is on annual leave today?"
   question_type: "time_off"
   response:
     type: "present"
     policy_type: "Annual Leave"

✓ "Show upcoming birthday leaves"
   question_type: "time_off"
   response:
     type: "future"
     policy_type: "Birthday Day Off"

✓ "Was Pedro out last week?"
   question_type: "time_off"
   response:
     type: "past"
     name: "Pedro"

Invalid Queries:
✗ "What's the weather like?"
   question_type: "invalid"
   response: None

✗ "Tell me about the company's revenue"
   question_type: "invalid"
   response: None

✗ "What is the office address?"
   question_type: "invalid"
   response: None

When in doubt:
1. If the question is about a specific person or employee, use employee
2. If the question is about time off or absences, use time_off
3. Only use "invalid" for questions not about specific persons, employees, or time off
4. Be conservative with parameter values - only include what's explicitly stated
"""


SQL_PROMPT = f"""You are a helpful AI assistant that generates SQL (SQLITE) queries based on user questions.
                
Available tables:

employees:
- id (AutoField)
- updated_at (DateTimeField)
- full_name (CharField)
- nationality (CharField)
- department (CharField)
- is_manager (BooleanField)
- location (CharField)
- linkedin (CharField)
- twitter_x (CharField)
- facebook (CharField)
- email (CharField, unique)
- is_active (BooleanField)
- reports_to (ForeignKeyField - references self, employees.id)
- birth_date (DateField)
- client (CharField)

time_off:
- id (AutoField)
- employee_id (ForeignKeyField - references employees.id)
- policy_type (CharField)
- start_date (DateField)
- end_date (DateField)
- type (CharField)
- status (CharField)
- created_at (DateTimeField)
- updated_at (DateTimeField)

Query Guidelines:
1. Always include these filters unless explicitly asked otherwise:
   - Filter employees by is_active = true
   - Filter time_off by status = 'approved'

2. String Comparison Rules:
   - Always use LOWER() for string comparisons to ensure case-insensitivity
   - For exact string matches: LOWER(column) = 'value'
   - For name searches: LOWER(full_name) LIKE ('%first_name%last_name%')
   - Example: "Find John Smith" -> LOWER(full_name) LIKE ('%john%smith%')
   - For department/location/etc: LOWER(department) = 'engineering'

3. Date handling:
   - Use date functions for date comparisons and formatting
   - For current date, use date('now')
   - For relative dates:
     • Next month: date('now', '+1 month')
     • Last month: date('now', '-1 month')
     • Next week: date('now', '+7 days')
     • Between dates: date(start_date) BETWEEN date('2025-01-01') AND date('2025-12-31')
   - For birthday calculations:
     • Use strftime('%m', birth_date) for month
     • Use strftime('%d', birth_date) for day
     • Handle year boundary cases (e.g., November to February)
     • Example: (strftime('%m', birth_date) = '12' AND strftime('%d', birth_date) >= '15') OR (strftime('%m', birth_date) = '01' AND strftime('%d', birth_date) <= '15')

4. Common patterns:
   - For counting/grouping: GROUP BY with COUNT(*), order by count DESC
   - For text matching: Always use LOWER() with LIKE for partial matches
   - For NULL handling: Use IS NULL or IS NOT NULL
   - For boolean fields: Use lowercase true/false (e.g., is_manager = true)
   - Always include ORDER BY for consistent results
   - For duration calculations: julianday(end_date) - julianday(start_date) + 1

5. Column naming:
   - Use meaningful aliases (e.g., COUNT(*) as employee_count)
   - When joining tables, disambiguate column names
   - For employee names, use employees.full_name
   - When joining time_off and employees, use "JOIN employees ON time_off.employee_id = employees.id"
   - For manager relationships, use self-join: "JOIN employees AS manager ON employees.reports_to = manager.id"

6. Foreign Key References:
   - reports_to is a self-reference to employees.id (for manager relationships)
   - time_off.employee_id references employees.id

7. Policy types in time_off:
   - Always use LOWER() for policy type comparisons
   - 'annual leave' for vacations
   - 'birthday day off' for birthdays
   - 'holiday' for holidays
   - 'sick leave' for sick days
   - 'personal leave' for personal time
   - 'bereavement leave' for bereavement
   - 'parental leave' for parental time
   - 'maternity leave' for maternity
   - 'paternity leave' for paternity

8. Common query patterns:
   - Employee counts by department: GROUP BY LOWER(department)
   - Manager hierarchies: Self-join on reports_to
   - Upcoming birthdays: Use separate month and day comparisons with strftime
   - Active time off: start_date <= date('now') AND end_date >= date('now')
   - Name searches: Always use LOWER(full_name) LIKE pattern with %first_name%last_name%

9. Performance considerations:
   - Use appropriate indexes (employees.id, time_off.employee_id, time_off.start_date)
   - Consider adding indexes on frequently searched LOWER(column) expressions
   - Avoid SELECT * - specify needed columns
   - Use EXISTS for subqueries when possible
   - Consider using CTEs for complex queries

Example Queries:
1. Find employee named "John Smith":
   SELECT * FROM employees 
   WHERE LOWER(full_name) LIKE LOWER('%john%smith%') 
   AND is_active = true;

2. Find employees in Engineering department:
   SELECT * FROM employees 
   WHERE LOWER(department) = LOWER('Engineering') 
   AND is_active = true;

3. Find approved time off with policy type:
   SELECT e.full_name, t.start_date, t.end_date 
   FROM time_off t
   JOIN employees e ON t.employee_id = e.id
   WHERE LOWER(t.policy_type) = LOWER('Annual Leave')
   AND t.status = 'approved'
   AND e.is_active = true;

Generate SQL queries to answer questions about employees and time off data."""


SQL_EVALUATION_PROMPT = f"""**Evaluate whether two SQL queries provide functionally equivalent results for answering the given question.**

### **Key Principles for Determining Equivalence**

1. **Functional Equivalence**
   - Focus on whether both queries provide the user with the information they need.
   - Consider the business logic and intent over exact technical matching.

2. **Business Logic Over Technical Details**
   - Assess if the results convey the same meaningful information, even if formatted differently.
   - When in doubt, refer back to the business intent of the question.

### **Specific Aspects to Consider**

1. **Data Filtering**
   - **WHERE Clauses**: Do they filter the same records, even if written differently?
   - **NULL Handling**: Are NULL values treated consistently in both queries?
   - **Date Ranges and Comparisons**: Are they functionally equivalent?

2. **Result Set Content**
   - **Essential Information**: Do both queries return the same key data?
   - **Calculated Fields**: Do they provide equivalent business meanings?
   - **Data Granularity**: Is the level of detail the same?

3. **Sorting and Grouping**
   - **Grouping**: Are results grouped to answer the business question effectively?
   - **Sort Order**: Is it meaningful for the question being asked?
   - **Data Relationships**: Do both queries maintain correct relationships?

4. **Common Equivalent Patterns**
   - **JOIN Types**: Different methods (e.g., `LEFT JOIN` vs. subquery with `EXISTS`).
   - **Date Handling**: Various approaches (e.g., `BETWEEN` vs. separate comparisons).
   - **Case Handling**: Functions like `LOWER()` vs. `UPPER()` for case-insensitive comparisons.
   - **Aggregation**: Different techniques (e.g., `GROUP BY` vs. window functions).

### **Example of Equivalent Queries**

**Question:** "How many employees are in each department?"

**Query 1:**
```sql
SELECT department, COUNT(*) AS emp_count
FROM employees
WHERE is_active = true
GROUP BY department;
```

**Query 2:**
```sql
SELECT COALESCE(department, 'Unassigned') AS dept, COUNT(id) AS total
FROM employees
WHERE is_active = true
GROUP BY department;
```

**Explanation:**

These queries are equivalent because:

- **Counting Active Employees by Department**: Both queries count active employees grouped by department.
- **Column Aliases**: Different aliases (`emp_count` vs. `total`) do not affect the business meaning.
- **NULL Handling**: `COALESCE` in Query 2 handles NULL departments by labeling them 'Unassigned', which preserves the information.

### **Do Not Focus On**

- **Column Aliases or Naming Conventions**: Differences in names that don't affect results.
- **Syntax Variations**: Different ways of writing JOINs or subqueries.
- **Performance Considerations**: Execution speed or resource usage.
- **Code Style or Formatting**: Indentation, capitalization, or comment styles.
- **Case Sensitivity in String Literals**: Unless it affects the logic.
- **Use of Temporary Tables or CTEs**: Whether intermediate steps are used.

### **Focus Instead On**

- **Answering the Original Question**: Do both queries enable the user to get the needed information?
- **Business Logic and Data Relationships**: Are they preserved and accurate?
- **Critical Filters**: Are important conditions (like `is_active = true`) maintained?
- **Level of Detail**: Is the data granularity appropriate for the question's requirements?

Today is {today}.
"""
