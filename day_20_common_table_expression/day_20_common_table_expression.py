"""
Common Table Expressions (CTEs)
===============================

Topic:
    WITH, reusable query logic, and recursive CTEs

This standalone study script teaches Common Table Expressions from beginner
through advanced practical usage. SQLite is used because Python's standard
library includes sqlite3, so the examples require no third-party package.

The examples cover:
    - Basic SQL queries
    - Why CTEs exist
    - WITH syntax
    - Single and multiple CTEs
    - CTE column naming
    - Reusing intermediate query logic
    - CTEs with JOIN, GROUP BY, HAVING, CASE, and window functions
    - CTEs for data validation and transformation
    - Recursive CTEs
    - Anchor and recursive members
    - Hierarchies
    - Paths and levels
    - Cycle protection
    - Date-series generation
    - Graph-style traversal
    - CTE limitations and trade-offs
    - Query design and debugging
    - Performance considerations
    - Security considerations
    - Practical reporting patterns
"""

import sqlite3
from datetime import date, timedelta
from pprint import pprint


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def print_title(title):
    """Print a readable section heading."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_rows(rows, columns=None):
    """Print sqlite rows as dictionaries for easier reading."""
    if not rows:
        print("(no rows)")
        return

    if columns is None:
        columns = rows[0].keys()

    print(" | ".join(str(column) for column in columns))
    print("-" * 80)

    for row in rows:
        print(" | ".join(str(row[column]) for column in columns))


def run_query(connection, sql, parameters=(), show_sql=False):
    """
    Execute a SELECT-style query and return sqlite3.Row objects.

    Parameterized values are used instead of string concatenation whenever
    external values are involved.
    """
    if show_sql:
        print("\nSQL:")
        print(sql.strip())
        if parameters:
            print("Parameters:", parameters)

    cursor = connection.execute(sql, parameters)
    return cursor.fetchall()


def run_script(connection, sql):
    """Execute multiple SQL statements."""
    connection.executescript(sql)


def explain_query(connection, sql, parameters=()):
    """Display SQLite's query plan for performance study."""
    rows = connection.execute(
        "EXPLAIN QUERY PLAN " + sql,
        parameters
    ).fetchall()

    print_rows(rows)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def create_database():
    """
    Create a small company database.

    The organization table intentionally contains a hierarchy:
        CEO
          -> Engineering Director
              -> Engineering Manager
                  -> Engineers
          -> Product Director
              -> Product Manager
                  -> Product Analysts

    This hierarchy will later be traversed with a recursive CTE.
    """
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")

    run_script(
        connection,
        """
        CREATE TABLE employees (
            employee_id INTEGER PRIMARY KEY,
            employee_name TEXT NOT NULL,
            manager_id INTEGER REFERENCES employees(employee_id),
            department TEXT NOT NULL,
            job_title TEXT NOT NULL,
            salary INTEGER NOT NULL CHECK (salary > 0),
            hire_date TEXT NOT NULL
        );

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            region TEXT NOT NULL
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
            order_date TEXT NOT NULL,
            amount REAL NOT NULL CHECK (amount >= 0),
            status TEXT NOT NULL CHECK (
                status IN ('completed', 'pending', 'cancelled')
            )
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL CHECK (price >= 0)
        );

        CREATE TABLE order_items (
            order_id INTEGER NOT NULL REFERENCES orders(order_id),
            product_id INTEGER NOT NULL REFERENCES products(product_id),
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            PRIMARY KEY (order_id, product_id)
        );

        CREATE INDEX idx_employees_manager
            ON employees(manager_id);

        CREATE INDEX idx_orders_customer
            ON orders(customer_id);

        CREATE INDEX idx_orders_date
            ON orders(order_date);

        CREATE INDEX idx_orders_status
            ON orders(status);
        """
    )

    run_script(
        connection,
        """
        INSERT INTO employees
            (employee_id, employee_name, manager_id, department, job_title, salary, hire_date)
        VALUES
            (1, 'Anita Rao', NULL, 'Executive', 'Chief Executive Officer', 240000, '2018-01-10'),
            (2, 'Vikram Shah', 1, 'Engineering', 'Engineering Director', 190000, '2019-03-15'),
            (3, 'Meera Iyer', 2, 'Engineering', 'Engineering Manager', 145000, '2020-06-01'),
            (4, 'Arjun Singh', 3, 'Engineering', 'Senior Software Engineer', 125000, '2021-01-12'),
            (5, 'Neha Kapoor', 3, 'Engineering', 'Software Engineer', 105000, '2022-02-20'),
            (6, 'Rahul Verma', 3, 'Engineering', 'Software Engineer', 98000, '2023-04-10'),
            (7, 'Karan Malhotra', 2, 'Engineering', 'Platform Manager', 140000, '2020-09-11'),
            (8, 'Isha Gupta', 7, 'Engineering', 'Cloud Engineer', 115000, '2022-05-17'),
            (9, 'Rohan Das', 7, 'Engineering', 'DevOps Engineer', 118000, '2021-12-02'),
            (10, 'Priya Nair', 1, 'Product', 'Product Director', 185000, '2019-07-22'),
            (11, 'Sahil Mehta', 10, 'Product', 'Product Manager', 135000, '2020-11-04'),
            (12, 'Tanya Bose', 11, 'Product', 'Product Analyst', 90000, '2023-01-09'),
            (13, 'Aman Jain', 11, 'Product', 'Product Analyst', 92000, '2022-08-14'),
            (14, 'Divya Menon', 1, 'Finance', 'Finance Manager', 130000, '2020-02-28');

        INSERT INTO customers (customer_id, customer_name, region)
        VALUES
            (1, 'Alpha Industries', 'North'),
            (2, 'Beta Retail', 'South'),
            (3, 'Crest Healthcare', 'West'),
            (4, 'Delta Systems', 'North'),
            (5, 'Evergreen Foods', 'East');

        INSERT INTO orders
            (order_id, customer_id, order_date, amount, status)
        VALUES
            (101, 1, '2026-01-05', 12000, 'completed'),
            (102, 1, '2026-02-10', 18000, 'completed'),
            (103, 1, '2026-03-04', 7000, 'pending'),
            (104, 2, '2026-01-12', 5000, 'completed'),
            (105, 2, '2026-02-18', 8500, 'cancelled'),
            (106, 2, '2026-03-21', 11000, 'completed'),
            (107, 3, '2026-01-25', 22000, 'completed'),
            (108, 3, '2026-03-08', 15000, 'completed'),
            (109, 4, '2026-02-05', 3000, 'pending'),
            (110, 4, '2026-03-10', 9000, 'completed'),
            (111, 5, '2026-01-17', 6500, 'completed'),
            (112, 5, '2026-03-19', 12500, 'completed');

        INSERT INTO products (product_id, product_name, category, price)
        VALUES
            (1, 'Cloud Platform', 'Infrastructure', 5000),
            (2, 'Security Suite', 'Security', 3500),
            (3, 'Analytics Pro', 'Analytics', 2500),
            (4, 'Developer Tools', 'Engineering', 1500);

        INSERT INTO order_items (order_id, product_id, quantity)
        VALUES
            (101, 1, 2),
            (101, 2, 1),
            (102, 1, 1),
            (102, 3, 3),
            (103, 4, 2),
            (104, 2, 1),
            (104, 3, 2),
            (106, 1, 1),
            (106, 4, 4),
            (107, 1, 3),
            (108, 2, 3),
            (108, 3, 2),
            (110, 4, 5),
            (111, 3, 2),
            (112, 1, 1),
            (112, 2, 2);
        """
    )

    return connection


