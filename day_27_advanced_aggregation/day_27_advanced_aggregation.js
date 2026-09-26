/*
 * Advanced SQL Aggregation: GROUPING SETS, ROLLUP, and CUBE
 * ===========================================================
 *
 * This file complements the Python implementation by emphasizing:
 *   - representation of grouping sets as JavaScript data structures
 *   - generation of ROLLUP and CUBE grouping sets
 *   - multidimensional aggregation
 *   - subtotal metadata
 *   - SQL generation
 *   - validation
 *   - edge cases
 *   - asynchronous execution patterns
 *   - performance measurement
 *
 * The program uses only standard JavaScript and can run in Node.js.
 *
 * GROUPING SETS, ROLLUP, and CUBE are SQL features, so this file models
 * their semantics in JavaScript and generates valid SQL statements.
 * Actual SQL execution requires a database driver and database system
 * supporting these features.
 */

"use strict";


// ============================================================================
// 1. SAMPLE DATA
// ============================================================================

const sales = [
    { id: 1, region: "North", country: "India", channel: "Online", category: "Electronics", revenue: 1200, quantity: 3 },
    { id: 2, region: "North", country: "India", channel: "Retail", category: "Electronics", revenue: 800, quantity: 2 },
    { id: 3, region: "North", country: "India", channel: "Online", category: "Furniture", revenue: 1500, quantity: 1 },
    { id: 4, region: "North", country: "Nepal", channel: "Online", category: "Electronics", revenue: 700, quantity: 2 },
    { id: 5, region: "South", country: "India", channel: "Online", category: "Electronics", revenue: 1800, quantity: 4 },
    { id: 6, region: "South", country: "India", channel: "Retail", category: "Furniture", revenue: 2200, quantity: 2 },
    { id: 7, region: "South", country: "India", channel: "Online", category: "Furniture", revenue: 1100, quantity: 1 },
    { id: 8, region: "South", country: "Sri Lanka", channel: "Retail", category: "Electronics", revenue: 900, quantity: 2 },
    { id: 9, region: "West", country: "India", channel: "Online", category: "Electronics", revenue: 2500, quantity: 5 },
    { id: 10, region: "West", country: "India", channel: "Retail", category: "Furniture", revenue: 1700, quantity: 2 },
    { id: 11, region: "West", country: "Pakistan", channel: "Online", category: "Furniture", revenue: 1000, quantity: 1 },
    { id: 12, region: "East", country: "India", channel: "Online", category: "Electronics", revenue: 1300, quantity: 3 },
    { id: 13, region: "East", country: "India", channel: "Retail", category: "Furniture", revenue: 1600, quantity: 2 },
    { id: 14, region: "East", country: "Bangladesh", channel: "Online", category: "Electronics", revenue: 600, quantity: 2 }
];


// ============================================================================
// 2. VALIDATION
// ============================================================================

function validateSales(rows) {
    if (!Array.isArray(rows)) {
        throw new TypeError("Sales data must be an array.");
    }

    const requiredFields = [
        "id",
        "region",
        "country",
        "channel",
        "category",
        "revenue",
        "quantity"
    ];

    rows.forEach((row, index) => {
        if (row === null || typeof row !== "object") {
            throw new TypeError(`Row ${index} must be an object.`);
        }

        for (const field of requiredFields) {
            if (!(field in row)) {
                throw new Error(`Row ${index} is missing '${field}'.`);
            }
        }

        if (!Number.isFinite(row.revenue)) {
            throw new TypeError(`Row ${index} has an invalid revenue.`);
        }

        if (!Number.isInteger(row.quantity) || row.quantity < 0) {
            throw new TypeError(`Row ${index} has an invalid quantity.`);
        }
    });
}

validateSales(sales);


// ============================================================================
// 3. BASIC GROUP BY
// ============================================================================

