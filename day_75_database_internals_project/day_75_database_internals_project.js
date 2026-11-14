"use strict";

/**
 * Database Internals Project
 * Event-driven query execution and database behavior analysis.
 *
 * Runtime: Node.js 18+
 * Dependencies: None
 */

const { EventEmitter } = require("node:events");
const { createHash } = require("node:crypto");
const fs = require("node:fs/promises");
const path = require("node:path");
const { performance } = require("node:perf_hooks");

// ============================================================
// 1. ERRORS AND DATABASE CONFIGURATION
// ============================================================

class DatabaseError extends Error {}
class ValidationError extends DatabaseError {}
class TransactionError extends DatabaseError {}
class StorageError extends DatabaseError {}
class QueryExecutionError extends DatabaseError {}

const TransactionState = Object.freeze({
    ACTIVE: "ACTIVE",
    COMMITTED: "COMMITTED",
    ABORTED: "ABORTED"
});

const CheckStatus = Object.freeze({
    PENDING: "PENDING",
    RUNNING: "RUNNING",
    PASSED: "PASSED",
    FAILED: "FAILED"
});

function validateIdentifier(identifier) {
    if (
        typeof identifier !== "string" ||
        !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(identifier)
    ) {
        throw new ValidationError(
            `Invalid database identifier: ${identifier}`
        );
    }

    return identifier;
}

function clone(value) {
    return structuredClone(value);
}

// ============================================================
// 2. PAGE MANAGEMENT AND BUFFER POOL
// ============================================================

class Page {
    constructor(id, type = "HEAP") {
        this.id = id;
        this.type = type;
        this.records = [];
        this.dirty = false;
        this.pageLSN = 0;
        this.checksum = "";
    }

    calculateChecksum() {
        return createHash("sha256")
            .update(JSON.stringify(this.records))
            .digest("hex");
    }

    refreshChecksum() {
        this.checksum = this.calculateChecksum();
    }

    validate() {
        return this.checksum === this.calculateChecksum();
    }
}

class BufferPool {
    constructor(capacity, disk, wal) {
        if (!Number.isInteger(capacity) || capacity < 1) {
            throw new ValidationError(
                "Buffer capacity must be a positive integer."
            );
        }

        this.capacity = capacity;
        this.disk = disk;
        this.wal = wal;
        this.frames = new Map();

        this.statistics = {
            hits: 0,
            misses: 0,
            evictions: 0
        };
    }

    async fetch(pageId) {
        if (this.frames.has(pageId)) {
            this.statistics.hits++;

            const page = this.frames.get(pageId);
            this.frames.delete(pageId);
            this.frames.set(pageId, page);

            return page;
        }

        this.statistics.misses++;

        if (this.frames.size >= this.capacity) {
            await this.evict();
        }

        const page = await this.disk.read(pageId);
        this.frames.set(pageId, page);

        return page;
    }

    async add(page) {
        if (this.frames.size >= this.capacity) {
            await this.evict();
        }

        this.frames.set(page.id, page);
    }

    async evict() {
        const oldestId = this.frames.keys().next().value;

        if (oldestId === undefined) return;

        const page = this.frames.get(oldestId);

        if (page.dirty) {
            await this.wal.flush();
            await this.disk.write(page, this.wal.durableLSN);
        }

        this.frames.delete(oldestId);
        this.statistics.evictions++;
    }

    async flushAll() {
        await this.wal.flush();

        for (const page of this.frames.values()) {
            if (page.dirty) {
                await this.disk.write(page, this.wal.durableLSN);
            }
        }
    }

    hitRatio() {
        const total =
            this.statistics.hits + this.statistics.misses;

        return total === 0
            ? 0
            : this.statistics.hits / total;
    }
}

// ============================================================
// 3. ASYNCHRONOUS DISK AND WRITE-AHEAD LOG
// ============================================================

class DiskManager {
    constructor(directory) {
        this.directory = directory;
        this.file = path.join(directory, "pages.json");
        this.pages = new Map();
        this.reads = 0;
        this.writes = 0;
    }

