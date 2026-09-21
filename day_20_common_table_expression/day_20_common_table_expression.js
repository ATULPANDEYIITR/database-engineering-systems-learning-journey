/*
 * Common Table Expressions (CTEs)
 *
 * This file complements the Python implementation by showing how JavaScript
 * can generate, organize, validate, and execute CTE-based SQL statements.
 *
 * The program is self-contained and uses no external npm packages.
 *
 * JavaScript itself does not provide a built-in relational database engine,
 * so the examples represent SQL as executable query strings and demonstrate
 * application-side construction, validation, parameter handling, and query
 * organization. The same SQL can be executed by a database driver such as a
 * SQLite, PostgreSQL, MySQL, or SQL Server client in a real application.
 */

"use strict";

/* ------------------------------------------------------------------------- *
 * Section 1: Basic CTE construction
 * ------------------------------------------------------------------------- */

function basicCteQuery() {
    const sql = `
WITH high_value_orders AS (
    SELECT
        order_id,
        customer_id,
        amount
    FROM orders
    WHERE amount >= ?
)
SELECT
    order_id,
    customer_id,
    amount
FROM high_value_orders
ORDER BY amount DESC;
`;

    return {
        sql: sql.trim(),
        parameters: [10000]
    };
}

console.log("BASIC CTE");
console.log(basicCteQuery());

/* ------------------------------------------------------------------------- *
 * Section 2: Multiple CTEs
 * ------------------------------------------------------------------------- */

function customerRevenueQuery(minimumRevenue) {
    /*
     * Each CTE represents a logical transformation:
     *
     * completed_orders
     *     -> filters source data
     *
     * customer_totals
     *     -> aggregates filtered data
     *
     * classified_customers
     *     -> derives a business category
     */
    return {
        sql: `
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
        SUM(amount) AS total_revenue
    FROM completed_orders
    GROUP BY customer_id
),
classified_customers AS (
    SELECT
        customer_id,
        order_count,
        total_revenue,
        CASE
            WHEN total_revenue >= ? THEN 'High Value'
            WHEN total_revenue >= 15000 THEN 'Growth'
            ELSE 'Standard'
        END AS customer_segment
    FROM customer_totals
)
SELECT
    customer_id,
    order_count,
    total_revenue,
    customer_segment
FROM classified_customers
ORDER BY total_revenue DESC;
`.trim(),
        parameters: [minimumRevenue]
    };
}

console.log("\nMULTIPLE CTEs");
console.log(customerRevenueQuery(30000));

/* ------------------------------------------------------------------------- *
 * Section 3: CTE with window functions
 * ------------------------------------------------------------------------- */

function rankedRevenueQuery() {
    return `
WITH customer_spend AS (
    SELECT
        customer_id,
        SUM(amount) AS total_spend
    FROM orders
    WHERE status = 'completed'
    GROUP BY customer_id
),
ranked AS (
    SELECT
        customer_id,
        total_spend,
        RANK() OVER (
            ORDER BY total_spend DESC
        ) AS revenue_rank,
        ROUND(
            100.0 * total_spend /
            SUM(total_spend) OVER (),
            2
        ) AS revenue_percentage
    FROM customer_spend
)
SELECT *
FROM ranked
ORDER BY revenue_rank;
`.trim();
}

console.log("\nCTE WITH WINDOW FUNCTION");
console.log(rankedRevenueQuery());

/* ------------------------------------------------------------------------- *
 * Section 4: Recursive hierarchy query
 * ------------------------------------------------------------------------- */

function employeeHierarchyQuery(rootEmployeeId) {
    /*
     * The parameter belongs to the anchor query.
     *
     * The recursive member then follows:
     *
     *     employee.manager_id = hierarchy.employee_id
     *
     * This turns parent-child rows into a complete hierarchy.
     */
    return {
        sql: `
WITH RECURSIVE employee_tree AS (
    SELECT
        employee_id,
        employee_name,
        manager_id,
        department,
        job_title,
        0 AS level,
        CAST(employee_id AS TEXT) AS path
    FROM employees
    WHERE employee_id = ?

    UNION ALL

    SELECT
        e.employee_id,
        e.employee_name,
        e.manager_id,
        e.department,
        e.job_title,
        tree.level + 1,
        tree.path || ' > ' || CAST(e.employee_id AS TEXT)
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
`.trim(),
        parameters: [rootEmployeeId]
    };
}