function groupBy(rows, dimensions) {
    if (!Array.isArray(dimensions) || dimensions.length === 0) {
        throw new Error("groupBy requires at least one dimension.");
    }

    const groups = new Map();

    for (const row of rows) {
        const key = JSON.stringify(
            dimensions.map((dimension) => row[dimension])
        );

        if (!groups.has(key)) {
            groups.set(key, {
                dimensions: Object.fromEntries(
                    dimensions.map((dimension) => [dimension, row[dimension]])
                ),
                revenue: 0,
                quantity: 0,
                orders: 0
            });
        }

        const aggregate = groups.get(key);
        aggregate.revenue += row.revenue;
        aggregate.quantity += row.quantity;
        aggregate.orders += 1;
    }

    return [...groups.values()];
}

console.log("\n=== BASIC GROUP BY region ===");
console.table(groupBy(sales, ["region"]));


// ============================================================================
// 4. ONE GROUPING SET
// ============================================================================

function aggregateGroupingSet(rows, dimensions) {
    const groups = new Map();

    for (const row of rows) {
        /*
         * JSON.stringify gives us a deterministic composite key for this
         * educational implementation.
         *
         * Production systems may use more specialized key representations
         * when very large data sets are processed.
         */
        const values = dimensions.map((dimension) => row[dimension]);
        const key = JSON.stringify(values);

        if (!groups.has(key)) {
            const dimensionsObject = {};

            for (const dimension of dimensions) {
                dimensionsObject[dimension] = row[dimension];
            }

            groups.set(key, {
                ...dimensionsObject,
                revenue: 0,
                quantity: 0,
                orders: 0
            });
        }

        const aggregate = groups.get(key);
        aggregate.revenue += row.revenue;
        aggregate.quantity += row.quantity;
        aggregate.orders += 1;
    }

    return [...groups.values()];
}


// ============================================================================
// 5. GROUPING SETS
// ============================================================================

function groupingSets(rows, sets) {
    if (!Array.isArray(sets)) {
        throw new TypeError("Grouping sets must be an array.");
    }

    const result = [];

    for (const dimensions of sets) {
        const aggregateRows = aggregateGroupingSet(rows, dimensions);

        for (const row of aggregateRows) {
            /*
             * A SQL subtotal has NULL for dimensions that are absent from
             * the current grouping set.
             */
            const completeRow = { ...row };

            for (const dimension of ["region", "channel", "category"]) {
                if (!dimensions.includes(dimension)) {
                    completeRow[dimension] = null;
                }
            }

            completeRow.groupingSet = dimensions.length === 0
                ? "()"
                : `(${dimensions.join(", ")})`;

            result.push(completeRow);
        }
    }

    return result;
}

const selectedGroupingSets = [
    ["region", "category"],
    ["region"],
    ["category"],
    []
];

console.log("\n=== GROUPING SETS ===");
console.table(groupingSets(sales, selectedGroupingSets));


// ============================================================================
// 6. ROLLUP
// ============================================================================

function rollupSets(dimensions) {
    if (!Array.isArray(dimensions)) {
        throw new TypeError("ROLLUP dimensions must be an array.");
    }

    /*
     * ROLLUP(a,b,c) means:
     *
     *   (a,b,c)
     *   (a,b)
     *   (a)
     *   ()
     */
    const sets = [];

    for (let size = dimensions.length; size >= 0; size--) {
        sets.push(dimensions.slice(0, size));
    }

    return sets;
}

const rollupDimensions = ["region", "channel", "category"];

console.log("\n=== ROLLUP SETS ===");
console.table(rollupSets(rollupDimensions));

console.log("\n=== ROLLUP AGGREGATION ===");
console.table(
    groupingSets(sales, rollupSets(rollupDimensions))
);


// ============================================================================
// 7. CUBE
// ============================================================================

function cubeSets(dimensions) {
    if (!Array.isArray(dimensions)) {
        throw new TypeError("CUBE dimensions must be an array.");
    }

    /*
     * CUBE generates every subset of the dimensions.
     *
     * For n dimensions:
     *
     *     number of grouping sets = 2^n
     *
     * For three dimensions:
     *
     *     (a,b,c)
     *     (a,b)
     *     (a,c)
     *     (b,c)
     *     (a)
     *     (b)
     *     (c)
     *     ()
     */
    const result = [];
    const numberOfCombinations = 2 ** dimensions.length;

    for (let mask = 0; mask < numberOfCombinations; mask++) {
        const groupingSet = [];

        for (let index = 0; index < dimensions.length; index++) {
            if ((mask & (1 << index)) !== 0) {
                groupingSet.push(dimensions[index]);
            }
        }

        result.push(groupingSet);
    }

    /*
     * Detailed grouping first makes the console output easier to read.
     */
    return result.sort(
        (left, right) => right.length - left.length
    );
}

