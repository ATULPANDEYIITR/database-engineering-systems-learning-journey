/*
 * SQL Joins I: INNER JOIN, LEFT JOIN, RIGHT JOIN
 *
 * This file complements the Python/sqlite3 implementation by building a
 * small in-memory relational engine in plain JavaScript. The purpose is to
 * make the mechanics of matching rows visible rather than hiding them behind
 * a database driver.
 *
 * Run with:
 *   node sql-joins-1.js
 *
 * The implementation demonstrates:
 * - relational rows as JavaScript objects
 * - INNER JOIN
 * - LEFT JOIN
 * - RIGHT JOIN
 * - NULL-like unmatched values
 * - join predicates
 * - aliases
 * - one-to-many row multiplication
 * - aggregation
 * - validation
 * - performance considerations
 * - a hash-indexed equality join
 * - comparison of nested-loop and indexed approaches
 */

"use strict";


function printTitle(title) {
    console.log("\n" + "=".repeat(78));
    console.log(title);
    console.log("=".repeat(78));
}


function printRows(rows) {
    if (rows.length === 0) {
        console.log("(no rows)");
        return;
    }

    console.table(rows);
}


function cloneRow(row) {
    return Object.assign({}, row);
}


function innerJoin(leftRows, rightRows, leftKey, rightKey, options = {}) {
    /*
     * Nested-loop INNER JOIN.
     *
     * For every left row, inspect every right row. A pair is emitted only
     * when both keys are equal and neither key is nullish.
     *
     * Time complexity: O(L * R)
     * Space complexity: O(number of output rows)
     */
    const result = [];
    const {
        leftPrefix = "left",
        rightPrefix = "right",
        predicate = () => true,
    } = options;

    for (const leftRow of leftRows) {
        for (const rightRow of rightRows) {
            const leftValue = leftRow[leftKey];
            const rightValue = rightRow[rightKey];

            /*
             * SQL's ordinary equality join does not match NULL to NULL.
             * JavaScript uses null/undefined as the closest representation
             * for this demonstration.
             */
            if (
                leftValue !== null &&
                leftValue !== undefined &&
                rightValue !== null &&
                rightValue !== undefined &&
                leftValue === rightValue &&
                predicate(leftRow, rightRow)
            ) {
                result.push({
                    [`${leftPrefix}_id`]: leftRow[leftKey],
                    [`${leftPrefix}_data`]: cloneRow(leftRow),
                    [`${rightPrefix}_data`]: cloneRow(rightRow),
                });
            }
        }
    }

    return result;
}


function leftJoin(leftRows, rightRows, leftKey, rightKey, options = {}) {
    /*
     * Nested-loop LEFT JOIN.
     *
     * Every left row is preserved. If there are no matching right rows, a
     * result row is emitted with right_data = null.
     *
     * If multiple right rows match one left row, multiple result rows are
     * emitted. This is why a one-to-many relationship can multiply rows.
     */
    const result = [];
    const {
        leftPrefix = "left",
        rightPrefix = "right",
        predicate = () => true,
    } = options;

    for (const leftRow of leftRows) {
        let foundMatch = false;

        for (const rightRow of rightRows) {
            const leftValue = leftRow[leftKey];
            const rightValue = rightRow[rightKey];

            if (
                leftValue !== null &&
                leftValue !== undefined &&
                rightValue !== null &&
                rightValue !== undefined &&
                leftValue === rightValue &&
                predicate(leftRow, rightRow)
            ) {
                foundMatch = true;

                result.push({
                    [`${leftPrefix}_id`]: leftRow[leftKey],
                    [`${leftPrefix}_data`]: cloneRow(leftRow),
                    [`${rightPrefix}_data`]: cloneRow(rightRow),
                });
            }
        }

        if (!foundMatch) {
            result.push({
                [`${leftPrefix}_id`]: leftRow[leftKey],
                [`${leftPrefix}_data`]: cloneRow(leftRow),
                [`${rightPrefix}_data`]: null,
            });
        }
    }

    return result;
}


function rightJoin(leftRows, rightRows, leftKey, rightKey, options = {}) {
    /*
     * RIGHT JOIN can be implemented by reversing the inputs and performing a
     * LEFT JOIN. This is the same conceptual transformation used in SQL:
     *
     * A RIGHT JOIN B
     *
     * is equivalent in preservation semantics to:
     *
     * B LEFT JOIN A
     */
    const reversed = leftJoin(
        rightRows,
        leftRows,
        rightKey,
        leftKey,
        {
            leftPrefix: "right",
            rightPrefix: "left",
            predicate: (rightRow, leftRow) => {
                return options.predicate
                    ? options.predicate(leftRow, rightRow)
                    : true;
            },
        }
    );

    return reversed.map(row => ({
        left_id: row.right_id,
        left_data: row.right_data,
        right_data: row.left_data,
    }));
}


