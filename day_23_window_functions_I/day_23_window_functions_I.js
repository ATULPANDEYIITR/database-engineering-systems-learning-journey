/*
 * Window Functions I | OVER, PARTITION BY, ORDER BY
 *
 * This JavaScript program complements the SQL-focused Python implementation
 * by implementing window-function ideas in ordinary JavaScript.
 *
 * JavaScript itself does not provide SQL's OVER(), PARTITION BY, or ORDER BY
 * syntax for arrays. This file therefore models the same analytical operations
 * explicitly. That makes the underlying mechanics visible:
 *
 *     1. divide rows into partitions;
 *     2. order rows within each partition;
 *     3. calculate a value using the current row and its window;
 *     4. preserve the original row instead of collapsing it.
 *
 * Runtime:
 *     Node.js 18+ recommended
 */

"use strict";

// -----------------------------------------------------------------------------
// 1. SAMPLE DATA
// -----------------------------------------------------------------------------

const employees = [
    { id: 101, name: "Aarav", department: "Engineering", salary: 95000 },
    { id: 102, name: "Diya", department: "Engineering", salary: 110000 },
    { id: 103, name: "Kabir", department: "Engineering", salary: 110000 },
    { id: 104, name: "Meera", department: "Engineering", salary: 82000 },
    { id: 105, name: "Rohan", department: "Sales", salary: 90000 },
    { id: 106, name: "Anaya", department: "Sales", salary: 105000 },
    { id: 107, name: "Vihaan", department: "Sales", salary: 105000 },
    { id: 108, name: "Ishita", department: "Sales", salary: 76000 },
    { id: 109, name: "Arjun", department: "Finance", salary: 120000 },
    { id: 110, name: "Sara", department: "Finance", salary: 98000 },
    { id: 111, name: "Neil", department: "Finance", salary: 98000 },
    { id: 112, name: "Tara", department: "Operations", salary: 88000 }
];

const sales = [
    { id: 1, employeeId: 105, date: "2026-01-02", region: "North", revenue: 1800 },
    { id: 2, employeeId: 106, date: "2026-01-03", region: "North", revenue: 2500 },
    { id: 3, employeeId: 107, date: "2026-01-03", region: "North", revenue: 900 },
    { id: 4, employeeId: 105, date: "2026-01-05", region: "North", revenue: 900 },
    { id: 5, employeeId: 106, date: "2026-01-08", region: "North", revenue: 1800 },
    { id: 6, employeeId: 107, date: "2026-01-10", region: "North", revenue: 2000 },
    { id: 7, employeeId: 108, date: "2026-01-11", region: "North", revenue: 600 },
    { id: 8, employeeId: 105, date: "2026-01-15", region: "North", revenue: 1500 },
    { id: 9, employeeId: 109, date: "2026-01-02", region: "West", revenue: 900 },
    { id: 10, employeeId: 110, date: "2026-01-04", region: "West", revenue: 2000 },
    { id: 11, employeeId: 111, date: "2026-01-04", region: "West", revenue: 1500 },
    { id: 12, employeeId: 109, date: "2026-01-07", region: "West", revenue: 1800 },
    { id: 13, employeeId: 110, date: "2026-01-12", region: "West", revenue: 1000 },
    { id: 14, employeeId: 111, date: "2026-01-14", region: "West", revenue: 2700 },
    { id: 15, employeeId: 112, date: "2026-01-03", region: "South", revenue: 1200 },
    { id: 16, employeeId: 112, date: "2026-01-09", region: "South", revenue: 1800 }
];


// -----------------------------------------------------------------------------
// 2. GENERAL HELPERS
// -----------------------------------------------------------------------------

function cloneRows(rows) {
    return rows.map(row => ({ ...row }));
}

function printTitle(title) {
    console.log("\n" + "=".repeat(80));
    console.log(title);
    console.log("=".repeat(80));
}