console.log("\nRECURSIVE EMPLOYEE HIERARCHY");
console.log(employeeHierarchyQuery(1));

/* ------------------------------------------------------------------------- *
 * Section 5: Recursive number sequence
 * ------------------------------------------------------------------------- */

function numberSequenceQuery(start, end) {
    /*
     * Validation occurs in JavaScript before SQL is generated.
     * The actual sequence is still generated by SQL recursion.
     */
    if (!Number.isInteger(start) || !Number.isInteger(end)) {
        throw new TypeError("Sequence boundaries must be integers.");
    }

    if (start > end) {
        throw new RangeError("Start value cannot be greater than end value.");
    }

    if (end - start > 100000) {
        throw new RangeError(
            "Requested recursive sequence is too large for this demonstration."
        );
    }

    return {
        sql: `
WITH RECURSIVE numbers(n) AS (
    SELECT ?
    UNION ALL
    SELECT n + 1
    FROM numbers
    WHERE n < ?
)
SELECT n
FROM numbers;
`.trim(),
        parameters: [start, end]
    };
}

console.log("\nRECURSIVE NUMBER SEQUENCE");
console.log(numberSequenceQuery(1, 10));

/* ------------------------------------------------------------------------- *
 * Section 6: Recursive date series
 * ------------------------------------------------------------------------- */

function dateSeriesQuery(startDate, endDate) {
    /*
     * Dates are validated at the application boundary.
     * The database performs the recursive date generation.
     */
    const start = new Date(`${startDate}T00:00:00Z`);
    const end = new Date(`${endDate}T00:00:00Z`);

    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
        throw new TypeError("Dates must use a valid ISO-style date.");
    }

    if (start > end) {
        throw new RangeError("Start date cannot be after end date.");
    }

    const maximumDays = 366;
    const differenceInDays =
        Math.floor((end - start) / 86400000);

    if (differenceInDays > maximumDays) {
        throw new RangeError(
            `Date range cannot exceed ${maximumDays} days in this demonstration.`
        );
    }

    return {
        sql: `
WITH RECURSIVE calendar(day) AS (
    SELECT DATE(?)
    UNION ALL
    SELECT DATE(day, '+1 day')
    FROM calendar
    WHERE day < DATE(?)
)
SELECT day
FROM calendar;
`.trim(),
        parameters: [startDate, endDate]
    };
}

console.log("\nRECURSIVE DATE SERIES");
console.log(dateSeriesQuery("2026-09-01", "2026-09-07"));

/* ------------------------------------------------------------------------- *
 * Section 7: Graph traversal
 * ------------------------------------------------------------------------- */

function graphTraversalQuery(startNode) {
    /*
     * UNION is deliberately used here instead of UNION ALL.
     *
     * For a graph with multiple paths to the same node, duplicate elimination
     * can prevent repeated states. For more complex graphs, explicit path
     * tracking or another cycle-detection strategy may be necessary.
     */
    return {
        sql: `
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
SELECT
    node,
    MIN(depth) AS minimum_depth
FROM reachable
GROUP BY node
ORDER BY minimum_depth, node;
`.trim(),
        parameters: [startNode]
    };
}

console.log("\nGRAPH TRAVERSAL");
console.log(graphTraversalQuery("A"));

/* ------------------------------------------------------------------------- *
 * Section 8: Explicit cycle protection
 * ------------------------------------------------------------------------- */

function cycleSafeTraversalQuery(startNode) {
    return {
        sql: `
WITH RECURSIVE walk(node, path, depth) AS (
    SELECT
        ?,
        '|' || ? || '|',
        0

    UNION ALL

    SELECT
        edge.destination,
        walk.path || edge.destination || '|',
        walk.depth + 1
    FROM graph_edges AS edge
    JOIN walk
        ON edge.source = walk.node
    WHERE INSTR(
        walk.path,
        '|' || edge.destination || '|'
    ) = 0
)
SELECT
    node,
    depth,
    path
FROM walk
ORDER BY depth, node;
`.trim(),
        parameters: [startNode, startNode]
    };
}

console.log("\nCYCLE-SAFE TRAVERSAL");
console.log(cycleSafeTraversalQuery("A"));

