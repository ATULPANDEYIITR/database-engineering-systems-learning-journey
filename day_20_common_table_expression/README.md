# Common Table Expressions

## Topic

Common Table Expressions (CTEs), including the `WITH` clause, reusable query logic, and introductory recursive CTEs.

## Introduction

A Common Table Expression is a named query result that exists for the duration of a single SQL statement. It is introduced with the `WITH` clause.

A CTE allows a complex query to be divided into logical stages. Instead of placing every transformation inside deeply nested subqueries, each stage can receive a meaningful name and be referenced by the later parts of the statement.

A simple CTE has the general structure:

    WITH cte_name AS (
        SELECT ...
    )
    SELECT ...
    FROM cte_name;

A recursive CTE extends this idea to problems in which rows depend on other rows in the same logical dataset. Hierarchies, organizational structures, dependency trees, graph traversal, date generation, and bill-of-materials expansion are common examples.

The Python implementation executes real CTE statements using SQLite through Python's standard `sqlite3` library. The JavaScript implementation concentrates on constructing, validating, parameterizing, and organizing CTE-based SQL for application use. The C++ implementation models an industry-style organizational hierarchy and implements the same recursive logic in memory while also generating the equivalent SQL.

---

## Fundamental concepts

### What a CTE represents

A CTE is a named query expression. It is not automatically a permanent table and it is not a database object that remains available after the statement finishes.

For example:

    WITH completed_orders AS (
        SELECT
            customer_id,
            amount
        FROM orders
        WHERE status = 'completed'
    )
    SELECT
        customer_id,
        SUM(amount) AS total_revenue
    FROM completed_orders
    GROUP BY customer_id;

The `completed_orders` CTE represents the filtered rows used by the final query.

The logical stages are:

1. Select completed orders.
2. Give that result the name `completed_orders`.
3. Aggregate the named result by customer.
4. Calculate total revenue.

The CTE therefore provides a way to give structure to a complicated statement.

### The `WITH` clause

The `WITH` clause introduces one or more CTEs.

The basic form is:

    WITH first_cte AS (
        SELECT ...
    )
    SELECT ...
    FROM first_cte;

Multiple CTEs are separated by commas:

    WITH
    first_cte AS (
        SELECT ...
    ),
    second_cte AS (
        SELECT ...
        FROM first_cte
    )
    SELECT ...
    FROM second_cte;

A later CTE can normally reference an earlier CTE in the same `WITH` clause.

### CTE scope

A normal CTE has statement-level scope.

For example:

    WITH recent_orders AS (
        SELECT *
        FROM orders
        WHERE order_date >= '2026-03-01'
    )
    SELECT *
    FROM recent_orders;

The name `recent_orders` is available to that statement.

It does not become a permanent table. A later independent statement cannot simply execute `SELECT * FROM recent_orders`.

If a result must persist beyond the statement, a permanent table, temporary table, or view may be more appropriate depending on the requirement.

---

## Why CTEs are useful

CTEs are particularly useful when a query contains several logical transformations.

Consider a reporting problem that requires:

- filtering cancelled orders
- calculating customer revenue
- counting orders
- classifying customers
- ranking customers

A single deeply nested query can perform all of these operations, but it can become difficult to understand.

A CTE-based design can separate them:

    WITH completed_orders AS (
        ...
    ),
    customer_metrics AS (
        ...
    ),
    classified_customers AS (
        ...
    ),
    ranked_customers AS (
        ...
    )
    SELECT ...
    FROM ranked_customers;

Each name describes the role of that stage.

This improves readability, makes debugging easier, and makes the logical structure visible.

CTEs do not automatically make a query faster. Query performance depends on the database optimizer, indexes, data volume, joins, filtering, aggregation, recursion, and the execution strategy chosen by the database.

---

## CTE versus a subquery

A CTE and a derived subquery can often express the same relational operation.

CTE form:

    WITH completed_orders AS (
        SELECT
            customer_id,
            amount
        FROM orders
        WHERE status = 'completed'
    )
    SELECT
        customer_id,
        SUM(amount) AS total_revenue
    FROM completed_orders
    GROUP BY customer_id;

Equivalent derived-table form:

    SELECT
        customer_id,
        SUM(amount) AS total_revenue
    FROM (
        SELECT
            customer_id,
            amount
        FROM orders
        WHERE status = 'completed'
    ) AS completed_orders
    GROUP BY customer_id;

The main distinction is the organization of the query. A CTE gives the intermediate relation an explicit name before the final query is written.

For multi-stage queries, this often makes the SQL easier to read.

---

## CTE versus a temporary table

A CTE and a temporary table have different purposes.

A CTE is part of a single SQL statement.

A temporary table is a database object that can normally be referenced by multiple statements within its applicable session or transaction scope.