function hashInnerJoin(leftRows, rightRows, leftKey, rightKey) {
    /*
     * Hash-based equality INNER JOIN.
     *
     * Build an index from right-side key -> rows, then probe it with each
     * left row.
     *
     * Average-case time complexity: O(L + R + output)
     * Additional space: O(R)
     *
     * This can be much faster than a nested loop for large equality joins,
     * but it requires memory for the hash table and is not a universal
     * replacement for every join strategy.
     */
    const index = new Map();

    for (const rightRow of rightRows) {
        const key = rightRow[rightKey];

        if (key === null || key === undefined) {
            continue;
        }

        if (!index.has(key)) {
            index.set(key, []);
        }

        index.get(key).push(rightRow);
    }

    const result = [];

    for (const leftRow of leftRows) {
        const key = leftRow[leftKey];

        if (key === null || key === undefined) {
            continue;
        }

        const matches = index.get(key) || [];

        for (const rightRow of matches) {
            result.push({
                left: cloneRow(leftRow),
                right: cloneRow(rightRow),
            });
        }
    }

    return result;
}


function flattenJoinResult(joinRows, leftAlias, rightAlias) {
    /*
     * Convert nested join records into readable application-level objects.
     */
    return joinRows.map(row => ({
        [`${leftAlias}`]: row.left_data,
        [`${rightAlias}`]: row.right_data,
    }));
}


function groupBy(rows, keyFunction) {
    const groups = new Map();

    for (const row of rows) {
        const key = keyFunction(row);

        if (!groups.has(key)) {
            groups.set(key, []);
        }

        groups.get(key).push(row);
    }

    return groups;
}


function demonstrateBasicData() {
    printTitle("1. Relational data represented in JavaScript");

    const customers = [
        { customer_id: 1, customer_name: "Asha", city: "Lucknow" },
        { customer_id: 2, customer_name: "Bharat", city: "Delhi" },
        { customer_id: 3, customer_name: "Chitra", city: "Mumbai" },
        { customer_id: 4, customer_name: "Dev", city: "Pune" },
        { customer_id: 5, customer_name: "Esha", city: "Jaipur" },
    ];

    const orders = [
        { order_id: 101, customer_id: 1, product: "Laptop", amount: 75000 },
        { order_id: 102, customer_id: 1, product: "Mouse", amount: 1500 },
        { order_id: 103, customer_id: 2, product: "Monitor", amount: 18000 },
        { order_id: 104, customer_id: 3, product: "Keyboard", amount: 3500 },
        { order_id: 105, customer_id: null, product: "Unassigned Device", amount: 9000 },
    ];

    printRows(customers);
    printRows(orders);

    return { customers, orders };
}


function demonstrateInnerJoin(customers, orders) {
    printTitle("2. INNER JOIN mechanics");

    const joined = innerJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    const readable = flattenJoinResult(joined, "customer", "order");

    printRows(readable);

    console.log(
        "Only customers with at least one matching order are present."
    );
}


function demonstrateLeftJoin(customers, orders) {
    printTitle("3. LEFT JOIN mechanics");

    const joined = leftJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    const readable = flattenJoinResult(joined, "customer", "order");

    printRows(readable);

    console.log(
        "Dev and Esha remain present with order = null."
    );
}


function demonstrateRightJoin(customers, orders) {
    printTitle("4. RIGHT JOIN mechanics");

    const joined = rightJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    const readable = flattenJoinResult(joined, "customer", "order");

    printRows(readable);

    console.log(
        "Every order is preserved, including the order whose customer_id is null."
    );
}


function demonstrateOnCondition(customers, orders) {
    printTitle("5. Additional ON condition");

    const expensiveOrders = leftJoin(
        customers,
        orders,
        "customer_id",
        "customer_id",
        {
            predicate: (_customer, order) => order.amount >= 5000,
        }
    );

    printRows(
        flattenJoinResult(expensiveOrders, "customer", "order")
    );

    console.log(
        "All customers are preserved, but only orders >= 5000 are eligible matches."
    );
}