function printRows(rows, columns = null) {
    if (rows.length === 0) {
        console.log("(no rows)");
        return;
    }

    const selectedColumns = columns ?? Object.keys(rows[0]);

    console.table(
        rows.map(row => {
            const output = {};
            for (const column of selectedColumns) {
                output[column] = row[column];
            }
            return output;
        })
    );
}

function compareValues(a, b) {
    if (a === b) return 0;
    if (a === null || a === undefined) return 1;
    if (b === null || b === undefined) return -1;
    return a < b ? -1 : 1;
}

function composeComparators(...comparators) {
    return (a, b) => {
        for (const comparator of comparators) {
            const result = comparator(a, b);
            if (result !== 0) {
                return result;
            }
        }
        return 0;
    };
}

function ascending(selector) {
    return (a, b) => compareValues(selector(a), selector(b));
}

function descending(selector) {
    return (a, b) => -compareValues(selector(a), selector(b));
}


// -----------------------------------------------------------------------------
// 3. PARTITIONING
// -----------------------------------------------------------------------------

function partitionRows(rows, partitionSelector) {
    /*
     * This is the JavaScript equivalent of:
     *
     *     PARTITION BY department
     *
     * Each unique partition key gets its own array.
     */
    const partitions = new Map();

    for (const row of rows) {
        const key = partitionSelector(row);

        if (!partitions.has(key)) {
            partitions.set(key, []);
        }

        partitions.get(key).push(row);
    }

    return partitions;
}


// -----------------------------------------------------------------------------
// 4. A GENERAL WINDOW-APPLICATION ENGINE
// -----------------------------------------------------------------------------

function applyWindow({
    rows,
    partitionBy = () => "__ALL_ROWS__",
    orderBy = [],
    calculate
}) {
    /*
     * This helper models the core mental structure of a SQL window:
     *
     *     function(...) OVER (
     *         PARTITION BY ...
     *         ORDER BY ...
     *     )
     *
     * Important:
     * - the original rows remain in the result;
     * - each partition is processed independently;
     * - ordering affects the analytical calculation.
     */
    const result = cloneRows(rows);
    const indexById = new Map();

    result.forEach((row, index) => {
        indexById.set(row, index);
    });

    const partitions = partitionRows(result, partitionBy);

    for (const partition of partitions.values()) {
        partition.sort(
            composeComparators(...orderBy)
        );

        for (let position = 0; position < partition.length; position++) {
            const row = partition[position];

            calculate({
                row,
                partition,
                position,
                result,
                index: indexById.get(row)
            });
        }
    }

    return result;
}


// -----------------------------------------------------------------------------
// 5. COUNT OVER
// -----------------------------------------------------------------------------

function demonstrateCountOver() {
    printTitle("COUNT OVER: preserve every employee while adding department size");

    const result = applyWindow({
        rows: employees,
        partitionBy: employee => employee.department,
        calculate: ({ row }) => {
            row.departmentEmployeeCount = 0;
        }
    });

    const partitions = partitionRows(result, row => row.department);

    for (const partition of partitions.values()) {
        for (const row of partition) {
            row.departmentEmployeeCount = partition.length;
        }
    }

    printRows(result, [
        "id",
        "name",
        "department",
        "salary",
        "departmentEmployeeCount"
    ]);
}


// -----------------------------------------------------------------------------
// 6. AVG OVER
// -----------------------------------------------------------------------------

function demonstrateAverageOver() {
    printTitle("AVG OVER PARTITION: salary compared with department average");

    const result = applyWindow({
        rows: employees,
        partitionBy: employee => employee.department,
        calculate: ({ row, partition }) => {
            const average =
                partition.reduce((sum, item) => sum + item.salary, 0) /
                partition.length;

            row.departmentAverage = Number(average.toFixed(2));
            row.differenceFromAverage =
                Number((row.salary - average).toFixed(2));
        }
    });

    result.sort(
        composeComparators(
            ascending(row => row.department),
            descending(row => row.salary),
            ascending(row => row.id)
        )
    );

    printRows(result, [
        "name",
        "department",
        "salary",
        "departmentAverage",
        "differenceFromAverage"
    ]);
}


