"use strict";

/*
Join Strategy: Join Keys, Cardinality, Duplicate Rows, and NULL Behavior

This file implements relational joins without external packages. JavaScript's
null is used to represent SQL NULL for the examples.

A critical distinction:
    JavaScript: null === null -> true
    SQL:        NULL = NULL  -> UNKNOWN

Therefore ordinary SQL equality joins do not match two NULL join keys.
*/

function printTitle(title) {
    console.log("\n" + "=".repeat(80));
    console.log(title);
    console.log("=".repeat(80));
}

function printRows(rows, title = "") {
    if (title) console.log(`\n${title}`);

    if (rows.length === 0) {
        console.log("(no rows)");
        return;
    }

    const columns = [];
    for (const row of rows) {
        for (const key of Object.keys(row)) {
            if (!columns.includes(key)) columns.push(key);
        }
    }

    console.table(rows, columns);
}

function sqlEqual(left, right) {
    // SQL equality does not consider NULL equal to NULL.
    if (left === null || left === undefined) return false;
    if (right === null || right === undefined) return false;
    return left === right;
}

function nullSafeEqual(left, right) {
    // Explicit null-safe comparison policy.
    return left === right;
}

function mergeRows(left, right) {
    // Prefixes prevent accidental property overwriting.
    const result = {};

    for (const [key, value] of Object.entries(left)) {
        result[`left.${key}`] = value;
    }

    for (const [key, value] of Object.entries(right)) {
        result[`right.${key}`] = value;
    }

    return result;
}

function nestedLoopInnerJoin(
    leftRows,
    rightRows,
    leftKey,
    rightKey,
    equality = sqlEqual
) {
    /*
    Nested-loop join:
        For every left row, scan every right row.

    Complexity:
        O(N * M)

    It is simple but becomes expensive for large inputs.
    */
    const result = [];

    for (const left of leftRows) {
        for (const right of rightRows) {
            if (equality(left[leftKey], right[rightKey])) {
                result.push(mergeRows(left, right));
            }
        }
    }

    return result;
}

function hashInnerJoin(leftRows, rightRows, leftKey, rightKey) {
    /*
    JavaScript Map provides a convenient hash-table-like structure.

    The right side is indexed once. Duplicate right keys map to arrays rather
    than a single row, because a join must preserve multiplicity.
    */
    const index = new Map();

    for (const right of rightRows) {
        const key = right[rightKey];

        if (key === null || key === undefined) continue;

        if (!index.has(key)) index.set(key, []);
        index.get(key).push(right);
    }

    const result = [];

    for (const left of leftRows) {
        const key = left[leftKey];

        if (key === null || key === undefined) continue;

        const matches = index.get(key) || [];

        for (const right of matches) {
            result.push(mergeRows(left, right));
        }
    }

    return result;
}

function leftOuterHashJoin(leftRows, rightRows, leftKey, rightKey) {
    const index = new Map();

    const rightColumns =
        rightRows.length > 0 ? Object.keys(rightRows[0]) : [];

    for (const right of rightRows) {
        const key = right[rightKey];

        if (key === null || key === undefined) continue;

        if (!index.has(key)) index.set(key, []);
        index.get(key).push(right);
    }

    const result = [];

    for (const left of leftRows) {
        const key = left[leftKey];
        const matches =
            key === null || key === undefined
                ? []
                : index.get(key) || [];

        if (matches.length > 0) {
            for (const right of matches) {
                result.push(mergeRows(left, right));
            }
        } else {
            const nullRight = {};

            for (const column of rightColumns) {
                nullRight[column] = null;
            }

            result.push(mergeRows(left, nullRight));
        }
    }

    return result;
}

function crossJoin(leftRows, rightRows) {
    /*
    Cartesian product:
        output size = N * M

    An accidental cross join is a common cause of unexpectedly huge results.
    */
    const result = [];

    for (const left of leftRows) {
        for (const right of rightRows) {
            result.push(mergeRows(left, right));
        }
    }

    return result;
}

