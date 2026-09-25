/*
 * Analytical Windows: LAG, LEAD, FIRST_VALUE, LAST_VALUE
 * ========================================================
 *
 * A self-contained JavaScript study file.
 *
 * JavaScript does not provide SQL window functions as core language
 * constructs. This file therefore implements the underlying analytical
 * mechanics with arrays, sorting, partitioning, and reusable functions.
 *
 * The implementations model the semantics of:
 *   LAG()
 *   LEAD()
 *   FIRST_VALUE()
 *   LAST_VALUE()
 *
 * The file also demonstrates:
 *   - partitions
 *   - deterministic ordering
 *   - offsets
 *   - defaults
 *   - NULL-like missing values
 *   - frame concepts
 *   - customer journey analysis
 *   - percentage changes
 *   - activity gaps
 *   - validation
 *   - performance considerations
 */

"use strict";

// -----------------------------------------------------------------------------
// 1. SAMPLE DATA
// -----------------------------------------------------------------------------

const sales = [
    { saleId: 1, customerId: 101, region: "North", date: "2026-01-05", product: "Laptop", quantity: 1, unitPrice: 1200 },
    { saleId: 2, customerId: 101, region: "North", date: "2026-01-20", product: "Mouse", quantity: 2, unitPrice: 25 },
    { saleId: 3, customerId: 101, region: "North", date: "2026-02-03", product: "Monitor", quantity: 1, unitPrice: 350 },
    { saleId: 4, customerId: 101, region: "North", date: "2026-02-20", product: "Keyboard", quantity: 1, unitPrice: 80 },
    { saleId: 5, customerId: 101, region: "North", date: "2026-03-10", product: "Laptop", quantity: 1, unitPrice: 1250 },

    { saleId: 6, customerId: 102, region: "South", date: "2026-01-07", product: "Phone", quantity: 1, unitPrice: 800 },
    { saleId: 7, customerId: 102, region: "South", date: "2026-01-25", product: "Case", quantity: 2, unitPrice: 30 },
    { saleId: 8, customerId: 102, region: "South", date: "2026-02-11", product: "Phone", quantity: 1, unitPrice: 820 },
    { saleId: 9, customerId: 102, region: "South", date: "2026-03-05", product: "Earbuds", quantity: 1, unitPrice: 150 },

    { saleId: 10, customerId: 103, region: "North", date: "2026-01-15", product: "Tablet", quantity: 1, unitPrice: 500 },
    { saleId: 11, customerId: 103, region: "North", date: "2026-02-15", product: "Tablet", quantity: 1, unitPrice: 500 },
    { saleId: 12, customerId: 103, region: "North", date: "2026-03-15", product: "Stylus", quantity: 1, unitPrice: 60 },

    { saleId: 13, customerId: 104, region: "West", date: "2026-01-03", product: "Camera", quantity: 1, unitPrice: 1000 },
    { saleId: 14, customerId: 104, region: "West", date: "2026-01-03", product: "Tripod", quantity: 1, unitPrice: 120 },
    { saleId: 15, customerId: 104, region: "West", date: "2026-02-01", product: "Lens", quantity: 1, unitPrice: 700 },
    { saleId: 16, customerId: 104, region: "West", date: "2026-03-01", product: "Camera", quantity: 1, unitPrice: 1100 },

    { saleId: 17, customerId: 105, region: "East", date: "2026-02-01", product: "Chair", quantity: 1, unitPrice: 250 },
    { saleId: 18, customerId: 105, region: "East", date: "2026-03-01", product: "Desk", quantity: 1, unitPrice: 450 }
];

function withRevenue(row) {
    return {
        ...row,
        revenue: row.quantity * row.unitPrice
    };
}

const salesWithRevenue = sales.map(withRevenue);

// -----------------------------------------------------------------------------
// 2. GENERAL UTILITIES
// -----------------------------------------------------------------------------

function cloneRows(rows) {
    return rows.map(row => ({ ...row }));
}

function compareByDateThenId(a, b) {
    const dateComparison = a.date.localeCompare(b.date);

    if (dateComparison !== 0) {
        return dateComparison;
    }

    return a.saleId - b.saleId;
}

function partitionBy(rows, keySelector) {
    const partitions = new Map();

    for (const row of rows) {
        const key = keySelector(row);

        if (!partitions.has(key)) {
            partitions.set(key, []);
        }

        partitions.get(key).push(row);
    }

    return partitions;
}

function orderedPartitions(rows, partitionSelector, comparator) {
    const partitions = partitionBy(rows, partitionSelector);

    for (const partition of partitions.values()) {
        partition.sort(comparator);
    }

    return partitions;
}

