"""
Filtering Data in SQL
=====================

Topic:
    Comparison operators, logical operators, NULL, BETWEEN, IN, LIKE

This standalone study script teaches SQL filtering from beginner to advanced
level using Python's built-in sqlite3 module.

The examples use an in-memory SQLite database, so no external database,
package, or input file is required.

The script demonstrates:
    - SELECT and WHERE
    - Comparison operators
    - Text and numeric comparisons
    - Boolean logic
    - AND, OR, NOT
    - Operator precedence and parentheses
    - NULL and three-valued logic
    - IS NULL and IS NOT NULL
    - COALESCE and NULL-safe reasoning
    - BETWEEN and NOT BETWEEN
    - IN and NOT IN
    - LIKE, NOT LIKE, wildcards, and escaping
    - Case sensitivity considerations
    - Filtering dates stored as ISO strings
    - Filtering calculated expressions
    - Filtering using CASE
    - Filtering aggregate results with HAVING
    - Subqueries and EXISTS
    - Correlated filtering
    - Conditional aggregation
    - Common mistakes
    - Edge cases
    - Performance considerations
    - Indexes and query plans
    - Security considerations
    - Parameterized queries
    - Testing filters
    - A practical multi-condition reporting example

Important:
    SQL syntax varies between database systems. The examples are written
    for SQLite because it is available through Python's standard library.
    Concepts such as WHERE, comparison operators, AND, OR, NULL, BETWEEN,
    IN, LIKE, IS NULL, HAVING, EXISTS, and parameterized queries are broadly
    applicable to SQL systems, but individual database engines can differ in
    details such as case sensitivity, date types, regular expressions,
    NULL behavior in specialized functions, and indexing behavior.
"""

import sqlite3
from datetime import date


# ============================================================================
# 1. DATABASE SETUP
# ============================================================================

def create_connection():
    """Create an in-memory SQLite database connection."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def create_schema(connection):
    """Create tables used throughout the tutorial."""
    connection.executescript(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            email TEXT,
            city TEXT,
            country TEXT NOT NULL,
            age INTEGER,
            membership TEXT,
            signup_date TEXT NOT NULL
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            stock_quantity INTEGER NOT NULL,
            supplier TEXT
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL,
            discount REAL,
            shipping_cost REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
        """
    )