# ---------------------------------------------------------------------------
# Fundamentals: what a CTE is
# ---------------------------------------------------------------------------

def basic_cte():
    print_title("1. Basic CTE: WITH creates a named temporary query result")

    connection = create_database()

    sql = """
        WITH high_value_orders AS (
            SELECT
                order_id,
                customer_id,
                amount
            FROM orders
            WHERE amount >= 10000
        )
        SELECT
            order_id,
            customer_id,
            amount
        FROM high_value_orders
        ORDER BY amount DESC;
    """

    rows = run_query(connection, sql, show_sql=True)
    print_rows(rows)

    print(
        "\nThe CTE named high_value_orders behaves like a temporary named "
        "result set for the duration of this statement."
    )

    connection.close()


# ---------------------------------------------------------------------------
# CTE compared with nested subquery
# ---------------------------------------------------------------------------

def cte_vs_subquery():
    print_title("2. CTE versus nested subquery")

    connection = create_database()

    cte_sql = """
        WITH completed_orders AS (
            SELECT customer_id, amount
            FROM orders
            WHERE status = 'completed'
        )
        SELECT
            customer_id,
            COUNT(*) AS order_count,
            SUM(amount) AS total_amount
        FROM completed_orders
        GROUP BY customer_id
        ORDER BY total_amount DESC;
    """

    subquery_sql = """
        SELECT
            customer_id,
            COUNT(*) AS order_count,
            SUM(amount) AS total_amount
        FROM (
            SELECT customer_id, amount
            FROM orders
            WHERE status = 'completed'
        )
        GROUP BY customer_id
        ORDER BY total_amount DESC;
    """

    print("\nCTE version:")
    print_rows(run_query(connection, cte_sql))

    print("\nEquivalent subquery version:")
    print_rows(run_query(connection, subquery_sql))

    print(
        "\nThe important difference is readability and organization. "
        "The CTE gives the intermediate relation a meaningful name."
    )

    connection.close()


# ---------------------------------------------------------------------------
# Multiple CTEs
# ---------------------------------------------------------------------------

def multiple_ctes():
    print_title("3. Multiple CTEs: build a query in logical stages")

    connection = create_database()

    sql = """
        WITH completed_orders AS (
            SELECT
                customer_id,
                amount
            FROM orders
            WHERE status = 'completed'
        ),
        customer_totals AS (
            SELECT
                customer_id,
                COUNT(*) AS order_count,
                SUM(amount) AS total_spend
            FROM completed_orders
            GROUP BY customer_id
        ),
        classified_customers AS (
            SELECT
                customer_id,
                order_count,
                total_spend,
                CASE
                    WHEN total_spend >= 30000 THEN 'Enterprise'
                    WHEN total_spend >= 15000 THEN 'Growth'
                    ELSE 'Standard'
                END AS customer_segment
            FROM customer_totals
        )
        SELECT
            c.customer_name,
            c.region,
            x.order_count,
            ROUND(x.total_spend, 2) AS total_spend,
            x.customer_segment
        FROM classified_customers AS x
        JOIN customers AS c
            ON c.customer_id = x.customer_id
        ORDER BY x.total_spend DESC;
    """

    rows = run_query(connection, sql, show_sql=True)
    print_rows(rows)

    print(
        "\nEach CTE consumes the result produced by an earlier logical stage."
    )

    connection.close()


# ---------------------------------------------------------------------------
# CTE column names
# ---------------------------------------------------------------------------

def cte_column_names():
    print_title("4. Explicit CTE column names")

    connection = create_database()

    sql = """
        WITH spending(customer_id, completed_spend) AS (
            SELECT
                customer_id,
                SUM(amount)
            FROM orders
            WHERE status = 'completed'
            GROUP BY customer_id
        )
        SELECT *
        FROM spending
        ORDER BY completed_spend DESC;
    """

    rows = run_query(connection, sql)
    print_rows(rows)

    print(
        "\nThe column list after the CTE name explicitly assigns names "
        "to the CTE's output columns."
    )

    connection.close()


# ---------------------------------------------------------------------------
# CTE with JOIN
# ---------------------------------------------------------------------------

