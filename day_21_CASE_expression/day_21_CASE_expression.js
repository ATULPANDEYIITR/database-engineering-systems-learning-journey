/*
 * CASE Expressions in SQL
 * =======================
 *
 * A self-contained JavaScript study file demonstrating SQL CASE concepts
 * alongside equivalent JavaScript business-rule implementations.
 *
 * The file intentionally uses JavaScript's standard runtime only. SQL
 * statements are represented as executable-style query strings so that the
 * SQL semantics can be studied without requiring an npm database package.
 *
 * The examples cover:
 * - Simple CASE
 * - Searched CASE
 * - NULL handling
 * - Business classification
 * - Conditional calculations
 * - Custom ordering
 * - Conditional aggregation
 * - Validation
 * - Nested rules
 * - SQL versus application-layer logic
 * - Parameterized query design
 * - Testing
 * - Performance and maintainability considerations
 */

"use strict";

/* -------------------------------------------------------------------------
 * Utility functions
 * ------------------------------------------------------------------------- */

function printTitle(title) {
    console.log("\n" + "=".repeat(88));
    console.log(title);
    console.log("=".repeat(88));
}

function printRows(rows) {
    if (rows.length === 0) {
        console.log("(no rows)");
        return;
    }

    const columns = Object.keys(rows[0]);
    console.log(columns.join(" | "));
    console.log("-".repeat(columns.join(" | ").length));

    for (const row of rows) {
        console.log(columns.map((column) => String(row[column])).join(" | "));
    }
}

function showSQL(title, sql) {
    printTitle(title);
    console.log(sql.trim());
}

/* -------------------------------------------------------------------------
 * Sample data
 * ------------------------------------------------------------------------- */

const customers = [
    {
        customerId: 1,
        customerName: "Aarav",
        country: "India",
        annualIncome: 45000,
        creditScore: 610,
        status: "active"
    },
    {
        customerId: 2,
        customerName: "Meera",
        country: "India",
        annualIncome: 125000,
        creditScore: 790,
        status: "active"
    },
    {
        customerId: 3,
        customerName: "Daniel",
        country: "USA",
        annualIncome: 95000,
        creditScore: 720,
        status: "active"
    },
    {
        customerId: 4,
        customerName: "Sophia",
        country: "UK",
        annualIncome: 38000,
        creditScore: 580,
        status: "inactive"
    },
    {
        customerId: 5,
        customerName: "Noah",
        country: null,
        annualIncome: null,
        creditScore: null,
        status: "prospect"
    }
];

const orders = [
    {
        orderId: 101,
        customerId: 1,
        amount: 450,
        paymentStatus: "paid",
        shippingDays: 3
    },
    {
        orderId: 102,
        customerId: 1,
        amount: 1200,
        paymentStatus: "paid",
        shippingDays: 5
    },
    {
        orderId: 103,
        customerId: 2,
        amount: 8500,
        paymentStatus: "paid",
        shippingDays: 2
    },
    {
        orderId: 104,
        customerId: 2,
        amount: 2200,
        paymentStatus: "pending",
        shippingDays: 8
    },
    {
        orderId: 105,
        customerId: 3,
        amount: 5000,
        paymentStatus: "paid",
        shippingDays: 4
    },
    {
        orderId: 106,
        customerId: 3,
        amount: 18000,
        paymentStatus: "paid",
        shippingDays: 12
    },
    {
        orderId: 107,
        customerId: 4,
        amount: 250,
        paymentStatus: "cancelled",
        shippingDays: 0
    },
    {
        orderId: 108,
        customerId: 5,
        amount: 900,
        paymentStatus: "pending",
        shippingDays: 15
    }
];

/* -------------------------------------------------------------------------
 * SQL CASE syntax
 * ------------------------------------------------------------------------- */

function demonstrateSQLSyntax() {
    showSQL(
        "1. SQL CASE syntax",
        `
Simple CASE:

CASE payment_status
    WHEN 'paid' THEN 'Payment complete'
    WHEN 'pending' THEN 'Awaiting payment'
    ELSE 'Other'
END

Searched CASE:

CASE
    WHEN amount < 1000 THEN 'Small'
    WHEN amount < 5000 THEN 'Medium'
    WHEN amount < 20000 THEN 'Large'
    ELSE 'Enterprise'
END
`
    );
}