def insert_sample_data(connection):
    """Insert a realistic dataset containing useful edge cases."""
    customers = [
        (1, "Aarav Sharma", "aarav@example.com", "Delhi", "India", 28, "Gold", "2024-01-15"),
        (2, "Priya Singh", "priya@example.com", "Lucknow", "India", 34, "Silver", "2024-02-20"),
        (3, "Rahul Verma", None, "Mumbai", "India", 22, "Bronze", "2024-03-10"),
        (4, "Neha Gupta", "neha@example.com", "Lucknow", "India", 41, "Gold", "2024-04-05"),
        (5, "Vikram Mehta", "vikram@example.com", "Bengaluru", "India", 19, None, "2024-05-12"),
        (6, "Ananya Iyer", "ananya@example.com", "Chennai", "India", 31, "Silver", "2024-06-18"),
        (7, "Kabir Khan", None, "Delhi", "India", 45, "Gold", "2024-07-22"),
        (8, "Sara Ali", "sara@example.com", "Pune", "India", 27, "Bronze", "2024-08-14"),
        (9, "John Carter", "john@example.com", "London", "United Kingdom", 38, "Gold", "2024-09-01"),
        (10, "Emily Stone", None, "New York", "United States", 29, None, "2024-10-11"),
        (11, "Rohan Das", "rohan@example.com", "Kolkata", "India", 52, "Silver", "2024-11-19"),
        (12, "Meera Joshi", "meera@example.com", "Jaipur", "India", None, "Bronze", "2024-12-03"),
    ]

    products = [
        (1, "Laptop Pro", "Electronics", 85000.00, 12, "TechSource"),
        (2, "Wireless Mouse", "Electronics", 1200.00, 50, "TechSource"),
        (3, "Mechanical Keyboard", "Electronics", 4500.00, 25, "KeyWorks"),
        (4, "Office Chair", "Furniture", 15000.00, 8, "ComfortCo"),
        (5, "Standing Desk", "Furniture", 28000.00, 5, "ComfortCo"),
        (6, "Notebook", "Stationery", 250.00, 100, None),
        (7, "Pen Set", "Stationery", 400.00, 75, "WriteWell"),
        (8, "Monitor", "Electronics", 22000.00, 15, "DisplayTech"),
        (9, "USB Hub", "Electronics", 1800.00, 0, "TechSource"),
        (10, "Desk Lamp", "Furniture", 3200.00, 20, None),
    ]

    orders = [
        (1, 1, 1, 1, "2025-01-05", "Delivered", 0.10, 0.00),
        (2, 2, 2, 2, "2025-01-08", "Delivered", None, 80.00),
        (3, 3, 6, 5, "2025-01-12", "Cancelled", 0.05, 50.00),
        (4, 4, 5, 1, "2025-01-15", "Delivered", 0.15, 0.00),
        (5, 5, 7, 3, "2025-01-20", "Pending", None, 60.00),
        (6, 6, 8, 2, "2025-02-02", "Delivered", 0.05, 0.00),
        (7, 7, 4, 1, "2025-02-10", "Returned", 0.10, 0.00),
        (8, 8, 3, 1, "2025-02-14", "Delivered", None, 100.00),
        (9, 9, 1, 1, "2025-02-20", "Pending", 0.20, 500.00),
        (10, 10, 10, 2, "2025-03-01", "Delivered", None, 75.00),
        (11, 11, 2, 4, "2025-03-10", "Delivered", 0.05, 90.00),
        (12, 12, 9, 1, "2025-03-15", "Pending", None, 60.00),
        (13, 1, 3, 2, "2025-03-18", "Delivered", 0.10, 100.00),
        (14, 4, 8, 1, "2025-03-25", "Cancelled", None, 120.00),
        (15, 6, 6, 10, "2025-04-02", "Delivered", 0.20, 50.00),
    ]

    connection.executemany(
        """
        INSERT INTO customers
        (customer_id, customer_name, email, city, country, age, membership, signup_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        customers,
    )

    connection.executemany(
        """
        INSERT INTO products
        (product_id, product_name, category, price, stock_quantity, supplier)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        products,
    )

    connection.executemany(
        """
        INSERT INTO orders
        (order_id, customer_id, product_id, quantity, order_date, status, discount, shipping_cost)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        orders,
    )

    connection.commit()


# ============================================================================
# 2. HELPER FUNCTIONS
# ============================================================================

def print_title(title):
    """Print a readable section heading."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def run_query(connection, sql, parameters=(), show_sql=True):
    """
    Execute a SELECT query and display the result.

    Parameterized queries are used whenever external values are involved.
    This avoids SQL injection and handles SQL values correctly.
    """
    if show_sql:
        print("\nSQL:")
        print(sql.strip())
        if parameters:
            print("Parameters:", parameters)

    cursor = connection.execute(sql, parameters)
    rows = cursor.fetchall()

    if not rows:
        print("Result: no rows")
        return []

    column_names = [description[0] for description in cursor.description]

    print("\nResult:")
    print(" | ".join(column_names))
    print("-" * 80)

    for row in rows:
        values = [str(row[column]) for column in column_names]
        print(" | ".join(values))

    return rows


def run_scalar(connection, sql, parameters=()):
    """Execute a query expected to return one value."""
    row = connection.execute(sql, parameters).fetchone()
    return row[0] if row else None


# ============================================================================
# 3. SELECT AND WHERE FUNDAMENTALS
# ============================================================================

def demonstrate_where_basics(connection):
    print_title("1. SELECT and WHERE fundamentals")

    # WHERE filters rows before the final result is returned.
    run_query(
        connection,
        """
        SELECT customer_id, customer_name, city
        FROM customers
        WHERE country = 'India'
        ORDER BY customer_id
        """,
    )

    # A WHERE clause can compare a numeric column with a literal.
    run_query(
        connection,
        """
        SELECT product_name, price
        FROM products
        WHERE price > 10000
        ORDER BY price DESC
        """,
    )

    # The equality operator in SQL is =, not ==.
    run_query(
        connection,
        """
        SELECT product_name, category
        FROM products
        WHERE category = 'Electronics'
        """,
    )

    # SQL also supports <> for "not equal".
    run_query(
        connection,
        """
        SELECT product_name, category
        FROM products
        WHERE category <> 'Electronics'
        """,
    )


# ============================================================================
# 4. COMPARISON OPERATORS
# ============================================================================

def demonstrate_comparison_operators(connection):
    print_title("2. Comparison operators")

    examples = {
        "Equal (=)": """
            SELECT product_name, price
            FROM products
            WHERE price = 1200
        """,
        "Not equal (<>)": """
            SELECT product_name, category
            FROM products
            WHERE category <> 'Furniture'
        """,
        "Greater than (>)": """
            SELECT product_name, price
            FROM products
            WHERE price > 20000
        """,
        "Greater than or equal (>=)": """
            SELECT product_name, price
            FROM products
            WHERE price >= 22000
        """,
        "Less than (<)": """
            SELECT product_name, stock_quantity
            FROM products
            WHERE stock_quantity < 10
        """,
        "Less than or equal (<=)": """
            SELECT product_name, stock_quantity
            FROM products
            WHERE stock_quantity <= 5
        """,
    }

    for description, sql in examples.items():
        print(f"\n--- {description} ---")
        run_query(connection, sql)

    # SQL comparisons operate on values according to the data type and
    # database's comparison rules. Numeric and text comparisons should not
    # be mixed casually.
    run_query(
        connection,
        """
        SELECT customer_name, age
        FROM customers
        WHERE age >= 30
        ORDER BY age
        """,
    )


# ============================================================================
# 5. LOGICAL OPERATORS
# ============================================================================

def demonstrate_logical_operators(connection):
    print_title("3. Logical operators: AND, OR, NOT")

    # AND requires both conditions to evaluate to TRUE.
    run_query(
        connection,
        """
        SELECT customer_name, age, membership
        FROM customers
        WHERE age >= 30
          AND membership = 'Gold'
        ORDER BY age
        """,
    )

    # OR requires at least one condition to evaluate to TRUE.
    run_query(
        connection,
        """
        SELECT customer_name, city
        FROM customers
        WHERE city = 'Delhi'
           OR city = 'Lucknow'
        ORDER BY customer_name
        """,
    )

    # NOT reverses a logical condition.
    run_query(
        connection,
        """
        SELECT product_name, category
        FROM products
        WHERE NOT category = 'Electronics'
        ORDER BY product_name
        """,
    )

    # A safer and clearer form is often <> for simple inequality.
    run_query(
        connection,
        """
        SELECT product_name, category
        FROM products
        WHERE category <> 'Electronics'
        ORDER BY product_name
        """,
    )


# ============================================================================
# 6. OPERATOR PRECEDENCE
# ============================================================================

def demonstrate_precedence(connection):
    print_title("4. Logical operator precedence and parentheses")

    # SQL generally evaluates NOT before AND, and AND before OR.
    #
    # This:
    #
    #     A OR B AND C
    #
    # is interpreted as:
    #
    #     A OR (B AND C)
    #
    # not:
    #
    #     (A OR B) AND C
    #
    # Parentheses should be used whenever the intended logic could be unclear.

    run_query(
        connection,
        """
        SELECT customer_name, city, membership
        FROM customers
        WHERE city = 'Delhi'
           OR city = 'Lucknow'
          AND membership = 'Gold'
        ORDER BY customer_name
        """,
    )

    run_query(
        connection,
        """
        SELECT customer_name, city, membership
        FROM customers
        WHERE (city = 'Delhi' OR city = 'Lucknow')
          AND membership = 'Gold'
        ORDER BY customer_name
        """,
    )

    # Negating a compound expression can make business rules explicit.
    run_query(
        connection,
        """
        SELECT product_name, category
        FROM products
        WHERE NOT (category = 'Electronics' OR price > 20000)
        ORDER BY product_name
        """,
    )


# ============================================================================
# 7. SQL THREE-VALUED LOGIC AND NULL
# ============================================================================

def demonstrate_null(connection):
    print_title("5. NULL and SQL three-valued logic")

    # NULL does not mean zero, an empty string, false, or "unknown text".
    # It represents a missing or unknown value.
    #
    # A normal comparison with NULL does not produce TRUE.
    #
    #     NULL = NULL
    #     NULL = 5
    #     NULL <> 5
    #
    # all produce UNKNOWN rather than TRUE in standard SQL's three-valued
    # logic model.

    run_query(
        connection,
        """
        SELECT customer_name, email
        FROM customers
        WHERE email IS NULL
        ORDER BY customer_id
        """,
    )

    run_query(
        connection,
        """
        SELECT customer_name, email
        FROM customers
        WHERE email IS NOT NULL
        ORDER BY customer_id
        """,
    )

    # This is intentionally demonstrated as a common mistake.
    # "email = NULL" does not correctly identify NULL values.
    run_query(
        connection,
        """
        SELECT customer_name, email
        FROM customers
        WHERE email = NULL
        ORDER BY customer_id
        """,
    )

    # SQL's WHERE clause keeps rows for which the condition is TRUE.
    # Rows producing FALSE or UNKNOWN are excluded.
    run_query(
        connection,
        """
        SELECT customer_name, age
        FROM customers
        WHERE age > 30
        ORDER BY customer_id
        """,
    )

    # The customer with age NULL is not returned because:
    #
    #     NULL > 30
    #
    # is UNKNOWN, not FALSE in the logical model.


# ============================================================================
# 8. NULL WITH AND / OR / NOT
# ============================================================================

def demonstrate_null_logic(connection):
    print_title("6. NULL with AND, OR, and NOT")

    # Three-valued logic has TRUE, FALSE, and UNKNOWN.
    #
    # Useful conceptual examples:
    #
    # TRUE AND UNKNOWN     -> UNKNOWN
    # FALSE AND UNKNOWN    -> FALSE
    # TRUE OR UNKNOWN      -> TRUE
    # FALSE OR UNKNOWN     -> UNKNOWN
    # NOT UNKNOWN          -> UNKNOWN
    #
    # SQLite can demonstrate the resulting behavior directly.

    run_query(
        connection,
        """
        SELECT
            NULL = NULL AS null_equals_null,
            NULL = 5 AS null_equals_five,
            NULL <> 5 AS null_not_equal_five,
            NULL > 5 AS null_greater_than_five,
            NOT (NULL = 5) AS not_unknown
        """,
    )

    run_query(
        connection,
        """
        SELECT
            (1 = 1) AND (NULL = 5) AS true_and_unknown,
            (1 = 2) AND (NULL = 5) AS false_and_unknown,
            (1 = 1) OR (NULL = 5) AS true_or_unknown,
            (1 = 2) OR (NULL = 5) AS false_or_unknown
        """,
    )

    # NOT IN has a particularly important NULL-related trap.
    #
    # If the list/subquery contains NULL, a NOT IN condition can produce
    # UNKNOWN for values that do not match any known value.
    run_query(
        connection,
        """
        SELECT customer_name
        FROM customers
        WHERE customer_id NOT IN (1, 2, NULL)
        ORDER BY customer_id
        """,
    )

    # A safer anti-membership pattern for nullable subqueries is often NOT
    # EXISTS. This is demonstrated later.


# ============================================================================
# 9. COALESCE AND NULL HANDLING
# ============================================================================

def demonstrate_null_handling(connection):
    print_title("7. COALESCE and explicit NULL handling")

    # COALESCE returns the first non-NULL expression.
    run_query(
        connection,
        """
        SELECT
            customer_name,
            membership,
            COALESCE(membership, 'No Membership') AS membership_label
        FROM customers
        ORDER BY customer_id
        """,
    )

    # COALESCE can be useful when a missing numeric value should be treated
    # as zero for a particular calculation. This is a business rule and
    # should only be done when treating NULL as zero is actually correct.
    run_query(
        connection,
        """
        SELECT
            order_id,
            discount,
            COALESCE(discount, 0) AS effective_discount
        FROM orders
        ORDER BY order_id
        """,
    )

    # Filtering after COALESCE changes the meaning of the filter:
    # this query treats missing discounts as zero.
    run_query(
        connection,
        """
        SELECT order_id, discount
        FROM orders
        WHERE COALESCE(discount, 0) = 0
        ORDER BY order_id
        """,
    )

    # Compare that with explicitly asking for missing discounts only.
    run_query(
        connection,
        """
        SELECT order_id, discount
        FROM orders
        WHERE discount IS NULL
        ORDER BY order_id
        """,
    )


# ============================================================================
# 10. BETWEEN
# ============================================================================

def demonstrate_between(connection):
    print_title("8. BETWEEN and NOT BETWEEN")

    # BETWEEN is inclusive at both ends.
    #
    # price BETWEEN 1000 AND 5000
    #
    # means:
    #
    # price >= 1000 AND price <= 5000

    run_query(
        connection,
        """
        SELECT product_name, price
        FROM products
        WHERE price BETWEEN 1000 AND 5000
        ORDER BY price
        """,
    )

    # NOT BETWEEN means outside the inclusive range.
    run_query(
        connection,
        """
        SELECT product_name, price
        FROM products
        WHERE price NOT BETWEEN 1000 AND 5000
        ORDER BY price
        """,
    )

    # Equivalent explicit expression.
    run_query(
        connection,
        """
        SELECT product_name, price
        FROM products
        WHERE price >= 1000
          AND price <= 5000
        ORDER BY price
        """,
    )

    # Edge case: if the tested value is NULL, BETWEEN evaluates to UNKNOWN.
    run_query(
        connection,
        """
        SELECT customer_name, age
        FROM customers
        WHERE age BETWEEN 20 AND 40
        ORDER BY customer_id
        """,
    )

    # BETWEEN can also be used with ISO-formatted dates in SQLite.
    # ISO format YYYY-MM-DD sorts chronologically as text.
    run_query(
        connection,
        """
        SELECT order_id, order_date, status
        FROM orders
        WHERE order_date BETWEEN '2025-02-01' AND '2025-03-01'
        ORDER BY order_date
        """,
    )


# ============================================================================
# 11. IN
# ============================================================================

def demonstrate_in(connection):
    print_title("9. IN and NOT IN")

    # IN is useful when a value may match one of several specified values.
    run_query(
        connection,
        """
        SELECT customer_name, city
        FROM customers
        WHERE city IN ('Delhi', 'Lucknow', 'Mumbai')
        ORDER BY customer_name
        """,
    )

    # NOT IN excludes values from a list.
    run_query(
        connection,
        """
        SELECT product_name, category
        FROM products
        WHERE category NOT IN ('Electronics', 'Stationery')
        ORDER BY product_name
        """,
    )

    # IN is logically similar to a series of OR conditions.
    run_query(
        connection,
        """
        SELECT product_name, category
        FROM products
        WHERE category = 'Furniture'
           OR category = 'Stationery'
        ORDER BY product_name
        """,
    )

    # Empty IN lists are a database-specific edge case. SQLite accepts
    # an empty list, but applications should construct dynamic lists safely
    # rather than concatenating arbitrary user input into SQL.


# ============================================================================
# 12. PARAMETERIZED IN
# ============================================================================

def demonstrate_parameterized_in(connection):
    print_title("10. Safe parameterized filtering")

    cities = ["Delhi", "Lucknow", "Pune"]

    # SQL parameters should not be created by string concatenation.
    # A variable-length IN list requires one placeholder per value.
    placeholders = ", ".join("?" for _ in cities)

    sql = f"""
        SELECT customer_name, city
        FROM customers
        WHERE city IN ({placeholders})
        ORDER BY customer_name
    """

    run_query(connection, sql, cities)

    # Edge case: an empty list should be handled explicitly.
    empty_cities = []

    if empty_cities:
        placeholders = ", ".join("?" for _ in empty_cities)
        sql = f"""
            SELECT customer_name, city
            FROM customers
            WHERE city IN ({placeholders})
        """
        run_query(connection, sql, empty_cities)
    else:
        print("\nEmpty filter list detected. Query was not generated.")


# ============================================================================
# 13. LIKE
# ============================================================================

def demonstrate_like(connection):
    print_title("11. LIKE and pattern matching")

    # LIKE performs pattern matching.
    #
    # % means zero or more characters.
    # _ means exactly one character.

    # Names beginning with "A".
    run_query(
        connection,
        """
        SELECT customer_name
        FROM customers
        WHERE customer_name LIKE 'A%'
        ORDER BY customer_name
        """,
    )

    # Names ending with "a".
    run_query(
        connection,
        """
        SELECT customer_name
        FROM customers
        WHERE customer_name LIKE '%a'
        ORDER BY customer_name
        """,
    )

    # Names containing "ar".
    run_query(
        connection,
        """
        SELECT customer_name
        FROM customers
        WHERE customer_name LIKE '%ar%'
        ORDER BY customer_name
        """,
    )

    # One-character wildcard.
    run_query(
        connection,
        """
        SELECT customer_name
        FROM customers
        WHERE customer_name LIKE 'A_a%'
        ORDER BY customer_name
        """,
    )

    # NOT LIKE excludes matching patterns.
    run_query(
        connection,
        """
        SELECT product_name
        FROM products
        WHERE product_name NOT LIKE '%Desk%'
        ORDER BY product_name
        """,
    )


# ============================================================================
# 14. LIKE ESCAPING
# ============================================================================

def demonstrate_like_escape(connection):
    print_title("12. LIKE wildcards and escaping")

    connection.execute(
        "CREATE TABLE coupon_codes (code TEXT NOT NULL)"
    )

    connection.executemany(
        "INSERT INTO coupon_codes(code) VALUES (?)",
        [
            ("SAVE10%",),
            ("SAVE20",),
            ("OFF_15",),
            ("NORMAL",),
        ],
    )
    connection.commit()

    # A literal percent sign can be searched for with an ESCAPE character.
    run_query(
        connection,
        r"""
        SELECT code
        FROM coupon_codes
        WHERE code LIKE '%\%%' ESCAPE '\'
        ORDER BY code
        """,
    )

    # A literal underscore can also be escaped.
    run_query(
        connection,
        r"""
        SELECT code
        FROM coupon_codes
        WHERE code LIKE '%\_%' ESCAPE '\'
        ORDER BY code
        """,
    )


# ============================================================================
# 15. CASE SENSITIVITY
# ============================================================================

def demonstrate_like_case(connection):
    print_title("13. LIKE case sensitivity and portability")

    # SQLite's default LIKE behavior is not identical to every other SQL
    # database. Case sensitivity depends on database engine and settings.
    #
    # Do not assume that LIKE behaves identically across PostgreSQL, MySQL,
    # SQL Server, Oracle, and SQLite.

    run_query(
        connection,
        """
        SELECT customer_name
        FROM customers
        WHERE customer_name LIKE 'a%'
        ORDER BY customer_name
        """,
    )

    # For portable case-insensitive searching, an explicit normalization
    # strategy may be used when appropriate.
    run_query(
        connection,
        """
        SELECT customer_name
        FROM customers
        WHERE LOWER(customer_name) LIKE LOWER(?)
        ORDER BY customer_name
        """,
        ("a%",),
    )


# ============================================================================
# 16. COMBINING OPERATORS
# ============================================================================

def demonstrate_complex_filters(connection):
    print_title("14. Combining comparison, logical, NULL, BETWEEN, IN, and LIKE")

    # This query combines multiple filtering concepts.
    run_query(
        connection,
        """
        SELECT customer_name, age, city, membership
        FROM customers
        WHERE country = 'India'
          AND age BETWEEN 25 AND 45
          AND city IN ('Delhi', 'Lucknow', 'Mumbai', 'Pune')
          AND membership IS NOT NULL
        ORDER BY age, customer_name
        """,
    )

    # A more complex product filter.
    run_query(
        connection,
        """
        SELECT product_name, category, price, stock_quantity
        FROM products
        WHERE (
                category = 'Electronics'
                AND price BETWEEN 1000 AND 50000
              )
          AND stock_quantity > 0
        ORDER BY price
        """,
    )

    # Search by pattern while excluding one category.
    run_query(
        connection,
        """
        SELECT product_name, category
        FROM products
        WHERE product_name LIKE '%o%'
          AND category <> 'Stationery'
        ORDER BY product_name
        """,
    )


# ============================================================================
# 17. FILTERING CALCULATED EXPRESSIONS
# ============================================================================

def demonstrate_calculated_filters(connection):
    print_title("15. Filtering calculated expressions")

    # SQL can filter based on an expression rather than only a stored column.
    #
    # Example:
    # quantity * price
    #
    # represents the gross line value.

    run_query(
        connection,
        """
        SELECT
            o.order_id,
            p.product_name,
            o.quantity,
            p.price,
            o.quantity * p.price AS gross_value
        FROM orders AS o
        JOIN products AS p
            ON o.product_id = p.product_id
        WHERE o.quantity * p.price > 20000
        ORDER BY gross_value DESC
        """,
    )

    # NULL arithmetic can produce NULL.
    #
    # If discount is NULL, multiplying it directly can result in NULL.
    # COALESCE can explicitly define the intended treatment.
    run_query(
        connection,
        """
        SELECT
            order_id,
            discount,
            COALESCE(discount, 0) AS effective_discount,
            1000 * (1 - COALESCE(discount, 0)) AS net_example
        FROM orders
        ORDER BY order_id
        """,
    )


# ============================================================================
# 18. CASE IN FILTERING
# ============================================================================

def demonstrate_case_filtering(connection):
    print_title("16. CASE expressions and conditional classification")

    # CASE creates conditional values.
    # It can be used in SELECT and, when necessary, in WHERE.
    run_query(
        connection,
        """
        SELECT
            product_name,
            price,
            CASE
                WHEN price < 1000 THEN 'Budget'
                WHEN price < 10000 THEN 'Mid-range'
                ELSE 'Premium'
            END AS price_segment
        FROM products
        ORDER BY price
        """,
    )

    # Filtering on a CASE expression is possible, though direct predicates
    # are often easier for the optimizer and clearer to maintain.
    run_query(
        connection,
        """
        SELECT product_name, price
        FROM products
        WHERE CASE
                  WHEN price >= 10000 THEN 1
                  ELSE 0
              END = 1
        ORDER BY price
        """,
    )


# ============================================================================
# 19. WHERE VERSUS HAVING
# ============================================================================

def demonstrate_where_vs_having(connection):
    print_title("17. WHERE versus HAVING")

    # WHERE filters individual rows before grouping.
    run_query(
        connection,
        """
        SELECT
            status,
            COUNT(*) AS order_count
        FROM orders
        WHERE status <> 'Cancelled'
        GROUP BY status
        ORDER BY status
        """,
    )

    # HAVING filters groups after GROUP BY.
    run_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY customer_id
        HAVING COUNT(*) >= 2
        ORDER BY order_count DESC
        """,
    )

    # A common mistake is trying to use an aggregate condition in WHERE.
    # For example, WHERE COUNT(*) >= 2 is invalid because COUNT(*) exists
    # after grouping. HAVING is the correct clause for group-level filtering.


# ============================================================================
# 20. SUBQUERY FILTERING
# ============================================================================

def demonstrate_subqueries(connection):
    print_title("18. Filtering with subqueries")

    # A scalar subquery can provide a value to compare against.
    average_price = run_scalar(
        connection,
        "SELECT AVG(price) FROM products",
    )

    print(f"\nAverage product price: {average_price:.2f}")

    run_query(
        connection,
        """
        SELECT product_name, price
        FROM products
        WHERE price > (
            SELECT AVG(price)
            FROM products
        )
        ORDER BY price DESC
        """,
    )

    # IN can use a subquery instead of a literal list.
    run_query(
        connection,
        """
        SELECT customer_name
        FROM customers
        WHERE customer_id IN (
            SELECT customer_id
            FROM orders
            WHERE status = 'Pending'
        )
        ORDER BY customer_name
        """,
    )


# ============================================================================
# 21. EXISTS AND NOT EXISTS
# ============================================================================

def demonstrate_exists(connection):
    print_title("19. EXISTS and NOT EXISTS")

    # EXISTS asks whether the subquery produces at least one row.
    # It is especially useful when filtering one table based on the
    # existence of related rows in another table.

    run_query(
        connection,
        """
        SELECT c.customer_name
        FROM customers AS c
        WHERE EXISTS (
            SELECT 1
            FROM orders AS o
            WHERE o.customer_id = c.customer_id
              AND o.status = 'Delivered'
        )
        ORDER BY c.customer_name
        """,
    )

    # NOT EXISTS is often safer than NOT IN when the subquery can contain
    # NULL values.
    run_query(
        connection,
        """
        SELECT c.customer_name
        FROM customers AS c
        WHERE NOT EXISTS (
            SELECT 1
            FROM orders AS o
            WHERE o.customer_id = c.customer_id
              AND o.status = 'Cancelled'
        )
        ORDER BY c.customer_name
        """,
    )


# ============================================================================
# 22. CORRELATED FILTERING
# ============================================================================

def demonstrate_correlated_subquery(connection):
    print_title("20. Correlated subquery filtering")

    # A correlated subquery references a column from the outer query.
    #
    # This finds products whose price is above the average price of their
    # own category.
    run_query(
        connection,
        """
        SELECT
            p.product_name,
            p.category,
            p.price
        FROM products AS p
        WHERE p.price > (
            SELECT AVG(p2.price)
            FROM products AS p2
            WHERE p2.category = p.category
        )
        ORDER BY p.category, p.price DESC
        """,
    )


# ============================================================================
# 23. DATE FILTERING
# ============================================================================

def demonstrate_date_filtering(connection):
    print_title("21. Date filtering")

    # SQLite stores these example dates as ISO-formatted TEXT values.
    # YYYY-MM-DD has a useful lexicographical ordering.
    run_query(
        connection,
        """
        SELECT order_id, order_date, status
        FROM orders
        WHERE order_date >= '2025-02-01'
          AND order_date < '2025-03-01'
        ORDER BY order_date
        """,
    )

    # A half-open interval [start, end) is often preferable to BETWEEN for
    # timestamps because it avoids accidentally excluding or including the
    # wrong time at the end boundary.
    #
    # For example:
    #
    #     timestamp >= start
    #     AND timestamp < next_period_start
    #
    # is commonly used for month/day filtering.


# ============================================================================
# 24. STRING, NUMERIC, AND NULL EDGE CASES
# ============================================================================

def demonstrate_edge_cases(connection):
    print_title("22. Important filtering edge cases")

    # NULL is not equal to NULL.
    run_query(
        connection,
        """
        SELECT
            CASE
                WHEN NULL IS NULL THEN 'NULL detected'
                ELSE 'Not NULL'
            END AS result
        """,
    )

    # Empty string and NULL are distinct concepts.
    connection.execute(
        "CREATE TABLE text_examples (id INTEGER PRIMARY KEY, value TEXT)"
    )
    connection.executemany(
        "INSERT INTO text_examples(id, value) VALUES (?, ?)",
        [
            (1, ""),
            (2, None),
            (3, "text"),
        ],
    )
    connection.commit()

    run_query(
        connection,
        """
        SELECT id, value
        FROM text_examples
        WHERE value = ''
        ORDER BY id
        """,
    )

    run_query(
        connection,
        """
        SELECT id, value
        FROM text_examples
        WHERE value IS NULL
        ORDER BY id
        """,
    )

    # Zero is also different from NULL.
    run_query(
        connection,
        """
        SELECT
            0 = 0 AS zero_equals_zero,
            0 IS NULL AS zero_is_null
        """,
    )


# ============================================================================
# 25. DYNAMIC FILTER BUILDING
# ============================================================================

def build_customer_filter(
    country=None,
    minimum_age=None,
    maximum_age=None,
    cities=None,
    membership=None,
    name_pattern=None,
    require_email=False,
):
    """
    Safely construct a dynamic WHERE clause.

    The SQL structure is built by the application, while all actual values
    remain parameterized. This is much safer than inserting values directly
    into SQL strings.
    """
    conditions = []
    parameters = []

    if country is not None:
        conditions.append("country = ?")
        parameters.append(country)

    if minimum_age is not None:
        conditions.append("age >= ?")
        parameters.append(minimum_age)

    if maximum_age is not None:
        conditions.append("age <= ?")
        parameters.append(maximum_age)

    if cities:
        placeholders = ", ".join("?" for _ in cities)
        conditions.append(f"city IN ({placeholders})")
        parameters.extend(cities)

    if membership is not None:
        conditions.append("membership = ?")
        parameters.append(membership)

    if name_pattern is not None:
        conditions.append("customer_name LIKE ?")
        parameters.append(name_pattern)

    if require_email:
        conditions.append("email IS NOT NULL")

    where_clause = " AND ".join(conditions)

    sql = """
        SELECT customer_id, customer_name, city, age, membership, email
        FROM customers
    """

    if where_clause:
        sql += "\nWHERE " + where_clause

    sql += "\nORDER BY customer_name"

    return sql, parameters


def demonstrate_dynamic_filters(connection):
    print_title("23. Dynamic filtering with parameterized SQL")

    sql, parameters = build_customer_filter(
        country="India",
        minimum_age=25,
        maximum_age=45,
        cities=["Delhi", "Lucknow", "Pune"],
        require_email=True,
    )

    run_query(connection, sql, parameters)

    sql, parameters = build_customer_filter(
        membership="Gold",
        name_pattern="%a%",
    )

    run_query(connection, sql, parameters)


# ============================================================================
# 26. SQL INJECTION DEMONSTRATION
# ============================================================================

def demonstrate_sql_injection_safety(connection):
    print_title("24. SQL injection and parameterized filtering")

    user_input = "' OR 1=1 --"

    # BAD IDEA:
    #
    #     sql = f"SELECT ... WHERE customer_name = '{user_input}'"
    #
    # User-controlled text becomes part of the SQL language.
    #
    # GOOD IDEA:
    # Keep SQL syntax and values separate.
    run_query(
        connection,
        """
        SELECT customer_name, email
        FROM customers
        WHERE customer_name = ?
        """,
        (user_input,),
    )

    print(
        "\nThe malicious-looking string was treated as a value rather than "
        "as executable SQL because it was parameterized."
    )


# ============================================================================
# 27. PERFORMANCE AND INDEXES
# ============================================================================

def demonstrate_indexing(connection):
    print_title("25. Filtering performance and indexes")

    # Indexes can speed up selective equality/range lookups on appropriate
    # columns. They also have storage and write-maintenance costs.
    connection.execute(
        "CREATE INDEX idx_customers_country ON customers(country)"
    )
    connection.execute(
        "CREATE INDEX idx_products_price ON products(price)"
    )
    connection.execute(
        "CREATE INDEX idx_orders_status ON orders(status)"
    )
    connection.commit()

    # EXPLAIN QUERY PLAN lets SQLite show how it intends to execute a query.
    run_query(
        connection,
        """
        EXPLAIN QUERY PLAN
        SELECT customer_name
        FROM customers
        WHERE country = 'India'
        """,
    )

    run_query(
        connection,
        """
        EXPLAIN QUERY PLAN
        SELECT product_name
        FROM products
        WHERE price BETWEEN 10000 AND 30000
        """,
    )

    # A leading wildcard such as '%phone%' can make ordinary B-tree indexes
    # less useful because the beginning of the value is unknown.
    run_query(
        connection,
        """
        EXPLAIN QUERY PLAN
        SELECT product_name
        FROM products
        WHERE product_name LIKE '%Desk%'
        """,
    )

    # Do not add indexes blindly. An index is useful only when its maintenance
    # cost and storage requirements are justified by actual access patterns.


# ============================================================================
# 28. FILTERING ORDER IN THE SQL EXECUTION MODEL
# ============================================================================

def demonstrate_logical_query_order(connection):
    print_title("26. Logical order of SQL query processing")

    # A simplified logical order is:
    #
    # 1. FROM / JOIN
    # 2. WHERE
    # 3. GROUP BY
    # 4. HAVING
    # 5. SELECT
    # 6. ORDER BY
    # 7. LIMIT
    #
    # The physical execution plan chosen by the optimizer can differ.
    #
    # This explains why WHERE cannot normally reference a SELECT alias from
    # the same query block.

    run_query(
        connection,
        """
        SELECT
            product_name,
            price * stock_quantity AS inventory_value
        FROM products
        WHERE price > 1000
        ORDER BY inventory_value DESC
        """,
    )


# ============================================================================
# 29. MULTIPLE FILTER CONDITIONS AS BUSINESS RULES
# ============================================================================

def demonstrate_business_filter(connection):
    print_title("27. Practical business filtering example")

    # Requirement:
    #
    # Find customers who:
    #   - are in India,
    #   - are between 25 and 45 years old,
    #   - live in selected cities,
    #   - have either Gold or Silver membership,
    #   - have a known email address.
    #
    # Each business rule becomes an explicit predicate.
    run_query(
        connection,
        """
        SELECT
            customer_id,
            customer_name,
            city,
            age,
            membership,
            email
        FROM customers
        WHERE country = 'India'
          AND age BETWEEN 25 AND 45
          AND city IN ('Delhi', 'Lucknow', 'Mumbai', 'Pune')
          AND membership IN ('Gold', 'Silver')
          AND email IS NOT NULL
        ORDER BY city, customer_name
        """,
    )


# ============================================================================
# 30. MULTIPLE FILTER CONDITIONS FOR ORDERS
# ============================================================================

def demonstrate_order_filter(connection):
    print_title("28. Practical order filtering example")

    # Requirement:
    #
    # Find non-cancelled orders placed in February or March 2025 where:
    #   - quantity is at least 1,
    #   - discount is either missing or at least 10%.
    run_query(
        connection,
        """
        SELECT
            order_id,
            order_date,
            quantity,
            status,
            discount
        FROM orders
        WHERE status <> 'Cancelled'
          AND order_date BETWEEN '2025-02-01' AND '2025-03-31'
          AND quantity >= 1
          AND (
                discount IS NULL
                OR discount >= 0.10
              )
        ORDER BY order_date
        """,
    )


# ============================================================================
# 31. CONDITIONAL AGGREGATION
# ============================================================================

def demonstrate_conditional_aggregation(connection):
    print_title("29. Conditional aggregation")

    # Filtering does not always mean removing rows.
    # Conditional aggregation can count or sum rows satisfying a condition
    # while keeping groups intact.

    run_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS total_orders,
            SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END)
                AS delivered_orders,
            SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END)
                AS cancelled_orders
        FROM orders
        GROUP BY customer_id
        ORDER BY customer_id
        """,
    )

    # SQLite also supports FILTER in some aggregate contexts, but the CASE
    # pattern is broadly useful across SQL dialects.
    run_query(
        connection,
        """
        SELECT
            COUNT(*) AS total_orders,
            COUNT(*) FILTER (WHERE status = 'Delivered') AS delivered_orders
        FROM orders
        """,
    )


