/*
 * SQL Foundations Project
 * ========================
 *
 * JavaScript companion implementation.
 *
 * This file deliberately does not require an npm package. JavaScript itself
 * does not provide a portable built-in SQL database API in every runtime, so
 * this implementation models relational concepts with JavaScript classes,
 * arrays, Maps, validation functions, joins, grouping, aggregation, indexes,
 * transactions, and a small query-oriented reporting layer.
 *
 * Run with:
 *     node sql_foundations.js
 *
 * The implementation complements the Python SQLite implementation by showing
 * how relational concepts map to application-level data structures and by
 * demonstrating JavaScript-specific functional and asynchronous patterns.
 */

"use strict";

const DATABASE_VERSION = "1.0";

function section(title) {
    console.log(`\n${"=".repeat(88)}\n${title}\n${"=".repeat(88)}`);
}

function subsection(title) {
    console.log(`\n${"-".repeat(72)}\n${title}\n${"-".repeat(72)}`);
}

function printRows(rows) {
    if (rows.length === 0) {
        console.log("(no rows)");
        return;
    }
    console.table(rows);
}

function assert(condition, message) {
    if (!condition) {
        throw new Error(`Assertion failed: ${message}`);
    }
}

class ConstraintError extends Error {
    constructor(message) {
        super(message);
        this.name = "ConstraintError";
    }
}

class ForeignKeyError extends ConstraintError {
    constructor(message) {
        super(message);
        this.name = "ForeignKeyError";
    }
}

class Table {
    constructor(name, primaryKey, columns) {
        this.name = name;
        this.primaryKey = primaryKey;
        this.columns = columns;
        this.rows = [];
        this.primaryIndex = new Map();
    }

    insert(row) {
        for (const column of this.columns) {
            if (!(column in row)) {
                throw new ConstraintError(
                    `Column '${column}' is missing from ${this.name}`
                );
            }
        }

        const key = row[this.primaryKey];

        if (key === null || key === undefined) {
            throw new ConstraintError(
                `${this.name}.${this.primaryKey} cannot be null`
            );
        }

        if (this.primaryIndex.has(key)) {
            throw new ConstraintError(
                `Duplicate primary key ${key} in ${this.name}`
            );
        }

        const copy = structuredClone(row);
        this.rows.push(copy);
        this.primaryIndex.set(key, copy);
    }

    findById(id) {
        return this.primaryIndex.get(id);
    }

    update(predicate, updater) {
        let count = 0;

        for (const row of this.rows) {
            if (predicate(row)) {
                updater(row);
                count += 1;
            }
        }

        return count;
    }

    delete(predicate) {
        const deleted = [];

        this.rows = this.rows.filter((row) => {
            if (!predicate(row)) {
                return true;
            }

            deleted.push(row);
            this.primaryIndex.delete(row[this.primaryKey]);
            return false;
        });

        return deleted;
    }

    all() {
        return this.rows.map((row) => structuredClone(row));
    }
}

class RelationalDatabase {
    constructor() {
        this.tables = new Map();
        this.indexes = new Map();
        this.transactionSnapshot = null;
    }

    createTable(name, primaryKey, columns) {
        if (this.tables.has(name)) {
            throw new Error(`Table ${name} already exists`);
        }

        this.tables.set(
            name,
            new Table(name, primaryKey, columns)
        );
    }

    table(name) {
        const table = this.tables.get(name);

        if (!table) {
            throw new Error(`Unknown table: ${name}`);
        }

        return table;
    }

    createIndex(indexName, tableName, column) {
        const table = this.table(tableName);
        const index = new Map();

        for (const row of table.rows) {
            const value = row[column];

            if (!index.has(value)) {
                index.set(value, []);
            }

            index.get(value).push(row);
        }

        this.indexes.set(indexName, {
            tableName,
            column,
            map: index,
        });
    }

