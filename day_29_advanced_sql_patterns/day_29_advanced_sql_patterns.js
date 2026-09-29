/*
 * Advanced SQL Patterns
 * =====================
 *
 * Topic:
 *   Top-N, gaps-and-islands, deduplication, and pivot-style analysis
 *
 * This JavaScript file is executable with a modern Node.js runtime and uses
 * plain JavaScript arrays to model relational data. It demonstrates the
 * algorithmic logic behind advanced SQL patterns while also generating the
 * equivalent SQL statements that can be executed by a relational database.
 *
 * No external npm packages are required.
 *
 * The examples cover:
 *   - Ranking
 *   - Top-N per group
 *   - Top-N with ties
 *   - Running totals
 *   - LAG/LEAD equivalents
 *   - Gaps-and-islands
 *   - Sessionization
 *   - Deduplication
 *   - Pivot-style conditional aggregation
 *   - Dynamic pivot SQL
 *   - Validation
 *   - Complexity and implementation trade-offs
 */

"use strict";

// -----------------------------------------------------------------------------
// 1. Sample relational data
// -----------------------------------------------------------------------------

const sales = [
    { saleId: 1, customerId: 101, salesperson: "Asha", region: "North", product: "Laptop", date: "2026-01-03", amount: 1200 },
    { saleId: 2, customerId: 101, salesperson: "Asha", region: "North", product: "Phone", date: "2026-01-04", amount: 800 },
    { saleId: 3, customerId: 101, salesperson: "Asha", region: "North", product: "Laptop", date: "2026-01-09", amount: 1500 },
    { saleId: 4, customerId: 102, salesperson: "Ravi", region: "North", product: "Tablet", date: "2026-01-05", amount: 600 },
    { saleId: 5, customerId: 102, salesperson: "Ravi", region: "North", product: "Phone", date: "2026-01-06", amount: 900 },
    { saleId: 6, customerId: 102, salesperson: "Ravi", region: "North", product: "Laptop", date: "2026-01-10", amount: 2100 },
    { saleId: 7, customerId: 103, salesperson: "Meera", region: "South", product: "Laptop", date: "2026-01-02", amount: 2200 },
    { saleId: 8, customerId: 103, salesperson: "Meera", region: "South", product: "Phone", date: "2026-01-08", amount: 700 },
    { saleId: 9, customerId: 103, salesperson: "Meera", region: "South", product: "Tablet", date: "2026-01-11", amount: 500 },
    { saleId: 10, customerId: 104, salesperson: "Kabir", region: "South", product: "Laptop", date: "2026-01-02", amount: 1800 },
    { saleId: 11, customerId: 104, salesperson: "Kabir", region: "South", product: "Phone", date: "2026-01-07", amount: 1100 },
    { saleId: 12, customerId: 104, salesperson: "Kabir", region: "South", product: "Tablet", date: "2026-01-09", amount: 900 },
    { saleId: 13, customerId: 105, salesperson: "Nisha", region: "West", product: "Laptop", date: "2026-01-03", amount: 1300 },
    { saleId: 14, customerId: 105, salesperson: "Nisha", region: "West", product: "Phone", date: "2026-01-03", amount: 1300 },
    { saleId: 15, customerId: 105, salesperson: "Nisha", region: "West", product: "Tablet", date: "2026-01-12", amount: 400 }
];

const events = [
    { eventId: 1, customerId: 101, date: "2026-01-01", type: "login", value: 0 },
    { eventId: 2, customerId: 101, date: "2026-01-02", type: "purchase", value: 120 },
    { eventId: 3, customerId: 101, date: "2026-01-03", type: "login", value: 0 },
    { eventId: 4, customerId: 101, date: "2026-01-04", type: "purchase", value: 90 },
    { eventId: 5, customerId: 101, date: "2026-01-10", type: "login", value: 0 },
    { eventId: 6, customerId: 101, date: "2026-01-11", type: "purchase", value: 150 },
    { eventId: 7, customerId: 102, date: "2026-01-02", type: "login", value: 0 },
    { eventId: 8, customerId: 102, date: "2026-01-03", type: "purchase", value: 80 },
    { eventId: 9, customerId: 102, date: "2026-01-08", type: "login", value: 0 },
    { eventId: 10, customerId: 102, date: "2026-01-09", type: "purchase", value: 100 },
    { eventId: 11, customerId: 102, date: "2026-01-10", type: "purchase", value: 60 },
    { eventId: 12, customerId: 103, date: "2026-01-01", type: "login", value: 0 },
    { eventId: 13, customerId: 103, date: "2026-01-15", type: "purchase", value: 300 }
];