# ============================================================================
# 32. FILTERING JOINED DATA
# ============================================================================

def demonstrate_join_filtering(connection):
    print_title("30. Filtering joined tables")

    # Filters can reference columns from multiple joined tables.
    run_query(
        connection,
        """
        SELECT
            o.order_id,
            c.customer_name,
            p.product_name,
            p.category,
            p.price,
            o.status
        FROM orders AS o
        JOIN customers AS c
            ON c.customer_id = o.customer_id
        JOIN products AS p
            ON p.product_id = o.product_id
        WHERE c.country = 'India'
          AND p.category = 'Electronics'
          AND p.price >= 5000
          AND o.status = 'Delivered'
        ORDER BY o.order_date
        """,
    )

    # Important JOIN edge case:
    #
    # With a LEFT JOIN, putting a right-table condition in WHERE can eliminate
    # NULL-extended rows and effectively behave like an INNER JOIN.
    #
    # The placement of a filter can therefore change query semantics.
    run_query(
        connection,
        """
        SELECT
            c.customer_name,
            o.order_id,
            o.status
        FROM customers AS c
        LEFT JOIN orders AS o
            ON o.customer_id = c.customer_id
           AND o.status = 'Delivered'
        ORDER BY c.customer_id
        """,
    )


# ============================================================================
# 33. FILTER TESTING
# ============================================================================