    lookup(indexName, value) {
        const index = this.indexes.get(indexName);

        if (!index) {
            throw new Error(`Unknown index: ${indexName}`);
        }

        return (index.map.get(value) || []).map((row) =>
            structuredClone(row)
        );
    }

    beginTransaction() {
        if (this.transactionSnapshot) {
            throw new Error("Nested transactions are not supported");
        }

        this.transactionSnapshot = new Map();

        for (const [name, table] of this.tables.entries()) {
            this.transactionSnapshot.set(name, {
                rows: structuredClone(table.rows),
            });
        }
    }

    rollback() {
        if (!this.transactionSnapshot) {
            throw new Error("No transaction is active");
        }

        for (const [name, snapshot] of this.transactionSnapshot.entries()) {
            const table = this.table(name);
            table.rows = structuredClone(snapshot.rows);
            table.primaryIndex = new Map();

            for (const row of table.rows) {
                table.primaryIndex.set(
                    row[table.primaryKey],
                    row
                );
            }
        }

        this.transactionSnapshot = null;
    }

    commit() {
        if (!this.transactionSnapshot) {
            throw new Error("No transaction is active");
        }

        this.transactionSnapshot = null;
        this.rebuildIndexes();
    }

    rebuildIndexes() {
        for (const [name, index] of this.indexes.entries()) {
            this.createIndex(
                name,
                index.tableName,
                index.column
            );
        }
    }

    transaction(callback) {
        this.beginTransaction();

        try {
            const result = callback();
            this.commit();
            return result;
        } catch (error) {
            this.rollback();
            throw error;
        }
    }
}

function validateEmail(email) {
    return (
        typeof email === "string" &&
        email.length <= 254 &&
        /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
    );
}

function validateCustomer(row) {
    if (!row.full_name || !row.city) {
        throw new ConstraintError(
            "Customer name and city are required"
        );
    }

    if (!validateEmail(row.email)) {
        throw new ConstraintError("Invalid email address");
    }

    if (!["active", "inactive", "blocked"].includes(row.status)) {
        throw new ConstraintError("Invalid customer status");
    }
}

function validateProduct(row) {
    if (row.price < 0) {
        throw new ConstraintError("Product price cannot be negative");
    }

    if (!Number.isInteger(row.stock_quantity) || row.stock_quantity < 0) {
        throw new ConstraintError(
            "Stock must be a non-negative integer"
        );
    }
}

function addCustomer(database, row) {
    validateCustomer(row);

    const existing = database
        .table("customers")
        .rows
        .some(
            (customer) =>
                customer.email.toLowerCase() ===
                row.email.toLowerCase()
        );

    if (existing) {
        throw new ConstraintError(
            "Customer email must be unique"
        );
    }

    database.table("customers").insert(row);
}

function addProduct(database, row) {
    validateProduct(row);

    if (!database.table("categories").findById(row.category_id)) {
        throw new ForeignKeyError(
            "Product references an unknown category"
        );
    }

    database.table("products").insert(row);
}

function addOrder(database, row) {
    if (!database.table("customers").findById(row.customer_id)) {
        throw new ForeignKeyError(
            "Order references an unknown customer"
        );
    }

    if (
        row.employee_id !== null &&
        !database.table("employees").findById(row.employee_id)
    ) {
        throw new ForeignKeyError(
            "Order references an unknown employee"
        );
    }

    if (
        !["pending", "paid", "shipped", "cancelled"].includes(
            row.status
        )
    ) {
        throw new ConstraintError("Invalid order status");
    }

    database.table("orders").insert(row);
}

function innerJoin(leftRows, rightRows, leftKey, rightKey) {
    const rightMap = new Map();

    for (const row of rightRows) {
        const key = row[rightKey];

        if (!rightMap.has(key)) {
            rightMap.set(key, []);
        }

        rightMap.get(key).push(row);
    }

    const result = [];

    for (const left of leftRows) {
        const matches = rightMap.get(left[leftKey]) || [];

        for (const right of matches) {
            result.push({
                left,
                right,
            });
        }
    }

    return result;
}

