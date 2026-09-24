/*
 * Window Functions II: ROW_NUMBER, RANK, DENSE_RANK, NTILE
 *
 * This standalone JavaScript program models SQL ranking window functions
 * without requiring a database or external npm package.
 *
 * SQL concepts demonstrated:
 *
 *   ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)
 *   RANK()       OVER (PARTITION BY ... ORDER BY ...)
 *   DENSE_RANK() OVER (PARTITION BY ... ORDER BY ...)
 *   NTILE(n)     OVER (PARTITION BY ... ORDER BY ...)
 *
 * The implementations make the mechanics explicit and add JavaScript
 * specific examples involving immutable-style transformations, validation,
 * classes, Maps, stable ordering, and performance measurement.
 */


"use strict";


// ============================================================================
// BASIC DATA
// ============================================================================

const employees = [
    { employeeId: 101, name: "Asha", department: "Engineering", salary: 125000 },
    { employeeId: 102, name: "Bharat", department: "Engineering", salary: 110000 },
    { employeeId: 103, name: "Chen", department: "Engineering", salary: 110000 },
    { employeeId: 104, name: "Divya", department: "Engineering", salary: 95000 },
    { employeeId: 105, name: "Ethan", department: "Engineering", salary: 85000 },
    { employeeId: 201, name: "Farah", department: "Sales", salary: 115000 },
    { employeeId: 202, name: "Gaurav", department: "Sales", salary: 100000 },
    { employeeId: 203, name: "Hana", department: "Sales", salary: 100000 },
    { employeeId: 204, name: "Ivan", department: "Sales", salary: 90000 },
    { employeeId: 205, name: "Julia", department: "Sales", salary: 75000 },
    { employeeId: 301, name: "Kabir", department: "HR", salary: 105000 },
    { employeeId: 302, name: "Leena", department: "HR", salary: 90000 },
    { employeeId: 303, name: "Manoj", department: "HR", salary: 90000 },
    { employeeId: 304, name: "Nisha", department: "HR", salary: 70000 }
];


function printTable(rows, title = "") {
    if (title) {
        console.log(`\n${title}`);
    }

    if (rows.length === 0) {
        console.log("(no rows)");
        return;
    }

    const columns = Object.keys(rows[0]);
    const widths = Object.fromEntries(
        columns.map(column => [
            column,
            Math.max(
                column.length,
                ...rows.map(row => String(row[column] ?? "").length)
            )
        ])
    );

    const header = columns
        .map(column => column.padEnd(widths[column]))
        .join(" | ");

    const separator = columns
        .map(column => "-".repeat(widths[column]))
        .join("-+-");

    console.log(header);
    console.log(separator);

    for (const row of rows) {
        console.log(
            columns
                .map(column => String(row[column] ?? "").padEnd(widths[column]))
                .join(" | ")
        );
    }
}

printTable(employees, "Original employee data");


// ============================================================================
// PARTITIONING
// ============================================================================

function partitionRows(rows, partitionColumns = []) {
    /*
     * JavaScript Map is useful here because each partition can be associated
     * with a composite key. JSON serialization gives us a simple key for
     * primitive values used in this educational example.
     */
    if (partitionColumns.length === 0) {
        return new Map([["__ALL_ROWS__", [...rows]]]);
    }

    const partitions = new Map();

    for (const row of rows) {
        const key = JSON.stringify(
            partitionColumns.map(column => row[column])
        );

        if (!partitions.has(key)) {
            partitions.set(key, []);
        }

        partitions.get(key).push(row);
    }

    return partitions;
}


function compareValues(left, right, ascending = true) {
    if (left === right) {
        return 0;
    }

    if (left === null || left === undefined) {
        return ascending ? -1 : 1;
    }

    if (right === null || right === undefined) {
        return ascending ? 1 : -1;
    }

    const result = left < right ? -1 : 1;
    return ascending ? result : -result;
}