def demonstrate_filter_testing(connection):
    print_title("31. Testing filtering logic")

    # Good SQL development tests include:
    #   - values exactly at boundaries,
    #   - values just outside boundaries,
    #   - NULL values,
    #   - empty strings where applicable,
    #   - duplicate values,
    #   - unexpected categories,
    #   - empty filter lists,
    #   - case differences,
    #   - missing relationships.

    test_cases = [
        ("Age lower boundary", "SELECT COUNT(*) FROM customers WHERE age = 25"),
        ("Age upper boundary", "SELECT COUNT(*) FROM customers WHERE age = 45"),
        ("NULL age", "SELECT COUNT(*) FROM customers WHERE age IS NULL"),
        ("NULL membership", "SELECT COUNT(*) FROM customers WHERE membership IS NULL"),
        ("Zero stock", "SELECT COUNT(*) FROM products WHERE stock_quantity = 0"),
        ("Inclusive price range", "SELECT COUNT(*) FROM products WHERE price BETWEEN 1200 AND 4500"),
    ]

    for name, sql in test_cases:
        count = run_scalar(connection, sql)
        print(f"{name}: {count}")


# ============================================================================
# 34. ASSERTION-BASED FILTER CHECKS
# ============================================================================

def demonstrate_assertions(connection):
    print_title("32. Assertions for expected filtering behavior")

    null_email_count = run_scalar(
        connection,
        "SELECT COUNT(*) FROM customers WHERE email IS NULL",
    )
    assert null_email_count == 3

    gold_count = run_scalar(
        connection,
        "SELECT COUNT(*) FROM customers WHERE membership = 'Gold'",
    )
    assert gold_count == 4

    in_count = run_scalar(
        connection,
        """
        SELECT COUNT(*)
        FROM customers
        WHERE city IN ('Delhi', 'Lucknow')
        """,
    )

    expected = run_scalar(
        connection,
        """
        SELECT COUNT(*)
        FROM customers
        WHERE city = 'Delhi' OR city = 'Lucknow'
        """,
    )

    assert in_count == expected

    print("All filtering assertions passed.")