A temporary table can be useful when:

- the intermediate result must be reused across several statements
- indexes on the intermediate result are useful
- the intermediate data must be inspected independently
- materialized intermediate storage is desirable

A CTE is useful when:

- the logic belongs naturally to one statement
- query organization is the main objective
- creating a separate temporary object would add unnecessary complexity

The exact behavior and optimizer treatment vary by database system.

---

## CTE versus a view

A view is a persistent database object containing a stored query definition.

A CTE is normally defined inside the statement that uses it.

A view can be referenced by many statements:

    SELECT *
    FROM customer_sales_view;

A CTE is defined locally:

    WITH customer_sales AS (
        SELECT ...
    )
    SELECT *
    FROM customer_sales;

A view is appropriate when a logical dataset is a reusable database-level abstraction. A CTE is appropriate when the logic is specific to one statement or report.

---

## Multiple CTEs

Multiple CTEs can form a sequence of logical transformations.

The Python implementation contains a customer classification example:

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
    SELECT *
    FROM classified_customers;

The three stages have distinct responsibilities.

### Stage 1: filtering

`completed_orders` establishes which orders are relevant.

### Stage 2: aggregation

`customer_totals` converts individual order rows into customer-level metrics.

### Stage 3: classification

`classified_customers` applies business rules to the aggregated values.

This structure is often easier to test and modify than one large nested expression.

---

## Explicit CTE column names

A CTE can optionally define its output column names:

    WITH spending(customer_id, completed_spend) AS (
        SELECT
            customer_id,
            SUM(amount)
        FROM orders
        GROUP BY customer_id
    )
    SELECT *
    FROM spending;

The names in the CTE column list correspond to the columns returned by the CTE query.

Explicit names can be useful when the expressions do not have clear or portable output names.

---

## CTEs with joins

A CTE can be joined to ordinary tables or other CTEs.

The Python implementation calculates product sales using:

- `order_items`
- `orders`
- `products`

The first CTE aggregates product quantities:

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
        ps.units_sold
    FROM product_sales AS ps
    JOIN products AS p
        ON p.product_id = ps.product_id;

The CTE establishes a product-level result, and the final query adds descriptive product information.

---

## CTEs with aggregation

CTEs are useful for isolating aggregation from later calculations.

A common structure is:

    WITH customer_metrics AS (
        SELECT
            customer_id,
            COUNT(*) AS order_count,
            SUM(amount) AS revenue,
            AVG(amount) AS average_order_value
        FROM orders
        WHERE status = 'completed'
        GROUP BY customer_id
    )
    SELECT *
    FROM customer_metrics
    ORDER BY revenue DESC;

The grouping operation is isolated from later presentation logic.

---

## CTEs with window functions

Window functions can be applied to CTE output.

For example:

    WITH customer_spend AS (
        SELECT
            customer_id,
            SUM(amount) AS total_spend
        FROM orders
        WHERE status = 'completed'
        GROUP BY customer_id
    ),
    ranked_customers AS (
        SELECT
            customer_id,
            total_spend,
            RANK() OVER (
                ORDER BY total_spend DESC
            ) AS spend_rank
        FROM customer_spend
    )
    SELECT *
    FROM ranked_customers;

The first stage produces one row per customer.

The second stage ranks those rows.

This separation is particularly useful when a window function depends on an aggregate calculated in an earlier stage.

---

## CTEs for data validation

A CTE can create an intermediate classification of records.

For example:

    WITH order_quality AS (
        SELECT
            order_id,
            amount,
            status,
            CASE
                WHEN amount < 0 THEN 'INVALID_AMOUNT'
                WHEN amount = 0 THEN 'ZERO_VALUE'
                ELSE 'VALID'
            END AS quality_status
        FROM orders
    )
    SELECT *
    FROM order_quality
    WHERE quality_status <> 'VALID';

This approach is useful in data-quality pipelines because the validation logic can be separated from the final filtering or reporting operation.

Database constraints remain important. Query-based validation should not be treated as a replacement for appropriate schema constraints.

---

## Recursive CTEs

A recursive CTE is a CTE that refers to itself.

The general conceptual form is:

    WITH RECURSIVE hierarchy AS (
        anchor_query

        UNION ALL

        recursive_query
    )
    SELECT ...
    FROM hierarchy;

The recursive CTE has two important components.

### Anchor member

The anchor member establishes the initial rows.

For an employee hierarchy, the anchor might select employees who have no manager:

    SELECT
        employee_id,
        employee_name,
        manager_id,
        0 AS level
    FROM employees
    WHERE manager_id IS NULL

These rows represent the starting point.

### Recursive member

The recursive member finds the next generation.