    async initialize() {
        await fs.mkdir(this.directory, { recursive: true });

        try {
            const contents = await fs.readFile(
                this.file,
                "utf8"
            );

            const storedPages = JSON.parse(contents);

            for (const stored of storedPages) {
                const page = Object.assign(
                    new Page(stored.id, stored.type),
                    stored
                );

                if (!page.validate()) {
                    throw new StorageError(
                        `Page ${page.id} checksum failure.`
                    );
                }

                this.pages.set(page.id, page);
            }
        } catch (error) {
            if (error.code !== "ENOENT") throw error;
        }
    }

    async read(id) {
        const page = this.pages.get(id);

        if (!page) {
            throw new StorageError(
                `Page ${id} was not found.`
            );
        }

        if (!page.validate()) {
            throw new StorageError(
                `Page ${id} is corrupted.`
            );
        }

        this.reads++;
        return clone(page);
    }

    async write(page, durableLSN) {
        if (page.pageLSN > durableLSN) {
            throw new StorageError(
                "WAL must be durable before the page is written."
            );
        }

        page.refreshChecksum();
        page.dirty = false;

        this.pages.set(page.id, clone(page));

        const contents = JSON.stringify(
            [...this.pages.values()]
        );

        const temporary = `${this.file}.tmp`;

        await fs.writeFile(temporary, contents, {
            encoding: "utf8",
            mode: 0o600
        });

        await fs.rename(temporary, this.file);
        this.writes++;
    }

    allocate(type = "HEAP") {
        const id = Math.max(0, ...this.pages.keys()) + 1;
        const page = new Page(id, type);
        page.refreshChecksum();
        this.pages.set(id, page);

        return page;
    }
}

class WriteAheadLog {
    constructor(directory) {
        this.file = path.join(directory, "database.wal");
        this.records = [];
        this.nextLSN = 1;
        this.durableLSN = 0;
    }

    async initialize() {
        try {
            const contents = await fs.readFile(
                this.file,
                "utf8"
            );

            this.records = contents
                .split("\n")
                .filter(Boolean)
                .map(line => JSON.parse(line));

            for (const record of this.records) {
                this.nextLSN = Math.max(
                    this.nextLSN,
                    record.lsn + 1
                );
                this.durableLSN = Math.max(
                    this.durableLSN,
                    record.lsn
                );
            }
        } catch (error) {
            if (error.code !== "ENOENT") throw error;
        }
    }

    async append(transactionId, operation, data = {}) {
        const record = {
            lsn: this.nextLSN++,
            transactionId,
            operation,
            timestamp: new Date().toISOString(),
            data
        };

        await fs.appendFile(
            this.file,
            JSON.stringify(record) + "\n",
            { encoding: "utf8", mode: 0o600 }
        );

        this.records.push(record);

        return record.lsn;
    }

    async flush() {
        const handle = await fs.open(this.file, "a");

        try {
            await handle.sync();
            this.durableLSN = this.records.length
                ? this.records[this.records.length - 1].lsn
                : this.durableLSN;
        } finally {
            await handle.close();
        }
    }
}

// ============================================================
// 4. EVENT-DRIVEN DATABASE ENGINE
// ============================================================

class DatabaseEngine extends EventEmitter {
    constructor(directory, options = {}) {
        super();

        this.directory = directory;
        this.capacity = options.bufferCapacity ?? 8;
        this.maxRecords = options.maxRecordsPerPage ?? 64;

        this.tables = new Map();
        this.indexes = new Map();
        this.transactionCounter = 1;
        this.rowCounter = 1;

        this.disk = new DiskManager(directory);
        this.wal = new WriteAheadLog(directory);
        this.buffer = null;
    }

    async initialize() {
        await this.disk.initialize();
        await this.wal.initialize();

        this.buffer = new BufferPool(
            this.capacity,
            this.disk,
            this.wal
        );

        for (const page of this.disk.pages.values()) {
            if (page.type !== "HEAP" || page.records.length === 0) {
                continue;
            }

            const table = page.records[0]._table;

            if (!this.tables.has(table)) {
                this.tables.set(table, []);
            }

            this.tables.get(table).push(page.id);

            for (const record of page.records) {
                this.rowCounter = Math.max(
                    this.rowCounter,
                    record._rowId + 1
                );
            }
        }

        this.emit("database:ready", {
            pages: this.disk.pages.size
        });

        return this;
    }

    beginTransaction() {
        return new Transaction(
            this,
            this.transactionCounter++
        );
    }