# ============================================================================
# 35. FILTERING ANTI-PATTERNS
# ============================================================================

def demonstrate_common_mistakes(connection):
    print_title("33. Common filtering mistakes")

    print(
        """
Common mistakes demonstrated conceptually:

1. Using == instead of =
   SQL equality normally uses =.

2. Comparing NULL with =
   Use IS NULL or IS NOT NULL.

3. Forgetting BETWEEN is inclusive
   BETWEEN 10 AND 20 includes both 10 and 20.

4. Mishandling OR and AND precedence
   Use parentheses to express business logic clearly.

5. Using NOT IN with nullable data
   NULL can cause UNKNOWN results. Consider NOT EXISTS.

6. Concatenating user input into SQL
   Use parameters.

7. Assuming LIKE has identical case behavior everywhere
   Database engines differ.

8. Applying functions to indexed columns without considering the query plan
   An expression such as LOWER(column) may prevent a normal index from
   being used efficiently unless an appropriate functional/index strategy
   exists.

9. Filtering a LEFT JOIN's right-side table in WHERE when preservation of
   unmatched left rows is required
   Put the condition in the JOIN's ON clause when appropriate.

10. Confusing NULL with zero or an empty string
    These represent different values and states.
"""
    )

    # Example of the correct NULL test.
    run_query(
        connection,
        """
        SELECT customer_name
        FROM customers
        WHERE email IS NULL
        ORDER BY customer_name
        """,
    )