function printRows(rows, columns) {
    console.table(
        rows.map(row => {
            const result = {};

            for (const column of columns) {
                result[column] = row[column];
            }

            return result;
        })
    );
}

// -----------------------------------------------------------------------------
// 3. CORE WINDOW OPERATIONS
// -----------------------------------------------------------------------------

function lag(values, offset = 1, defaultValue = null) {
    if (!Number.isInteger(offset) || offset < 0) {
        throw new RangeError("LAG offset must be a non-negative integer.");
    }

    return values.map((_, index) => {
        const sourceIndex = index - offset;

        return sourceIndex >= 0
            ? values[sourceIndex]
            : defaultValue;
    });
}

function lead(values, offset = 1, defaultValue = null) {
    if (!Number.isInteger(offset) || offset < 0) {
        throw new RangeError("LEAD offset must be a non-negative integer.");
    }

    return values.map((_, index) => {
        const sourceIndex = index + offset;

        return sourceIndex < values.length
            ? values[sourceIndex]
            : defaultValue;
    });
}

function firstValue(values, defaultValue = null) {
    return values.length > 0 ? values[0] : defaultValue;
}

function lastValue(values, defaultValue = null) {
    return values.length > 0
        ? values[values.length - 1]
        : defaultValue;
}

// -----------------------------------------------------------------------------
// 4. SQL-LIKE PARTITIONED WINDOW FUNCTIONS
// -----------------------------------------------------------------------------

function applyPartitionedWindow(
    rows,
    partitionSelector,
    orderComparator,
    valueSelector
) {
    const partitions = orderedPartitions(
        rows,
        partitionSelector,
        orderComparator
    );

    const result = [];

    for (const partition of partitions.values()) {
        const values = partition.map(valueSelector);

        const previousValues = lag(values);
        const nextValues = lead(values);
        const first = firstValue(values);
        const last = lastValue(values);

        partition.forEach((row, index) => {
            result.push({
                ...row,
                previousValue: previousValues[index],
                nextValue: nextValues[index],
                firstValue: first,
                lastValue: last
            });
        });
    }

    result.sort((a, b) => {
        const customerComparison = a.customerId - b.customerId;

        if (customerComparison !== 0) {
            return customerComparison;
        }

        return compareByDateThenId(a, b);
    });

    return result;
}

// -----------------------------------------------------------------------------
// 5. LAG DEMONSTRATION
// -----------------------------------------------------------------------------

function demonstrateLag() {
    console.log("\n1. LAG(): previous sale revenue");

    const result = applyPartitionedWindow(
        salesWithRevenue,
        row => row.customerId,
        compareByDateThenId,
        row => row.revenue
    );

    printRows(result, [
        "saleId",
        "customerId",
        "date",
        "revenue",
        "previousValue"
    ]);
}

// -----------------------------------------------------------------------------
// 6. LEAD DEMONSTRATION
// -----------------------------------------------------------------------------

function demonstrateLead() {
    console.log("\n2. LEAD(): next sale revenue");

    const result = applyPartitionedWindow(
        salesWithRevenue,
        row => row.customerId,
        compareByDateThenId,
        row => row.revenue
    );

    printRows(result, [
        "saleId",
        "customerId",
        "date",
        "revenue",
        "nextValue"
    ]);
}

// -----------------------------------------------------------------------------
// 7. FIRST_VALUE AND LAST_VALUE
// -----------------------------------------------------------------------------

function demonstrateFirstAndLast() {
    console.log("\n3. FIRST_VALUE() and LAST_VALUE() semantics");

    const result = applyPartitionedWindow(
        salesWithRevenue,
        row => row.customerId,
        compareByDateThenId,
        row => row.revenue
    );

    printRows(result, [
        "saleId",
        "customerId",
        "date",
        "revenue",
        "firstValue",
        "lastValue"
    ]);
}

// -----------------------------------------------------------------------------
// 8. CUSTOMER JOURNEY
// -----------------------------------------------------------------------------