For example:

    SELECT
        e.employee_id,
        e.employee_name,
        e.manager_id,
        hierarchy.level + 1
    FROM employees AS e
    JOIN hierarchy
        ON e.manager_id = hierarchy.employee_id

The recursive query takes rows already found by the CTE and finds their children.

### Combining the two parts

The anchor and recursive member are commonly combined with `UNION ALL`.

The database repeatedly applies the recursive member to newly produced rows until no additional rows are generated or a database-specific recursion limit is reached.

---

## Employee hierarchy example

The Python implementation contains an organizational structure beginning with a CEO.

The hierarchy includes:

- Chief Executive Officer
- Engineering Director
- Engineering Manager
- Software Engineers
- Platform Manager
- Cloud and DevOps Engineers
- Product Director
- Product Manager
- Product Analysts
- Finance Manager

The recursive CTE builds the complete hierarchy.

Its logical structure is:

    WITH RECURSIVE employee_tree AS (
        SELECT
            employee_id,
            employee_name,
            manager_id,
            0 AS level,
            employee_name AS path
        FROM employees
        WHERE manager_id IS NULL

        UNION ALL

        SELECT
            e.employee_id,
            e.employee_name,
            e.manager_id,
            tree.level + 1,
            tree.path || ' > ' || e.employee_name
        FROM employees AS e
        JOIN employee_tree AS tree
            ON e.manager_id = tree.employee_id
    )
    SELECT *
    FROM employee_tree;

The `level` column records the depth.

The `path` column records the route from the root to the employee.

For example, a conceptual result might contain:

    Anita Rao > Vikram Shah > Meera Iyer > Rahul Verma

The path is useful for displaying hierarchy relationships and for constructing deterministic hierarchical ordering.

---

## Recursive subtree queries

A recursive CTE does not need to begin at the entire organization's roots.

It can begin at one selected employee.

For example:

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
    FROM subtree;

The parameter determines the root of the requested subtree.

This is useful for questions such as:

- Which employees report to this manager?
- How many organizational levels exist below a manager?
- Which resources belong to a business unit?
- Which descendants are affected by a structural change?

---

## Recursive ancestor queries

Recursion can move upward rather than downward.

For a selected employee:

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
    SELECT *
    FROM management_chain
    ORDER BY distance;

This follows the `manager_id` relationship toward the root.

The direction of the recursive join determines whether a hierarchy is traversed downward, upward, or through another relationship.

---

## Recursive number generation

Recursive CTEs can generate sequences.

The Python implementation uses:

    WITH RECURSIVE numbers(n) AS (
        SELECT 1

        UNION ALL

        SELECT n + 1
        FROM numbers
        WHERE n < 10
    )
    SELECT n
    FROM numbers;

The anchor produces `1`.

The recursive member produces `2`, then `3`, and so on.

The condition `n < 10` provides termination.

This pattern demonstrates recursion without requiring a hierarchy.

---

## Recursive date generation

A similar technique can produce calendar dates:

    WITH RECURSIVE calendar(day) AS (
        SELECT DATE('2026-01-01')

        UNION ALL

        SELECT DATE(day, '+1 day')
        FROM calendar
        WHERE day < DATE('2026-01-07')
    )
    SELECT day
    FROM calendar;

This is useful for reporting problems where every calendar period needs to appear even when no transaction occurred during that period.

For production workloads, dedicated calendar tables may be preferable when a large or permanent calendar dimension is needed.

---

## Graph traversal

Hierarchies are a special type of graph.

Recursive CTEs can also traverse more general graph relationships.

Suppose a table contains:

    source | destination

The recursive query can begin at a selected node and follow outgoing edges.

A simplified form is:

    WITH RECURSIVE reachable(node, depth) AS (
        SELECT ?, 0

        UNION

        SELECT
            edge.destination,
            reachable.depth + 1
        FROM graph_edges AS edge
        JOIN reachable
            ON edge.source = reachable.node
    )
    SELECT *
    FROM reachable;

Graph traversal introduces additional concerns because graphs can contain cycles and multiple paths between the same nodes.

---

## `UNION` versus `UNION ALL`

This distinction is particularly important in recursive queries.

`UNION ALL` keeps duplicate rows.

`UNION` removes duplicate rows according to the database's set semantics.

`UNION ALL` is usually preferred when every generated row is meaningful and duplicates should not be removed.

`UNION` can be useful in graph-style traversal when duplicate states must be eliminated.

The choice has both semantic and performance implications.

Duplicate elimination can require additional work because the database must identify duplicate rows.

---

## Recursive termination

Every recursive query should be designed with termination in mind.

A number sequence has an obvious boundary:

    WHERE n < 10

An organizational hierarchy naturally stops when employees have no children.

A graph is more complicated because a graph can contain cycles.

A poorly designed recursive query can generate far more rows than expected.