// -----------------------------------------------------------------------------
// 7. ROW_NUMBER
// -----------------------------------------------------------------------------

function demonstrateRowNumber() {
    printTitle("ROW_NUMBER: unique position within each department");

    const result = applyWindow({
        rows: employees,
        partitionBy: employee => employee.department,
        orderBy: [
            descending(employee => employee.salary),
            ascending(employee => employee.id)
        ],
        calculate: ({ row, position }) => {
            row.rowNumber = position + 1;
        }
    });

    result.sort(
        composeComparators(
            ascending(row => row.department),
            ascending(row => row.rowNumber)
        )
    );

    printRows(result, [
        "name",
        "department",
        "salary",
        "rowNumber"
    ]);
}


// -----------------------------------------------------------------------------
// 8. RANK
// -----------------------------------------------------------------------------

function demonstrateRank() {
    printTitle("RANK: equal values share a rank and gaps appear after ties");

    const result = applyWindow({
        rows: employees,
        partitionBy: employee => employee.department,
        orderBy: [
            descending(employee => employee.salary),
            ascending(employee => employee.id)
        ],
        calculate: ({ row, partition, position }) => {
            /*
             * RANK compares only the business ordering value, not the unique
             * tiebreaker used to stabilize ROW_NUMBER.
             */
            const higherSalaryCount = partition.filter(
                other => other.salary > row.salary
            ).length;

            row.rank = higherSalaryCount + 1;
            row.position = position + 1;
        }
    });

    result.sort(
        composeComparators(
            ascending(row => row.department),
            ascending(row => row.position)
        )
    );

    printRows(result, [
        "name",
        "department",
        "salary",
        "rank",
        "position"
    ]);
}


// -----------------------------------------------------------------------------
// 9. DENSE_RANK
// -----------------------------------------------------------------------------

function demonstrateDenseRank() {
    printTitle("DENSE_RANK: equal values share a rank without gaps");

    const result = applyWindow({
        rows: employees,
        partitionBy: employee => employee.department,
        orderBy: [
            descending(employee => employee.salary),
            ascending(employee => employee.id)
        ],
        calculate: ({ row, partition }) => {
            const distinctHigherSalaries = new Set(
                partition
                    .filter(other => other.salary > row.salary)
                    .map(other => other.salary)
            );

            row.denseRank = distinctHigherSalaries.size + 1;
        }
    });

    result.sort(
        composeComparators(
            ascending(row => row.department),
            ascending(row => row.denseRank),
            ascending(row => row.id)
        )
    );

    printRows(result, [
        "name",
        "department",
        "salary",
        "denseRank"
    ]);
}


// -----------------------------------------------------------------------------
// 10. LAG
// -----------------------------------------------------------------------------

function demonstrateLag() {
    printTitle("LAG: compare each sale with the previous sale in its region");

    const result = applyWindow({
        rows: sales,
        partitionBy: sale => sale.region,
        orderBy: [
            ascending(sale => sale.date),
            ascending(sale => sale.id)
        ],
        calculate: ({ row, partition, position }) => {
            const previous = partition[position - 1];

            row.previousRevenue = previous
                ? previous.revenue
                : null;

            row.changeFromPrevious =
                previous
                    ? row.revenue - previous.revenue
                    : null;
        }
    });

    result.sort(
        composeComparators(
            ascending(row => row.region),
            ascending(row => row.date),
            ascending(row => row.id)
        )
    );

    printRows(result, [
        "id",
        "date",
        "region",
        "revenue",
        "previousRevenue",
        "changeFromPrevious"
    ]);
}