function customerJourney() {
    console.log("\n4. Customer journey analysis");

    const partitions = orderedPartitions(
        salesWithRevenue,
        row => row.customerId,
        compareByDateThenId
    );

    const result = [];

    for (const [customerId, rows] of partitions) {
        const revenues = rows.map(row => row.revenue);
        const products = rows.map(row => row.product);

        const previousRevenue = lag(revenues);
        const nextRevenue = lead(revenues);
        const previousProduct = lag(products);
        const nextProduct = lead(products);

        rows.forEach((row, index) => {
            result.push({
                customerId,
                saleDate: row.date,
                product: row.product,
                previousProduct: previousProduct[index],
                nextProduct: nextProduct[index],
                revenue: row.revenue,
                changeFromPrevious:
                    previousRevenue[index] == null
                        ? null
                        : row.revenue - previousRevenue[index],
                changeToNext:
                    nextRevenue[index] == null
                        ? null
                        : nextRevenue[index] - row.revenue
            });
        }
    }

    printRows(result, [
        "customerId",
        "saleDate",
        "product",
        "previousProduct",
        "nextProduct",
        "revenue",
        "changeFromPrevious",
        "changeToNext"
    ]);
}

// -----------------------------------------------------------------------------
// 9. PERCENTAGE CHANGE
// -----------------------------------------------------------------------------

function percentageChange(currentValue, previousValue) {
    if (previousValue == null || previousValue === 0) {
        return null;
    }

    return ((currentValue - previousValue) / previousValue) * 100;
}

function demonstratePercentageChange() {
    console.log("\n5. Percentage change");

    const partitions = orderedPartitions(
        salesWithRevenue,
        row => row.customerId,
        compareByDateThenId
    );

    const result = [];

    for (const [customerId, rows] of partitions) {
        const revenues = rows.map(row => row.revenue);
        const previousRevenues = lag(revenues);

        rows.forEach((row, index) => {
            result.push({
                customerId,
                date: row.date,
                revenue: row.revenue,
                previousRevenue: previousRevenues[index],
                percentageChange: percentageChange(
                    row.revenue,
                    previousRevenues[index]
                )
            });
        });
    }

    printRows(result, [
        "customerId",
        "date",
        "revenue",
        "previousRevenue",
        "percentageChange"
    ]);
}

// -----------------------------------------------------------------------------
// 10. ACTIVITY GAP
// -----------------------------------------------------------------------------

function daysBetween(firstDate, secondDate) {
    const first = new Date(`${firstDate}T00:00:00Z`);
    const second = new Date(`${secondDate}T00:00:00Z`);

    return Math.round(
        (second.getTime() - first.getTime()) / (24 * 60 * 60 * 1000)
    );
}

function demonstrateActivityGap() {
    console.log("\n6. Days between customer transactions");

    const partitions = orderedPartitions(
        salesWithRevenue,
        row => row.customerId,
        compareByDateThenId
    );

    const result = [];

    for (const [customerId, rows] of partitions) {
        const dates = rows.map(row => row.date);
        const previousDates = lag(dates);

        rows.forEach((row, index) => {
            result.push({
                customerId,
                date: row.date,
                previousDate: previousDates[index],
                daysSincePrevious:
                    previousDates[index] == null
                        ? null
                        : daysBetween(previousDates[index], row.date)
            });
        }
    }

    printRows(result, [
        "customerId",
        "date",
        "previousDate",
        "daysSincePrevious"
    ]);
}

// -----------------------------------------------------------------------------
// 11. OFFSET AND DEFAULT VALUES
// -----------------------------------------------------------------------------

function demonstrateOffsets() {
    console.log("\n7. LAG and LEAD with offsets and defaults");

    const values = [100, 200, 300, 400];

    console.log("Values:", values);
    console.log("LAG(values, 2, 0):", lag(values, 2, 0));
    console.log("LEAD(values, 2, 0):", lead(values, 2, 0));
}

// -----------------------------------------------------------------------------
// 12. WINDOW FRAME MODEL
// -----------------------------------------------------------------------------

function boundedAverage(values, preceding, following) {
    if (!Number.isInteger(preceding) || preceding < 0) {
        throw new RangeError("preceding must be a non-negative integer.");
    }

    if (!Number.isInteger(following) || following < 0) {
        throw new RangeError("following must be a non-negative integer.");
    }

    return values.map((_, index) => {
        const start = Math.max(0, index - preceding);
        const end = Math.min(values.length - 1, index + following);

        const frame = values.slice(start, end + 1);
        const total = frame.reduce((sum, value) => sum + value, 0);

        return total / frame.length;
    });
}

function demonstrateFrame() {
    console.log("\n8. Bounded frame model");

    const values = [100, 200, 300, 400, 500];

    console.log(
        "Centered one-row frame:",
        boundedAverage(values, 1, 1)
    );
}

// -----------------------------------------------------------------------------
// 13. DETERMINISTIC ORDERING
// -----------------------------------------------------------------------------

function demonstrateTieBreaking() {
    console.log("\n9. Deterministic ordering");

    const customerRows = salesWithRevenue
        .filter(row => row.customerId === 104)
        .sort(compareByDateThenId);

    const products = customerRows.map(row => row.product);

    printRows(
        customerRows.map((row, index) => ({
            saleId: row.saleId,
            date: row.date,
            product: row.product,
            previousProduct: lag(products)[index]
        })),
        [
            "saleId",
            "date",
            "product",
            "previousProduct"
        ]
    );
}

// -----------------------------------------------------------------------------
// 14. CLASSIFY MOVEMENT
// -----------------------------------------------------------------------------

function classifyMovement(current, previous) {
    if (previous == null) {
        return "FIRST SALE";
    }

    if (current > previous) {
        return "INCREASE";
    }

    if (current < previous) {
        return "DECREASE";
    }

    return "UNCHANGED";
}

function demonstrateMovementClassification() {
    console.log("\n10. Revenue movement classification");

    const partitions = orderedPartitions(
        salesWithRevenue,
        row => row.customerId,
        compareByDateThenId
    );

    const result = [];

    for (const [customerId, rows] of partitions) {
        const revenues = rows.map(row => row.revenue);
        const previousRevenues = lag(revenues);

        rows.forEach((row, index) => {
            result.push({
                customerId,
                date: row.date,
                revenue: row.revenue,
                previousRevenue: previousRevenues[index],
                movement: classifyMovement(
                    row.revenue,
                    previousRevenues[index]
                )
            });
        });
    }

    printRows(result, [
        "customerId",
        "date",
        "revenue",
        "previousRevenue",
        "movement"
    ]);
}

// -----------------------------------------------------------------------------
// 15. VALIDATION
// -----------------------------------------------------------------------------

function assertEqual(actual, expected, message) {
    if (actual !== expected) {
        throw new Error(
            `${message}: expected ${expected}, received ${actual}`
        );
    }
}

function assertArrayEqual(actual, expected, message) {
    if (actual.length !== expected.length) {
        throw new Error(
            `${message}: different lengths`
        );
    }

    actual.forEach((value, index) => {
        if (value !== expected[index]) {
            throw new Error(
                `${message}: index ${index}, expected ${expected[index]}, received ${value}`
            );
        }
    });
}

function runTests() {
    console.log("\n11. Automated validation");

    assertArrayEqual(
        lag([10, 20, 30]),
        [null, 10, 20],
        "LAG basic behavior"
    );

    assertArrayEqual(
        lead([10, 20, 30]),
        [20, 30, null],
        "LEAD basic behavior"
    );

    assertArrayEqual(
        lag([10, 20, 30], 2, 0),
        [0, 0, 10],
        "LAG offset/default behavior"
    );

    assertArrayEqual(
        lead([10, 20, 30], 2, 0),
        [30, 0, 0],
        "LEAD offset/default behavior"
    );

    assertEqual(
        firstValue([10, 20, 30]),
        10,
        "FIRST_VALUE behavior"
    );

    assertEqual(
        lastValue([10, 20, 30]),
        30,
        "LAST_VALUE behavior"
    );

    assertEqual(
        percentageChange(120, 100),
        20,
        "Percentage change"
    );

    assertEqual(
        percentageChange(100, 0),
        null,
        "Zero-denominator protection"
    );

    console.log("All JavaScript assertions passed.");
}

// -----------------------------------------------------------------------------
// 16. PERFORMANCE NOTES AS EXECUTABLE INFORMATION
// -----------------------------------------------------------------------------

function printPerformanceNotes() {
    console.log(`
Performance considerations
---------------------------
1. Partitioning groups rows before relative-row calculations.
2. Sorting each partition is normally the expensive operation.
3. A typical ordered analytical workflow is dominated by sorting and memory.
4. SQL databases can use indexes to reduce sorting work.
5. In JavaScript, avoid repeatedly sorting the same partition.
6. Reuse partitioned and ordered data when multiple window calculations
   use the same partition/order definition.
7. LAG and LEAD themselves are O(1) per row after ordering.
8. FIRST_VALUE and LAST_VALUE are O(1) per row after a partition is ordered.
9. Materializing large datasets increases memory usage.
10. Streaming systems require specialized state management because a
    future row is not necessarily available when the current row arrives.
`);
}

// -----------------------------------------------------------------------------
// 17. MAIN
// -----------------------------------------------------------------------------

function main() {
    console.log("Analytical Windows: LAG, LEAD, FIRST_VALUE, LAST_VALUE");

    demonstrateLag();
    demonstrateLead();
    demonstrateFirstAndLast();
    customerJourney();
    demonstratePercentageChange();
    demonstrateActivityGap();
    demonstrateOffsets();
    demonstrateFrame();
    demonstrateTieBreaking();
    demonstrateMovementClassification();
    runTests();
    printPerformanceNotes();

    console.log("\nStudy file completed successfully.");
}

main();