Important questions include:

- What is the starting set?
- What produces the next row?
- What eventually prevents another row?
- Can the data contain cycles?
- Can the same logical node be reached by multiple paths?
- Is maximum depth known?
- Can the result grow exponentially?

---

## Cycle detection

Consider a graph:

    A -> B
    B -> C
    C -> A

A naive recursive traversal can repeatedly move through the cycle.

One strategy is explicit path tracking.

The Python implementation uses a path representation such as:

    |A|B|C|

Before following an edge to a destination, the query checks whether the destination already appears as a complete path component.

The principle is:

    WHERE INSTR(
        path,
        '|' || destination || '|'
    ) = 0

The delimiters reduce accidental partial matches.

For example, searching for node `2` should not accidentally match node `12`.

Production systems should choose cycle detection strategies appropriate to the database engine, identifier format, graph size, and required semantics.

---

## Hierarchical paths

A recursive query can carry an accumulated path.

For example:

    tree.path || ' > ' || e.employee_name

This produces a human-readable path.

Paths can also be represented using IDs:

    1.2.3.5

An ID-based path can be easier to process programmatically and can be useful for deterministic ordering.

The C++ implementation demonstrates path construction in its `HierarchyNode`.

---

## Hierarchical ordering

Simply sorting by `employee_id` does not necessarily display an organizational hierarchy correctly.

A recursive query can build a sort path.

For example:

    printf('%06d', employee_id)

can create fixed-width identifiers that can be concatenated:

    000001.000002.000003

Sorting these values can produce a deterministic traversal order.

The exact strategy should match the required hierarchy semantics.

---

## Recursive bill of materials

A bill of materials is another practical recursive problem.

For example:

    Laptop
      -> Motherboard
          -> CPU
          -> RAM
          -> SSD
      -> Battery
      -> Keyboard
          -> Keycap

A recursive CTE can expand the components.

The Python implementation calculates total required quantities by multiplying quantities across levels.

If one motherboard requires two units of RAM and one laptop requires one motherboard, the laptop requires two RAM units.

This pattern can apply to:

- manufacturing
- product configuration
- software package dependencies
- infrastructure dependencies
- nested component structures

---

## Python implementation

The Python program uses the standard `sqlite3` library.

No third-party package is required.

The database is created in memory using:

    sqlite3.connect(":memory:")

This makes the study program self-contained.

The database contains:

- `employees`
- `customers`
- `orders`
- `products`
- `order_items`

Indexes are also created for frequently used relationships and filters.

The Python implementation demonstrates actual execution of CTE SQL, which makes it the primary executable SQL-learning component.

### Basic CTE demonstration

The `basic_cte()` function creates a CTE named `high_value_orders`.

It filters orders and then queries the CTE.

This demonstrates the fundamental `WITH ... AS (...)` structure.

### Multiple CTE demonstration

The `multiple_ctes()` function creates:

- `completed_orders`
- `customer_totals`
- `classified_customers`

This demonstrates how CTEs can be chained.

### Window-function demonstration

The `cte_with_window_function()` function calculates customer spending and then applies `RANK()` and a percentage calculation.

This shows how CTEs can separate aggregation from analytical operations.

### Recursive hierarchy

The `recursive_employee_hierarchy()` function demonstrates:

- `WITH RECURSIVE`
- anchor member
- recursive member
- hierarchy level
- path construction
- parent-child joins

### Recursive graph traversal

The `recursive_graph_traversal()` function demonstrates traversal through an edge table.

### Cycle-safe traversal

The `recursive_cycle_protection()` function demonstrates explicit path checking.

### Bill of materials

The `recursive_bill_of_materials()` function demonstrates recursive quantity accumulation.

### Query plan

The `performance_plan()` function uses SQLite's `EXPLAIN QUERY PLAN`.

This is important because CTE syntax alone does not reveal how a database will execute the query.

### Testing

The `test_cte_logic()` function verifies the expected number of completed orders using an assertion.

This demonstrates that SQL logic can be tested as part of a program rather than being treated only as ad hoc interactive work.

---

## JavaScript implementation

The JavaScript file focuses on the application layer around CTE-based SQL.

JavaScript itself does not include a relational database engine in the standard runtime, so the program does not pretend that a database exists when no database driver has been installed.

Instead, it demonstrates how an application can:

- construct SQL
- keep parameters separate
- validate inputs
- build multi-stage CTEs
- prepare recursive queries
- validate recursion boundaries
- prepare execution-plan requests
- inject an asynchronous database execution function

### Parameter handling

The JavaScript examples keep values in a separate `parameters` array.

For example:

    {
        sql: "... WHERE amount >= ? ...",
        parameters: [10000]
    }

This reflects the parameterized-query pattern used by database drivers.