    async insert(transaction, table, input) {
        validateIdentifier(table);

        if (
            !input ||
            typeof input !== "object" ||
            Array.isArray(input) ||
            Object.keys(input).length === 0
        ) {
            throw new ValidationError(
                "Insert requires a non-empty object."
            );
        }

        const row = {
            ...clone(input),
            _rowId: this.rowCounter++,
            _table: table
        };

        let page = null;

        for (const pageId of this.tables.get(table) ?? []) {
            const candidate = await this.buffer.fetch(pageId);

            if (candidate.records.length < this.maxRecords) {
                page = candidate;
                break;
            }
        }

        if (!page) {
            page = this.disk.allocate("HEAP");

            if (!this.tables.has(table)) {
                this.tables.set(table, []);
            }

            this.tables.get(table).push(page.id);
            await this.buffer.add(page);
        }

        const slot = page.records.length;

        const lsn = await this.wal.append(
            transaction.id,
            "INSERT",
            {
                table,
                row
            }
        );

        page.records.push(row);
        page.pageLSN = lsn;
        page.dirty = true;

        transaction.undo.push(async () => {
            const current = await this.buffer.fetch(page.id);

            const position = current.records.findIndex(
                record => record._rowId === row._rowId
            );

            if (position >= 0) {
                current.records.splice(position, 1);
                current.dirty = true;
            }

            for (const index of this.indexes.values()) {
                index.delete(row[index.column]);
            }
        });

        for (const index of this.indexes.values()) {
            if (
                index.table === table &&
                Object.hasOwn(row, index.column)
            ) {
                const value = row[index.column];

                if (index.entries.has(value)) {
                    await transaction.rollback();

                    throw new ValidationError(
                        `Duplicate index value: ${value}`
                    );
                }

                index.entries.set(value, {
                    pageId: page.id,
                    slot
                });
            }
        }

        this.emit("row:inserted", {
            transactionId: transaction.id,
            table,
            rowId: row._rowId
        });
    }

    async scan(table) {
        validateIdentifier(table);

        const rows = [];

        for (const pageId of this.tables.get(table) ?? []) {
            const page = await this.buffer.fetch(pageId);

            for (const record of page.records) {
                const {
                    _rowId,
                    _table,
                    ...visible
                } = record;

                rows.push(clone(visible));
            }
        }

        return rows;
    }

    async createIndex(table, column) {
        validateIdentifier(table);
        validateIdentifier(column);

        const name = `${table}.${column}`;

        if (this.indexes.has(name)) {
            throw new ValidationError("Index already exists.");
        }

        const entries = new Map();

        for (const pageId of this.tables.get(table) ?? []) {
            const page = await this.buffer.fetch(pageId);

            page.records.forEach((record, slot) => {
                if (!Object.hasOwn(record, column)) return;

                const value = record[column];

                if (entries.has(value)) {
                    throw new ValidationError(
                        `Duplicate index key: ${value}`
                    );
                }

                entries.set(value, {
                    pageId,
                    slot
                });
            });
        }

        this.indexes.set(name, {
            table,
            column,
            entries
        });

        this.emit("index:created", { table, column });
    }

    async indexLookup(table, column, value) {
        const index = this.indexes.get(
            `${table}.${column}`
        );

        if (!index) {
            throw new DatabaseError("Index not found.");
        }

        const location = index.entries.get(value);

        if (!location) return null;

        const page = await this.buffer.fetch(location.pageId);
        const row = page.records[location.slot];

        if (!row) {
            throw new StorageError("Stale index entry.");
        }

        const { _rowId, _table, ...visible } = row;

        return clone(visible);
    }
}

// ============================================================
// 5. TRANSACTION MANAGEMENT
// ============================================================

class Transaction {
    constructor(database, id) {
        this.database = database;
        this.id = id;
        this.state = TransactionState.ACTIVE;
        this.undo = [];
    }

    ensureActive() {
        if (this.state !== TransactionState.ACTIVE) {
            throw new TransactionError(
                "Transaction is no longer active."
            );
        }
    }

    async insert(table, row) {
        this.ensureActive();
        await this.database.insert(this, table, row);
    }

    async commit() {
        this.ensureActive();

        await this.database.wal.append(
            this.id,
            "COMMIT"
        );

        await this.database.wal.flush();
        await this.database.buffer.flushAll();

        this.state = TransactionState.COMMITTED;
        this.undo = [];

        this.database.emit("transaction:committed", {
            transactionId: this.id
        });
    }