function compareRows(left, right, orderColumns) {
    for (const { column, ascending = true } of orderColumns) {
        const comparison = compareValues(
            left[column],
            right[column],
            ascending
        );

        if (comparison !== 0) {
            return comparison;
        }
    }

    return 0;
}


function sortPartition(rows, orderColumns) {
    /*
     * toSorted() is used when available in modern JavaScript environments.
     * The fallback copies the array before calling sort(), preventing
     * accidental mutation of the original partition.
     */
    const copy = [...rows];

    if (typeof copy.toSorted === "function") {
        return copy.toSorted(
            (left, right) => compareRows(left, right, orderColumns)
        );
    }

    return copy.sort(
        (left, right) => compareRows(left, right, orderColumns)
    );
}


function orderKey(row, orderColumns) {
    return JSON.stringify(
        orderColumns.map(({ column }) => row[column])
    );
}


// ============================================================================
// ROW_NUMBER
// ============================================================================

function rowNumber(
    rows,
    partitionColumns,
    orderColumns,
    outputColumn = "rowNumber"
) {
    /*
     * Equivalent SQL:
     *
     * ROW_NUMBER() OVER (
     *     PARTITION BY department
     *     ORDER BY salary DESC, employeeId ASC
     * )
     *
     * Every row receives a distinct position.
     */
    const result = [];

    for (const partition of partitionRows(rows, partitionColumns).values()) {
        const ordered = sortPartition(partition, orderColumns);

        ordered.forEach((row, index) => {
            result.push({
                ...row,
                [outputColumn]: index + 1
            });
        });
    }

    return result;
}

printTable(
    rowNumber(
        employees,
        ["department"],
        [
            { column: "salary", ascending: false },
            { column: "employeeId", ascending: true }
        ]
    ),
    "ROW_NUMBER"
);


// ============================================================================
// RANK
// ============================================================================

function rankRows(
    rows,
    partitionColumns,
    orderColumns,
    outputColumn = "rank"
) {
    /*
     * RANK shares a position for equal ordering keys.
     *
     * Example:
     *
     * values: 100, 100, 90, 80
     * rank:     1,   1,  3,  4
     */
    const result = [];

    for (const partition of partitionRows(rows, partitionColumns).values()) {
        const ordered = sortPartition(partition, orderColumns);

        let previousKey = null;
        let currentRank = 0;

        ordered.forEach((row, index) => {
            const currentKey = orderKey(row, orderColumns);

            if (index === 0) {
                currentRank = 1;
            } else if (currentKey !== previousKey) {
                currentRank = index + 1;
            }

            result.push({
                ...row,
                [outputColumn]: currentRank
            });

            previousKey = currentKey;
        });
    }

    return result;
}

printTable(
    rankRows(
        employees,
        ["department"],
        [{ column: "salary", ascending: false }]
    ),
    "RANK"
);


// ============================================================================
// DENSE_RANK
// ============================================================================

function denseRankRows(
    rows,
    partitionColumns,
    orderColumns,
    outputColumn = "denseRank"
) {
    /*
     * DENSE_RANK also shares positions for ties, but does not leave gaps.
     *
     * values:      100, 100, 90, 80
     * dense rank:    1,   1,  2,  3
     */
    const result = [];

    for (const partition of partitionRows(rows, partitionColumns).values()) {
        const ordered = sortPartition(partition, orderColumns);

        let previousKey = null;
        let currentRank = 0;

        for (const row of ordered) {
            const currentKey = orderKey(row, orderColumns);

            if (currentRank === 0 || currentKey !== previousKey) {
                currentRank += 1;
            }

            result.push({
                ...row,
                [outputColumn]: currentRank
            });

            previousKey = currentKey;
        }
    }

    return result;
}

printTable(
    denseRankRows(
        employees,
        ["department"],
        [{ column: "salary", ascending: false }]
    ),
    "DENSE_RANK"
);


// ============================================================================
// NTILE
// ============================================================================