function leftJoin(leftRows, rightRows, leftKey, rightKey) {
    const rightMap = new Map();

    for (const row of rightRows) {
        const key = row[rightKey];

        if (!rightMap.has(key)) {
            rightMap.set(key, []);
        }

        rightMap.get(key).push(row);
    }

    const result = [];

    for (const left of leftRows) {
        const matches = rightMap.get(left[leftKey]) || [];

        if (matches.length === 0) {
            result.push({
                left,
                right: null,
            });
            continue;
        }

        for (const right of matches) {
            result.push({
                left,
                right,
            });
        }
    }

    return result;
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

function sum(rows, valueFunction) {
    return rows.reduce(
        (total, row) => total + valueFunction(row),
        0
    );
}

function average(rows, valueFunction) {
    return rows.length === 0
        ? null
        : sum(rows, valueFunction) / rows.length;
}

function orderTotal(database, orderId) {
    return sum(
        database
            .table("order_items")
            .rows
            .filter((item) => item.order_id === orderId),
        (item) => item.quantity * item.unit_price
    );
}

function buildDatabase() {
    const database = new RelationalDatabase();

    database.createTable(
        "customers",
        "customer_id",
        [
            "customer_id",
            "full_name",
            "email",
            "city",
            "signup_date",
            "status",
        ]
    );

    database.createTable(
        "employees",
        "employee_id",
        [
            "employee_id",
            "full_name",
            "department",
            "salary",
        ]
    );

    database.createTable(
        "categories",
        "category_id",
        [
            "category_id",
            "category_name",
        ]
    );

    database.createTable(
        "products",
        "product_id",
        [
            "product_id",
            "category_id",
            "product_name",
            "price",
            "stock_quantity",
            "active",
        ]
    );

    database.createTable(
        "orders",
        "order_id",
        [
            "order_id",
            "customer_id",
            "employee_id",
            "order_date",
            "status",
        ]
    );

    database.createTable(
        "order_items",
        "item_id",
        [
            "item_id",
            "order_id",
            "product_id",
            "quantity",
            "unit_price",
        ]
    );

    database.createTable(
        "payments",
        "payment_id",
        [
            "payment_id",
            "order_id",
            "amount",
            "payment_method",
            "paid_at",
            "status",
        ]
    );

    const customers = [
        [1, "Aarav Sharma", "aarav@example.com", "Lucknow", "2025-01-12", "active"],
        [2, "Priya Singh", "priya@example.com", "Delhi", "2025-02-20", "active"],
        [3, "Rohan Verma", "rohan@example.com", "Mumbai", "2025-03-05", "active"],
        [4, "Ananya Gupta", "ananya@example.com", "Lucknow", "2025-03-18", "active"],
        [5, "Kabir Khan", "kabir@example.com", "Bengaluru", "2025-04-02", "inactive"],
        [6, "Meera Joshi", "meera@example.com", "Pune", "2025-04-15", "active"],
        [7, "Vikram Rao", "vikram@example.com", "Hyderabad", "2025-05-11", "blocked"],
        [8, "Ishita Patel", "ishita@example.com", "Ahmedabad", "2025-06-21", "active"],
    ];

    customers.forEach(
        ([
            customer_id,
            full_name,
            email,
            city,
            signup_date,
            status,
        ]) => {
            addCustomer(database, {
                customer_id,
                full_name,
                email,
                city,
                signup_date,
                status,
            });
        }
    );

    [
        [1, "Neha Kapoor", "Sales", 65000],
        [2, "Arjun Mehta", "Operations", 72000],
        [3, "Sana Ali", "Support", 58000],
    ].forEach(
        ([employee_id, full_name, department, salary]) => {
            database.table("employees").insert({
                employee_id,
                full_name,
                department,
                salary,
            });
        }
    );

    [
        [1, "Programming"],
        [2, "Data"],
        [3, "Business"],
        [4, "Cloud"],
    ].forEach(([category_id, category_name]) => {
        database.table("categories").insert({
            category_id,
            category_name,
        });
    });

    [
        [1, 1, "Python Foundations", 4999, 50, true],
        [2, 1, "Advanced Python", 6999, 40, true],
        [3, 2, "SQL Foundations", 3999, 100, true],
        [4, 2, "Data Analytics", 5999, 60, true],
        [5, 3, "Product Management", 5499, 30, true],
        [6, 3, "Business Metrics", 4499, 25, true],
        [7, 4, "Cloud Fundamentals", 7999, 20, true],
        [8, 4, "DevOps Foundations", 8999, 15, false],
    ].forEach(
        ([
            product_id,
            category_id,
            product_name,
            price,
            stock_quantity,
            active,
        ]) => {
            addProduct(database, {
                product_id,
                category_id,
                product_name,
                price,
                stock_quantity,
                active,
            });
        }
    );

    [
        [1, 1, 1, "2025-07-01T10:30:00", "paid"],
        [2, 2, 1, "2025-07-02T11:10:00", "shipped"],
        [3, 1, 2, "2025-07-04T09:15:00", "paid"],
        [4, 3, 2, "2025-07-06T15:20:00", "cancelled"],
        [5, 4, 1, "2025-07-10T16:45:00", "shipped"],
        [6, 6, 3, "2025-07-12T13:00:00", "paid"],
        [7, 2, 2, "2025-07-15T12:00:00", "pending"],
        [8, 8, 1, "2025-07-20T17:30:00", "paid"],
    ].forEach(
        ([
            order_id,
            customer_id,
            employee_id,
            order_date,
            status,
        ]) => {
            addOrder(database, {
                order_id,
                customer_id,
                employee_id,
                order_date,
                status,
            });
        }
    );

    [
        [1, 1, 3, 1, 3999],
        [2, 1, 1, 1, 4999],
        [3, 2, 4, 1, 5999],
        [4, 2, 6, 2, 4499],
        [5, 3, 2, 1, 6999],
        [6, 3, 3, 2, 3999],
        [7, 4, 7, 1, 7999],
        [8, 5, 5, 1, 5499],
        [9, 5, 3, 1, 3999],
        [10, 6, 1, 1, 4999],
        [11, 6, 4, 1, 5999],
        [12, 7, 7, 1, 7999],
        [13, 8, 2, 1, 6999],
        [14, 8, 5, 1, 5499],
    ].forEach(
        ([
            item_id,
            order_id,
            product_id,
            quantity,
            unit_price,
        ]) => {
            database.table("order_items").insert({
                item_id,
                order_id,
                product_id,
                quantity,
                unit_price,
            });
        }
    );

    [
        [1, 1, 8998, "upi", "2025-07-01T10:31:00", "completed"],
        [2, 2, 14997, "card", "2025-07-02T11:11:00", "completed"],
        [3, 3, 14997, "upi", "2025-07-04T09:16:00", "completed"],
        [4, 4, 7999, "card", "2025-07-06T15:21:00", "refunded"],
        [5, 5, 9498, "upi", "2025-07-10T16:46:00", "completed"],
        [6, 6, 10998, "bank_transfer", "2025-07-12T13:01:00", "completed"],
        [7, 7, 7999, "upi", null, "pending"],
        [8, 8, 12498, "card", "2025-07-20T17:31:00", "completed"],
    ].forEach(
        ([
            payment_id,
            order_id,
            amount,
            payment_method,
            paid_at,
            status,
        ]) => {
            database.table("payments").insert({
                payment_id,
                order_id,
                amount,
                payment_method,
                paid_at,
                status,
            });
        }
    );

    database.createIndex(
        "idx_customer_city",
        "customers",
        "city"
    );

    database.createIndex(
        "idx_order_customer",
        "orders",
        "customer_id"
    );

    database.createIndex(
        "idx_product_category",
        "products",
        "category_id"
    );

    return database;
}

function demonstrateFundamentals(database) {
    section("1. RELATIONAL FUNDAMENTALS");

    printRows(
        database
            .table("customers")
            .all()
            .map((customer) => ({
                customer_id: customer.customer_id,
                full_name: customer.full_name,
                city: customer.city,
                status: customer.status,
            }))
    );

    console.log(
        "A primary key identifies a row. A foreign key connects rows between tables."
    );
    console.log(
        "JavaScript arrays represent row collections, while Maps model efficient key-based indexes."
    );
}

function demonstrateFiltering(database) {
    section("2. FILTERING AND SORTING");

    const activeLucknowCustomers = database
        .table("customers")
        .rows
        .filter(
            (customer) =>
                customer.status === "active" &&
                customer.city === "Lucknow"
        )
        .sort((a, b) =>
            a.full_name.localeCompare(b.full_name)
        )
        .map((customer) => ({
            name: customer.full_name,
            email: customer.email,
        }));

    printRows(activeLucknowCustomers);

    subsection("LIKE-style filtering");
    const pythonProducts = database
        .table("products")
        .rows
        .filter((product) =>
            product.product_name
                .toLowerCase()
                .includes("python")
        )
        .map((product) => ({
            product: product.product_name,
            price: product.price,
        }));

    printRows(pythonProducts);
}

function demonstrateJoins(database) {
    section("3. JOINS");

    const orderCustomerJoin = innerJoin(
        database.table("orders").rows,
        database.table("customers").rows,
        "customer_id",
        "customer_id"
    ).map(({ left: order, right: customer }) => ({
        order_id: order.order_id,
        customer: customer.full_name,
        status: order.status,
        order_date: order.order_date,
    }));

    printRows(orderCustomerJoin);

    subsection("Order line report");

    const orderItemRows = innerJoin(
        database.table("orders").rows,
        database.table("order_items").rows,
        "order_id",
        "order_id"
    );

    const detailed = [];

    for (const { left: order, right: item } of orderItemRows) {
        const customer = database
            .table("customers")
            .findById(order.customer_id);

        const product = database
            .table("products")
            .findById(item.product_id);

        detailed.push({
            order_id: order.order_id,
            customer: customer.full_name,
            product: product.product_name,
            quantity: item.quantity,
            line_total: item.quantity * item.unit_price,
        });
    }

    printRows(detailed);
}

function demonstrateAggregation(database) {
    section("4. GROUPING AND AGGREGATION");

    const groups = groupBy(
        database.table("orders").rows,
        (order) => order.customer_id
    );

    const customerOrderCounts = [];

    for (const [customerId, orders] of groups.entries()) {
        const customer = database
            .table("customers")
            .findById(customerId);

        customerOrderCounts.push({
            customer: customer.full_name,
            order_count: orders.length,
            revenue: sum(
                orders.filter(
                    (order) => order.status !== "cancelled"
                ),
                (order) => orderTotal(
                    database,
                    order.order_id
                )
            ),
        });
    }

    customerOrderCounts.sort(
        (a, b) => b.revenue - a.revenue
    );

    printRows(customerOrderCounts);
}

function demonstrateConditionalLogic(database) {
    section("5. CASE-STYLE BUSINESS LOGIC");

    const products = database
        .table("products")
        .rows
        .map((product) => {
            let priceBand;

            if (product.price >= 7000) {
                priceBand = "premium";
            } else if (product.price >= 5000) {
                priceBand = "standard";
            } else {
                priceBand = "entry";
            }

            return {
                product: product.product_name,
                price: product.price,
                price_band: priceBand,
            };
        });

    printRows(products);
}

function demonstrateIndex(database) {
    section("6. INDEX CONCEPT");

    subsection("Indexed lookup");
    const rows = database.lookup(
        "idx_customer_city",
        "Lucknow"
    );

    printRows(
        rows.map((customer) => ({
            customer_id: customer.customer_id,
            full_name: customer.full_name,
            city: customer.city,
        }))
    );

    console.log(
        "An index trades additional memory and maintenance work for faster lookup."
    );
}

function demonstrateConstraints(database) {
    section("7. CONSTRAINTS AND VALIDATION");

    subsection("Duplicate key");
    try {
        database.table("customers").insert({
            customer_id: 1,
            full_name: "Duplicate",
            email: "duplicate@example.com",
            city: "Delhi",
            signup_date: "2025-08-01",
            status: "active",
        });
    } catch (error) {
        console.log(error.name + ":", error.message);
    }

    subsection("Invalid email");
    try {
        addCustomer(database, {
            customer_id: 99,
            full_name: "Invalid Customer",
            email: "not-an-email",
            city: "Delhi",
            signup_date: "2025-08-01",
            status: "active",
        });
    } catch (error) {
        console.log(error.name + ":", error.message);
    }

    subsection("Invalid foreign key");
    try {
        addOrder(database, {
            order_id: 99,
            customer_id: 999,
            employee_id: 1,
            order_date: "2025-08-01T10:00:00",
            status: "pending",
        });
    } catch (error) {
        console.log(error.name + ":", error.message);
    }
}

function demonstrateTransactions(database) {
    section("8. TRANSACTIONS");

    const productId = 3;
    const quantity = 2;

    const before = database
        .table("products")
        .findById(productId)
        .stock_quantity;

    database.transaction(() => {
        const product = database
            .table("products")
            .findById(productId);

        if (product.stock_quantity < quantity) {
            throw new ConstraintError(
                "Insufficient stock"
            );
        }

        product.stock_quantity -= quantity;
    });

    const after = database
        .table("products")
        .findById(productId)
        .stock_quantity;

    console.log({ before, after });

    subsection("Rollback");
    const rollbackBefore = database
        .table("products")
        .findById(1)
        .stock_quantity;

    try {
        database.transaction(() => {
            const product = database
                .table("products")
                .findById(1);

            product.stock_quantity -= 1;

            throw new Error(
                "Simulated payment provider failure"
            );
        });
    } catch (error) {
        console.log("Transaction failed:", error.message);
    }

    const rollbackAfter = database
        .table("products")
        .findById(1)
        .stock_quantity;

    console.log({
        rollbackBefore,
        rollbackAfter,
        rolledBack: rollbackBefore === rollbackAfter,
    });
}

function demonstrateWindowLikeRanking(database) {
    section("9. WINDOW-FUNCTION-LIKE RANKING");

    const products = [...database.table("products").rows]
        .sort((a, b) => b.price - a.price);

    let previousPrice = null;
    let currentRank = 0;

    const ranked = products.map((product, index) => {
        if (product.price !== previousPrice) {
            currentRank = index + 1;
            previousPrice = product.price;
        }

        return {
            product: product.product_name,
            price: product.price,
            rank: currentRank,
        };
    });

    printRows(ranked);
}

function demonstrateDataQuality(database) {
    section("10. DATA QUALITY TESTS");

    const customers = database.table("customers").rows;
    const products = database.table("products").rows;
    const orders = database.table("orders").rows;

    assert(
        customers.every((customer) =>
            validateEmail(customer.email)
        ),
        "all customer emails should be valid"
    );

    assert(
        products.every(
            (product) =>
                product.price >= 0 &&
                product.stock_quantity >= 0
        ),
        "products should have valid financial and stock values"
    );

    assert(
        orders.every((order) =>
            database
                .table("customers")
                .findById(order.customer_id)
        ),
        "orders should reference customers"
    );

    console.log("PASS: all data-quality tests");
}

async function demonstrateAsyncApplicationPattern(database) {
    section("11. ASYNCHRONOUS APPLICATION PATTERN");

    /*
     * Real web applications normally obtain database results asynchronously.
     * This small helper emulates that API boundary without requiring a package.
     */
    function fetchCustomerOrders(customerId) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                try {
                    const customer = database
                        .table("customers")
                        .findById(customerId);

                    if (!customer) {
                        throw new ForeignKeyError(
                            "Customer not found"
                        );
                    }

                    const orders = database
                        .table("orders")
                        .rows
                        .filter(
                            (order) =>
                                order.customer_id === customerId
                        )
                        .map((order) => ({
                            order_id: order.order_id,
                            status: order.status,
                            total: orderTotal(
                                database,
                                order.order_id
                            ),
                        }));

                    resolve({
                        customer: customer.full_name,
                        orders,
                    });
                } catch (error) {
                    reject(error);
                }
            }, 10);
        });
    }

    const result = await fetchCustomerOrders(1);
    console.log(JSON.stringify(result, null, 2));
}