    async rollback() {
        this.ensureActive();

        for (const undo of [...this.undo].reverse()) {
            await undo();
        }

        await this.database.wal.append(
            this.id,
            "ABORT"
        );

        await this.database.wal.flush();
        await this.database.buffer.flushAll();

        this.state = TransactionState.ABORTED;
        this.undo = [];

        this.database.emit("transaction:aborted", {
            transactionId: this.id
        });
    }
}

// ============================================================
// 6. QUERY EXECUTION PIPELINE
// ============================================================

class QueryExecutor {
    constructor(database) {
        this.database = database;
    }

    async execute(plan) {
        const started = performance.now();

        const rows = await this.executeNode(plan);

        return {
            rows,
            metrics: {
                returnedRows: rows.length,
                elapsedMilliseconds:
                    performance.now() - started
            }
        };
    }

    async executeNode(node) {
        switch (node.type) {
            case "SCAN":
                return this.database.scan(node.table);

            case "INDEX_LOOKUP": {
                const row = await this.database.indexLookup(
                    node.table,
                    node.column,
                    node.value
                );

                return row ? [row] : [];
            }

            case "FILTER": {
                const rows = await this.executeNode(node.child);

                return rows.filter(row => {
                    if (!Object.hasOwn(row, node.column)) {
                        throw new QueryExecutionError(
                            `Unknown column: ${node.column}`
                        );
                    }

                    return node.predicate(row[node.column]);
                });
            }

            case "PROJECT": {
                const rows = await this.executeNode(node.child);

                return rows.map(row => {
                    const projected = {};

                    for (const column of node.columns) {
                        if (!Object.hasOwn(row, column)) {
                            throw new QueryExecutionError(
                                `Unknown column: ${column}`
                            );
                        }

                        projected[column] = row[column];
                    }

                    return projected;
                });
            }

            case "SORT": {
                const rows = await this.executeNode(node.child);

                return rows.sort((a, b) => {
                    const left = a[node.column];
                    const right = b[node.column];

                    if (left === right) return 0;

                    const comparison = left < right ? -1 : 1;

                    return node.direction === "DESC"
                        ? -comparison
                        : comparison;
                });
            }

            case "LIMIT": {
                const rows = await this.executeNode(node.child);

                if (
                    !Number.isInteger(node.count) ||
                    node.count < 0
                ) {
                    throw new QueryExecutionError(
                        "Invalid LIMIT value."
                    );
                }

                return rows.slice(0, node.count);
            }

            case "HASH_JOIN":
                return this.hashJoin(node);

            case "HASH_AGGREGATE":
                return this.aggregate(node);

            default:
                throw new QueryExecutionError(
                    `Unsupported operator: ${node.type}`
                );
        }
    }

    async hashJoin(node) {
        const [leftRows, rightRows] = await Promise.all([
            this.executeNode(node.left),
            this.executeNode(node.right)
        ]);

        const hashTable = new Map();

        for (const row of leftRows) {
            const key = row[node.leftKey];

            if (!hashTable.has(key)) {
                hashTable.set(key, []);
            }

            hashTable.get(key).push(row);
        }

        const results = [];

        for (const right of rightRows) {
            const matches = hashTable.get(
                right[node.rightKey]
            ) ?? [];

            for (const left of matches) {
                const merged = { ...left };

                for (const [key, value] of Object.entries(right)) {
                    const destination = Object.hasOwn(
                        merged,
                        key
                    )
                        ? `right_${key}`
                        : key;

                    merged[destination] = value;
                }

                results.push(merged);
            }
        }

        return results;
    }

    async aggregate(node) {
        const rows = await this.executeNode(node.child);
        const groups = new Map();

        for (const row of rows) {
            const key = row[node.groupColumn];
            const value = row[node.aggregateColumn];

            if (typeof value !== "number" ||
                !Number.isFinite(value)) {
                throw new QueryExecutionError(
                    "Aggregate input must be a finite number."
                );
            }

            if (!groups.has(key)) {
                groups.set(key, {
                    count: 0,
                    sum: 0,
                    minimum: Infinity,
                    maximum: -Infinity
                });
            }

            const group = groups.get(key);

            group.count++;
            group.sum += value;
            group.minimum = Math.min(group.minimum, value);
            group.maximum = Math.max(group.maximum, value);
        }

        return [...groups.entries()].map(([key, value]) => ({
            [node.groupColumn]: key,
            ...value,
            average: value.sum / value.count
        }));
    }
}