const employees = [
    { recordId: 1, employeeId: 501, name: "Arjun", email: "arjun@example.com", department: "Engineering", salary: 90000, updatedAt: "2026-01-01T09:00:00" },
    { recordId: 2, employeeId: 501, name: "Arjun Kumar", email: "arjun@example.com", department: "Engineering", salary: 95000, updatedAt: "2026-02-01T09:00:00" },
    { recordId: 3, employeeId: 502, name: "Bhavna", email: "bhavna@example.com", department: "Finance", salary: 85000, updatedAt: "2026-01-15T09:00:00" },
    { recordId: 4, employeeId: 502, name: "Bhavna", email: "bhavna@example.com", department: "Finance", salary: 88000, updatedAt: "2026-02-15T09:00:00" },
    { recordId: 5, employeeId: 503, name: "Chirag", email: "chirag@example.com", department: "Engineering", salary: 78000, updatedAt: "2026-01-10T09:00:00" },
    { recordId: 6, employeeId: 504, name: "Divya", email: "divya@example.com", department: "HR", salary: 70000, updatedAt: "2026-01-05T09:00:00" },
    { recordId: 7, employeeId: 504, name: "Divya", email: "divya@example.com", department: "HR", salary: 72000, updatedAt: "2026-03-05T09:00:00" }
];


// -----------------------------------------------------------------------------
// 2. General utility functions
// -----------------------------------------------------------------------------