function validateBucketCount(bucketCount) {
    if (!Number.isInteger(bucketCount) || bucketCount <= 0) {
        throw new RangeError(
            "NTILE requires a positive integer bucket count."
        );
    }
}


function ntileRows(
    rows,
    bucketCount,
    partitionColumns,
    orderColumns,
    outputColumn = "ntile"
) {
    /*
     * SQL:
     *
     * NTILE(4) OVER (
     *     PARTITION BY department
     *     ORDER BY salary DESC
     * )
     *
     * The rows are divided into approximately equal buckets.
     */
    validateBucketCount(bucketCount);

    const result = [];

    for (const partition of partitionRows(rows, partitionColumns).values()) {
        const ordered = sortPartition(partition, orderColumns);
        const rowCount = ordered.length;

        if (rowCount === 0) {
            continue;
        }

        const baseSize = Math.floor(rowCount / bucketCount);
        const remainder = rowCount % bucketCount;

        ordered.forEach((row, index) => {
            let bucket;

            if (index < (baseSize + 1) * remainder) {
                bucket = Math.floor(index / (baseSize + 1)) + 1;
            } else if (baseSize === 0) {
                bucket = remainder;
            } else {
                bucket =
                    remainder +
                    Math.floor(
                        (index - (baseSize + 1) * remainder) / baseSize
                    ) +
                    1;
            }

            result.push({
                ...row,
                [outputColumn]: bucket
            });
        });
    }

    return result;
}

printTable(
    ntileRows(
        employees,
        4,
        ["department"],
        [
            { column: "salary", ascending: false },
            { column: "employeeId", ascending: true }
        ]
    ),
    "NTILE(4)"
);


// ============================================================================
// ALL FOUR FUNCTIONS
// ============================================================================

function combineRankings(rows) {
    const specifications = {
        rowNumber: rowNumber(
            rows,
            ["department"],
            [
                { column: "salary", ascending: false },
                { column: "employeeId", ascending: true }
            ]
        ),
        rank: rankRows(
            rows,
            ["department"],
            [{ column: "salary", ascending: false }]
        ),
        denseRank: denseRankRows(
            rows,
            ["department"],
            [{ column: "salary", ascending: false }]
        ),
        ntile: ntileRows(
            rows,
            4,
            ["department"],
            [
                { column: "salary", ascending: false },
                { column: "employeeId", ascending: true }
            ]
        )
    };

    const byId = new Map();

    for (const row of specifications.rowNumber) {
        byId.set(row.employeeId, {
            employeeId: row.employeeId,
            name: row.name,
            department: row.department,
            salary: row.salary,
            ROW_NUMBER: row.rowNumber
        });
    }

    for (const row of specifications.rank) {
        byId.get(row.employeeId).RANK = row.rank;
    }

    for (const row of specifications.denseRank) {
        byId.get(row.employeeId).DENSE_RANK = row.denseRank;
    }

    for (const row of specifications.ntile) {
        byId.get(row.employeeId)["NTILE(4)"] = row.ntile;
    }

    return [...byId.values()];
}

printTable(
    combineRankings(employees),
    "All four ranking functions"
);


// ============================================================================
// TOP-N PER GROUP
// ============================================================================

function topNPerGroup(rows, n) {
    /*
     * ROW_NUMBER is appropriate when exactly N physical rows are required
     * from every group.
     */
    if (!Number.isInteger(n) || n < 1) {
        throw new RangeError("n must be a positive integer.");
    }

    return rowNumber(
        rows,
        ["department"],
        [
            { column: "salary", ascending: false },
            { column: "employeeId", ascending: true }
        ],
        "rn"
    ).filter(row => row.rn <= n);
}

printTable(
    topNPerGroup(employees, 2),
    "Top 2 employees per department"
);


// ============================================================================
// TOP-N WITH TIES
// ============================================================================