// ============================================================
// 7. QUERY COST AND PLAN EVALUATION
// ============================================================

class QueryOptimizer {
    estimateScanCost(rowCount, rowsPerPage) {
        return Math.ceil(rowCount / rowsPerPage);
    }

    estimateIndexCost(rowCount, distinctCount) {
        if (rowCount <= 0 || distinctCount <= 0) {
            return Infinity;
        }

        const treeHeight = Math.log2(rowCount);
        const estimatedMatches = rowCount / distinctCount;

        return treeHeight + estimatedMatches;
    }

    chooseAccessPath({
        rowCount,
        distinctCount,
        rowsPerPage = 64
    }) {
        const scanCost = this.estimateScanCost(
            rowCount,
            rowsPerPage
        );

        const indexCost = this.estimateIndexCost(
            rowCount,
            distinctCount
        );

        return {
            selected: indexCost < scanCost
                ? "INDEX_SCAN"
                : "TABLE_SCAN",
            scanCost,
            indexCost
        };
    }
}

// ============================================================
// 8. DEMONSTRATION
// ============================================================

async function main() {
    const directory = path.join(
        process.cwd(),
        "database_internals_demo"
    );

    const database = await new DatabaseEngine(
        directory,
        {
            bufferCapacity: 2,
            maxRecordsPerPage: 3
        }
    ).initialize();

    database.on("database:ready", event => {
        console.log("Database ready:", event);
    });

    database.on("row:inserted", event => {
        console.log("Inserted:", event);
    });

    database.on("transaction:committed", event => {
        console.log("Committed:", event);
    });

    const transaction = database.beginTransaction();

    try {
        await transaction.insert("employees", {
            employeeId: 201,
            name: "Asha",
            department: "Engineering",
            salary: 90000
        });

        await transaction.insert("employees", {
            employeeId: 202,
            name: "Ravi",
            department: "Engineering",
            salary: 85000
        });

        await transaction.insert("employees", {
            employeeId: 203,
            name: "Meera",
            department: "Research",
            salary: 110000
        });

        await transaction.insert("employees", {
            employeeId: 204,
            name: "Kabir",
            department: "Research",
            salary: 95000
        });

        await transaction.commit();
    } catch (error) {
        if (transaction.state === TransactionState.ACTIVE) {
            await transaction.rollback();
        }

        throw error;
    }

    await database.createIndex(
        "employees",
        "employeeId"
    );

    const executor = new QueryExecutor(database);

    const plan = {
        type: "SORT",
        column: "salary",
        direction: "DESC",
        child: {
            type: "PROJECT",
            columns: ["name", "department", "salary"],
            child: {
                type: "FILTER",
                column: "salary",
                predicate: value => value >= 90000,
                child: {
                    type: "SCAN",
                    table: "employees"
                }
            }
        }
    };

    const result = await executor.execute(plan);

    console.log("\nQUERY RESULTS");
    console.table(result.rows);
    console.log("Query metrics:", result.metrics);

    console.log("\nINDEX LOOKUP");
    console.log(
        await database.indexLookup(
            "employees",
            "employeeId",
            203
        )
    );

    const aggregation = await executor.execute({
        type: "HASH_AGGREGATE",
        groupColumn: "department",
        aggregateColumn: "salary",
        child: {
            type: "SCAN",
            table: "employees"
        }
    });

    console.log("\nAGGREGATION");
    console.table(aggregation.rows);

    const optimizer = new QueryOptimizer();

    console.log("\nACCESS PATH DECISION");

    console.log(optimizer.chooseAccessPath({
        rowCount: 100000,
        distinctCount: 100000,
        rowsPerPage: 64
    }));

    console.log("\nBUFFER POOL");
    console.log(database.buffer.statistics);
    console.log("Hit ratio:", database.buffer.hitRatio());

    console.log("\nDISK OPERATIONS");
    console.log({
        reads: database.disk.reads,
        writes: database.disk.writes
    });

    console.log("\nWAL RECORDS");
    console.log(database.wal.records.length);
}

main().catch(error => {
    console.error("Database execution failed:", error);
    process.exitCode = 1;
});