The application should not build SQL by concatenating untrusted user values into the statement.

### CteQueryBuilder

The `CteQueryBuilder` class demonstrates application-side composition of CTE stages.

It validates CTE names with an identifier rule:

    /^[A-Za-z_][A-Za-z0-9_]*$/

This matters because SQL identifiers and ordinary values are different things.

A value can generally be bound as a parameter.

A table name or CTE name normally cannot simply be supplied as an ordinary value parameter.

If identifiers must be dynamic, an application should use a strict allow-list or database-specific safe identifier mechanism.

### Async execution

The `executeCteReport()` function accepts an execution function instead of depending on a specific npm package.

This is dependency injection.

A real database layer could provide a function that sends the SQL and parameter array to the selected database driver.

This keeps query construction separate from connection management.

---

## C++ case study

The C++ program models an enterprise organizational analytics system.

The central relationship is:

    employee.managerId -> manager.employeeId

This is a parent-child relationship.

The program builds a hierarchy from those relationships and calculates department-level metrics.

### Employee

The `Employee` structure stores:

- employee ID
- employee name
- optional manager ID
- department
- job title
- salary

`std::optional<int>` represents the possibility that an employee has no manager.

A top-level executive therefore has no manager ID.

### EmployeeRepository

`EmployeeRepository` stores employee records and provides operations such as:

- adding employees
- finding an employee by ID
- locating direct reports
- finding top-level employees

The repository represents the kind of application-side data-access abstraction that could sit around a database.

### OrganizationAnalyzer

`OrganizationAnalyzer` contains the recursive hierarchy algorithm.

Its `traverse()` function accepts:

- employee ID
- hierarchy level
- current path
- visited set
- result collection

The recursive call processes each direct report.

This corresponds conceptually to the recursive member of a SQL CTE.

### Cycle protection

The C++ implementation maintains an `unordered_set<int>` of IDs currently being traversed.

If an employee is encountered again within the current traversal path, the function raises an error.

This is important because real organizational data should normally be a tree or forest, but corrupted data can introduce cycles.

The program deliberately creates a cyclic test case to demonstrate the failure condition.

### Department aggregation

After building the hierarchy, the program groups employees by department and calculates:

- employee count
- payroll
- average salary

This corresponds conceptually to:

    GROUP BY department

### Ranking

The department results are sorted by payroll and assigned a rank.

This corresponds to the analytical purpose of a SQL window function such as:

    RANK() OVER (
        ORDER BY payroll DESC
    )

The C++ implementation performs the ranking explicitly because the C++ standard library does not provide SQL window functions.

### SQL generation

`SqlGenerator` produces the SQL form of the same business logic.

The generated recursive query contains:

- anchor member
- `UNION ALL`
- recursive member
- hierarchy level
- hierarchy path

The second generated query contains:

- recursive organization construction
- department aggregation
- department ranking

This creates a direct conceptual connection between the C++ algorithm and the SQL implementation.

---

## Industry scenario

The case study represents an enterprise organization where management relationships are stored in a relational table.

A business application might need to answer:

- Who reports to a selected manager?
- How many levels exist below a manager?
- Which employees belong to an organizational branch?
- What is the payroll of each department?
- Which department has the largest payroll?
- What is the management path for an employee?
- Is the organization structurally valid?
- Does the data contain a cycle?

Without recursive SQL, applications often have to repeatedly query the database or retrieve a large dataset and construct the hierarchy manually.

A recursive CTE allows the database to express the traversal as a relational operation.

---

## Recursive CTE conceptual model

A useful mental model is:

    Anchor
       |
       v
    Current rows
       |
       v
    Recursive relationship
       |
       v
    New rows
       |
       v
    Repeat
       |
       v
    No more rows

For an employee hierarchy:

    Top-level employee
           |
           v
    Direct reports
           |
           v
    Their direct reports
           |
           v
    Next management level
           |
           v
    Continue until no children remain

The database handles the iterative evaluation of the recursive relation according to its SQL implementation.

---

## Important distinctions

### CTE versus permanent table

A CTE is statement-scoped.

A permanent table persists as database data.

### CTE versus temporary table

A temporary table can survive across multiple statements within its applicable scope.

A CTE belongs to one statement.

### CTE versus view

A view is a persistent database object containing a stored query definition.

A CTE is normally defined at the point where the statement uses it.

### CTE versus stored procedure

A stored procedure is a database program object supported by some database systems.

A CTE is a query expression.

They solve different problems.

### Recursive CTE versus ordinary CTE

An ordinary CTE does not reference itself.

A recursive CTE references its own result to produce additional rows.

---

## Edge cases

### Empty CTE result

A CTE can produce zero rows.

The final query must correctly handle that possibility.