function semiJoin(leftRows, rightRows, leftKey, rightKey) {
    /*
    A semi join answers:
        "Does at least one matching row exist?"

    It does not duplicate a left row when multiple right rows match.
    */
    const rightKeys = new Set(
        rightRows
            .map(row => row[rightKey])
            .filter(value => value !== null && value !== undefined)
    );

    return leftRows.filter(
        row =>
            row[leftKey] !== null &&
            row[leftKey] !== undefined &&
            rightKeys.has(row[leftKey])
    );
}

function antiJoin(leftRows, rightRows, leftKey, rightKey) {
    const rightKeys = new Set(
        rightRows
            .map(row => row[rightKey])
            .filter(value => value !== null && value !== undefined)
    );

    return leftRows.filter(
        row =>
            row[leftKey] === null ||
            row[leftKey] === undefined ||
            !rightKeys.has(row[leftKey])
    );
}

function compositeKey(row, columns) {
    /*
    JSON serialization gives us a simple deterministic representation for
    primitive composite keys. Production systems may use a more specialized
    representation when performance is critical.
    */
    return JSON.stringify(columns.map(column => row[column]));
}

function compositeHashJoin(
    leftRows,
    rightRows,
    leftColumns,
    rightColumns
) {
    const index = new Map();

    for (const right of rightRows) {
        const values = rightColumns.map(column => right[column]);

        // Ordinary SQL composite equality fails if a component is NULL.
        if (values.some(value => value === null || value === undefined)) {
            continue;
        }

        const key = compositeKey(right, rightColumns);

        if (!index.has(key)) index.set(key, []);
        index.get(key).push(right);
    }

    const result = [];

    for (const left of leftRows) {
        const values = leftColumns.map(column => left[column]);

        if (values.some(value => value === null || value === undefined)) {
            continue;
        }

        const key = compositeKey(left, leftColumns);

        for (const right of index.get(key) || []) {
            result.push(mergeRows(left, right));
        }
    }

    return result;
}

function countByKey(rows, key) {
    const counts = new Map();

    for (const row of rows) {
        const value = row[key];
        counts.set(value, (counts.get(value) || 0) + 1);
    }

    return counts;
}

function classifyCardinality(leftRows, rightRows, leftKey, rightKey) {
    const leftCounts = countByKey(leftRows, leftKey);
    const rightCounts = countByKey(rightRows, rightKey);

    const leftDuplicate = [...leftCounts.entries()].some(
        ([key, count]) =>
            key !== null && key !== undefined && count > 1
    );

    const rightDuplicate = [...rightCounts.entries()].some(
        ([key, count]) =>
            key !== null && key !== undefined && count > 1
    );

    if (!leftDuplicate && !rightDuplicate) return "1:1";
    if (!leftDuplicate && rightDuplicate) return "1:N";
    if (leftDuplicate && !rightDuplicate) return "N:1";
    return "N:N";
}

function expectedJoinOutputSize(
    leftRows,
    rightRows,
    leftKey,
    rightKey
) {
    const leftCounts = countByKey(leftRows, leftKey);
    const rightCounts = countByKey(rightRows, rightKey);

    let total = 0;

    for (const [key, leftCount] of leftCounts.entries()) {
        if (key === null || key === undefined) continue;
        total += leftCount * (rightCounts.get(key) || 0);
    }

    return total;
}

function validateUniqueKey(rows, key) {
    const counts = countByKey(rows, key);

    const duplicates = [];

    for (const [value, count] of counts.entries()) {
        if (value !== null && value !== undefined && count > 1) {
            duplicates.push({ value, count });
        }
    }

    if (duplicates.length > 0) {
        throw new Error(
            `Expected unique key '${key}', duplicates found: ` +
            JSON.stringify(duplicates)
        );
    }
}