def cte_with_join():
    print_title("5. CTE combined with JOIN")

    connection = create_database()

    sql = """
        WITH product_sales AS (
            SELECT
                oi.product_id,
                SUM(oi.quantity) AS units_sold
            FROM order_items AS oi
            JOIN orders AS o
                ON o.order_id = oi.order_id
            WHERE o.status = 'completed'
            GROUP BY oi.product_id
        )
        SELECT
            p.product_name,
            p.category,
            ps.units_sold,
            p.price,
            ROUND(ps.units_sold * p.price, 2) AS calculated_value
        FROM product_sales AS ps
        JOIN products AS p
            ON p.product_id = ps.product_id
        ORDER BY calculated_value DESC;
    """

    print_rows(run_query(connection, sql))

    connection.close()


# ---------------------------------------------------------------------------
# CTE with HAVING
# ---------------------------------------------------------------------------

def cte_with_having():
    print_title("6. CTE with GROUP BY and HAVING")

    connection = create_database()

    sql = """
        WITH regional_sales AS (
            SELECT
                c.region,
                COUNT(o.order_id) AS completed_orders,
                SUM(o.amount) AS revenue
            FROM customers AS c
            JOIN orders AS o
                ON o.customer_id = c.customer_id
            WHERE o.status = 'completed'
            GROUP BY c.region
            HAVING SUM(o.amount) >= 15000
        )
        SELECT *
        FROM regional_sales
        ORDER BY revenue DESC;
    """

    print_rows(run_query(connection, sql))

    connection.close()


# ---------------------------------------------------------------------------
# CTE and window functions
# ---------------------------------------------------------------------------

def cte_with_window_function():
    print_title("7. CTE with a window function")

    connection = create_database()

    sql = """
        WITH customer_spend AS (
            SELECT
                c.customer_id,
                c.customer_name,
                c.region,
                SUM(o.amount) AS total_spend
            FROM customers AS c
            JOIN orders AS o
                ON o.customer_id = c.customer_id
            WHERE o.status = 'completed'
            GROUP BY
                c.customer_id,
                c.customer_name,
                c.region
        ),
        ranked_customers AS (
            SELECT
                customer_id,
                customer_name,
                region,
                total_spend,
                RANK() OVER (
                    ORDER BY total_spend DESC
                ) AS spend_rank,
                ROUND(
                    100.0 * total_spend /
                    SUM(total_spend) OVER (),
                    2
                ) AS percentage_of_total
            FROM customer_spend
        )
        SELECT *
        FROM ranked_customers
        ORDER BY spend_rank;
    """

    print_rows(run_query(connection, sql))

    print(
        "\nA CTE can make a complex window-function query easier to read "
        "by separating aggregation from ranking."
    )

    connection.close()


# ---------------------------------------------------------------------------
# Data quality with CTEs
# ---------------------------------------------------------------------------

def cte_for_validation():
    print_title("8. CTE for data-quality classification")

    connection = create_database()

    sql = """
        WITH order_quality AS (
            SELECT
                order_id,
                customer_id,
                amount,
                status,
                CASE
                    WHEN amount < 0 THEN 'INVALID_AMOUNT'
                    WHEN status NOT IN (
                        'completed',
                        'pending',
                        'cancelled'
                    ) THEN 'INVALID_STATUS'
                    WHEN amount = 0 THEN 'ZERO_VALUE'
                    ELSE 'VALID'
                END AS quality_status
            FROM orders
        )
        SELECT *
        FROM order_quality
        WHERE quality_status <> 'VALID'
        ORDER BY order_id;
    """

    rows = run_query(connection, sql)
    print_rows(rows)

    print(
        "\nThe current schema prevents several invalid states, so the "
        "query intentionally demonstrates a validation pattern rather "
        "than relying on invalid rows already existing."
    )

    connection.close()


# ---------------------------------------------------------------------------
# CTE used more than once
# ---------------------------------------------------------------------------

def cte_reuse():
    print_title("9. Reusing a CTE multiple times")

    connection = create_database()

    sql = """
        WITH completed_orders AS (
            SELECT
                customer_id,
                amount
            FROM orders
            WHERE status = 'completed'
        )
        SELECT
            c.customer_name,
            (
                SELECT ROUND(SUM(co.amount), 2)
                FROM completed_orders AS co
                WHERE co.customer_id = c.customer_id
            ) AS customer_spend,
            (
                SELECT COUNT(*)
                FROM completed_orders AS co
                WHERE co.customer_id = c.customer_id
            ) AS completed_order_count
        FROM customers AS c
        ORDER BY customer_spend DESC;
    """

    print_rows(run_query(connection, sql))

    print(
        "\nA CTE provides one named logical definition that can be "
        "referenced more than once within the statement."
    )

    connection.close()


# ---------------------------------------------------------------------------
# Recursive CTE fundamentals
# ---------------------------------------------------------------------------

def recursive_employee_hierarchy():
    print_title("10. Recursive CTE: employee hierarchy")

    connection = create_database()

    sql = """
        WITH RECURSIVE employee_tree AS (
            -- Anchor member: begin at the top-level employee.
            SELECT
                employee_id,
                employee_name,
                manager_id,
                department,
                job_title,
                0 AS level,
                employee_name AS path
            FROM employees
            WHERE manager_id IS NULL

            UNION ALL

            -- Recursive member: find direct reports of the current rows.
            SELECT
                e.employee_id,
                e.employee_name,
                e.manager_id,
                e.department,
                e.job_title,
                tree.level + 1,
                tree.path || ' > ' || e.employee_name
            FROM employees AS e
            JOIN employee_tree AS tree
                ON e.manager_id = tree.employee_id
        )
        SELECT
            employee_id,
            employee_name,
            department,
            job_title,
            level,
            path
        FROM employee_tree
        ORDER BY path;
    """

    rows = run_query(connection, sql, show_sql=True)
    print_rows(rows)

    print(
        "\nA recursive CTE consists conceptually of two parts:"
        "\n  1. An anchor query that establishes the initial rows."
        "\n  2. A recursive query that produces the next generation."
        "\n"
        "\nUNION ALL combines the anchor rows with rows produced by recursion."
    )

    connection.close()