Aggregates can then produce different results depending on whether a grouping row exists.

### NULL values

CTEs do not change SQL `NULL` semantics.

For example:

    COALESCE(value, 0)

can explicitly replace `NULL` with zero when that is the required business meaning.

### Duplicate rows

`UNION ALL` preserves duplicates.

`UNION` removes duplicates.

The difference is important in recursive graph traversal.

### Cycles

Parent-child data can be corrupted or graph data can naturally contain cycles.

Recursive queries must account for this when the data model permits cycles.

### Large recursion depth

A query that works on a small demonstration hierarchy may become expensive on production data with thousands or millions of relationships.

The expected depth and result size should be understood.

### Multiple paths

A graph can reach the same node through multiple routes.

Whether those paths should remain separate or collapse into a unique set is a business and algorithmic decision.

---

## Common mistakes

### Forgetting the termination condition

A number generator such as:

    SELECT n + 1
    FROM numbers

without an appropriate stopping condition can continue indefinitely until a database-specific limit or resource boundary is reached.

### Using the wrong recursive join

For a manager hierarchy, the relationship is usually:

    employee.manager_id = parent.employee_id

Reversing this relationship changes the traversal direction or produces incorrect results.

### Confusing level with distance

A hierarchy level generally describes distance from the chosen root.

If a query starts from one manager, level zero means that selected manager, not necessarily the organization's CEO.

### Ignoring cycles

Tree-shaped data is not automatically guaranteed to be acyclic.

If the database does not enforce the structure, recursive queries should account for the possibility of malformed relationships.

### Carrying unnecessary columns

Every column carried through a recursive CTE increases the amount of data involved in the recursive operation.

Only carry columns required for the final result or recursive computation.

### Assuming CTEs are automatically faster

A CTE is primarily a logical query-organization mechanism.

Performance depends on the database engine and optimizer.

### Assuming a CTE is always materialized

Different database systems and versions can optimize CTEs differently.

A CTE should not automatically be treated as a physically stored intermediate table.

### Building SQL with string concatenation

Application code should not concatenate untrusted values directly into SQL.

Use parameter binding for values.

---

## Performance considerations

### Index parent-child relationships

For organizational data, an index such as:

    CREATE INDEX idx_employees_manager
    ON employees(manager_id);

can make child lookup substantially more efficient.

### Filter early when appropriate

If a CTE can remove irrelevant rows before an expensive join or aggregation, that may reduce the working set.

The optimizer may already transform the query, so the actual execution plan should be inspected.

### Avoid unnecessary columns

A recursive CTE should carry only the information required for:

- recursion
- final output
- filtering
- ordering
- calculations

### Inspect execution plans

SQLite provides `EXPLAIN QUERY PLAN`.

Other database systems provide their own execution-plan tools.

The relevant question is not simply:

    "Is this a CTE?"

The relevant questions include:

- Which indexes are being used?
- How many rows are being scanned?
- Which joins are expensive?
- Is a sort required?
- Is duplicate elimination expensive?
- Is recursion producing too many rows?
- Is an intermediate result being materialized?

### Recursive performance

Suppose a hierarchy contains `N` reachable employees.

An efficient indexed database traversal can be approximately proportional to the number of reachable rows and relationships.

Poor indexing can cause repeated scanning of the employee table for every recursive level.

The C++ case study intentionally uses a simple vector-based repository. Its direct-report search scans the collection, making it suitable for demonstration but not ideal for very large datasets.

A production C++ implementation could maintain a mapping such as:

    manager ID -> vector of child employee IDs

This would make child lookup substantially more efficient.

### Ranking performance

Ranking departments requires ordering the department-level results.

If there are `M` departments, sorting is generally `O(M log M)`.

Since the number of departments is usually much smaller than the number of raw transactions or employees, this stage is often relatively inexpensive.

---

## Security considerations

CTEs do not provide SQL injection protection by themselves.

Applications must still use parameterized SQL.

Unsafe pattern:

    "SELECT ... WHERE amount >= " + userInput

Safer pattern:

    SELECT ...
    WHERE amount >= ?

with the value supplied separately to the database driver.

The JavaScript implementation explicitly keeps SQL and parameters separate.

The Python implementation uses `sqlite3` parameter binding.

The C++ program explains the same parameterization concept even though it does not depend on an external database library.

### Dynamic identifiers

Values and identifiers are different.

A database driver can normally bind a value such as:

    10000

but a table name such as:

    orders

is part of SQL syntax.

If an application allows a user to select among table or column names, use a strict allow-list rather than inserting arbitrary text into SQL.

### Recursive workload control

Recursive queries can be computationally expensive.

Applications should validate requested ranges, roots, and traversal conditions where appropriate.

The JavaScript implementation validates recursive number ranges and date ranges before constructing the query.