function demonstrateBasicJoins() {
    printTitle("1. Basic join types");

    const employees = [
        { employeeId: 1, name: "Asha", departmentId: 10 },
        { employeeId: 2, name: "Ravi", departmentId: 20 },
        { employeeId: 3, name: "Meera", departmentId: 30 },
        { employeeId: 4, name: "Kabir", departmentId: 99 }
    ];

    const departments = [
        { departmentId: 10, department: "Engineering" },
        { departmentId: 20, department: "Finance" },
        { departmentId: 30, department: "Security" }
    ];

    printRows(
        hashInnerJoin(
            employees,
            departments,
            "departmentId",
            "departmentId"
        ),
        "Inner join"
    );

    printRows(
        leftOuterHashJoin(
            employees,
            departments,
            "departmentId",
            "departmentId"
        ),
        "Left outer join"
    );

    printRows(
        crossJoin(
            [{ color: "red" }, { color: "blue" }],
            [{ size: "S" }, { size: "M" }]
        ),
        "Cross join"
    );
}

function demonstrateDuplicateRows() {
    printTitle("2. Cardinality and duplicate rows");

    const customers = [
        { customerId: 1, name: "Asha" },
        { customerId: 2, name: "Ravi" }
    ];

    const orders = [
        { orderId: "O1", customerId: 1 },
        { orderId: "O2", customerId: 1 },
        { orderId: "O3", customerId: 1 },
        { orderId: "O4", customerId: 2 }
    ];

    console.log(
        "Observed cardinality:",
        classifyCardinality(
            customers,
            orders,
            "customerId",
            "customerId"
        )
    );

    const joined = hashInnerJoin(
        customers,
        orders,
        "customerId",
        "customerId"
    );

    printRows(joined, "1:N join");

    const manyLeft = [
        { eventId: "E1", accountId: 7 },
        { eventId: "E2", accountId: 7 },
        { eventId: "E3", accountId: 7 }
    ];

    const manyRight = [
        { transactionId: "T1", accountId: 7 },
        { transactionId: "T2", accountId: 7 }
    ];

    console.log(
        "N:N expected rows:",
        expectedJoinOutputSize(
            manyLeft,
            manyRight,
            "accountId",
            "accountId"
        )
    );
}

function demonstrateNullBehavior() {
    printTitle("3. NULL behavior");

    const left = [
        { id: 1, code: "A" },
        { id: 2, code: null },
        { id: 3, code: "B" }
    ];

    const right = [
        { recordId: 10, code: "A" },
        { recordId: 11, code: null },
        { recordId: 12, code: "B" }
    ];

    printRows(
        nestedLoopInnerJoin(
            left,
            right,
            "code",
            "code",
            sqlEqual
        ),
        "SQL-style equality"
    );

    printRows(
        nestedLoopInnerJoin(
            left,
            right,
            "code",
            "code",
            nullSafeEqual
        ),
        "Null-safe equality"
    );

    console.log("JavaScript null === null:", null === null);
    console.log(
        "SQL-style equality for NULL:",
        sqlEqual(null, null)
    );
}

function demonstrateCompositeKeys() {
    printTitle("4. Composite keys");

    const shipments = [
        { country: "IN", customerId: 10, shipment: "S1" },
        { country: "US", customerId: 10, shipment: "S2" },
        { country: "IN", customerId: 20, shipment: "S3" }
    ];

    const customers = [
        { country: "IN", customerId: 10, name: "Asha" },
        { country: "US", customerId: 10, name: "John" },
        { country: "IN", customerId: 20, name: "Ravi" }
    ];

    printRows(
        compositeHashJoin(
            shipments,
            customers,
            ["country", "customerId"],
            ["country", "customerId"]
        ),
        "Country + customerId join"
    );
}

function demonstrateSemiAnti() {
    printTitle("5. Semi and anti joins");

    const products = [
        { productId: 1, product: "Keyboard" },
        { productId: 2, product: "Mouse" },
        { productId: 3, product: "Monitor" }
    ];

    const sales = [
        { saleId: "S1", productId: 1 },
        { saleId: "S2", productId: 1 },
        { saleId: "S3", productId: 3 }
    ];

    printRows(
        semiJoin(products, sales, "productId", "productId"),
        "Products with at least one sale"
    );

    printRows(
        antiJoin(products, sales, "productId", "productId"),
        "Products with no sale"
    );
}