/* -------------------------------------------------------------------------
 * Simple CASE equivalent
 * ------------------------------------------------------------------------- */

function describePaymentStatus(status) {
    // This JavaScript switch has the same basic idea as SQL's simple CASE.
    switch (status) {
        case "paid":
            return "Payment complete";
        case "pending":
            return "Awaiting payment";
        case "cancelled":
            return "Order cancelled";
        case "refunded":
            return "Money returned";
        default:
            return "Unknown status";
    }
}

function demonstrateSimpleCase() {
    printTitle("2. Simple CASE represented in JavaScript");

    for (const order of orders) {
        console.log(
            `${order.orderId}: ${order.paymentStatus} -> ` +
            `${describePaymentStatus(order.paymentStatus)}`
        );
    }
}

/* -------------------------------------------------------------------------
 * Searched CASE equivalent
 * ------------------------------------------------------------------------- */

function classifyOrderAmount(amount) {
    // Conditions are evaluated from top to bottom.
    // This mirrors a searched CASE expression.
    if (amount < 1000) {
        return "Small";
    }

    if (amount < 5000) {
        return "Medium";
    }

    if (amount < 20000) {
        return "Large";
    }

    return "Enterprise";
}

function demonstrateSearchedCase() {
    printTitle("3. Searched CASE represented in JavaScript");

    for (const order of orders) {
        console.log(
            `${order.orderId}: ${order.amount} -> ` +
            `${classifyOrderAmount(order.amount)}`
        );
    }

    showSQL(
        "Equivalent SQL",
        `
SELECT
    order_id,
    amount,
    CASE
        WHEN amount < 1000 THEN 'Small'
        WHEN amount < 5000 THEN 'Medium'
        WHEN amount < 20000 THEN 'Large'
        ELSE 'Enterprise'
    END AS order_size
FROM orders;
`
    );
}

/* -------------------------------------------------------------------------
 * NULL handling
 * ------------------------------------------------------------------------- */

function classifyIncome(income) {
    // JavaScript's null check corresponds conceptually to SQL's IS NULL.
    // SQL NULL and JavaScript null are not identical concepts, but both
    // require explicit missing-value handling.
    if (income === null || income === undefined) {
        return "Income unavailable";
    }

    if (income < 50000) {
        return "Low income";
    }

    if (income < 100000) {
        return "Middle income";
    }

    return "High income";
}

function demonstrateNullHandling() {
    printTitle("4. NULL and missing values");

    for (const customer of customers) {
        console.log(
            `${customer.customerName}: ` +
            `${classifyIncome(customer.annualIncome)}`
        );
    }

    showSQL(
        "SQL NULL rule",
        `
CASE
    WHEN annual_income IS NULL THEN 'Income unavailable'
    WHEN annual_income < 50000 THEN 'Low income'
    WHEN annual_income < 100000 THEN 'Middle income'
    ELSE 'High income'
END
`
    );

    console.log(
        "\nSQL lesson: use IS NULL rather than = NULL."
    );
}

/* -------------------------------------------------------------------------
 * Customer segmentation
 * ------------------------------------------------------------------------- */

function segmentCustomer(customer) {
    if (
        customer.annualIncome === null ||
        customer.creditScore === null
    ) {
        return "Insufficient data";
    }

    if (
        customer.creditScore >= 750 &&
        customer.annualIncome >= 100000
    ) {
        return "Premium";
    }

    if (
        customer.creditScore >= 650 &&
        customer.annualIncome >= 50000
    ) {
        return "Standard";
    }

    if (customer.creditScore >= 600) {
        return "Developing";
    }

    return "High risk";
}