---

## Debugging CTEs

Complex CTE queries should be debugged stage by stage.

Suppose the complete query is:

    WITH completed_orders AS (...),
    customer_totals AS (...),
    ranked_customers AS (...)
    SELECT ...

A useful debugging approach is to temporarily isolate `completed_orders`.

Then inspect its output.

Next, reproduce the first stage as a subquery and inspect `customer_totals`.

Finally, inspect the ranking stage.

This approach makes it easier to identify whether a problem originates from:

- filtering
- joining
- aggregation
- grouping
- classification
- window functions
- recursion

The Python `debugging_ctes()` function demonstrates this approach.

---

## Design considerations

A well-designed CTE should usually have a clear responsibility.

Good names include:

- `completed_orders`
- `customer_totals`
- `monthly_sales`
- `ranked_customers`
- `employee_tree`
- `department_metrics`

Names such as:

- `temp1`
- `data`
- `result`
- `query2`

make complex queries harder to understand.

A CTE should not be created solely because the syntax is available. If a query is clearer as a normal `SELECT`, there is no requirement to introduce a CTE.

A useful design principle is:

    One CTE stage = one meaningful logical transformation

This is not an absolute rule. Some transformations naturally belong together.

---

## Practical applications

CTEs are useful in many database workloads.

### Business analytics

Examples include:

- customer revenue
- monthly sales
- product performance
- regional reporting
- customer segmentation
- ranking

### Organizational systems

Examples include:

- employee hierarchies
- management chains
- business-unit trees
- organizational reporting

### Financial systems

Examples include:

- account hierarchies
- transaction aggregation
- portfolio classifications
- reporting-period calculations

### Manufacturing

Examples include:

- bills of materials
- component expansion
- dependency structures

### Software systems

Examples include:

- package dependencies
- service dependencies
- configuration inheritance

### Network and graph-like data

Examples include:

- reachable nodes
- dependency traversal
- relationship exploration
- path discovery

### Time-series preparation

Examples include:

- calendar generation
- missing-period detection
- period-based reporting

---

## Advanced CTE patterns demonstrated

The implementations collectively demonstrate several advanced patterns.

### Staged analytics

    filtered data
        ->
    aggregated data
        ->
    derived metrics
        ->
    ranking
        ->
    final presentation

### Recursive hierarchy

    root
        ->
    children
        ->
    grandchildren
        ->
    deeper descendants

### Accumulated recursive state

A recursive CTE can carry values such as:

- depth
- path
- quantity
- cumulative amount
- parent identifier

### Graph traversal

A recursive CTE can follow an edge relationship rather than a simple tree.

### Cycle protection

The recursive state can carry enough information to prevent revisiting a node.

### Recursive expansion

Bill-of-materials processing multiplies quantities across hierarchy levels.

---

## Python, JavaScript, and C++ comparison

### Python

Python is the strongest of the three implementations for directly executing the SQL in this study because its standard library includes SQLite support.

The Python program demonstrates:

- actual database creation
- actual table creation
- actual inserts
- actual CTE execution
- recursive CTE execution
- query plans
- parameterized SQL
- testing

This makes it useful for learning the SQL behavior itself.

### JavaScript

JavaScript demonstrates the application layer around SQL.

It focuses on:

- query construction
- query composition
- parameter separation
- validation
- dynamic query structure
- asynchronous execution patterns
- database-driver abstraction

This reflects how CTEs can be integrated into a web or server-side JavaScript application.

### C++

C++ demonstrates the algorithmic and systems perspective.

The C++ case study models:

- relational employee records
- parent-child relationships
- recursive traversal
- cycle detection
- aggregation
- ranking
- validation
- complexity analysis

It also generates the equivalent SQL.

The C++ implementation is intentionally independent of a third-party database library so that the case study can be compiled with a standard C++17 compiler.

---

## Implementation considerations

When CTE logic is used in a real application, several layers should remain conceptually separate.

### Database schema

Defines:

- tables
- columns
- constraints
- indexes
- relationships

### SQL query

Defines:

- filtering
- joins
- aggregation
- recursion
- analytical transformations

### Application layer

Defines:

- input validation
- authorization
- parameter binding
- error handling
- query selection
- response formatting

### Presentation layer

Defines:

- tables
- reports
- dashboards
- API responses

The JavaScript and C++ implementations demonstrate this separation at different levels.

---

## Production considerations

Before using recursive CTEs in production, the data model and workload should be understood.

Important questions include:

- How many rows can the hierarchy contain?
- What is the maximum depth?
- Can cycles occur?
- Is `manager_id` indexed?
- Can a user request an unrestricted subtree?
- Can the query generate a very large result?
- Does the database engine impose a recursion limit?
- Does the application need all columns?
- Is the result used interactively or in batch processing?
- Does the database optimizer treat the CTE as expected?
- Has the query been tested against production-scale data?