# ---------------------------------------------------------------------------
# Recursive CTE starting from a selected manager
# ---------------------------------------------------------------------------

def recursive_subtree():
    print_title("11. Recursive CTE: retrieve one manager's entire subtree")

    connection = create_database()

    selected_manager = 2

    sql = """
        WITH RECURSIVE subtree AS (
            SELECT
                employee_id,
                employee_name,
                manager_id,
                0 AS distance
            FROM employees
            WHERE employee_id = ?

            UNION ALL

            SELECT
                e.employee_id,
                e.employee_name,
                e.manager_id,
                subtree.distance + 1
            FROM employees AS e
            JOIN subtree
                ON e.manager_id = subtree.employee_id
        )
        SELECT *
        FROM subtree
        ORDER BY distance, employee_id;
    """

    rows = run_query(connection, sql, (selected_manager,))
    print_rows(rows)

    connection.close()


# ---------------------------------------------------------------------------
# Recursive CTE: ancestors
# ---------------------------------------------------------------------------

def recursive_ancestors():
    print_title("12. Recursive CTE: find management ancestors")

    connection = create_database()

    employee_id = 6

    sql = """
        WITH RECURSIVE management_chain AS (
            SELECT
                employee_id,
                employee_name,
                manager_id,
                0 AS distance
            FROM employees
            WHERE employee_id = ?

            UNION ALL

            SELECT
                manager.employee_id,
                manager.employee_name,
                manager.manager_id,
                chain.distance + 1
            FROM employees AS manager
            JOIN management_chain AS chain
                ON manager.employee_id = chain.manager_id
        )
        SELECT
            employee_id,
            employee_name,
            distance
        FROM management_chain
        ORDER BY distance;
    """

    rows = run_query(connection, sql, (employee_id,))
    print_rows(rows)

    connection.close()


# ---------------------------------------------------------------------------
# Recursive CTE: generate numbers
# ---------------------------------------------------------------------------

def recursive_number_sequence():
    print_title("13. Recursive CTE: generate a sequence")

    connection = create_database()

    sql = """
        WITH RECURSIVE numbers(n) AS (
            SELECT 1

            UNION ALL

            SELECT n + 1
            FROM numbers
            WHERE n < 10
        )
        SELECT n
        FROM numbers;
    """

    print_rows(run_query(connection, sql))

    print(
        "\nThe stopping condition is essential. Without a condition that "
        "eventually prevents another recursive row, recursion can continue "
        "until the database's recursion limit or another resource limit "
        "is reached."
    )

    connection.close()


# ---------------------------------------------------------------------------
# Recursive CTE: dates
# ---------------------------------------------------------------------------

def recursive_date_series():
    print_title("14. Recursive CTE: generate dates")

    connection = create_database()

    sql = """
        WITH RECURSIVE calendar(day) AS (
            SELECT DATE('2026-01-01')

            UNION ALL

            SELECT DATE(day, '+1 day')
            FROM calendar
            WHERE day < DATE('2026-01-07')
        )
        SELECT day
        FROM calendar;
    """

    print_rows(run_query(connection, sql))

    connection.close()


# ---------------------------------------------------------------------------
# Recursive CTE: hierarchy aggregation
# ---------------------------------------------------------------------------

def recursive_hierarchy_aggregation():
    print_title("15. Recursive hierarchy with accumulated information")

    connection = create_database()

    sql = """
        WITH RECURSIVE organization AS (
            SELECT
                employee_id,
                employee_name,
                manager_id,
                salary,
                0 AS level,
                salary AS hierarchy_salary
            FROM employees
            WHERE manager_id IS NULL

            UNION ALL

            SELECT
                e.employee_id,
                e.employee_name,
                e.manager_id,
                e.salary,
                organization.level + 1,
                organization.hierarchy_salary + e.salary
            FROM employees AS e
            JOIN organization
                ON e.manager_id = organization.employee_id
        )
        SELECT
            employee_name,
            level,
            salary,
            hierarchy_salary
        FROM organization
        ORDER BY level, employee_id;
    """

    print_rows(run_query(connection, sql))

    print(
        "\nThe hierarchy_salary column illustrates an important recursive "
        "pattern: values can be carried forward and accumulated during "
        "each recursive step."
    )

    connection.close()


# ---------------------------------------------------------------------------
# Recursive CTE: graph traversal
# ---------------------------------------------------------------------------

def recursive_graph_traversal():
    print_title("16. Recursive CTE as a graph traversal")

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    run_script(
        connection,
        """
        CREATE TABLE connections (
            source TEXT NOT NULL,
            destination TEXT NOT NULL
        );

        INSERT INTO connections(source, destination) VALUES
            ('A', 'B'),
            ('A', 'C'),
            ('B', 'D'),
            ('C', 'D'),
            ('D', 'E');
        """
    )

    sql = """
        WITH RECURSIVE reachable(node, depth) AS (
            SELECT 'A', 0

            UNION

            SELECT
                c.destination,
                reachable.depth + 1
            FROM connections AS c
            JOIN reachable
                ON c.source = reachable.node
        )
        SELECT
            node,
            MIN(depth) AS minimum_depth
        FROM reachable
        GROUP BY node
        ORDER BY minimum_depth, node;
    """

    print_rows(run_query(connection, sql))

    print(
        "\nUNION rather than UNION ALL is useful in this graph example "
        "because duplicate reachable states are removed. In cyclic graphs, "
        "duplicate elimination can also help prevent endless revisiting, "
        "although the exact design should depend on the graph semantics."
    )

    connection.close()