function demonstrateBusinessSegmentation() {
    printTitle("5. Multi-condition business segmentation");

    const rows = customers.map((customer) => ({
        customer: customer.customerName,
        income: customer.annualIncome,
        creditScore: customer.creditScore,
        segment: segmentCustomer(customer)
    }));

    printRows(rows);

    showSQL(
        "Equivalent SQL business rule",
        `
CASE
    WHEN annual_income IS NULL OR credit_score IS NULL
        THEN 'Insufficient data'
    WHEN credit_score >= 750 AND annual_income >= 100000
        THEN 'Premium'
    WHEN credit_score >= 650 AND annual_income >= 50000
        THEN 'Standard'
    WHEN credit_score >= 600
        THEN 'Developing'
    ELSE 'High risk'
END AS customer_segment
`
    );
}

/* -------------------------------------------------------------------------
 * Conditional calculations
 * ------------------------------------------------------------------------- */

function calculateServiceFee(order) {
    // CASE can return a calculated numeric value, not only text.
    if (order.paymentStatus === "cancelled") {
        return 0;
    }

    if (order.amount >= 50000) {
        return order.amount * 0.005;
    }

    if (order.amount >= 10000) {
        return order.amount * 0.01;
    }

    return order.amount * 0.02;
}

function demonstrateConditionalCalculation() {
    printTitle("6. CASE returning calculated numeric values");

    for (const order of orders) {
        const fee = calculateServiceFee(order);

        console.log(
            `Order ${order.orderId}: amount=${order.amount.toFixed(2)}, ` +
            `fee=${fee.toFixed(2)}`
        );
    }

    showSQL(
        "Equivalent SQL",
        `
CASE
    WHEN payment_status = 'cancelled' THEN 0
    WHEN amount >= 50000 THEN amount * 0.005
    WHEN amount >= 10000 THEN amount * 0.01
    ELSE amount * 0.02
END AS service_fee
`
    );
}

/* -------------------------------------------------------------------------
 * Custom ordering
 * ------------------------------------------------------------------------- */

function paymentPriority(status) {
    // This function mirrors:
    //
    // ORDER BY CASE payment_status
    //     WHEN 'pending' THEN 1
    //     WHEN 'paid' THEN 2
    //     ...
    // END
    const priorities = {
        pending: 1,
        paid: 2,
        refunded: 3,
        cancelled: 4
    };

    return priorities[status] ?? 5;
}

function demonstrateCustomOrdering() {
    printTitle("7. CASE for custom business ordering");

    const sortedOrders = [...orders].sort((first, second) => {
        const priorityDifference =
            paymentPriority(first.paymentStatus) -
            paymentPriority(second.paymentStatus);

        if (priorityDifference !== 0) {
            return priorityDifference;
        }

        return second.amount - first.amount;
    });

    for (const order of sortedOrders) {
        console.log(
            `${order.paymentStatus.padEnd(10)} ` +
            `${String(order.orderId).padEnd(5)} ` +
            `${order.amount}`
        );
    }

    showSQL(
        "Equivalent SQL",
        `
ORDER BY
    CASE payment_status
        WHEN 'pending' THEN 1
        WHEN 'paid' THEN 2
        WHEN 'refunded' THEN 3
        WHEN 'cancelled' THEN 4
        ELSE 5
    END,
    amount DESC;
`
    );
}

/* -------------------------------------------------------------------------
 * Conditional aggregation
 * ------------------------------------------------------------------------- */

function conditionalAggregation(data) {
    /*
     * SQL:
     *
     * SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END)
     *
     * JavaScript can reproduce the same concept with reduce().
     */
    return data.reduce(
        (result, order) => {
            result.totalOrders += 1;

            if (order.paymentStatus === "paid") {
                result.paidOrders += 1;
                result.paidRevenue += order.amount;
            }

            if (order.paymentStatus === "pending") {
                result.pendingOrders += 1;
                result.pendingRevenue += order.amount;
            }

            if (order.paymentStatus === "cancelled") {
                result.cancelledOrders += 1;
            }

            return result;
        },
        {
            totalOrders: 0,
            paidOrders: 0,
            pendingOrders: 0,
            cancelledOrders: 0,
            paidRevenue: 0,
            pendingRevenue: 0
        }
    );
}