function demonstrateWhereLikeFiltering(customers, orders) {
    printTitle("6. ON filtering versus post-join filtering");

    const allOrders = leftJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    /*
     * This represents the conceptual effect of:
     *
     * LEFT JOIN ...
     * WHERE order.amount >= 5000
     *
     * Unmatched customers have order = null and are removed by the filter.
     */
    const filteredAfterJoin = allOrders.filter(row => {
        return row.right_data !== null && row.right_data.amount >= 5000;
    });

    printRows(
        flattenJoinResult(filteredAfterJoin, "customer", "order")
    );

    console.log(
        "Filtering after the LEFT JOIN removes rows whose right side is null."
    );
}


function demonstrateNullSemantics(customers, orders) {
    printTitle("7. NULL behavior");

    const joined = leftJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    const unmatchedCustomers = joined.filter(row => row.right_data === null);

    console.log("Customers without orders:");
    printRows(
        unmatchedCustomers.map(row => row.left_data)
    );

    const unassignedOrders = orders.filter(order => {
        return order.customer_id === null;
    });

    console.log("Orders with NULL customer_id:");
    printRows(unassignedOrders);

    console.log(
        "A normal equality join does not treat null === null as a relational match."
    );
}


function demonstrateOneToMany(customers, orders) {
    printTitle("8. One-to-many row multiplication");

    const joined = innerJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    const ashaRows = joined.filter(row => {
        return row.left_data.customer_id === 1;
    });

    printRows(
        ashaRows.map(row => ({
            customer: row.left_data.customer_name,
            order_id: row.right_data.order_id,
            product: row.right_data.product,
        }))
    );

    console.log(
        "Asha has two orders, so the joined result contains two Asha rows."
    );
}


function demonstrateAggregation(customers, orders) {
    printTitle("9. Aggregation after LEFT JOIN");

    const joined = leftJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    const groups = groupBy(
        joined,
        row => row.left_data.customer_id
    );

    const report = [];

    for (const [customerId, rows] of groups) {
        const customer = rows[0].left_data;
        const validOrders = rows
            .filter(row => row.right_data !== null)
            .map(row => row.right_data);

        const totalSpend = validOrders.reduce(
            (sum, order) => sum + order.amount,
            0
        );

        report.push({
            customer_id: Number(customerId),
            customer_name: customer.customer_name,
            order_count: validOrders.length,
            total_spend: totalSpend,
        });
    }

    report.sort((a, b) => b.total_spend - a.total_spend);

    printRows(report);
}


function demonstrateMultiTableJoin() {
    printTitle("10. Joining multiple relations");

    const departments = [
        { department_id: 10, department_name: "Engineering" },
        { department_id: 20, department_name: "Finance" },
        { department_id: 30, department_name: "Human Resources" },
        { department_id: 40, department_name: "Security" },
    ];

    const employees = [
        { employee_id: 1, employee_name: "Anita", department_id: 10, salary: 95000 },
        { employee_id: 2, employee_name: "Ravi", department_id: 10, salary: 110000 },
        { employee_id: 3, employee_name: "Meera", department_id: 20, salary: 90000 },
        { employee_id: 4, employee_name: "Karan", department_id: null, salary: 70000 },
        { employee_id: 5, employee_name: "Nisha", department_id: 30, salary: 85000 },
    ];

    const joined = leftJoin(
        departments,
        employees,
        "department_id",
        "department_id"
    );

    printRows(
        joined.map(row => ({
            department: row.left_data.department_name,
            employee: row.right_data
                ? row.right_data.employee_name
                : null,
            salary: row.right_data
                ? row.right_data.salary
                : null,
        }))
    );
}


function demonstrateHashJoin(customers, orders) {
    printTitle("11. Hash-based equality JOIN");

    const nestedLoopResult = innerJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    const hashResult = hashInnerJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    console.log("Nested-loop result count:", nestedLoopResult.length);
    console.log("Hash-join result count:", hashResult.length);

    console.log(
        "Both produce the same number of matching pairs for this equality join."
    );

    printRows(hashResult);
}


function generateLargeDataSet(numberOfCustomers, numberOfOrders) {
    const customers = [];
    const orders = [];

    for (let index = 1; index <= numberOfCustomers; index += 1) {
        customers.push({
            customer_id: index,
            customer_name: `Customer ${index}`,
            city: index % 2 === 0 ? "Delhi" : "Lucknow",
        });
    }

    for (let index = 1; index <= numberOfOrders; index += 1) {
        orders.push({
            order_id: index,
            customer_id: (index % numberOfCustomers) + 1,
            product: `Product ${index % 20}`,
            amount: (index % 100) * 100 + 100,
        });
    }

    return { customers, orders };
}