// -----------------------------------------------------------------------------
// 11. LEAD
// -----------------------------------------------------------------------------

function demonstrateLead() {
    printTitle("LEAD: inspect the next row in the ordered partition");

    const result = applyWindow({
        rows: sales,
        partitionBy: sale => sale.region,
        orderBy: [
            ascending(sale => sale.date),
            ascending(sale => sale.id)
        ],
        calculate: ({ row, partition, position }) => {
            const next = partition[position + 1];
            row.nextRevenue = next ? next.revenue : null;
        }
    });

    result.sort(
        composeComparators(
            ascending(row => row.region),
            ascending(row => row.date),
            ascending(row => row.id)
        )
    );

    printRows(result, [
        "id",
        "date",
        "region",
        "revenue",
        "nextRevenue"
    ]);
}


// -----------------------------------------------------------------------------
// 12. RUNNING TOTAL
// -----------------------------------------------------------------------------

function demonstrateRunningTotal() {
    printTitle("RUNNING TOTAL: cumulative revenue within each region");

    const result = applyWindow({
        rows: sales,
        partitionBy: sale => sale.region,
        orderBy: [
            ascending(sale => sale.date),
            ascending(sale => sale.id)
        ],
        calculate: ({ row, partition, position }) => {
            row.runningRevenue = partition
                .slice(0, position + 1)
                .reduce((sum, item) => sum + item.revenue, 0);
        }
    });

    result.sort(
        composeComparators(
            ascending(row => row.region),
            ascending(row => row.date),
            ascending(row => row.id)
        )
    );

    printRows(result, [
        "id",
        "date",
        "region",
        "revenue",
        "runningRevenue"
    ]);
}


// -----------------------------------------------------------------------------
// 13. MOVING WINDOW
// -----------------------------------------------------------------------------

function demonstrateMovingAverage() {
    printTitle("MOVING WINDOW: three-row moving average");

    const result = applyWindow({
        rows: sales,
        partitionBy: sale => sale.region,
        orderBy: [
            ascending(sale => sale.date),
            ascending(sale => sale.id)
        ],
        calculate: ({ row, partition, position }) => {
            const start = Math.max(0, position - 2);
            const windowRows = partition.slice(start, position + 1);

            const average =
                windowRows.reduce(
                    (sum, item) => sum + item.revenue,
                    0
                ) / windowRows.length;

            row.movingAverage = Number(average.toFixed(2));
        }
    });

    result.sort(
        composeComparators(
            ascending(row => row.region),
            ascending(row => row.date),
            ascending(row => row.id)
        )
    );

    printRows(result, [
        "id",
        "date",
        "region",
        "revenue",
        "movingAverage"
    ]);
}


// -----------------------------------------------------------------------------
// 14. FIRST_VALUE AND LAST_VALUE
// -----------------------------------------------------------------------------

function demonstrateFirstAndLastValue() {
    printTitle("FIRST_VALUE and LAST_VALUE");

    const result = applyWindow({
        rows: employees,
        partitionBy: employee => employee.department,
        orderBy: [
            descending(employee => employee.salary),
            ascending(employee => employee.id)
        ],
        calculate: ({ row, partition }) => {
            row.firstEmployee = partition[0].name;

            /*
             * With a complete-partition interpretation, the final row is the
             * last row in the ordered partition.
             */
            row.lastEmployee = partition[partition.length - 1].name;
        }
    });

    result.sort(
        composeComparators(
            ascending(row => row.department),
            descending(row => row.salary),
            ascending(row => row.id)
        )
    );

    printRows(result, [
        "name",
        "department",
        "salary",
        "firstEmployee",
        "lastEmployee"
    ]);
}


// -----------------------------------------------------------------------------
// 15. NTILE
// -----------------------------------------------------------------------------