const cubeGroupingSets = cubeSets(rollupDimensions);

console.log("\n=== CUBE SETS ===");
console.table(cubeGroupingSets);

console.log("\n=== FIRST CUBE ROWS ===");
console.table(
    groupingSets(sales, cubeGroupingSets).slice(0, 25)
);


// ============================================================================
// 8. GROUPING()
// ============================================================================

function grouping(dimension, groupingSet) {
    /*
     * SQL GROUPING(column):
     *
     *     0 -> dimension participates in this grouping level
     *     1 -> dimension was aggregated away
     */
    return groupingSet.includes(dimension) ? 0 : 1;
}

function groupingId(dimensions, groupingSet) {
    /*
     * This models the common bit-mask concept behind GROUPING_ID.
     *
     * Exact bit ordering should be verified against the target DBMS.
     */
    return dimensions.reduce(
        (id, dimension) => (
            (id << 1) | grouping(dimension, groupingSet)
        ),
        0
    );
}

function addGroupingMetadata(rows, dimensions, sets) {
    const output = [];

    for (const groupingSet of sets) {
        const aggregateRows = aggregateGroupingSet(sales, groupingSet);

        for (const aggregate of aggregateRows) {
            const row = {
                region: aggregate.region ?? null,
                channel: aggregate.channel ?? null,
                category: aggregate.category ?? null,
                revenue: aggregate.revenue
            };

            for (const dimension of dimensions) {
                row[`GROUPING(${dimension})`] =
                    grouping(dimension, groupingSet);
            }

            row.GROUPING_ID = groupingId(dimensions, groupingSet);
            row.groupingSet = groupingSet.length
                ? groupingSet.join(", ")
                : "()";

            output.push(row);
        }
    }

    return output;
}

console.log("\n=== GROUPING METADATA ===");
console.table(
    addGroupingMetadata(
        sales,
        rollupDimensions,
        rollupSets(rollupDimensions)
    )
);


// ============================================================================
// 9. LABELING SUBTOTALS SAFELY
// ============================================================================

function labelAggregationRow(row) {
    /*
     * Using only:
     *
     *     row.region ?? "ALL REGIONS"
     *
     * can be incorrect when the original source data itself contains NULL.
     *
     * GROUPING() metadata provides the semantic distinction.
     */
    return {
        region:
            row["GROUPING(region)"] === 1
                ? "ALL REGIONS"
                : row.region,

        channel:
            row["GROUPING(channel)"] === 1
                ? "ALL CHANNELS"
                : row.channel,

        category:
            row["GROUPING(category)"] === 1
                ? "ALL CATEGORIES"
                : row.category,

        revenue: row.revenue
    };
}

const metadata = addGroupingMetadata(
    sales,
    rollupDimensions,
    rollupSets(rollupDimensions)
);

console.log("\n=== LABELED SUBTOTALS ===");
console.table(metadata.map(labelAggregationRow));


// ============================================================================
// 10. HAVING-LIKE FILTER
// ============================================================================

function havingMinimumRevenue(rows, minimumRevenue) {
    if (!Number.isFinite(minimumRevenue)) {
        throw new TypeError("Minimum revenue must be numeric.");
    }

    /*
     * This represents HAVING because the aggregate has already been
     * calculated.
     */
    return rows.filter((row) => row.revenue >= minimumRevenue);
}

console.log("\n=== HAVING revenue >= 3000 ===");
console.table(
    havingMinimumRevenue(
        groupingSets(sales, selectedGroupingSets),
        3000
    )
);


// ============================================================================
// 11. WHERE VS HAVING
// ============================================================================

function whereRevenueAtLeast(rows, minimumRevenue) {
    /*
     * WHERE conceptually operates before GROUP BY.
     */
    return rows.filter((row) => row.revenue >= minimumRevenue);
}

const highValueSourceRows = whereRevenueAtLeast(sales, 1000);