function demonstrateValidation() {
    printTitle("6. Join validation");

    const accounts = [
        { accountId: 1, owner: "Asha" },
        { accountId: 2, owner: "Ravi" },
        { accountId: 2, owner: "Duplicate Ravi" }
    ];

    try {
        validateUniqueKey(accounts, "accountId");
    } catch (error) {
        console.log("Validation failed as expected:");
        console.log(error.message);
    }
}

function demonstrateRealWorldCase() {
    printTitle("7. Industry-style sales enrichment");

    const customers = [
        { customerId: 1, segment: "retail" },
        { customerId: 2, segment: "business" },
        { customerId: 3, segment: "retail" }
    ];

    const orders = [
        { orderId: "O1", customerId: 1, amount: 100 },
        { orderId: "O2", customerId: 1, amount: 200 },
        { orderId: "O3", customerId: 2, amount: 500 },
        { orderId: "O4", customerId: 2, amount: 700 }
    ];

    const joined = hashInnerJoin(
        customers,
        orders,
        "customerId",
        "customerId"
    );

    printRows(joined, "Order rows enriched with segment");

    const revenueBySegment = new Map();

    for (const row of joined) {
        const segment = row["left.segment"];
        const amount = row["right.amount"];

        revenueBySegment.set(
            segment,
            (revenueBySegment.get(segment) || 0) + amount
        );
    }

    console.log("\nRevenue by segment:");
    for (const [segment, amount] of revenueBySegment) {
        console.log(`${segment}: ${amount}`);
    }
}

function demonstrateAssertions() {
    printTitle("8. Executable correctness checks");

    const left = [
        { id: 1, value: "A" },
        { id: 2, value: "B" }
    ];

    const right = [
        { id: 1, category: "X" },
        { id: 2, category: "Y" }
    ];

    const result = hashInnerJoin(left, right, "id", "id");

    console.assert(
        result.length === 2,
        "A 1:1 inner join should return two rows."
    );

    const nullResult = hashInnerJoin(
        [{ id: null }],
        [{ id: null }],
        "id",
        "id"
    );

    console.assert(
        nullResult.length === 0,
        "Ordinary SQL equality should not match NULL with NULL."
    );

    const semiResult = semiJoin(
        [{ id: 1 }, { id: 2 }],
        [{ id: 1 }, { id: 1 }],
        "id",
        "id"
    );

    console.assert(
        semiResult.length === 1,
        "A semi join should not duplicate the left row."
    );

    console.log("Assertions completed.");
}

function main() {
    console.log("Join Strategy Study");
    console.log(
        "Join keys define matching, cardinality predicts multiplicity, " +
        "duplicates can multiply rows, and NULL requires special semantics."
    );

    demonstrateBasicJoins();
    demonstrateDuplicateRows();
    demonstrateNullBehavior();
    demonstrateCompositeKeys();
    demonstrateSemiAnti();
    demonstrateValidation();
    demonstrateRealWorldCase();
    demonstrateAssertions();

    printTitle("Key rules");
    console.log("1. INNER JOIN returns matching pairs.");
    console.log("2. LEFT JOIN preserves all left rows.");
    console.log("3. A duplicate key is not automatically an error.");
    console.log("4. 3 matching rows × 4 matching rows = 12 joined rows.");
    console.log("5. Ordinary SQL equality does not match NULL to NULL.");
    console.log("6. Composite joins compare every key component.");
    console.log("7. Semi joins test existence without multiplying rows.");
    console.log("8. Anti joins identify rows with no match.");
    console.log("9. Hash joins trade memory for faster expected lookups.");
    console.log("10. Cross joins produce N × M combinations.");
}

main();