function print(title, value) {
    console.log(`\n${"=".repeat(88)}\n${title}\n${"=".repeat(88)}`);
    console.table(value);
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

function compareDescending(left, right) {
    return right - left;
}

function parseDate(value) {
    return new Date(`${value}T00:00:00Z`);
}

function daysBetween(firstDate, secondDate) {
    const millisecondsPerDay = 24 * 60 * 60 * 1000;
    return Math.round(
        (parseDate(secondDate) - parseDate(firstDate)) / millisecondsPerDay
    );
}


// -----------------------------------------------------------------------------
// 3. ROW_NUMBER, RANK, and DENSE_RANK
// -----------------------------------------------------------------------------

function rankWithinGroups(rows, groupKey, valueKey) {
    /*
     * This function models SQL:
     *
     * ROW_NUMBER() OVER (
     *     PARTITION BY region
     *     ORDER BY amount DESC, sale_id
     * )
     *
     * A deterministic tie-breaker is essential when an application requires
     * exactly N rows rather than all tied rows.
     */
    const groups = groupBy(rows, row => row[groupKey]);
    const result = [];

    for (const groupRows of groups.values()) {
        const sorted = [...groupRows].sort((a, b) => {
            const valueDifference = b[valueKey] - a[valueKey];

            if (valueDifference !== 0) {
                return valueDifference;
            }

            return a.saleId - b.saleId;
        });

        sorted.forEach((row, index) => {
            result.push({
                ...row,
                rowNumber: index + 1
            });
        });
    }

    return result.sort((a, b) =>
        a[groupKey].localeCompare(b[groupKey]) ||
        a.rowNumber - b.rowNumber
    );
}

function addRankAndDenseRank(rows, groupKey, valueKey) {
    /*
     * SQL RANK and DENSE_RANK differ when ties occur:
     *
     * Values:       100, 100, 90
     * RANK:           1,   1,  3
     * DENSE_RANK:     1,   1,  2
     */
    const groups = groupBy(rows, row => row[groupKey]);
    const result = [];

    for (const groupRows of groups.values()) {
        const sorted = [...groupRows].sort(
            (a, b) => b[valueKey] - a[valueKey]
        );

        let previousValue;
        let rank = 0;
        let denseRank = 0;

        sorted.forEach((row, index) => {
            if (index === 0 || row[valueKey] !== previousValue) {
                rank = index + 1;
                denseRank += 1;
            }

            result.push({
                ...row,
                rank,
                denseRank
            });

            previousValue = row[valueKey];
        });
    }

    return result;
}


// -----------------------------------------------------------------------------
// 4. Top-N per group
// -----------------------------------------------------------------------------

function topNPerGroup(rows, groupKey, valueKey, n) {
    if (!Number.isInteger(n) || n <= 0) {
        throw new RangeError("n must be a positive integer.");
    }

    return rankWithinGroups(rows, groupKey, valueKey)
        .filter(row => row.rowNumber <= n);
}

function topNWithTies(rows, groupKey, valueKey, n) {
    if (!Number.isInteger(n) || n <= 0) {
        throw new RangeError("n must be a positive integer.");
    }

    return addRankAndDenseRank(rows, groupKey, valueKey)
        .filter(row => row.rank <= n);
}

print(
    "Top 2 sales per region using ROW_NUMBER semantics",
    topNPerGroup(sales, "region", "amount", 2)
);

print(
    "Top 2 ranks per region using RANK semantics",
    topNWithTies(sales, "region", "amount", 2)
);


// -----------------------------------------------------------------------------
// 5. LAG, LEAD, and running totals
// -----------------------------------------------------------------------------

function addLagAndLead(rows, groupKey, dateKey, valueKey) {
    const groups = groupBy(rows, row => row[groupKey]);
    const result = [];

    for (const groupRows of groups.values()) {
        const sorted = [...groupRows].sort(
            (a, b) =>
                parseDate(a[dateKey]) - parseDate(b[dateKey]) ||
                a.saleId - b.saleId
        );

        sorted.forEach((row, index) => {
            result.push({
                ...row,
                previousValue:
                    index === 0 ? null : sorted[index - 1][valueKey],
                nextValue:
                    index === sorted.length - 1
                        ? null
                        : sorted[index + 1][valueKey]
            });
        });
    }

    return result.sort(
        (a, b) =>
            a[groupKey].localeCompare(b[groupKey]) ||
            parseDate(a[dateKey]) - parseDate(b[dateKey])
    );
}

function addRunningTotal(rows, groupKey, dateKey, valueKey) {
    const groups = groupBy(rows, row => row[groupKey]);
    const result = [];

    for (const groupRows of groups.values()) {
        const sorted = [...groupRows].sort(
            (a, b) =>
                parseDate(a[dateKey]) - parseDate(b[dateKey]) ||
                a.saleId - b.saleId
        );

        let runningTotal = 0;

        for (const row of sorted) {
            runningTotal += row[valueKey];

            result.push({
                ...row,
                runningTotal
            });
        }
    }

    return result;
}

print(
    "JavaScript equivalent of LAG and LEAD",
    addLagAndLead(sales, "salesperson", "date", "amount")
);

print(
    "JavaScript equivalent of a partitioned running total",
    addRunningTotal(sales, "region", "date", "amount")
);


// -----------------------------------------------------------------------------
// 6. Gaps-and-islands
// -----------------------------------------------------------------------------

function consecutiveDateIslands(eventRows) {
    /*
     * The relational technique is:
     *
     *   date - ROW_NUMBER()
     *
     * Consecutive dates produce the same derived island key.
     *
     * This implementation uses an equivalent procedural representation:
     * a new island starts whenever the gap from the previous date is greater
     * than one day.
     */
    const customerGroups = groupBy(eventRows, row => row.customerId);
    const islands = [];

    for (const [customerId, customerEvents] of customerGroups) {
        const sorted = [...customerEvents].sort(
            (a, b) =>
                parseDate(a.date) - parseDate(b.date) ||
                a.eventId - b.eventId
        );

        let currentIsland = null;

        for (const event of sorted) {
            const startsNewIsland =
                currentIsland === null ||
                daysBetween(currentIsland.endDate, event.date) > 1;

            if (startsNewIsland) {
                currentIsland = {
                    customerId,
                    startDate: event.date,
                    endDate: event.date,
                    eventCount: 1
                };

                islands.push(currentIsland);
            } else {
                currentIsland.endDate = event.date;
                currentIsland.eventCount += 1;
            }
        }
    }

    return islands;
}

print(
    "Consecutive-date islands",
    consecutiveDateIslands(events)
);


// -----------------------------------------------------------------------------
// 7. Sessionization
// -----------------------------------------------------------------------------

function sessionize(eventRows, gapThresholdDays = 1) {
    /*
     * A session is an island defined by a maximum allowed inactivity gap.
     *
     * In production event systems the threshold may be 30 minutes, one hour,
     * or another domain-specific interval. This sample uses calendar dates.
     */
    if (gapThresholdDays < 0) {
        throw new RangeError("Session gap cannot be negative.");
    }

    const groups = groupBy(eventRows, row => row.customerId);
    const sessions = [];

    for (const [customerId, customerEvents] of groups) {
        const sorted = [...customerEvents].sort(
            (a, b) =>
                parseDate(a.date) - parseDate(b.date) ||
                a.eventId - b.eventId
        );

        let sessionNumber = 0;
        let session = null;

        for (const event of sorted) {
            const gap = session === null
                ? Infinity
                : daysBetween(session.endDate, event.date);

            if (session === null || gap > gapThresholdDays) {
                sessionNumber += 1;

                session = {
                    customerId,
                    sessionNumber,
                    startDate: event.date,
                    endDate: event.date,
                    events: 1,
                    value: event.value
                };

                sessions.push(session);
            } else {
                session.endDate = event.date;
                session.events += 1;
                session.value += event.value;
            }
        }
    }

    return sessions;
}

print(
    "Sessionized customer activity",
    sessionize(events, 1)
);


// -----------------------------------------------------------------------------
// 8. Duplicate detection and deterministic deduplication
// -----------------------------------------------------------------------------

function findDuplicates(rows, keyFunction) {
    const groups = groupBy(rows, keyFunction);

    return [...groups.entries()]
        .filter(([, groupRows]) => groupRows.length > 1)
        .map(([key, groupRows]) => ({
            key,
            duplicateCount: groupRows.length,
            records: groupRows
        }));
}

function deduplicateKeepNewest(rows, keyFunction, dateKey) {
    /*
     * This models:
     *
     * ROW_NUMBER() OVER (
     *     PARTITION BY email
     *     ORDER BY updated_at DESC, record_id DESC
     * )
     *
     * The first row in each sorted group is retained.
     */
    const groups = groupBy(rows, keyFunction);
    const retained = [];

    for (const groupRows of groups.values()) {
        const sorted = [...groupRows].sort(
            (a, b) =>
                new Date(b[dateKey]) - new Date(a[dateKey]) ||
                b.recordId - a.recordId
        );

        retained.push(sorted[0]);
    }

    return retained.sort((a, b) => a.recordId - b.recordId);
}

print(
    "Duplicate employee groups",
    findDuplicates(employees, employee => employee.email)
);

const deduplicatedEmployees = deduplicateKeepNewest(
    employees,
    employee => employee.email,
    "updatedAt"
);

print(
    "Employees after deterministic deduplication",
    deduplicatedEmployees
);


// -----------------------------------------------------------------------------
// 9. Pivot-style analysis
// -----------------------------------------------------------------------------

function pivotSales(rows, categories) {
    /*
     * SQL engines without a PIVOT keyword can use:
     *
     * SUM(CASE WHEN product = 'Laptop' THEN amount ELSE 0 END)
     *
     * This JavaScript implementation models the same conditional aggregation.
     */
    const groups = groupBy(rows, row => row.region);

    return [...groups.entries()].map(([region, groupRows]) => {
        const output = { region };

        for (const category of categories) {
            output[category] = groupRows
                .filter(row => row.product === category)
                .reduce((total, row) => total + row.amount, 0);
        }

        output.total = groupRows.reduce(
            (total, row) => total + row.amount,
            0
        );

        return output;
    });
}

const products = ["Laptop", "Phone", "Tablet"];

print(
    "Pivot-style sales by region and product",
    pivotSales(sales, products)
);


// -----------------------------------------------------------------------------
// 10. Dynamic pivot SQL generation
// -----------------------------------------------------------------------------

function quoteSqlLiteral(value) {
    /*
     * SQL string literals use doubled single quotes.
     * This function protects literal values, but identifiers still require
     * allow-list validation.
     */
    return `'${String(value).replaceAll("'", "''")}'`;
}

function quoteIdentifier(identifier) {
    /*
     * Identifiers cannot normally be parameterized as SQL values.
     * An application should only permit known-safe identifiers.
     */
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(identifier)) {
        throw new Error(`Unsafe SQL identifier: ${identifier}`);
    }

    return `"${identifier}"`;
}