console.log("\n=== WHERE revenue >= 1000, THEN GROUP ===");
console.table(
    groupBy(highValueSourceRows, ["region"])
);

console.log("\n=== GROUP FIRST, THEN HAVING total >= 3000 ===");
console.table(
    havingMinimumRevenue(
        groupBy(sales, ["region"]),
        3000
    )
);


// ============================================================================
// 12. SQL GENERATION
// ============================================================================

function quoteIdentifier(identifier) {
    /*
     * SQL identifiers cannot safely be interpolated from arbitrary input.
     * This simple whitelist-based validator prevents obvious identifier
     * injection in generated educational SQL.
     */
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(identifier)) {
        throw new Error(`Invalid SQL identifier: ${identifier}`);
    }

    return identifier;
}

function sqlColumnList(dimensions) {
    return dimensions.map(quoteIdentifier).join(", ");
}

function groupingSetToSql(dimensions) {
    return dimensions.length === 0
        ? "()"
        : `(${sqlColumnList(dimensions)})`;
}

function buildGroupingSetsQuery(tableName, sets) {
    const safeTable = quoteIdentifier(tableName);

    const allDimensions = [
        ...new Set(sets.flat())
    ];

    const selectDimensions = allDimensions.map(
        (dimension) => quoteIdentifier(dimension)
    );

    const groupingSetSql = sets
        .map(groupingSetToSql)
        .join(",\n            ");

    return `
SELECT
    ${selectDimensions.join(",\n    ")}${selectDimensions.length ? "," : ""}
    SUM(revenue) AS total_revenue,
    SUM(quantity) AS total_quantity,
    COUNT(*) AS order_count
FROM ${safeTable}
GROUP BY GROUPING SETS (
    ${groupingSetSql}
)
ORDER BY total_revenue DESC;
`.trim();
}

function buildRollupQuery(tableName, dimensions) {
    const safeTable = quoteIdentifier(tableName);
    const safeDimensions = sqlColumnList(dimensions);

    return `
SELECT
    ${safeDimensions},
    SUM(revenue) AS total_revenue,
    GROUPING_ID(${safeDimensions}) AS grouping_id
FROM ${safeTable}
GROUP BY ROLLUP(${safeDimensions})
ORDER BY total_revenue DESC;
`.trim();
}

function buildCubeQuery(tableName, dimensions) {
    const safeTable = quoteIdentifier(tableName);
    const safeDimensions = sqlColumnList(dimensions);

    return `
SELECT
    ${safeDimensions},
    SUM(revenue) AS total_revenue,
    GROUPING_ID(${safeDimensions}) AS grouping_id
FROM ${safeTable}
GROUP BY CUBE(${safeDimensions})
ORDER BY total_revenue DESC;
`.trim();
}

console.log("\n=== GENERATED GROUPING SETS SQL ===");
console.log(
    buildGroupingSetsQuery("sales", selectedGroupingSets)
);

console.log("\n=== GENERATED ROLLUP SQL ===");
console.log(
    buildRollupQuery("sales", rollupDimensions)
);

console.log("\n=== GENERATED CUBE SQL ===");
console.log(
    buildCubeQuery("sales", rollupDimensions)
);


// ============================================================================
// 13. DIMENSIONALITY VALIDATION
// ============================================================================

function validateCubeSize(numberOfDimensions, maximumGroupingSets = 1024) {
    if (!Number.isInteger(numberOfDimensions) || numberOfDimensions < 0) {
        throw new RangeError("Dimension count must be a non-negative integer.");
    }

    const groupingSetCount = 2 ** numberOfDimensions;

    if (groupingSetCount > maximumGroupingSets) {
        throw new Error(
            `CUBE would produce ${groupingSetCount} grouping sets, ` +
            `exceeding the configured limit of ${maximumGroupingSets}.`
        );
    }

    return groupingSetCount;
}

console.log("\n=== CUBE SIZE VALIDATION ===");

for (const dimensionCount of [1, 2, 3, 5, 10]) {
    console.log(
        `${dimensionCount} dimensions -> ` +
        `${validateCubeSize(dimensionCount)} grouping sets`
    );
}