function demonstrateConditionalAggregation() {
    printTitle("8. Conditional aggregation");

    const metrics = conditionalAggregation(orders);
    printRows([metrics]);

    showSQL(
        "Equivalent SQL",
        `
SELECT
    COUNT(*) AS total_orders,
    SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END)
        AS paid_orders,
    SUM(CASE WHEN payment_status = 'pending' THEN 1 ELSE 0 END)
        AS pending_orders,
    SUM(CASE WHEN payment_status = 'cancelled' THEN 1 ELSE 0 END)
        AS cancelled_orders,
    SUM(CASE WHEN payment_status = 'paid' THEN amount ELSE 0 END)
        AS paid_revenue
FROM orders;
`
    );
}

/* -------------------------------------------------------------------------
 * Customer-level aggregation
 * ------------------------------------------------------------------------- */

function calculateCustomerRevenue(data) {
    const totals = new Map();

    for (const order of data) {
        if (order.paymentStatus !== "paid") {
            continue;
        }

        const existing = totals.get(order.customerId) ?? 0;
        totals.set(order.customerId, existing + order.amount);
    }

    return totals;
}

function demonstrateCustomerAggregation() {
    printTitle("9. Conditional aggregation by customer");

    const totals = calculateCustomerRevenue(orders);

    for (const [customerId, amount] of totals.entries()) {
        console.log(
            `Customer ${customerId}: paid revenue=${amount.toFixed(2)}`
        );
    }

    showSQL(
        "Equivalent SQL",
        `
SELECT
    customer_id,
    SUM(
        CASE
            WHEN payment_status = 'paid' THEN amount
            ELSE 0
        END
    ) AS paid_revenue
FROM orders
GROUP BY customer_id;
`
    );
}

/* -------------------------------------------------------------------------
 * Validation
 * ------------------------------------------------------------------------- */

function validateCustomer(customer) {
    /*
     * CASE can be used in SQL to turn raw data-quality problems into
     * diagnostic categories. The JavaScript version uses the same rule order.
     */
    if (
        customer.annualIncome === null &&
        customer.creditScore === null
    ) {
        return "Missing income and credit score";
    }

    if (customer.annualIncome === null) {
        return "Missing income";
    }

    if (customer.creditScore === null) {
        return "Missing credit score";
    }

    if (customer.annualIncome < 0) {
        return "Invalid negative income";
    }

    if (
        customer.creditScore < 300 ||
        customer.creditScore > 850
    ) {
        return "Invalid credit score";
    }

    return "Valid";
}

function demonstrateValidation() {
    printTitle("10. Data-quality validation");

    for (const customer of customers) {
        console.log(
            `${customer.customerName}: ${validateCustomer(customer)}`
        );
    }

    showSQL(
        "Equivalent SQL",
        `
CASE
    WHEN annual_income IS NULL AND credit_score IS NULL
        THEN 'Missing income and credit score'
    WHEN annual_income IS NULL
        THEN 'Missing income'
    WHEN credit_score IS NULL
        THEN 'Missing credit score'
    WHEN annual_income < 0
        THEN 'Invalid negative income'
    WHEN credit_score < 300 OR credit_score > 850
        THEN 'Invalid credit score'
    ELSE 'Valid'
END AS data_quality_status
`
    );
}

/* -------------------------------------------------------------------------
 * Nested CASE equivalent
 * ------------------------------------------------------------------------- */

function classifyProfile(customer) {
    if (customer.creditScore === null) {
        return "Unknown";
    }

    if (customer.creditScore >= 700) {
        if (customer.annualIncome === null) {
            return "High-score/income-unknown";
        }

        if (customer.annualIncome >= 100000) {
            return "High-score/high-income";
        }

        return "High-score/lower-income";
    }

    if (
        customer.annualIncome !== null &&
        customer.annualIncome >= 100000
    ) {
        return "Lower-score/high-income";
    }

    return "Lower-score/other";
}

function demonstrateNestedRules() {
    printTitle("11. Nested business rules");

    for (const customer of customers) {
        console.log(
            `${customer.customerName}: ${classifyProfile(customer)}`
        );
    }

    showSQL(
        "Equivalent nested CASE",
        `
CASE
    WHEN credit_score IS NULL THEN 'Unknown'
    WHEN credit_score >= 700 THEN
        CASE
            WHEN annual_income >= 100000
                THEN 'High-score/high-income'
            WHEN annual_income IS NULL
                THEN 'High-score/income-unknown'
            ELSE 'High-score/lower-income'
        END
    ELSE
        CASE
            WHEN annual_income >= 100000
                THEN 'Lower-score/high-income'
            ELSE 'Lower-score/other'
        END
END AS profile
`
    );
}