function buildDynamicPivotSQL(categories) {
    if (!Array.isArray(categories) || categories.length === 0) {
        throw new Error("At least one pivot category is required.");
    }

    const expressions = categories.map(category => {
        const literal = quoteSqlLiteral(category);
        const alias = quoteIdentifier(`${category.toLowerCase()}_sales`);

        return (
            `SUM(CASE WHEN product = ${literal} ` +
            `THEN amount ELSE 0 END) AS ${alias}`
        );
    });

    return [
        "SELECT",
        "    region,",
        `    ${expressions.join(",\n    ")}`,
        "FROM sales",
        "GROUP BY region",
        "ORDER BY region;"
    ].join("\n");
}

console.log("\nGenerated dynamic pivot SQL:\n");
console.log(buildDynamicPivotSQL(products));


// -----------------------------------------------------------------------------
// 11. Combined analytical report
// -----------------------------------------------------------------------------

function buildRegionalReport(rows) {
    /*
     * This combines several analytical concepts:
     *   1. group totals
     *   2. deterministic ranking
     *   3. percentage of group total
     *   4. running totals
     */
    const groups = groupBy(rows, row => row.region);
    const result = [];

    for (const [region, groupRows] of groups) {
        const regionTotal = groupRows.reduce(
            (total, row) => total + row.amount,
            0
        );

        const ranked = [...groupRows].sort(
            (a, b) =>
                b.amount - a.amount ||
                a.saleId - b.saleId
        );

        const chronological = [...groupRows].sort(
            (a, b) =>
                parseDate(a.date) - parseDate(b.date) ||
                a.saleId - b.saleId
        );

        const runningTotals = new Map();
        let runningTotal = 0;

        for (const row of chronological) {
            runningTotal += row.amount;
            runningTotals.set(row.saleId, runningTotal);
        }

        ranked.forEach((row, index) => {
            result.push({
                saleId: row.saleId,
                region,
                salesperson: row.salesperson,
                product: row.product,
                amount: row.amount,
                regionTotal,
                percentOfRegion: Number(
                    ((row.amount / regionTotal) * 100).toFixed(2)
                ),
                regionRank: index + 1,
                regionRunningTotal: runningTotals.get(row.saleId)
            });
        });
    }

    return result.sort(
        (a, b) =>
            a.region.localeCompare(b.region) ||
            a.regionRank - b.regionRank
    );
}