function topNWithTies(rows, n) {
    /*
     * RANK is useful when all rows sharing the Nth position should survive.
     */
    if (!Number.isInteger(n) || n < 1) {
        throw new RangeError("n must be a positive integer.");
    }

    return rankRows(
        rows,
        ["department"],
        [{ column: "salary", ascending: false }],
        "salaryRank"
    ).filter(row => row.salaryRank <= n);
}

printTable(
    topNWithTies(employees, 2),
    "Top 2 salary positions per department, including ties"
);


// ============================================================================
// SECOND-HIGHEST DISTINCT VALUE
// ============================================================================

function secondHighestDistinctSalary(rows) {
    /*
     * DENSE_RANK treats equal salary values as one distinct level.
     */
    return denseRankRows(
        rows,
        ["department"],
        [{ column: "salary", ascending: false }],
        "salaryLevel"
    ).filter(row => row.salaryLevel === 2);
}

printTable(
    secondHighestDistinctSalary(employees),
    "Second-highest distinct salary per department"
);


// ============================================================================
// DEDUPLICATION
// ============================================================================

const customerRecords = [
    {
        recordId: 1,
        customerId: "C100",
        updatedAt: "2026-09-20",
        value: "old"
    },
    {
        recordId: 2,
        customerId: "C100",
        updatedAt: "2026-09-23",
        value: "new"
    },
    {
        recordId: 3,
        customerId: "C200",
        updatedAt: "2026-09-21",
        value: "only"
    },
    {
        recordId: 4,
        customerId: "C300",
        updatedAt: "2026-09-19",
        value: "old"
    },
    {
        recordId: 5,
        customerId: "C300",
        updatedAt: "2026-09-22",
        value: "latest"
    }
];

function latestRecordPerCustomer(records) {
    /*
     * Equivalent concept:
     *
     * ROW_NUMBER() OVER (
     *     PARTITION BY customer_id
     *     ORDER BY updated_at DESC, record_id DESC
     * )
     *
     * Keep rn = 1.
     */
    return rowNumber(
        records,
        ["customerId"],
        [
            { column: "updatedAt", ascending: false },
            { column: "recordId", ascending: false }
        ],
        "rn"
    ).filter(row => row.rn === 1);
}

printTable(
    latestRecordPerCustomer(customerRecords),
    "Latest record per customer"
);


// ============================================================================
// NTILE DISTRIBUTION
// ============================================================================

function ntileDistribution(rowCount, bucketCount) {
    validateBucketCount(bucketCount);

    if (rowCount <= 0) {
        return [];
    }

    const baseSize = Math.floor(rowCount / bucketCount);
    const remainder = rowCount % bucketCount;

    return Array.from(
        { length: bucketCount },
        (_, index) => baseSize + (index < remainder ? 1 : 0)
    );
}

console.log("\nNTILE DISTRIBUTION");

for (const [rowCount, bucketCount] of [
    [10, 4],
    [11, 4],
    [12, 4],
    [5, 10],
    [3, 2]
]) {
    const distribution = ntileDistribution(rowCount, bucketCount);
    console.log(
        `rows=${rowCount}, buckets=${bucketCount}, ` +
        `distribution=[${distribution.join(", ")}]`
    );
}


// ============================================================================
// TIE BEHAVIOR
// ============================================================================

const tieData = [
    { employeeId: 1, name: "Player 1", department: "Competition", salary: 100 },
    { employeeId: 2, name: "Player 2", department: "Competition", salary: 100 },
    { employeeId: 3, name: "Player 3", department: "Competition", salary: 90 },
    { employeeId: 4, name: "Player 4", department: "Competition", salary: 90 },
    { employeeId: 5, name: "Player 5", department: "Competition", salary: 80 }
];

printTable(
    combineRankings(tieData),
    "Tie comparison"
);


// ============================================================================
// IMPORTANT ORDERING DISTINCTION
// ============================================================================