For frequently reused reporting logic, a view, materialized view, summary table, or other design may sometimes be more appropriate than rebuilding a large recursive result for every request.

The appropriate choice depends on workload, freshness requirements, database engine, and data size.

---

## Key SQL structures

### Ordinary CTE

    WITH name AS (
        SELECT ...
    )
    SELECT ...
    FROM name;

### Multiple CTEs

    WITH
    first_stage AS (
        SELECT ...
    ),
    second_stage AS (
        SELECT ...
        FROM first_stage
    )
    SELECT ...
    FROM second_stage;

### Recursive CTE

    WITH RECURSIVE hierarchy AS (
        SELECT ...
        FROM source
        WHERE root_condition

        UNION ALL

        SELECT ...
        FROM source
        JOIN hierarchy
            ON relationship_condition
    )
    SELECT ...
    FROM hierarchy;

### Parameterized CTE

    WITH qualifying_rows AS (
        SELECT ...
        FROM orders
        WHERE amount >= ?
    )
    SELECT ...
    FROM qualifying_rows;

---

## Relationship between recursion and ordinary query processing

An ordinary CTE can be understood as naming an intermediate relational expression.

A recursive CTE adds repeated evaluation of a relationship.

For a hierarchy:

    Root rows
        +
    rows related to roots
        +
    rows related to those rows
        +
    ...

The process stops when another recursive iteration produces no new applicable rows or when database-specific recursion limits or query conditions stop the operation.

This makes recursive CTEs particularly appropriate for data whose structure cannot be represented by a fixed number of joins.

A fixed hierarchy might be written with several explicit joins, but that becomes impractical when the depth is unknown.

---

## Limitations

CTEs are not universally the best solution.

Potential limitations include:

- recursive queries can be expensive
- large intermediate results can consume substantial resources
- graph traversal can generate many paths
- cycle protection can add complexity
- optimizer behavior varies between database engines
- database-specific syntax differs
- CTE readability does not guarantee performance
- some workloads are better served by precomputed structures
- repeated reporting may benefit from summary tables or materialized views
- deeply layered CTEs can themselves become difficult to understand

The correct design depends on the underlying data and workload rather than on the presence of a particular SQL feature.

---

## Practical study sequence

The implementations provide a progression from simple to advanced concepts:

1. Basic `WITH` syntax.
2. One CTE.
3. Multiple CTEs.
4. Explicit CTE column names.
5. Joins.
6. Aggregation.
7. `HAVING`.
8. Window functions.
9. Validation.
10. Reusable intermediate logic.
11. Recursive employee hierarchy.
12. Recursive subtree traversal.
13. Recursive ancestor traversal.
14. Recursive number generation.
15. Recursive date generation.
16. Recursive aggregation.
17. Graph traversal.
18. Cycle protection.
19. Bill-of-materials expansion.
20. Parameterized application queries.
21. Debugging.
22. Query-plan analysis.
23. Production-oriented performance and security considerations.

This progression connects simple `WITH` queries to the more complex recursive patterns used in hierarchical and graph-like data.

---

## Files and execution

### Python

The Python file can be executed with a modern Python 3 installation.

It uses only the standard library.

The primary database functionality comes from `sqlite3`.

The script creates its database in memory, so it does not require a database file.

### JavaScript

The JavaScript file can be executed in a modern JavaScript runtime such as Node.js.

It does not require an npm package for the demonstrations because the database execution layer is represented by generated SQL and an injected asynchronous execution function.

A real application would connect the generated SQL to an appropriate database driver.

### C++

The C++ program uses C++17 standard-library features.

It can be compiled with a C++17-compatible compiler.

The program does not require a third-party database library because the case study implements the recursive algorithm directly in memory and separately generates the corresponding SQL.

---

## Technical concepts demonstrated

The complete implementations cover:

- Common Table Expressions
- `WITH`
- `WITH RECURSIVE`
- CTE naming
- CTE scope
- multiple CTEs
- derived query stages
- aggregation
- `GROUP BY`
- `HAVING`
- `CASE`
- `JOIN`
- window functions
- `RANK`
- `DENSE_RANK`
- `UNION`
- `UNION ALL`
- parameterized queries
- recursive anchor members
- recursive members
- hierarchy traversal
- ancestor traversal
- subtree traversal
- graph traversal
- cycle detection
- path construction
- recursive counters
- recursive date generation
- accumulated recursive state
- bill-of-materials expansion
- data validation
- debugging
- execution-plan inspection
- indexing considerations
- SQL injection prevention
- application-side query construction
- asynchronous database execution patterns
- algorithmic complexity
- production workload considerations