# ---------------------------------------------------------------------------
# Recursive CTE: explicit path-based cycle protection
# ---------------------------------------------------------------------------

def recursive_cycle_protection():
    print_title("17. Recursive traversal with explicit cycle protection")

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    run_script(
        connection,
        """
        CREATE TABLE directed_edges (
            source TEXT NOT NULL,
            destination TEXT NOT NULL
        );

        INSERT INTO directed_edges(source, destination) VALUES
            ('A', 'B'),
            ('B', 'C'),
            ('C', 'A'),
            ('C', 'D');
        """
    )

    sql = """
        WITH RECURSIVE walk(node, path) AS (
            SELECT
                'A',
                '|A|'

            UNION ALL

            SELECT
                e.destination,
                walk.path || e.destination || '|'
            FROM directed_edges AS e
            JOIN walk
                ON e.source = walk.node
            WHERE INSTR(
                walk.path,
                '|' || e.destination || '|'
            ) = 0
        )
        SELECT
            node,
            path
        FROM walk
        ORDER BY LENGTH(path), path;
    """

    print_rows(run_query(connection, sql))

    print(
        "\nThe path is stored using delimiters so that a complete node "
        "identifier can be searched rather than accidentally matching "
        "part of another identifier."
    )

    connection.close()


# ---------------------------------------------------------------------------
# Recursive CTE: bill of materials
# ---------------------------------------------------------------------------

def recursive_bill_of_materials():
    print_title("18. Recursive CTE: bill of materials expansion")

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    run_script(
        connection,
        """
        CREATE TABLE components (
            parent TEXT NOT NULL,
            child TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0)
        );

        INSERT INTO components(parent, child, quantity) VALUES
            ('Laptop', 'Motherboard', 1),
            ('Laptop', 'Battery', 1),
            ('Laptop', 'Keyboard', 1),
            ('Motherboard', 'CPU', 1),
            ('Motherboard', 'RAM', 2),
            ('Motherboard', 'SSD', 1),
            ('Keyboard', 'Keycap', 80);
        """
    )

    sql = """
        WITH RECURSIVE bom(item, quantity, level) AS (
            SELECT
                child,
                quantity,
                1
            FROM components
            WHERE parent = 'Laptop'

            UNION ALL

            SELECT
                c.child,
                bom.quantity * c.quantity,
                bom.level + 1
            FROM components AS c
            JOIN bom
                ON c.parent = bom.item
        )
        SELECT
            item,
            SUM(quantity) AS total_required,
            MIN(level) AS minimum_level
        FROM bom
        GROUP BY item
        ORDER BY minimum_level, item;
    """

    print_rows(run_query(connection, sql))

    print(
        "\nThis pattern appears in manufacturing, package dependency "
        "analysis, product configuration, and other hierarchical systems."
    )

    connection.close()


# ---------------------------------------------------------------------------
# CTE with parameters
# ---------------------------------------------------------------------------

def parameterized_cte():
    print_title("19. Parameterized values and CTEs")

    connection = create_database()

    minimum_amount = 10000

    sql = """
        WITH qualifying_orders AS (
            SELECT
                order_id,
                customer_id,
                amount
            FROM orders
            WHERE amount >= ?
              AND status = 'completed'
        )
        SELECT
            q.order_id,
            c.customer_name,
            q.amount
        FROM qualifying_orders AS q
        JOIN customers AS c
            ON c.customer_id = q.customer_id
        ORDER BY q.amount DESC;
    """

    rows = run_query(connection, sql, (minimum_amount,))
    print_rows(rows)

    print(
        "\nUsing a parameter prevents a value from being interpreted as "
        "SQL syntax. CTEs do not remove the need for normal SQL security "
        "practices."
    )

    connection.close()


# ---------------------------------------------------------------------------
# CTE used for a business report
# ---------------------------------------------------------------------------

def business_report():
    print_title("20. Industry-style sales report built with CTE stages")

    connection = create_database()

    sql = """
        WITH completed_sales AS (
            SELECT
                o.order_id,
                o.customer_id,
                o.order_date,
                o.amount
            FROM orders AS o
            WHERE o.status = 'completed'
        ),
        monthly_sales AS (
            SELECT
                customer_id,
                STRFTIME('%Y-%m', order_date) AS sales_month,
                SUM(amount) AS monthly_revenue
            FROM completed_sales
            GROUP BY
                customer_id,
                STRFTIME('%Y-%m', order_date)
        ),
        customer_month_totals AS (
            SELECT
                customer_id,
                SUM(monthly_revenue) AS total_revenue,
                COUNT(*) AS active_months
            FROM monthly_sales
            GROUP BY customer_id
        ),
        ranked_customers AS (
            SELECT
                customer_id,
                total_revenue,
                active_months,
                DENSE_RANK() OVER (
                    ORDER BY total_revenue DESC
                ) AS revenue_rank
            FROM customer_month_totals
        )
        SELECT
            c.customer_name,
            c.region,
            r.total_revenue,
            r.active_months,
            r.revenue_rank
        FROM ranked_customers AS r
        JOIN customers AS c
            ON c.customer_id = r.customer_id
        ORDER BY r.revenue_rank, c.customer_name;
    """

    print_rows(run_query(connection, sql))

    print(
        "\nThis is a practical CTE pattern: filter raw data, aggregate it, "
        "derive business metrics, rank the resulting entities, and finally "
        "join descriptive attributes."
    )

    connection.close()


# ---------------------------------------------------------------------------
# CTE and NULL behavior
# ---------------------------------------------------------------------------