# ============================================================================
# 36. FILTERING WITH USER-DEFINED BUSINESS THRESHOLDS
# ============================================================================

def demonstrate_parameterized_thresholds(connection):
    print_title("34. Parameterized thresholds")

    minimum_price = 5000
    maximum_price = 30000

    # Values should be parameters rather than inserted into the SQL string.
    run_query(
        connection,
        """
        SELECT product_name, price
        FROM products
        WHERE price BETWEEN ? AND ?
        ORDER BY price
        """,
        (minimum_price, maximum_price),
    )

    minimum_stock = 10

    run_query(
        connection,
        """
        SELECT product_name, stock_quantity
        FROM products
        WHERE stock_quantity >= ?
        ORDER BY stock_quantity DESC
        """,
        (minimum_stock,),
    )


# ============================================================================
# 37. COMPARISON OF FILTERING TECHNIQUES
# ============================================================================

def demonstrate_filter_comparisons(connection):
    print_title("35. Comparison of related filtering techniques")

    print(
        """
Equality versus IN:
    category = 'Electronics'
    is best for one known value.

    category IN ('Electronics', 'Furniture')
    is concise for multiple known values.

BETWEEN versus explicit comparisons:
    price BETWEEN 1000 AND 5000
    is concise and inclusive.

    price >= 1000 AND price <= 5000
    makes the two boundary conditions explicit.

LIKE versus equality:
    name = 'Aarav Sharma'
    requires an exact value.

    name LIKE 'Aarav%'
    performs pattern matching.

IS NULL versus equality:
    email IS NULL
    correctly tests missing values.

    email = NULL
    does not correctly test missing values.

IN versus EXISTS:
    IN is useful for membership in a known list or subquery result.

    EXISTS is useful when the question is whether at least one related row
    exists and is often preferable for correlated relationship checks.

NOT IN versus NOT EXISTS:
    NOT IN can be affected by NULL values in the comparison set.

    NOT EXISTS avoids that specific three-valued-logic trap.
"""
    )

    # Concrete IN example.
    run_query(
        connection,
        """
        SELECT product_name
        FROM products
        WHERE category IN ('Furniture', 'Stationery')
        ORDER BY product_name
        """,
    )

    # Concrete EXISTS example.
    run_query(
        connection,
        """
        SELECT c.customer_name
        FROM customers AS c
        WHERE EXISTS (
            SELECT 1
            FROM orders AS o
            WHERE o.customer_id = c.customer_id
        )
        ORDER BY c.customer_name
        """,
    )