try {
    validateCubeSize(15, 1024);
} catch (error) {
    console.log(`Expected protection: ${error.message}`);
}


// ============================================================================
// 14. PERFORMANCE MEASUREMENT
// ============================================================================

function measure(label, operation) {
    const start = performance.now();
    const result = operation();
    const elapsed = performance.now() - start;

    console.log(
        `${label}: ${elapsed.toFixed(3)} ms`
    );

    return result;
}

measure(
    "ROLLUP reference aggregation",
    () => groupingSets(sales, rollupSets(rollupDimensions))
);

measure(
    "CUBE reference aggregation",
    () => groupingSets(sales, cubeSets(rollupDimensions))
);


// ============================================================================
// 15. ASYNCHRONOUS DATABASE-STYLE API
// ============================================================================

class AggregationService {
    constructor(rows) {
        validateSales(rows);
        this.rows = rows;
    }

    async executeRollup(dimensions) {
        /*
         * A real application could replace this implementation with:
         *
         *     await database.query(sql)
         *
         * Keeping the method asynchronous makes the application boundary
         * resemble real database code without requiring an external driver.
         */
        return Promise.resolve(
            groupingSets(this.rows, rollupSets(dimensions))
        );
    }

    async executeCube(dimensions) {
        return Promise.resolve(
            groupingSets(this.rows, cubeSets(dimensions))
        );
    }

    async executeGroupingSets(sets) {
        return Promise.resolve(
            groupingSets(this.rows, sets)
        );
    }
}

async function demonstrateService() {
    const service = new AggregationService(sales);

    const regionalSummary = await service.executeRollup(
        ["region", "channel"]
    );

    console.log("\n=== ASYNCHRONOUS SERVICE RESULT ===");
    console.table(regionalSummary);
}


// ============================================================================
// 16. EMPTY DATA EDGE CASE
// ============================================================================

function demonstrateEmptyData() {
    const empty = [];

    console.log("\n=== EMPTY DATA ===");
    console.table(
        groupingSets(
            empty,
            [
                ["region"],
                []
            ]
        )
    );

    /*
     * This reference implementation returns no rows for an empty input.
     *
     * SQL aggregate behavior, particularly for GROUP BY (), can differ from
     * this simplified JavaScript model. COUNT, SUM, AVG, MIN, and MAX also
     * have different empty-set semantics. Always test the target DBMS.
     */
}


// ============================================================================
// 17. NULL EDGE CASE
// ============================================================================

function demonstrateNullData() {
    const rows = [
        {
            id: 100,
            region: null,
            country: "India",
            channel: "Online",
            category: "Electronics",
            revenue: 500,
            quantity: 1
        },
        {
            id: 101,
            region: "North",
            country: "India",
            channel: "Online",
            category: "Electronics",
            revenue: 700,
            quantity: 1
        }
    ];

    console.log("\n=== SOURCE DATA CONTAINING NULL ===");
    console.table(groupBy(rows, ["region"]));

    /*
     * This demonstrates why SQL GROUPING() is important.
     *
     * A displayed NULL may represent:
     *   1. a real NULL from source data
     *   2. a subtotal generated by ROLLUP/CUBE
     */
}


// ============================================================================
// 18. COMPARISON
// ============================================================================

function printConceptualComparison() {
    console.log(`
=== CONCEPTUAL COMPARISON ===

GROUP BY
    One grouping level.

GROUPING SETS
    Explicitly selected grouping levels.

ROLLUP(a,b,c)
    (a,b,c)
    (a,b)
    (a)
    ()

CUBE(a,b,c)
    Every subset of a,b,c.
    Number of grouping sets = 2^3 = 8.

ROLLUP is hierarchical.
CUBE is multidimensional.
GROUPING SETS is explicitly controlled.
`);
}

printConceptualComparison();


// ============================================================================
// 19. EXECUTE ASYNC EXAMPLES
// ============================================================================

(async () => {
    await demonstrateService();
    demonstrateEmptyData();
    demonstrateNullData();
})().catch((error) => {
    /*
     * A top-level error boundary prevents an asynchronous failure from
     * becoming an unexplained unhandled rejection.
     */
    console.error("Aggregation demonstration failed:", error.message);
});