console.log(`
ORDER BY semantics:

RANK with ORDER BY salary DESC
    Equal salaries tie.

RANK with ORDER BY salary DESC, employeeId ASC
    A unique employeeId normally eliminates ties because the complete
    ordering key is now unique.

This is an important distinction. A secondary key can be an excellent
tie-breaker for ROW_NUMBER, but adding a unique secondary key to RANK or
DENSE_RANK changes which rows are considered equal.
`);


// ============================================================================
// REUSABLE CLASS
// ============================================================================

class WindowRankingEngine {
    /*
     * Encapsulates a window specification so that the same partitioning and
     * ordering rules can be applied consistently to multiple functions.
     */
    constructor({ partitionColumns = [], orderColumns = [] } = {}) {
        this.partitionColumns = [...partitionColumns];
        this.orderColumns = [...orderColumns];
    }

    rowNumber(rows) {
        return rowNumber(
            rows,
            this.partitionColumns,
            this.orderColumns
        );
    }

    rank(rows) {
        return rankRows(
            rows,
            this.partitionColumns,
            this.orderColumns
        );
    }

    denseRank(rows) {
        return denseRankRows(
            rows,
            this.partitionColumns,
            this.orderColumns
        );
    }

    ntile(rows, buckets) {
        return ntileRows(
            rows,
            buckets,
            this.partitionColumns,
            this.orderColumns
        );
    }
}

const engine = new WindowRankingEngine({
    partitionColumns: ["department"],
    orderColumns: [
        { column: "salary", ascending: false },
        { column: "employeeId", ascending: true }
    ]
});

printTable(
    engine.rowNumber(employees),
    "Reusable ranking engine"
);


// ============================================================================
// ASYNCHRONOUS APPLICATION-STYLE EXAMPLE
// ============================================================================

async function loadSalesData() {
    /*
     * This Promise models an asynchronous data-access operation.
     * A real application could replace it with fetch() or a database API.
     */
    return [
        { saleId: 1, region: "North", salesperson: "A", revenue: 90000 },
        { saleId: 2, region: "North", salesperson: "B", revenue: 85000 },
        { saleId: 3, region: "North", salesperson: "C", revenue: 85000 },
        { saleId: 4, region: "North", salesperson: "D", revenue: 70000 },
        { saleId: 5, region: "South", salesperson: "E", revenue: 95000 },
        { saleId: 6, region: "South", salesperson: "F", revenue: 95000 },
        { saleId: 7, region: "South", salesperson: "G", revenue: 80000 },
        { saleId: 8, region: "South", salesperson: "H", revenue: 60000 }
    ];
}


async function runSalesAnalysis() {
    const sales = await loadSalesData();

    const rankedSales = rowNumber(
        sales,
        ["region"],
        [
            { column: "revenue", ascending: false },
            { column: "saleId", ascending: true }
        ],
        "regionalPosition"
    );

    const competitionRanking = rankRows(
        sales,
        ["region"],
        [{ column: "revenue", ascending: false }],
        "competitionRank"
    );

    const salesWithBoth = rankedSales.map(row => {
        const ranked = competitionRanking.find(
            candidate => candidate.saleId === row.saleId
        );

        return {
            ...row,
            competitionRank: ranked.competitionRank
        };
    });

    printTable(
        salesWithBoth,
        "Asynchronous regional sales analysis"
    );
}


// ============================================================================
// VALIDATION AND TESTING
// ============================================================================

function assertEqual(actual, expected, message) {
    const actualText = JSON.stringify(actual);
    const expectedText = JSON.stringify(expected);

    if (actualText !== expectedText) {
        throw new Error(
            `${message}\nExpected: ${expectedText}\nActual: ${actualText}`
        );
    }
}