/* ------------------------------------------------------------------------- *
 * Section 9: Bill of materials
 * ------------------------------------------------------------------------- */

function billOfMaterialsQuery(productName) {
    return {
        sql: `
WITH RECURSIVE bill_of_materials(item, quantity, level) AS (
    SELECT
        child,
        quantity,
        1
    FROM components
    WHERE parent = ?

    UNION ALL

    SELECT
        component.child,
        bill_of_materials.quantity * component.quantity,
        bill_of_materials.level + 1
    FROM components AS component
    JOIN bill_of_materials
        ON component.parent = bill_of_materials.item
)
SELECT
    item,
    SUM(quantity) AS total_required,
    MIN(level) AS minimum_level
FROM bill_of_materials
GROUP BY item
ORDER BY minimum_level, item;
`.trim(),
        parameters: [productName]
    };
}

console.log("\nBILL OF MATERIALS");
console.log(billOfMaterialsQuery("Laptop"));

/* ------------------------------------------------------------------------- *
 * Section 10: Query builder for a reporting application
 * ------------------------------------------------------------------------- */

class CteQueryBuilder {
    constructor() {
        this.ctes = [];
        this.parameters = [];
        this.finalQuery = null;
    }

    addCte(name, query, parameters = []) {
        /*
         * CTE names are SQL identifiers, not ordinary values.
         * Therefore they cannot safely be inserted from arbitrary user
         * input. This builder validates the identifier.
         */
        if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) {
            throw new Error(`Invalid CTE identifier: ${name}`);
        }

        if (typeof query !== "string" || query.trim() === "") {
            throw new TypeError("CTE query must be a non-empty string.");
        }

        if (!Array.isArray(parameters)) {
            throw new TypeError("CTE parameters must be an array.");
        }

        this.ctes.push({
            name,
            query: query.trim()
        });

        this.parameters.push(...parameters);

        return this;
    }

    setFinalQuery(query, parameters = []) {
        if (typeof query !== "string" || query.trim() === "") {
            throw new TypeError("Final query must be a non-empty string.");
        }

        if (!Array.isArray(parameters)) {
            throw new TypeError("Final-query parameters must be an array.");
        }

        this.finalQuery = query.trim();
        this.parameters.push(...parameters);

        return this;
    }

    build(recursive = false) {
        if (this.ctes.length === 0) {
            throw new Error("At least one CTE is required.");
        }

        if (!this.finalQuery) {
            throw new Error("A final SELECT or statement is required.");
        }

        const withKeyword = recursive ? "WITH RECURSIVE" : "WITH";

        const cteSql = this.ctes
            .map((cte) => `${cte.name} AS (\n${cte.query}\n)`)
            .join(",\n");

        return {
            sql: `${withKeyword} ${cteSql}\n${this.finalQuery};`,
            parameters: [...this.parameters]
        };
    }
}

/* ------------------------------------------------------------------------- *
 * Section 11: Query builder example
 * ------------------------------------------------------------------------- */

function buildSalesReport() {
    const builder = new CteQueryBuilder();

    builder.addCte(
        "completed_orders",
        `
SELECT
    customer_id,
    amount,
    order_date
FROM orders
WHERE status = 'completed'
AND order_date >= ?
`,
        ["2026-01-01"]
    );

    builder.addCte(
        "customer_metrics",
        `
SELECT
    customer_id,
    COUNT(*) AS order_count,
    SUM(amount) AS total_revenue,
    AVG(amount) AS average_order_value
FROM completed_orders
GROUP BY customer_id
`
    );

    builder.addCte(
        "ranked_customers",
        `
SELECT
    customer_id,
    order_count,
    total_revenue,
    average_order_value,
    RANK() OVER (
        ORDER BY total_revenue DESC
    ) AS revenue_rank
FROM customer_metrics
`
    );

    builder.setFinalQuery(`
SELECT
    customer_id,
    order_count,
    ROUND(total_revenue, 2) AS total_revenue,
    ROUND(average_order_value, 2) AS average_order_value,
    revenue_rank
FROM ranked_customers
ORDER BY revenue_rank, customer_id
`);

    return builder.build();
}

console.log("\nBUILT SALES REPORT");
console.log(buildSalesReport());