def cte_null_behavior():
    print_title("21. CTEs do not change SQL NULL semantics")

    connection = create_database()

    sql = """
        WITH customer_spend AS (
            SELECT
                c.customer_id,
                c.customer_name,
                COALESCE(SUM(
                    CASE
                        WHEN o.status = 'completed' THEN o.amount
                        ELSE NULL
                    END
                ), 0) AS completed_spend
            FROM customers AS c
            LEFT JOIN orders AS o
                ON o.customer_id = c.customer_id
            GROUP BY
                c.customer_id,
                c.customer_name
        )
        SELECT *
        FROM customer_spend
        ORDER BY customer_id;
    """

    print_rows(run_query(connection, sql))

    print(
        "\nCOALESCE converts a NULL aggregate result into zero. "
        "The CTE itself does not change NULL behavior."
    )

    connection.close()


# ---------------------------------------------------------------------------
# CTE debugging
# ---------------------------------------------------------------------------

def debugging_ctes():
    print_title("22. Debugging a multi-stage CTE")

    connection = create_database()

    full_query = """
        WITH completed_orders AS (
            SELECT
                customer_id,
                amount
            FROM orders
            WHERE status = 'completed'
        ),
        totals AS (
            SELECT
                customer_id,
                SUM(amount) AS total
            FROM completed_orders
            GROUP BY customer_id
        )
        SELECT *
        FROM totals
        ORDER BY total DESC;
    """

    print("Final query result:")
    print_rows(run_query(connection, full_query))

    first_stage = """
        SELECT
            customer_id,
            amount
        FROM orders
        WHERE status = 'completed';
    """

    second_stage = """
        SELECT
            customer_id,
            SUM(amount) AS total
        FROM (
            SELECT
                customer_id,
                amount
            FROM orders
            WHERE status = 'completed'
        )
        GROUP BY customer_id;
    """

    print("\nDebugging stage 1:")
    print_rows(run_query(connection, first_stage))

    print("\nDebugging stage 2:")
    print_rows(run_query(connection, second_stage))

    print(
        "\nA useful debugging method is to temporarily run an individual "
        "logical stage as a standalone SELECT. This helps identify where "
        "rows or calculations stop matching expectations."
    )

    connection.close()


# ---------------------------------------------------------------------------
# EXPLAIN QUERY PLAN
# ---------------------------------------------------------------------------

def performance_plan():
    print_title("23. Performance: inspect the query plan")

    connection = create_database()

    sql = """
        WITH completed_orders AS (
            SELECT
                customer_id,
                amount
            FROM orders
            WHERE status = 'completed'
        )
        SELECT
            customer_id,
            SUM(amount) AS total
        FROM completed_orders
        GROUP BY customer_id;
    """

    print("SQLite query plan:")
    explain_query(connection, sql)

    print(
        "\nImportant performance principle: a CTE is primarily a query "
        "organization mechanism. Its presence does not automatically mean "
        "the database creates a permanent or indexed temporary table."
    )

    connection.close()


# ---------------------------------------------------------------------------
# Materialization discussion using SQLite syntax
# ---------------------------------------------------------------------------

def materialization_concept():
    print_title("24. Materialization is database-specific")

    print(
        """
Some database systems provide controls or optimizer behavior around CTE
materialization. The exact rules differ by database engine and version.

A CTE should therefore not be assumed to mean:

    "run this query once, store every row physically, and reuse the stored rows."

The optimizer may inline, materialize, spool, or otherwise transform the
logical query depending on the engine and circumstances.

The correct performance approach is to inspect the actual execution plan,
measure representative workloads, and understand the target database.
"""
    )


# ---------------------------------------------------------------------------
# CTE scope
# ---------------------------------------------------------------------------

def cte_scope():
    print_title("25. CTE scope")

    connection = create_database()

    sql = """
        WITH recent_orders AS (
            SELECT *
            FROM orders
            WHERE order_date >= '2026-03-01'
        )
        SELECT COUNT(*) AS order_count
        FROM recent_orders;
    """

    print_rows(run_query(connection, sql))

    try:
        connection.execute(
            "SELECT COUNT(*) FROM recent_orders"
        )
    except sqlite3.Error as error:
        print(
            "\nExpected error when referencing the CTE outside its statement:"
        )
        print(error)

    connection.close()


# ---------------------------------------------------------------------------
# CTE and data modification
# ---------------------------------------------------------------------------

def cte_with_data_modification():
    print_title("26. CTEs and data modification")

    connection = create_database()

    print(
        """
CTEs can participate in data-modification statements in database systems
that support the corresponding syntax.

SQLite has specific syntax rules around DML and CTEs. This example focuses
on the portable conceptual pattern rather than assuming every database
supports exactly the same statement form.

Conceptually, a system may use:

    WITH candidates AS (...)
    UPDATE target
    SET ...
    WHERE ...;

The important idea is that the CTE can define the rows or calculations used
by the modification statement.
"""
    )

    connection.close()


# ---------------------------------------------------------------------------
# CTE naming best practices
# ---------------------------------------------------------------------------

def naming_best_practices():
    print_title("27. CTE naming and design principles")

    print(
        """
Useful naming principles:

    completed_orders
        Describes the rows represented by the CTE.

    customer_totals
        Describes the aggregation represented by the CTE.

    ranked_customers
        Describes the transformation performed by the CTE.

Avoid names such as:

    temp1
    data
    result
    x
    query2

Good CTE names make a multi-stage SQL statement read like a sequence of
logical transformations.
"""
    )


# ---------------------------------------------------------------------------
# Recursive CTE rules
# ---------------------------------------------------------------------------

def recursive_rules():
    print_title("28. Recursive CTE rules and common failure modes")

    print(
        """
A recursive CTE generally contains:

    WITH RECURSIVE name AS (
        anchor query
        UNION ALL
        recursive query
    )
    SELECT ...

Important design questions:

1. What is the starting set?
2. What relationship produces the next set?
3. What condition stops recursion?
4. Can the data contain cycles?
5. Can the recursive step produce duplicate states?
6. What is the maximum expected depth?
7. What indexes support the recursive join?
8. Is the result guaranteed to remain finite?

Common mistakes:

- Forgetting the termination condition.
- Joining in the wrong direction.
- Using UNION ALL when duplicate elimination is required.
- Failing to protect against cycles.
- Generating an unexpectedly huge result.
- Assuming hierarchy depth is small when production data is not bounded.
"""
    )