function demonstrateNtile(bucketCount = 4) {
    printTitle(`NTILE(${bucketCount}): distribute employees into ordered buckets`);

    if (!Number.isInteger(bucketCount) || bucketCount <= 0) {
        throw new RangeError("bucketCount must be a positive integer");
    }

    const result = [...employees]
        .sort(
            composeComparators(
                descending(employee => employee.salary),
                ascending(employee => employee.id)
            )
        )
        .map((employee, index, allRows) => ({
            ...employee,
            bucket: Math.floor(
                (index * bucketCount) / allRows.length
            ) + 1
        }));

    printRows(result, [
        "name",
        "salary",
        "bucket"
    ]);
}


// -----------------------------------------------------------------------------
// 16. TOP-N PER GROUP
// -----------------------------------------------------------------------------

function topNPerGroup(rows, partitionSelector, orderSelector, n) {
    if (!Number.isInteger(n) || n <= 0) {
        throw new RangeError("n must be a positive integer");
    }

    const partitions = partitionRows(rows, partitionSelector);
    const result = [];

    for (const partition of partitions.values()) {
        const ordered = [...partition].sort(
            composeComparators(
                descending(orderSelector),
                ascending(row => row.id)
            )
        );

        ordered.slice(0, n).forEach((row, index) => {
            result.push({
                ...row,
                groupPosition: index + 1
            });
        });
    }

    return result;
}

function demonstrateTopNPerGroup() {
    printTitle("TOP-N PER GROUP: top two salaries in every department");

    const result = topNPerGroup(
        employees,
        employee => employee.department,
        employee => employee.salary,
        2
    );

    result.sort(
        composeComparators(
            ascending(row => row.department),
            ascending(row => row.groupPosition)
        )
    );

    printRows(result, [
        "name",
        "department",
        "salary",
        "groupPosition"
    ]);
}


// -----------------------------------------------------------------------------
// 17. PERCENT OF PARTITION TOTAL
// -----------------------------------------------------------------------------

function demonstratePercentageOfPartition() {
    printTitle("PERCENT OF PARTITION TOTAL");

    const result = applyWindow({
        rows: sales,
        partitionBy: sale => sale.region,
        calculate: ({ row, partition }) => {
            const total = partition.reduce(
                (sum, item) => sum + item.revenue,
                0
            );

            row.regionTotal = total;
            row.percentOfRegion =
                Number(((row.revenue / total) * 100).toFixed(2));
        }
    });

    result.sort(
        composeComparators(
            ascending(row => row.region),
            descending(row => row.revenue),
            ascending(row => row.id)
        )
    );

    printRows(result, [
        "id",
        "region",
        "revenue",
        "regionTotal",
        "percentOfRegion"
    ]);
}


// -----------------------------------------------------------------------------
// 18. CONDITIONAL WINDOW LOGIC
// -----------------------------------------------------------------------------

function demonstrateConditionalWindow() {
    printTitle("CONDITIONAL WINDOW AGGREGATION");

    const result = applyWindow({
        rows: employees,
        partitionBy: employee => employee.department,
        calculate: ({ row, partition }) => {
            row.highSalaryCount = partition.filter(
                item => item.salary >= 100000
            ).length;
        }
    });

    printRows(result, [
        "name",
        "department",
        "salary",
        "highSalaryCount"
    ]);
}


// -----------------------------------------------------------------------------
// 19. NULL HANDLING
// -----------------------------------------------------------------------------

function demonstrateNullHandling() {
    printTitle("NULL HANDLING AND EXPLICIT ORDERING");

    const scores = [
        { name: "A", score: 90 },
        { name: "B", score: null },
        { name: "C", score: 75 },
        { name: "D", score: null },
        { name: "E", score: 95 }
    ];

    /*
     * Explicit NULL placement prevents business logic from depending on
     * runtime-specific default ordering behavior.
     */
    const ordered = [...scores].sort(
        (a, b) => {
            const aNull = a.score === null;
            const bNull = b.score === null;

            if (aNull !== bNull) {
                return aNull ? 1 : -1;
            }

            return compareValues(b.score, a.score);
        }
    );

    const result = ordered.map((row, index) => ({
        ...row,
        position: index + 1
    }));

    printRows(result);
}