/* ------------------------------------------------------------------------- *
 * Section 12: Safe dynamic filtering
 * ------------------------------------------------------------------------- */

const ALLOWED_REGIONS = new Set([
    "North",
    "South",
    "East",
    "West"
]);

function buildRegionalReport(region) {
    /*
     * Values should be parameters.
     * This allow-list prevents an unexpected region value from being treated
     * as an identifier or SQL fragment.
     */
    if (!ALLOWED_REGIONS.has(region)) {
        throw new Error(`Unsupported region: ${region}`);
    }

    return {
        sql: `
WITH completed_orders AS (
    SELECT
        o.customer_id,
        o.amount
    FROM orders AS o
    WHERE o.status = 'completed'
),
regional_customers AS (
    SELECT
        c.customer_id,
        c.customer_name,
        c.region
    FROM customers AS c
    WHERE c.region = ?
),
regional_revenue AS (
    SELECT
        rc.region,
        SUM(co.amount) AS revenue
    FROM regional_customers AS rc
    JOIN completed_orders AS co
        ON co.customer_id = rc.customer_id
    GROUP BY rc.region
)
SELECT *
FROM regional_revenue;
`.trim(),
        parameters: [region]
    };
}

console.log("\nSAFE REGIONAL REPORT");
console.log(buildRegionalReport("North"));

/* ------------------------------------------------------------------------- *
 * Section 13: CTE debugging helper
 * ------------------------------------------------------------------------- */

function inspectCteStages() {
    const stages = {
        completedOrders: `
SELECT
    customer_id,
    amount
FROM orders
WHERE status = 'completed'
`.trim(),

        customerTotals: `
SELECT
    customer_id,
    SUM(amount) AS total_revenue
FROM completed_orders
GROUP BY customer_id
`.trim(),

        rankedCustomers: `
SELECT
    customer_id,
    total_revenue,
    RANK() OVER (
        ORDER BY total_revenue DESC
    ) AS revenue_rank
FROM customer_totals
`.trim()
    };

    for (const [stageName, query] of Object.entries(stages)) {
        console.log(`\n--- ${stageName} ---`);
        console.log(query);
    }
}

console.log("\nDEBUGGING CTE STAGES");
inspectCteStages();

/* ------------------------------------------------------------------------- *
 * Section 14: Performance analysis helper
 * ------------------------------------------------------------------------- */

function explainQueryPlanQuery(sql) {
    if (!sql.trim().toUpperCase().startsWith("WITH")) {
        throw new Error(
            "This helper expects a query beginning with WITH."
        );
    }

    return {
        sql: `EXPLAIN QUERY PLAN ${sql}`,
        parameters: []
    };
}

const performanceQuery = `
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
`.trim();

console.log("\nEXPLAIN QUERY PLAN REQUEST");
console.log(explainQueryPlanQuery(performanceQuery));

/* ------------------------------------------------------------------------- *
 * Section 15: Async database-driver pattern
 * ------------------------------------------------------------------------- */

function createAsyncQueryPlan(sql, parameters = []) {
    /*
     * A real application would pass this object to a database driver's
     * asynchronous query method.
     *
     * Keeping the SQL and parameters separate allows the database driver to
     * perform parameter binding instead of requiring unsafe string
     * interpolation.
     */
    return {
        sql,
        parameters
    };
}

async function executeCteReport(executeQuery) {
    if (typeof executeQuery !== "function") {
        throw new TypeError(
            "executeQuery must be a function supplied by the database layer."
        );
    }

    const query = buildSalesReport();

    /*
     * The database connection is deliberately injected. This keeps the
     * reporting logic independent from a particular npm database package.
     */
    return executeQuery(query.sql, query.parameters);
}

/* ------------------------------------------------------------------------- *
 * Section 16: Edge-case validation
 * ------------------------------------------------------------------------- */

function validateRecursiveRange(start, end) {
    if (!Number.isInteger(start) || !Number.isInteger(end)) {
        return {
            valid: false,
            reason: "Both boundaries must be integers."
        };
    }

    if (start > end) {
        return {
            valid: false,
            reason: "Start cannot exceed end."
        };
    }

    if (end - start > 100000) {
        return {
            valid: false,
            reason: "Range is too large."
        };
    }

    return {
        valid: true,
        reason: null
    };
}