function demonstratePerformanceTradeoff(database) {
    section("12. PERFORMANCE TRADE-OFF");

    const cities = [
        "Lucknow",
        "Delhi",
        "Mumbai",
        "Pune",
        "Bengaluru",
        "Hyderabad",
        "Ahmedabad",
    ];

    const largeDataset = [];

    for (let i = 0; i < 100000; i += 1) {
        largeDataset.push({
            customer_id: i,
            city: cities[i % cities.length],
        });
    }

    const targetCity = "Lucknow";

    const linearStart = performance.now();

    const linearMatches = largeDataset.filter(
        (row) => row.city === targetCity
    );

    const linearTime = performance.now() - linearStart;

    const indexStart = performance.now();

    const cityIndex = new Map();

    for (const row of largeDataset) {
        if (!cityIndex.has(row.city)) {
            cityIndex.set(row.city, []);
        }

        cityIndex.get(row.city).push(row);
    }

    const indexedMatches =
        cityIndex.get(targetCity) || [];

    const indexTime = performance.now() - indexStart;

    console.log({
        linearMatches: linearMatches.length,
        indexedMatches: indexedMatches.length,
        linearLookupMilliseconds: linearTime.toFixed(3),
        indexBuildMilliseconds: indexTime.toFixed(3),
    });

    console.log(
        "Indexes are valuable when their build and maintenance costs are justified by repeated lookups."
    );
}