function runTests() {
    const data = [
        { id: 1, group: "A", value: 100 },
        { id: 2, group: "A", value: 100 },
        { id: 3, group: "A", value: 90 },
        { id: 4, group: "A", value: 80 }
    ];

    const rowNumbers = rowNumber(
        data,
        ["group"],
        [
            { column: "value", ascending: false },
            { column: "id", ascending: true }
        ]
    );

    assertEqual(
        rowNumbers.map(row => row.rowNumber),
        [1, 2, 3, 4],
        "ROW_NUMBER failed"
    );

    const ranks = rankRows(
        data,
        ["group"],
        [{ column: "value", ascending: false }]
    );

    assertEqual(
        ranks.map(row => row.rank),
        [1, 1, 3, 4],
        "RANK failed"
    );

    const denseRanks = denseRankRows(
        data,
        ["group"],
        [{ column: "value", ascending: false }]
    );

    assertEqual(
        denseRanks.map(row => row.denseRank),
        [1, 1, 2, 3],
        "DENSE_RANK failed"
    );

    const tiles = ntileRows(
        data,
        2,
        ["group"],
        [
            { column: "value", ascending: false },
            { column: "id", ascending: true }
        ]
    );

    assertEqual(
        tiles.map(row => row.ntile),
        [1, 1, 2, 2],
        "NTILE failed"
    );

    const independentGroups = [
        { id: 1, group: "A", value: 100 },
        { id: 2, group: "B", value: 100 }
    ];

    const groupRanks = rowNumber(
        independentGroups,
        ["group"],
        [{ column: "value", ascending: false }]
    );

    assertEqual(
        groupRanks.map(row => row.rowNumber),
        [1, 1],
        "PARTITION BY failed"
    );

    console.log("\nAll JavaScript ranking tests passed.");

    try {
        ntileRows(
            data,
            0,
            ["group"],
            [{ column: "value", ascending: false }]
        );

        throw new Error("Expected NTILE validation to fail.");
    } catch (error) {
        if (!(error instanceof RangeError)) {
            throw error;
        }

        console.log("NTILE validation test passed.");
    }
}


// ============================================================================
// PERFORMANCE DEMONSTRATION
// ============================================================================

function createSyntheticEmployees(count) {
    const departments = ["Engineering", "Sales", "HR", "Finance"];

    return Array.from({ length: count }, (_, index) => ({
        employeeId: index + 1,
        name: `Employee ${index + 1}`,
        department: departments[index % departments.length],
        salary: 50000 + ((index * 7919) % 100000)
    }));
}


function performanceDemo() {
    const data = createSyntheticEmployees(20000);

    const start = process.hrtime.bigint();

    const ranked = rowNumber(
        data,
        ["department"],
        [
            { column: "salary", ascending: false },
            { column: "employeeId", ascending: true }
        ]
    );

    const end = process.hrtime.bigint();

    const elapsedMilliseconds =
        Number(end - start) / 1_000_000;

    console.log(
        `\nProcessed ${ranked.length} rows with ROW_NUMBER in ` +
        `${elapsedMilliseconds.toFixed(3)} ms`
    );

    /*
     * This is an educational benchmark, not a database performance claim.
     * Database engines can exploit indexes, parallelism, specialized sorting,
     * memory management, query optimization, and physical execution plans.
     */
}

performanceDemo();


// ============================================================================
// APPLICATION DECISION GUIDE
// ============================================================================

console.log(`
FUNCTION SELECTION

ROW_NUMBER
    Use when every row needs a unique position.
    Common examples: top N per group and deterministic deduplication.

RANK
    Use when ties should share a position and gaps should remain.
    Common examples: competition-style leaderboards.

DENSE_RANK
    Use when ties should share a position but rank numbers should remain
    consecutive.
    Common examples: distinct salary or price levels.

NTILE
    Use when rows need to be divided into approximately equal groups.
    Common examples: quartiles, deciles, customer segmentation.

Central example:

Values       100, 100, 90, 80
ROW_NUMBER     1,   2,  3,  4
RANK           1,   1,  3,  4
DENSE_RANK     1,   1,  2,  3
NTILE(2)       1,   1,  2,  2
`);


runTests();

runSalesAnalysis().catch(error => {
    console.error("Sales analysis failed:", error.message);
});