# ============================================================================
# 38. ADVANCED FILTERING WITH MULTIPLE CONDITIONS
# ============================================================================

def demonstrate_advanced_report(connection):
    print_title("36. Advanced multi-condition reporting query")

    # This example combines:
    #   - JOIN
    #   - comparison operators
    #   - BETWEEN
    #   - IN
    #   - IS NULL
    #   - arithmetic
    #   - CASE
    #   - aggregation
    #   - HAVING
    #
    # It reports customers with delivered orders whose gross order value
    # exceeds a threshold after considering discounts.
    run_query(
        connection,
        """
        SELECT
            c.customer_name,
            COUNT(o.order_id) AS delivered_orders,
            SUM(o.quantity * p.price) AS gross_value,
            SUM(
                o.quantity * p.price
                * (1 - COALESCE(o.discount, 0))
            ) AS net_value,
            CASE
                WHEN SUM(
                    o.quantity * p.price
                    * (1 - COALESCE(o.discount, 0))
                ) >= 50000
                THEN 'High Value'
                WHEN SUM(
                    o.quantity * p.price
                    * (1 - COALESCE(o.discount, 0))
                ) >= 20000
                THEN 'Medium Value'
                ELSE 'Standard Value'
            END AS customer_segment
        FROM customers AS c
        JOIN orders AS o
            ON o.customer_id = c.customer_id
        JOIN products AS p
            ON p.product_id = o.product_id
        WHERE c.country = 'India'
          AND c.age BETWEEN 20 AND 55
          AND c.city IN ('Delhi', 'Lucknow', 'Mumbai', 'Pune', 'Bengaluru', 'Chennai')
          AND o.status = 'Delivered'
          AND p.category IN ('Electronics', 'Furniture')
        GROUP BY c.customer_id, c.customer_name
        HAVING SUM(
            o.quantity * p.price
            * (1 - COALESCE(o.discount, 0))
        ) >= 10000
        ORDER BY net_value DESC
        """,
    )


# ============================================================================
# 39. SQL FILTERING WITH CASE-BASED FLAGS
# ============================================================================