/* -------------------------------------------------------------------------
 * SQL CASE in application design
 * ------------------------------------------------------------------------- */

function demonstrateLayerSelection() {
    printTitle("12. Choosing between SQL CASE and JavaScript logic");

    console.log(`
Use SQL CASE when:
- The transformation belongs to the query.
- Filtering, grouping, sorting, or aggregation depends on the rule.
- Sending raw rows to the application would create unnecessary data transfer.
- The database is the natural owner of the classification.

Use JavaScript when:
- The rule depends on application state.
- The calculation requires browser or application APIs.
- The business rule is intentionally outside the database.
- The result is needed after data retrieval.

A rule duplicated independently in SQL and JavaScript can drift over time.
When the same business rule exists in multiple layers, define ownership and
test both implementations against the same boundary cases.
`);
}

/* -------------------------------------------------------------------------
 * Parameterized query design
 * ------------------------------------------------------------------------- */

function demonstrateParameterizedSQL() {
    printTitle("13. Parameterized SQL");

    const minimumAmount = 5000;

    /*
     * The following is a query template, not a concatenated query.
     * The ? placeholder represents a parameter in many SQL APIs.
     */
    const sql = `
SELECT
    order_id,
    amount,
    CASE
        WHEN amount >= ? THEN 'Above threshold'
        ELSE 'Below threshold'
    END AS threshold_status
FROM orders
ORDER BY order_id;
`;

    console.log("Threshold:", minimumAmount);
    console.log(sql.trim());

    console.log(`
The actual database driver should receive the SQL text and parameter
separately. Do not construct SQL by inserting untrusted user input directly
into the SQL string.
`);
}

/* -------------------------------------------------------------------------
 * Rule-table thinking
 * ------------------------------------------------------------------------- */

function demonstrateRuleTableDesign() {
    printTitle("14. When CASE becomes a rule-management problem");

    const ruleTable = [
        { minimum: 0, maximum: 999.99, category: "Small" },
        { minimum: 1000, maximum: 4999.99, category: "Medium" },
        { minimum: 5000, maximum: 19999.99, category: "Large" },
        { minimum: 20000, maximum: Infinity, category: "Enterprise" }
    ];

    function classifyUsingRules(amount) {
        const rule = ruleTable.find(
            (candidate) =>
                amount >= candidate.minimum &&
                amount <= candidate.maximum
        );

        return rule ? rule.category : "Unclassified";
    }

    for (const amount of [250, 1000, 5000, 20000, 100000]) {
        console.log(
            `${amount}: ${classifyUsingRules(amount)}`
        );
    }

    showSQL(
        "CASE version of the same rule",
        `
CASE
    WHEN amount < 1000 THEN 'Small'
    WHEN amount < 5000 THEN 'Medium'
    WHEN amount < 20000 THEN 'Large'
    ELSE 'Enterprise'
END
`
    );

    console.log(`
A database rule table can be useful when thresholds change frequently.
A hard-coded CASE can be preferable when the rule is stable, simple, and
closely tied to the query.
`);
}

/* -------------------------------------------------------------------------
 * Boundary testing
 * ------------------------------------------------------------------------- */

function testClassificationBoundaries() {
    printTitle("15. Testing CASE-style business rules");

    const tests = [
        [0, "Small"],
        [999.99, "Small"],
        [1000, "Medium"],
        [4999.99, "Medium"],
        [5000, "Large"],
        [19999.99, "Large"],
        [20000, "Enterprise"]
    ];

    let passed = 0;

    for (const [amount, expected] of tests) {
        const actual = classifyOrderAmount(amount);
        const success = actual === expected;

        console.log(
            `${success ? "PASS" : "FAIL"} ` +
            `amount=${amount} expected=${expected} actual=${actual}`
        );

        if (success) {
            passed += 1;
        }
    }

    console.log(`\nPassed ${passed}/${tests.length} tests.`);

    if (passed !== tests.length) {
        throw new Error("CASE boundary tests failed.");
    }
}