function demonstratePerformance() {
    printTitle("12. Performance considerations");

    const {
        customers,
        orders,
    } = generateLargeDataSet(2000, 10000);

    console.time("nested-loop INNER JOIN");

    /*
     * This is deliberately a modest dataset because a nested-loop join has
     * O(L * R) comparisons and becomes expensive rapidly.
     */
    const nestedLoop = innerJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    console.timeEnd("nested-loop INNER JOIN");

    console.time("hash INNER JOIN");

    const hashResult = hashInnerJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    console.timeEnd("hash INNER JOIN");

    console.log("Nested-loop output rows:", nestedLoop.length);
    console.log("Hash-join output rows:", hashResult.length);

    console.log(
        `
For an equality join, the hash implementation avoids comparing every
customer against every order. A production database may use a different
physical strategy based on statistics, indexes, memory, ordering, and
optimizer decisions.
`
    );
}


function demonstrateValidation(customers, orders) {
    printTitle("13. Join validation and defensive programming");

    const customerIds = new Set(
        customers.map(customer => customer.customer_id)
    );

    const orphanOrders = orders.filter(order => {
        return (
            order.customer_id !== null &&
            !customerIds.has(order.customer_id)
        );
    });

    console.log("Orders referring to nonexistent customers:");
    printRows(orphanOrders);

    console.log(
        "A relational database can enforce this relationship with a foreign key."
    );
}


function demonstrateCommonMistakes(customers, orders) {
    printTitle("14. Common mistakes");

    console.log(
        `
Mistake: treating a LEFT JOIN as if it always returns one row per left row.

Correction: one-to-many matches produce multiple result rows.

Mistake: filtering nullable right-side columns after a LEFT JOIN without
considering the effect.

Correction: decide whether the condition belongs in ON or WHERE.

Mistake: joining on unrelated columns.

Correction: identify the actual primary-key/foreign-key relationship.

Mistake: assuming NULL equals NULL.

Correction: SQL uses three-valued logic, so ordinary equality does not match
NULL values.

Mistake: using nested loops on very large equality-join datasets in application
code.

Correction: use a database engine, an index, or an appropriate hash-based
algorithm when implementing the operation yourself.
`
    );

    const result = leftJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    console.log("Rows produced by the LEFT JOIN:", result.length);
}


function runAssertions(customers, orders) {
    printTitle("15. Executable semantic checks");

    const inner = innerJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    const left = leftJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    const right = rightJoin(
        customers,
        orders,
        "customer_id",
        "customer_id"
    );

    /*
     * Four orders have valid customer matches.
     */
    console.assert(
        inner.length === 4,
        `Expected 4 INNER JOIN rows, got ${inner.length}`
    );

    /*
     * Six rows occur in the LEFT JOIN:
     * Asha -> 2
     * Bharat -> 1
     * Chitra -> 1
     * Dev -> 1 unmatched
     * Esha -> 1 unmatched
     */
    console.assert(
        left.length === 6,
        `Expected 6 LEFT JOIN rows, got ${left.length}`
    );

    /*
     * Five orders are preserved by the RIGHT JOIN.
     */
    console.assert(
        right.length === 5,
        `Expected 5 RIGHT JOIN rows, got ${right.length}`
    );

    console.log("INNER JOIN assertion: PASSED");
    console.log("LEFT JOIN assertion: PASSED");
    console.log("RIGHT JOIN assertion: PASSED");
}


function main() {
    printTitle("SQL Joins I: INNER JOIN, LEFT JOIN, RIGHT JOIN");

    const { customers, orders } = demonstrateBasicData();

    demonstrateInnerJoin(customers, orders);
    demonstrateLeftJoin(customers, orders);
    demonstrateRightJoin(customers, orders);
    demonstrateOnCondition(customers, orders);
    demonstrateWhereLikeFiltering(customers, orders);
    demonstrateNullSemantics(customers, orders);
    demonstrateOneToMany(customers, orders);
    demonstrateAggregation(customers, orders);
    demonstrateMultiTableJoin();
    demonstrateHashJoin(customers, orders);
    demonstratePerformance();
    demonstrateValidation(customers, orders);
    demonstrateCommonMistakes(customers, orders);
    runAssertions(customers, orders);

    printTitle("16. Completed");
    console.log("All JavaScript JOIN demonstrations completed.");
}


main();