def demonstrate_filter_flags(connection):
    print_title("37. Turning filter logic into analytical flags")

    # Instead of removing rows, CASE can create a flag describing whether a
    # row meets a condition.
    run_query(
        connection,
        """
        SELECT
            product_name,
            price,
            stock_quantity,
            CASE
                WHEN stock_quantity = 0 THEN 'Out of Stock'
                WHEN stock_quantity < 10 THEN 'Low Stock'
                ELSE 'Available'
            END AS stock_status
        FROM products
        ORDER BY stock_quantity, product_name
        """,
    )


# ============================================================================
# 40. REAL-WORLD FILTER DESIGN PRINCIPLES
# ============================================================================

def demonstrate_design_principles():
    print_title("38. Filter design principles")

    print(
        """
1. State the business rule before writing SQL.
   Example:
       "Customers aged 25 through 40 in either Delhi or Lucknow."

2. Convert each rule into an explicit predicate.
       age BETWEEN 25 AND 40
       AND city IN ('Delhi', 'Lucknow')

3. Decide how NULL should behave.
   Ask whether missing data should be:
       - excluded,
       - included,
       - replaced with a default,
       - treated as unknown.

4. Use parentheses for mixed AND/OR conditions.

5. Use parameters for values supplied by users or applications.

6. Test boundary values.
   For BETWEEN, test:
       lower boundary,
       upper boundary,
       just below,
       just above.

7. Check query plans for large tables.
   Correct logic is necessary, but production performance also matters.

8. Avoid unnecessary transformations on indexed columns.

9. Keep filtering logic readable.
   A technically correct condition can still be difficult to audit if it
   contains deeply nested Boolean expressions without clear formatting.

10. Confirm whether filtering belongs in WHERE, HAVING, JOIN ON, or a
    subquery based on the required semantics.
"""
    )


# ============================================================================
# 41. MINI PRACTICE EXERCISES
# ============================================================================

def demonstrate_practice_exercises(connection):
    print_title("39. Practice exercises with executable answers")

    exercises = [
        (
            "Products costing at least 10000",
            """
            SELECT product_name, price
            FROM products
            WHERE price >= 10000
            ORDER BY price
            """,
        ),
        (
            "Indian customers aged 30 or more",
            """
            SELECT customer_name, age
            FROM customers
            WHERE country = 'India'
              AND age >= 30
            ORDER BY age
            """,
        ),
        (
            "Customers from Delhi or Pune",
            """
            SELECT customer_name, city
            FROM customers
            WHERE city IN ('Delhi', 'Pune')
            ORDER BY customer_name
            """,
        ),
        (
            "Products between 1000 and 5000",
            """
            SELECT product_name, price
            FROM products
            WHERE price BETWEEN 1000 AND 5000
            ORDER BY price
            """,
        ),
        (
            "Customers without email addresses",
            """
            SELECT customer_name
            FROM customers
            WHERE email IS NULL
            ORDER BY customer_name
            """,
        ),
        (
            "Products whose names contain 'o'",
            """
            SELECT product_name
            FROM products
            WHERE product_name LIKE '%o%'
            ORDER BY product_name
            """,
        ),
        (
            "Delivered orders with quantity at least 2",
            """
            SELECT order_id, quantity, status
            FROM orders
            WHERE status = 'Delivered'
              AND quantity >= 2
            ORDER BY quantity DESC
            """,
        ),
    ]

    for number, (question, sql) in enumerate(exercises, start=1):
        print(f"\nExercise {number}: {question}")
        run_query(connection, sql)


# ============================================================================
# 42. COMPLETE INTEGRATED EXAMPLE
# ============================================================================

def integrated_filtering_example(connection):
    print_title("40. Complete integrated filtering example")

    # Business requirement:
    #
    # Return Indian customers aged 25-50 who live in one of four selected
    # cities, have Gold or Silver membership, have an email, and have at
    # least one delivered order for an Electronics product priced between
    # 5000 and 50000.
    #
    # The query demonstrates:
    #   - WHERE
    #   - AND
    #   - BETWEEN
    #   - IN
    #   - IS NOT NULL
    #   - JOIN
    #   - EXISTS
    #   - aliases
    #   - explicit parentheses

    sql = """
        SELECT
            c.customer_id,
            c.customer_name,
            c.city,
            c.age,
            c.membership,
            c.email
        FROM customers AS c
        WHERE c.country = ?
          AND c.age BETWEEN ? AND ?
          AND c.city IN (?, ?, ?, ?)
          AND c.membership IN (?, ?)
          AND c.email IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM orders AS o
              JOIN products AS p
                  ON p.product_id = o.product_id
              WHERE o.customer_id = c.customer_id
                AND o.status = ?
                AND p.category = ?
                AND p.price BETWEEN ? AND ?
          )
        ORDER BY c.city, c.customer_name
    """

    parameters = (
        "India",
        25,
        50,
        "Delhi",
        "Lucknow",
        "Mumbai",
        "Pune",
        "Gold",
        "Silver",
        "Delivered",
        "Electronics",
        5000,
        50000,
    )

    run_query(connection, sql, parameters)


# ============================================================================
# 43. MAIN PROGRAM
# ============================================================================

def main():
    """
    Execute the complete SQL filtering tutorial.

    Every example runs against the same in-memory database. The database is
    automatically discarded when the connection closes.
    """
    connection = create_connection()

    try:
        create_schema(connection)
        insert_sample_data(connection)

        demonstrate_where_basics(connection)
        demonstrate_comparison_operators(connection)
        demonstrate_logical_operators(connection)
        demonstrate_precedence(connection)
        demonstrate_null(connection)
        demonstrate_null_logic(connection)
        demonstrate_null_handling(connection)
        demonstrate_between(connection)
        demonstrate_in(connection)
        demonstrate_parameterized_in(connection)
        demonstrate_like(connection)
        demonstrate_like_escape(connection)
        demonstrate_like_case(connection)
        demonstrate_complex_filters(connection)
        demonstrate_calculated_filters(connection)
        demonstrate_case_filtering(connection)
        demonstrate_where_vs_having(connection)
        demonstrate_subqueries(connection)
        demonstrate_exists(connection)
        demonstrate_correlated_subquery(connection)
        demonstrate_date_filtering(connection)
        demonstrate_edge_cases(connection)
        demonstrate_dynamic_filters(connection)
        demonstrate_sql_injection_safety(connection)
        demonstrate_indexing(connection)
        demonstrate_logical_query_order(connection)
        demonstrate_business_filter(connection)
        demonstrate_order_filter(connection)
        demonstrate_conditional_aggregation(connection)
        demonstrate_join_filtering(connection)
        demonstrate_filter_testing(connection)
        demonstrate_assertions(connection)
        demonstrate_common_mistakes(connection)
        demonstrate_parameterized_thresholds(connection)
        demonstrate_filter_comparisons(connection)
        demonstrate_advanced_report(connection)
        demonstrate_filter_flags(connection)
        demonstrate_design_principles()
        demonstrate_practice_exercises(connection)
        integrated_filtering_example(connection)

        print_title("Tutorial execution completed")
        print("All SQL filtering demonstrations executed successfully.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