// -----------------------------------------------------------------------------
// 20. DETERMINISTIC TIE BREAKING
// -----------------------------------------------------------------------------

function demonstrateDeterministicTieBreaking() {
    printTitle("DETERMINISTIC TIE BREAKING");

    const result = [...employees].sort(
        composeComparators(
            descending(employee => employee.salary),
            ascending(employee => employee.id)
        )
    );

    result.forEach((employee, index) => {
        employee.position = index + 1;
    });

    printRows(result, [
        "id",
        "name",
        "salary",
        "position"
    ]);
}


// -----------------------------------------------------------------------------
// 21. CASE STUDY: SALES ANALYTICS
// -----------------------------------------------------------------------------

function buildSalesAnalytics(rows) {
    /*
     * This function combines several window concepts into a realistic
     * analytical report:
     *
     * - regional total;
     * - running regional total;
     * - previous revenue;
     * - regional ranking;
     * - percentage contribution.
     */
    const result = applyWindow({
        rows,
        partitionBy: sale => sale.region,
        orderBy: [
            ascending(sale => sale.date),
            ascending(sale => sale.id)
        ],
        calculate: ({ row, partition, position }) => {
            const regionTotal = partition.reduce(
                (sum, item) => sum + item.revenue,
                0
            );

            const runningTotal = partition
                .slice(0, position + 1)
                .reduce(
                    (sum, item) => sum + item.revenue,
                    0
                );

            const previous = partition[position - 1];

            const orderedByRevenue = [...partition].sort(
                composeComparators(
                    descending(item => item.revenue),
                    ascending(item => item.id)
                )
            );

            const revenueRank = orderedByRevenue.findIndex(
                item => item.id === row.id
            ) + 1;

            row.regionTotal = regionTotal;
            row.runningRegionTotal = runningTotal;
            row.previousRevenue = previous ? previous.revenue : null;
            row.revenueChange = previous
                ? row.revenue - previous.revenue
                : null;
            row.revenueRank = revenueRank;
            row.percentOfRegion =
                Number(((row.revenue / regionTotal) * 100).toFixed(2));
        }
    });

    return result;
}

function demonstrateSalesCaseStudy() {
    printTitle("INDUSTRY-STYLE SALES ANALYTICS CASE STUDY");

    const result = buildSalesAnalytics(sales);

    result.sort(
        composeComparators(
            ascending(row => row.region),
            ascending(row => row.date),
            ascending(row => row.id)
        )
    );

    printRows(result, [
        "id",
        "date",
        "region",
        "revenue",
        "regionTotal",
        "runningRegionTotal",
        "previousRevenue",
        "revenueChange",
        "revenueRank",
        "percentOfRegion"
    ]);
}


// -----------------------------------------------------------------------------
// 22. PERFORMANCE CONSIDERATIONS
// -----------------------------------------------------------------------------

function benchmarkWindowLikeOperation() {
    printTitle("PERFORMANCE CONSIDERATIONS");

    const largeDataset = [];

    for (let index = 1; index <= 20000; index++) {
        largeDataset.push({
            id: index,
            department: `D${index % 20}`,
            salary: 50000 + (index % 100) * 1000
        });
    }

    const start = performance.now();

    const result = applyWindow({
        rows: largeDataset,
        partitionBy: row => row.department,
        orderBy: [
            descending(row => row.salary),
            ascending(row => row.id)
        ],
        calculate: ({ row, position }) => {
            row.position = position + 1;
        }
    });

    const elapsed = performance.now() - start;

    console.log(`Processed ${result.length} rows.`);
    console.log(`Elapsed time: ${elapsed.toFixed(2)} ms.`);
    console.log(
        "For database workloads, measure the actual SQL query plan and " +
        "consider suitable indexes rather than assuming an index will " +
        "eliminate every sort."
    );
}