# ---------------------------------------------------------------------------
# Recursive hierarchy with ordering
# ---------------------------------------------------------------------------

def hierarchy_ordering():
    print_title("29. Recursive hierarchy and deterministic ordering")

    connection = create_database()

    sql = """
        WITH RECURSIVE hierarchy AS (
            SELECT
                employee_id,
                employee_name,
                manager_id,
                0 AS level,
                printf('%06d', employee_id) AS sort_path
            FROM employees
            WHERE manager_id IS NULL

            UNION ALL

            SELECT
                e.employee_id,
                e.employee_name,
                e.manager_id,
                h.level + 1,
                h.sort_path || '.' || printf('%06d', e.employee_id)
            FROM employees AS e
            JOIN hierarchy AS h
                ON e.manager_id = h.employee_id
        )
        SELECT
            employee_id,
            employee_name,
            level,
            sort_path
        FROM hierarchy
        ORDER BY sort_path;
    """

    print_rows(run_query(connection, sql))

    print(
        "\nA path column can be used as a deterministic traversal key when "
        "the application requires hierarchical output rather than simply "
        "sorting by employee ID or level."
    )

    connection.close()


# ---------------------------------------------------------------------------
# Testing CTE logic
# ---------------------------------------------------------------------------

def test_cte_logic():
    print_title("30. Testing a CTE result")

    connection = create_database()

    sql = """
        WITH completed_orders AS (
            SELECT *
            FROM orders
            WHERE status = 'completed'
        )
        SELECT COUNT(*) AS count
        FROM completed_orders;
    """

    row = connection.execute(sql).fetchone()

    expected_count = 9

    print("Actual completed-order count:", row["count"])
    print("Expected count:", expected_count)

    assert row["count"] == expected_count

    print("Test passed.")

    connection.close()


# ---------------------------------------------------------------------------
# Advanced practical query: retention-style monthly activity
# ---------------------------------------------------------------------------

def monthly_activity():
    print_title("31. Advanced example: monthly customer activity")

    connection = create_database()

    sql = """
        WITH completed_orders AS (
            SELECT
                customer_id,
                STRFTIME('%Y-%m', order_date) AS month
            FROM orders
            WHERE status = 'completed'
        ),
        customer_months AS (
            SELECT DISTINCT
                customer_id,
                month
            FROM completed_orders
        ),
        monthly_customer_counts AS (
            SELECT
                month,
                COUNT(*) AS active_customers
            FROM customer_months
            GROUP BY month
        )
        SELECT
            month,
            active_customers
        FROM monthly_customer_counts
        ORDER BY month;
    """

    print_rows(run_query(connection, sql))

    print(
        "\nThis pattern separates raw event filtering, deduplication, and "
        "aggregation into understandable stages."
    )

    connection.close()


# ---------------------------------------------------------------------------
# Advanced practical query: customer order classification
# ---------------------------------------------------------------------------

def customer_order_classification():
    print_title("32. Advanced example: customer behavior classification")

    connection = create_database()

    sql = """
        WITH completed_orders AS (
            SELECT
                customer_id,
                amount
            FROM orders
            WHERE status = 'completed'
        ),
        customer_metrics AS (
            SELECT
                customer_id,
                COUNT(*) AS order_count,
                SUM(amount) AS revenue,
                AVG(amount) AS average_order_value
            FROM completed_orders
            GROUP BY customer_id
        ),
        classified AS (
            SELECT
                customer_id,
                order_count,
                ROUND(revenue, 2) AS revenue,
                ROUND(average_order_value, 2) AS average_order_value,
                CASE
                    WHEN revenue >= 30000
                         AND order_count >= 2
                        THEN 'High-value recurring'
                    WHEN revenue >= 15000
                        THEN 'High-value'
                    WHEN order_count >= 2
                        THEN 'Recurring'
                    ELSE 'Occasional'
                END AS behavior_class
            FROM customer_metrics
        )
        SELECT
            c.customer_name,
            x.order_count,
            x.revenue,
            x.average_order_value,
            x.behavior_class
        FROM classified AS x
        JOIN customers AS c
            ON c.customer_id = x.customer_id
        ORDER BY x.revenue DESC;
    """

    print_rows(run_query(connection, sql))

    connection.close()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def edge_cases():
    print_title("33. Important CTE edge cases")

    connection = create_database()

    print("\nEdge case 1: empty result")
    sql_empty = """
        WITH nothing AS (
            SELECT *
            FROM orders
            WHERE amount > 999999999
        )
        SELECT COUNT(*) AS rows_found
        FROM nothing;
    """
    print_rows(run_query(connection, sql_empty))

    print("\nEdge case 2: duplicate rows")
    sql_duplicates = """
        WITH repeated_regions AS (
            SELECT region
            FROM customers
            UNION ALL
            SELECT region
            FROM customers
        )
        SELECT
            region,
            COUNT(*) AS occurrences
        FROM repeated_regions
        GROUP BY region
        ORDER BY region;
    """
    print_rows(run_query(connection, sql_duplicates))

    print("\nEdge case 3: removing duplicates with UNION")
    sql_distinct = """
        WITH regions AS (
            SELECT region
            FROM customers
            UNION
            SELECT region
            FROM customers
        )
        SELECT region
        FROM regions
        ORDER BY region;
    """
    print_rows(run_query(connection, sql_distinct))

    print("\nEdge case 4: NULL manager")
    sql_null_manager = """
        WITH top_level AS (
            SELECT *
            FROM employees
            WHERE manager_id IS NULL
        )
        SELECT employee_name, manager_id
        FROM top_level;
    """
    print_rows(run_query(connection, sql_null_manager))

    connection.close()