print(
    "Combined regional analytical report",
    buildRegionalReport(sales)
);


// -----------------------------------------------------------------------------
// 12. Equivalent SQL patterns
// -----------------------------------------------------------------------------

const SQL_PATTERNS = {
    topNPerGroup: `
WITH ranked AS (
    SELECT
        sale_id,
        region,
        amount,
        ROW_NUMBER() OVER (
            PARTITION BY region
            ORDER BY amount DESC, sale_id
        ) AS rn
    FROM sales
)
SELECT *
FROM ranked
WHERE rn <= 2;
`,

    topNWithTies: `
WITH ranked AS (
    SELECT
        sale_id,
        region,
        amount,
        RANK() OVER (
            PARTITION BY region
            ORDER BY amount DESC
        ) AS ranking
    FROM sales
)
SELECT *
FROM ranked
WHERE ranking <= 2;
`,

    deduplication: `
DELETE FROM employee_records
WHERE record_id IN (
    SELECT record_id
    FROM (
        SELECT
            record_id,
            ROW_NUMBER() OVER (
                PARTITION BY email
                ORDER BY updated_at DESC, record_id DESC
            ) AS rn
        FROM employee_records
    )
    WHERE rn > 1
);
`,

    pivotStyle: `
SELECT
    region,
    SUM(CASE WHEN product = 'Laptop' THEN amount ELSE 0 END) AS laptop,
    SUM(CASE WHEN product = 'Phone' THEN amount ELSE 0 END) AS phone,
    SUM(CASE WHEN product = 'Tablet' THEN amount ELSE 0 END) AS tablet
FROM sales
GROUP BY region;
`
};