/* -------------------------------------------------------------------------
 * Incorrect ordering demonstration
 * ------------------------------------------------------------------------- */

function demonstrateOrderingPitfall() {
    printTitle("16. CASE rule-ordering pitfall");

    function incorrectClassification(amount) {
        if (amount >= 1000) {
            return "At least 1,000";
        }

        if (amount >= 5000) {
            return "At least 5,000";
        }

        return "Below 1,000";
    }

    const amount = 8000;

    console.log(
        `Incorrect ordering for ${amount}: ` +
        incorrectClassification(amount)
    );

    console.log(`
The >= 5,000 rule can never be reached for values >= 5,000 because the
broader >= 1,000 condition matches first.

Correct SQL ordering would put the more restrictive condition first:

CASE
    WHEN amount >= 5000 THEN 'At least 5,000'
    WHEN amount >= 1000 THEN 'At least 1,000'
    ELSE 'Below 1,000'
END
`);
}

/* -------------------------------------------------------------------------
 * Performance discussion
 * ------------------------------------------------------------------------- */

function discussPerformance() {
    printTitle("17. Performance considerations");

    console.log(`
CASE is normally inexpensive compared with large joins, sorting, grouping,
network transfer, or scanning large tables.

Important points:

1. CASE in SELECT usually performs per-row expression evaluation.
2. CASE in ORDER BY can contribute to sorting cost.
3. CASE in WHERE can make a predicate less directly index-friendly.
4. Repeating a complex CASE expression increases maintenance cost.
5. Conditional aggregation processes the rows participating in aggregation.
6. Generated/computed columns can sometimes make repeated classifications
   easier to index.
7. Query plans should be measured with realistic data.

JavaScript performance considerations are different. If the database can
perform a transformation efficiently before transferring millions of rows,
doing the classification in SQL may reduce network and application-memory
cost.
`);
}

/* -------------------------------------------------------------------------
 * Security discussion
 * ------------------------------------------------------------------------- */

function discussSecurity() {
    printTitle("18. Security considerations");

    console.log(`
CASE is not an authorization mechanism.

Do not assume that returning "Allowed" or "Denied" from CASE protects data.
Authorization should be enforced through appropriate database permissions,
row-level controls, application authorization, or another explicit security
mechanism.

For SQL statements:

- Use parameterized values.
- Validate dynamic identifiers.
- Do not concatenate untrusted values into SQL.
- Test unexpected NULL values.
- Audit high-impact business rules.
- Avoid exposing confidential classifications to unauthorized users.
`);
}

/* -------------------------------------------------------------------------
 * Main execution
 * ------------------------------------------------------------------------- */

function main() {
    demonstrateSQLSyntax();
    demonstrateSimpleCase();
    demonstrateSearchedCase();
    demonstrateNullHandling();
    demonstrateBusinessSegmentation();
    demonstrateConditionalCalculation();
    demonstrateCustomOrdering();
    demonstrateConditionalAggregation();
    demonstrateCustomerAggregation();
    demonstrateValidation();
    demonstrateNestedRules();
    demonstrateLayerSelection();
    demonstrateParameterizedSQL();
    demonstrateRuleTableDesign();
    testClassificationBoundaries();
    demonstrateOrderingPitfall();
    discussPerformance();
    discussSecurity();

    printTitle("19. Core CASE reference");

    console.log(`
Simple CASE:

CASE expression
    WHEN value1 THEN result1
    WHEN value2 THEN result2
    ELSE result
END

Searched CASE:

CASE
    WHEN condition1 THEN result1
    WHEN condition2 THEN result2
    ELSE result
END

Conditional count:

SUM(CASE WHEN condition THEN 1 ELSE 0 END)

Conditional amount:

SUM(CASE WHEN condition THEN amount ELSE 0 END)

Custom ordering:

ORDER BY CASE status
    WHEN 'pending' THEN 1
    WHEN 'paid' THEN 2
    ELSE 3
END

The central concept is that SQL CASE transforms conditions into values.
It is especially useful for classification, conditional calculations,
aggregation, sorting, validation, reporting, and business-rule encoding.
`);
}

main();