function demonstrateNormalization() {
    section("13. NORMALIZATION");

    console.log(
        [
            "Bad design: order_id, customer_name, customer_email, product1, product2, product3",
            "Better design: customers, products, orders, order_items",
            "The separate tables reduce duplication and update anomalies.",
            "A many-to-many relationship can be represented with a junction table.",
        ].join("\n")
    );
}

async function main() {
    console.log(`SQL Foundations JavaScript Study File v${DATABASE_VERSION}`);

    const database = buildDatabase();

    demonstrateFundamentals(database);
    demonstrateFiltering(database);
    demonstrateJoins(database);
    demonstrateAggregation(database);
    demonstrateConditionalLogic(database);
    demonstrateIndex(database);
    demonstrateConstraints(database);
    demonstrateTransactions(database);
    demonstrateWindowLikeRanking(database);
    demonstrateDataQuality(database);
    await demonstrateAsyncApplicationPattern(database);
    demonstratePerformanceTradeoff(database);
    demonstrateNormalization();

    section("FINAL RECORD COUNTS");

    printRows([
        {
            customers: database.table("customers").rows.length,
            employees: database.table("employees").rows.length,
            categories: database.table("categories").rows.length,
            products: database.table("products").rows.length,
            orders: database.table("orders").rows.length,
            order_items: database.table("order_items").rows.length,
            payments: database.table("payments").rows.length,
        },
    ]);

    console.log("\nJavaScript relational-database case study completed.");
}

main().catch((error) => {
    console.error("Application failure:", error);
    process.exitCode = 1;
});