console.log("\nEDGE CASE VALIDATION");
console.log(validateRecursiveRange(1, 10));
console.log(validateRecursiveRange(10, 1));
console.log(validateRecursiveRange(1, 200000));

/* ------------------------------------------------------------------------- *
 * Section 17: CTE versus subquery comparison
 * ------------------------------------------------------------------------- */

function comparisonQueries() {
    const cte = `
WITH completed_orders AS (
    SELECT customer_id, amount
    FROM orders
    WHERE status = 'completed'
)
SELECT
    customer_id,
    SUM(amount) AS total_revenue
FROM completed_orders
GROUP BY customer_id;
`.trim();

    const subquery = `
SELECT
    customer_id,
    SUM(amount) AS total_revenue
FROM (
    SELECT customer_id, amount
    FROM orders
    WHERE status = 'completed'
) AS completed_orders
GROUP BY customer_id;
`.trim();

    return {
        cte,
        subquery,
        difference:
            "Both can express the same relational transformation; the CTE gives the intermediate result a named query stage."
    };
}

console.log("\nCTE VS SUBQUERY");
console.log(comparisonQueries());

/* ------------------------------------------------------------------------- *
 * Section 18: Complete industry-style analytics query
 * ------------------------------------------------------------------------- */

function completeAnalyticsQuery() {
    return {
        sql: `
WITH completed_orders AS (
    SELECT
        o.order_id,
        o.customer_id,
        o.order_date,
        o.amount
    FROM orders AS o
    WHERE o.status = 'completed'
),
monthly_customer_sales AS (
    SELECT
        customer_id,
        STRFTIME('%Y-%m', order_date) AS sales_month,
        SUM(amount) AS monthly_revenue
    FROM completed_orders
    GROUP BY
        customer_id,
        STRFTIME('%Y-%m', order_date)
),
customer_metrics AS (
    SELECT
        customer_id,
        SUM(monthly_revenue) AS total_revenue,
        COUNT(*) AS active_months,
        AVG(monthly_revenue) AS average_monthly_revenue
    FROM monthly_customer_sales
    GROUP BY customer_id
),
ranked_customers AS (
    SELECT
        customer_id,
        total_revenue,
        active_months,
        average_monthly_revenue,
        DENSE_RANK() OVER (
            ORDER BY total_revenue DESC
        ) AS revenue_rank
    FROM customer_metrics
)
SELECT
    customer_id,
    ROUND(total_revenue, 2) AS total_revenue,
    active_months,
    ROUND(average_monthly_revenue, 2) AS average_monthly_revenue,
    revenue_rank
FROM ranked_customers
ORDER BY revenue_rank, customer_id;
`.trim(),
        parameters: []
    };
}

console.log("\nCOMPLETE ANALYTICS QUERY");
console.log(completeAnalyticsQuery());

/* ------------------------------------------------------------------------- *
 * Section 19: Main demonstration
 * ------------------------------------------------------------------------- */

function main() {
    console.log("\n" + "=".repeat(80));
    console.log("COMMON TABLE EXPRESSIONS: JAVASCRIPT STUDY IMPLEMENTATION");
    console.log("=".repeat(80));

    console.log("\nThe JavaScript file demonstrates:");
    console.log("1. Basic CTE construction");
    console.log("2. Multiple CTE stages");
    console.log("3. Window functions after CTE aggregation");
    console.log("4. Recursive hierarchies");
    console.log("5. Recursive sequences");
    console.log("6. Recursive date generation");
    console.log("7. Graph traversal");
    console.log("8. Cycle protection");
    console.log("9. Bill-of-materials expansion");
    console.log("10. Query construction and validation");
    console.log("11. Parameterized queries");
    console.log("12. Application-side query organization");
    console.log("13. Debugging and execution-plan preparation");
    console.log("14. Industry-style analytics");

    console.log("\nAsync query execution example:");

    executeCteReport(async (sql, parameters) => {
        /*
         * This mock function does not contact a database. In a real
         * application, replace it with a call to the chosen database
         * driver's parameterized query API.
         */
        return {
            executed: false,
            reason: "Database driver injection point",
            sql,
            parameters
        };
    })
        .then((result) => {
            console.log(result);
        })
        .catch((error) => {
            console.error("Query execution error:", error.message);
        });
}

main();