console.log("\nCore SQL patterns:");
for (const [name, sql] of Object.entries(SQL_PATTERNS)) {
    console.log(`\n--- ${name} ---`);
    console.log(sql.trim());
}


// -----------------------------------------------------------------------------
// 13. Complexity discussion represented as executable metadata
// -----------------------------------------------------------------------------

const complexityNotes = [
    {
        pattern: "Top-N per group",
        typicalCost: "O(n log n) when sorting is required",
        keyConcern: "Partition size and ordering cost"
    },
    {
        pattern: "Gaps-and-islands",
        typicalCost: "O(n log n) because ordered window processing is usually required",
        keyConcern: "Correct chronological ordering"
    },
    {
        pattern: "Deduplication",
        typicalCost: "O(n log n) when each duplicate group must be ordered",
        keyConcern: "Deterministic retention rule"
    },
    {
        pattern: "Pivot-style aggregation",
        typicalCost: "O(n * k) for k conditional categories in a straightforward implementation",
        keyConcern: "Large numbers of categories can make generated SQL wide"
    }
];

print("Performance considerations", complexityNotes);


// -----------------------------------------------------------------------------
// 14. Validation and edge cases
// -----------------------------------------------------------------------------

function assert(condition, message) {
    if (!condition) {
        throw new Error(`Assertion failed: ${message}`);
    }
}

function validateTopN() {
    const result = topNPerGroup(sales, "region", "amount", 2);
    const counts = new Map();

    for (const row of result) {
        counts.set(
            row.region,
            (counts.get(row.region) || 0) + 1
        );
    }

    assert(counts.get("North") === 2, "North should contain two rows");
    assert(counts.get("South") === 2, "South should contain two rows");
    assert(counts.get("West") === 2, "West should contain two rows");
}

function validateDeduplication() {
    const result = deduplicateKeepNewest(
        employees,
        employee => employee.email,
        "updatedAt"
    );

    const emails = result.map(employee => employee.email);

    assert(
        new Set(emails).size === emails.length,
        "Deduplicated email values must be unique"
    );

    const arjun = result.find(
        employee => employee.email === "arjun@example.com"
    );

    assert(
        arjun.salary === 95000,
        "The newest Arjun record should be retained"
    );
}

function validatePivot() {
    const result = pivotSales(sales, products);
    const north = result.find(row => row.region === "North");

    assert(north.Laptop === 3600, "North laptop sales");
    assert(north.Phone === 1700, "North phone sales");
    assert(north.Tablet === 600, "North tablet sales");
}

function demonstrateEdgeCases() {
    const tiedRows = [
        { saleId: 1, region: "X", amount: 100 },
        { saleId: 2, region: "X", amount: 100 },
        { saleId: 3, region: "X", amount: 90 }
    ];

    const exactTopTwo = topNPerGroup(
        tiedRows,
        "region",
        "amount",
        2
    );

    const tiedTopTwo = topNWithTies(
        tiedRows,
        "region",
        "amount",
        1
    );

    assert(
        exactTopTwo.length === 2,
        "ROW_NUMBER semantics should return exactly two rows"
    );

    assert(
        tiedTopTwo.length === 2,
        "RANK semantics should return both tied first-place rows"
    );

    try {
        topNPerGroup(sales, "region", "amount", 0);
        throw new Error("Expected invalid N to fail.");
    } catch (error) {
        assert(
            error instanceof RangeError,
            "Invalid N should produce RangeError"
        );
    }
}

validateTopN();
validateDeduplication();
validatePivot();
demonstrateEdgeCases();

console.log("\nAll JavaScript analytical tests passed.");