# ---------------------------------------------------------------------------
# SQL injection discussion
# ---------------------------------------------------------------------------

def security_considerations():
    print_title("34. Security considerations")

    print(
        """
A CTE does not provide security by itself.

Use parameterized queries for values:

    WHERE amount >= ?

Do not construct SQL like:

    WHERE amount >= ' + user_input + '

User-controlled identifiers such as table names and column names usually
cannot be supplied as ordinary value parameters. They require controlled
allow-lists or database-specific identifier handling.

Security considerations include:

- Parameterize values.
- Validate application input.
- Use least-privilege database accounts.
- Avoid exposing unnecessary columns.
- Apply row-level authorization where required.
- Treat recursive queries as potentially expensive operations.
- Apply reasonable depth and workload controls where the database supports
  them.
- Test authorization independently from query readability.
"""
    )


# ---------------------------------------------------------------------------
# Performance considerations
# ---------------------------------------------------------------------------

def performance_considerations():
    print_title("35. Performance considerations")

    print(
        """
CTEs improve logical organization, but readability and performance are
different concerns.

Important considerations:

1. Index the columns used by joins and filters.
2. In recursive hierarchies, index manager_id or the equivalent parent key.
3. Filter data as early as practical when it reduces the working set.
4. Avoid carrying unnecessary columns through every CTE.
5. Inspect EXPLAIN or the database-specific execution plan.
6. Test realistic data volumes.
7. Watch recursive queries for explosive growth.
8. Understand whether the target database materializes or inlines CTEs.
9. Do not assume a CTE is faster than an equivalent derived table.
10. Measure rather than relying on syntax-based assumptions.
"""
    )


# ---------------------------------------------------------------------------
# Final integrated example
# ---------------------------------------------------------------------------

def integrated_example():
    print_title("36. Integrated example: organizational analytics")

    connection = create_database()

    sql = """
        WITH RECURSIVE organization AS (
            SELECT
                employee_id,
                employee_name,
                manager_id,
                department,
                salary,
                0 AS level,
                employee_id AS root_manager_id
            FROM employees
            WHERE manager_id IS NULL

            UNION ALL

            SELECT
                e.employee_id,
                e.employee_name,
                e.manager_id,
                e.department,
                e.salary,
                o.level + 1,
                o.root_manager_id
            FROM employees AS e
            JOIN organization AS o
                ON e.manager_id = o.employee_id
        ),
        department_metrics AS (
            SELECT
                department,
                COUNT(*) AS employee_count,
                SUM(salary) AS payroll,
                ROUND(AVG(salary), 2) AS average_salary
            FROM organization
            GROUP BY department
        ),
        ranked_departments AS (
            SELECT
                department,
                employee_count,
                payroll,
                average_salary,
                RANK() OVER (
                    ORDER BY payroll DESC
                ) AS payroll_rank
            FROM department_metrics
        )
        SELECT
            department,
            employee_count,
            payroll,
            average_salary,
            payroll_rank
        FROM ranked_departments
        ORDER BY payroll_rank;
    """

    print_rows(run_query(connection, sql))

    print(
        """
This integrated query demonstrates why CTEs are useful in larger SQL
statements:

    Recursive CTE
        Builds the complete organization hierarchy.

    department_metrics
        Converts the hierarchy into department-level metrics.

    ranked_departments
        Applies analytical ranking to the derived metrics.

Each stage has one primary responsibility.
"""
    )

    connection.close()


# ---------------------------------------------------------------------------
# Study checklist
# ---------------------------------------------------------------------------

def study_checklist():
    print_title("37. Practical CTE checklist")

    checklist = [
        "Can I explain what WITH does?",
        "Can I write a single CTE?",
        "Can I use multiple CTEs in one statement?",
        "Can I join a CTE to a normal table?",
        "Can I aggregate CTE output?",
        "Can I use a window function after a CTE?",
        "Can I distinguish a CTE from a permanent table?",
        "Can I distinguish a CTE from a view?",
        "Can I explain CTE scope?",
        "Can I identify an anchor member?",
        "Can I identify a recursive member?",
        "Can I design a termination condition?",
        "Can I recognize a cyclic graph?",
        "Can I protect recursive traversal against cycles?",
        "Can I inspect a query plan?",
        "Can I use parameters safely?",
        "Can I separate filtering, aggregation, and ranking into logical stages?",
    ]

    for number, item in enumerate(checklist, start=1):
        print(f"{number:2}. {item}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """
    Run every demonstration in a predictable order.

    The examples intentionally use separate in-memory databases so that each
    lesson is independent and can be modified without affecting later ones.
    """
    basic_cte()
    cte_vs_subquery()
    multiple_ctes()
    cte_column_names()
    cte_with_join()
    cte_with_having()
    cte_with_window_function()
    cte_for_validation()
    cte_reuse()

    recursive_employee_hierarchy()
    recursive_subtree()
    recursive_ancestors()
    recursive_number_sequence()
    recursive_date_series()
    recursive_hierarchy_aggregation()
    recursive_graph_traversal()
    recursive_cycle_protection()
    recursive_bill_of_materials()

    parameterized_cte()
    business_report()
    cte_null_behavior()
    debugging_ctes()
    performance_plan()
    materialization_concept()
    cte_scope()
    cte_with_data_modification()
    naming_best_practices()
    recursive_rules()
    hierarchy_ordering()
    test_cte_logic()
    monthly_activity()
    customer_order_classification()
    edge_cases()
    security_considerations()
    performance_considerations()
    integrated_example()
    study_checklist()

    print_title("Study completed")
    print(
        "The script demonstrated non-recursive and recursive CTE patterns "
        "using SQLite through Python's standard library."
    )


if __name__ == "__main__":
    main()