// -----------------------------------------------------------------------------
// 23. VALIDATION AND ERROR HANDLING
// -----------------------------------------------------------------------------

function validateEmployee(employee) {
    if (!Number.isInteger(employee.id) || employee.id <= 0) {
        throw new TypeError("Employee id must be a positive integer.");
    }

    if (typeof employee.name !== "string" || employee.name.trim() === "") {
        throw new TypeError("Employee name must be a non-empty string.");
    }

    if (
        typeof employee.salary !== "number" ||
        !Number.isFinite(employee.salary) ||
        employee.salary < 0
    ) {
        throw new TypeError(
            "Employee salary must be a finite non-negative number."
        );
    }
}

function demonstrateValidation() {
    printTitle("VALIDATION AND ERROR HANDLING");

    const validEmployee = {
        id: 999,
        name: "Test User",
        salary: 75000
    };

    validateEmployee(validEmployee);
    console.log("Valid employee accepted.");

    const invalidEmployee = {
        id: -5,
        name: "",
        salary: -100
    };

    try {
        validateEmployee(invalidEmployee);
    } catch (error) {
        console.log(`Invalid employee rejected: ${error.message}`);
    }
}


// -----------------------------------------------------------------------------
// 24. TESTS
// -----------------------------------------------------------------------------

function assert(condition, message) {
    if (!condition) {
        throw new Error(`Assertion failed: ${message}`);
    }
}

function runTests() {
    printTitle("TESTS");

    const rowNumberResult = applyWindow({
        rows: employees,
        partitionBy: employee => employee.department,
        orderBy: [
            descending(employee => employee.salary),
            ascending(employee => employee.id)
        ],
        calculate: ({ row, position }) => {
            row.rowNumber = position + 1;
        }
    });

    const engineering = rowNumberResult
        .filter(row => row.department === "Engineering")
        .sort(ascending(row => row.rowNumber));

    assert(
        engineering[0].name === "Diya",
        "Diya should have the first engineering position."
    );

    assert(
        engineering.length === 4,
        "Engineering should contain four employees."
    );

    const topSales = topNPerGroup(
        employees,
        employee => employee.department,
        employee => employee.salary,
        2
    );

    assert(
        topSales.filter(row => row.department === "Sales").length === 2,
        "Top-N function should return two Sales employees."
    );

    const ranks = employees
        .filter(employee => employee.department === "Engineering")
        .sort(descending(employee => employee.salary));

    assert(ranks[0].salary === ranks[1].salary, "Expected a salary tie.");

    console.log("All tests passed.");
}


// -----------------------------------------------------------------------------
// 25. MAIN
// -----------------------------------------------------------------------------

function main() {
    console.log("=".repeat(80));
    console.log("WINDOW FUNCTIONS I | OVER, PARTITION BY, ORDER BY");
    console.log("=".repeat(80));

    demonstrateCountOver();
    demonstrateAverageOver();
    demonstrateRowNumber();
    demonstrateRank();
    demonstrateDenseRank();
    demonstrateLag();
    demonstrateLead();
    demonstrateRunningTotal();
    demonstrateMovingAverage();
    demonstrateFirstAndLastValue();
    demonstrateNtile();
    demonstrateTopNPerGroup();
    demonstratePercentageOfPartition();
    demonstrateConditionalWindow();
    demonstrateNullHandling();
    demonstrateDeterministicTieBreaking();
    demonstrateSalesCaseStudy();
    benchmarkWindowLikeOperation();
    demonstrateValidation();
    runTests();

    printTitle("PROGRAM COMPLETED");
    console.log(
        "The JavaScript implementation modeled the mechanics behind SQL " +
        "window functions while preserving individual rows."
    );
}

main();
