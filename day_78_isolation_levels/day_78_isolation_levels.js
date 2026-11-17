"use strict";

/*
 * Database Transaction Isolation Laboratory
 *
 * Demonstrates:
 * - Read Uncommitted
 * - Read Committed
 * - Repeatable Read
 * - Serializable
 *
 * Uses an asynchronous transaction scheduler, versioned records,
 * transaction-local writes, optimistic validation, and commit events.
 *
 * Run with Node.js 18 or later.
 */

const { EventEmitter } = require("node:events");
const { randomUUID } = require("node:crypto");

const IsolationLevel = Object.freeze({
    READ_UNCOMMITTED: "READ UNCOMMITTED",
    READ_COMMITTED: "READ COMMITTED",
    REPEATABLE_READ: "REPEATABLE READ",
    SERIALIZABLE: "SERIALIZABLE"
});

const TransactionState = Object.freeze({
    ACTIVE: "ACTIVE",
    COMMITTED: "COMMITTED",
    ABORTED: "ABORTED"
});

class TransactionError extends Error {}
class SerializationError extends TransactionError {}
class WriteConflictError extends TransactionError {}
class ValidationError extends TransactionError {}

class Transaction {
    constructor(id, isolation, snapshot) {
        this.id = id;
        this.isolation = isolation;
        this.state = TransactionState.ACTIVE;
        this.snapshot = new Map(snapshot);
        this.writes = new Map();
        this.readVersions = new Map();
        this.writeVersions = new Map();
        this.startedAt = Date.now();
    }

    ensureActive() {
        if (this.state !== TransactionState.ACTIVE) {
            throw new TransactionError(
                `Transaction ${this.id} is ${this.state}`
            );
        }
    }
}

class TransactionalDatabase extends EventEmitter {
    constructor(initialData = {}) {
        super();

        this.records = new Map();
        this.pendingWrites = new Map();
        this.transactions = new Map();
        this.version = 0;

        for (const [key, value] of Object.entries(initialData)) {
            this.records.set(key, {
                value,
                version: ++this.version
            });
        }
    }

    begin(isolation) {
        if (!Object.values(IsolationLevel).includes(isolation)) {
            throw new ValidationError("Unsupported isolation level");
        }

        const snapshot = new Map(
            [...this.records.entries()].map(
                ([key, record]) => [
                    key,
                    { value: record.value, version: record.version }
                ]
            )
        );

        const transaction = new Transaction(
            randomUUID(),
            isolation,
            snapshot
        );

        this.transactions.set(transaction.id, transaction);

        this.emit("begin", {
            id: transaction.id,
            isolation
        });

        return transaction;
    }

    getCommittedView(transaction) {
        if (
            transaction.isolation === IsolationLevel.REPEATABLE_READ ||
            transaction.isolation === IsolationLevel.SERIALIZABLE
        ) {
            return transaction.snapshot;
        }

        return this.records;
    }

    read(transaction, key) {
        transaction.ensureActive();

        if (transaction.writes.has(key)) {
            return transaction.writes.get(key);
        }

        // PostgreSQL does not expose uncommitted changes even when
        // READ UNCOMMITTED is requested.
        const view = this.getCommittedView(transaction);
        const record = view.get(key);

        if (!record) {
            throw new ValidationError(`Record not found: ${key}`);
        }

        if (!transaction.readVersions.has(key)) {
            transaction.readVersions.set(key, record.version);
        }

        return record.value;
    }

    write(transaction, key, value) {
        transaction.ensureActive();

        if (!this.records.has(key)) {
            throw new ValidationError(`Unknown record: ${key}`);
        }

        if (
            typeof value !== "number" ||
            !Number.isFinite(value)
        ) {
            throw new ValidationError("Value must be a finite number");
        }

        transaction.writes.set(key, value);

        if (!transaction.writeVersions.has(key)) {
            transaction.writeVersions.set(
                key,
                this.records.get(key).version
            );
        }

        if (!this.pendingWrites.has(transaction.id)) {
            this.pendingWrites.set(transaction.id, new Map());
        }

        this.pendingWrites.get(transaction.id).set(key, value);

        this.emit("write", {
            transactionId: transaction.id,
            key,
            value
        });
    }

    validate(transaction) {
        // Write-write conflict detection.
        for (const [key, originalVersion] of transaction.writeVersions) {
            const current = this.records.get(key);

            if (!current || current.version !== originalVersion) {
                throw new WriteConflictError(
                    `Concurrent modification: ${key}`
                );
            }
        }

        if (transaction.isolation === IsolationLevel.SERIALIZABLE) {
            // Simplified optimistic validation. A production serializable
            // engine also needs predicate and dependency tracking.
            for (const [key, originalVersion] of transaction.readVersions) {
                if (transaction.writes.has(key)) {
                    continue;
                }

                const current = this.records.get(key);

                if (!current || current.version !== originalVersion) {
                    throw new SerializationError(
                        `Read dependency changed: ${key}`
                    );
                }
            }
        }
    }

    async commit(transaction) {
        transaction.ensureActive();

        try {
            this.validate(transaction);

            // No await is permitted between validation and publication.
            // JavaScript executes this section without event-loop interleaving.
            for (const [key, value] of transaction.writes) {
                this.records.set(key, {
                    value,
                    version: ++this.version
                });
            }

            transaction.state = TransactionState.COMMITTED;
            this.pendingWrites.delete(transaction.id);

            const result = {
                id: transaction.id,
                isolation: transaction.isolation,
                writes: Object.fromEntries(transaction.writes),
                durationMs: Date.now() - transaction.startedAt
            };

            this.emit("commit", result);

            return result;
        } catch (error) {
            this.rollback(transaction);
            throw error;
        }
    }

    rollback(transaction) {
        transaction.ensureActive();

        transaction.writes.clear();
        transaction.state = TransactionState.ABORTED;

        this.pendingWrites.delete(transaction.id);

        this.emit("rollback", {
            id: transaction.id
        });
    }

    inspect() {
        return Object.fromEntries(
            [...this.records.entries()].map(
                ([key, record]) => [key, record.value]
            )
        );
    }
}

class TransferService {
    constructor(database) {
        this.database = database;
    }

    async transfer(source, destination, amount) {
        if (
            typeof amount !== "number" ||
            !Number.isFinite(amount) ||
            amount <= 0
        ) {
            throw new ValidationError(
                "Transfer amount must be a positive finite number"
            );
        }

        const transaction = this.database.begin(
            IsolationLevel.SERIALIZABLE
        );

        try {
            const sourceBalance = this.database.read(
                transaction,
                source
            );

            const destinationBalance = this.database.read(
                transaction,
                destination
            );

            if (sourceBalance < amount) {
                throw new TransactionError("Insufficient funds");
            }

            this.database.write(
                transaction,
                source,
                sourceBalance - amount
            );

            this.database.write(
                transaction,
                destination,
                destinationBalance + amount
            );

            return await this.database.commit(transaction);
        } catch (error) {
            if (transaction.state === TransactionState.ACTIVE) {
                this.database.rollback(transaction);
            }

            throw error;
        }
    }
}

async function demonstrateReadCommitted() {
    console.log("\n1. READ COMMITTED");

    const db = new TransactionalDatabase({
        inventory: 100
    });

    const reader = db.begin(IsolationLevel.READ_COMMITTED);
    const writer = db.begin(IsolationLevel.READ_COMMITTED);

    const first = db.read(reader, "inventory");

    db.write(writer, "inventory", 75);
    await db.commit(writer);

    const second = db.read(reader, "inventory");

    console.log({ first, second });

    if (first === second) {
        throw new Error("Expected a non-repeatable read");
    }

    db.rollback(reader);
}

async function demonstrateRepeatableRead() {
    console.log("\n2. REPEATABLE READ");

    const db = new TransactionalDatabase({
        inventory: 100
    });

    const reader = db.begin(IsolationLevel.REPEATABLE_READ);
    const writer = db.begin(IsolationLevel.READ_COMMITTED);

    const first = db.read(reader, "inventory");

    db.write(writer, "inventory", 50);
    await db.commit(writer);

    const second = db.read(reader, "inventory");

    console.log({ first, second });

    if (first !== second) {
        throw new Error("Snapshot consistency violated");
    }

    await db.commit(reader);
}

async function demonstrateConcurrentWrites() {
    console.log("\n3. CONCURRENT WRITE CONFLICT");

    const db = new TransactionalDatabase({
        stock: 200
    });

    const first = db.begin(IsolationLevel.REPEATABLE_READ);
    const second = db.begin(IsolationLevel.REPEATABLE_READ);

    db.write(first, "stock", 150);
    db.write(second, "stock", 120);

    await db.commit(first);

    try {
        await db.commit(second);
        throw new Error("Expected a write conflict");
    } catch (error) {
        if (!(error instanceof WriteConflictError)) {
            throw error;
        }

        console.log(error.message);
    }

    console.log("Final stock:", db.inspect().stock);
}

async function demonstrateSerializable() {
    console.log("\n4. SERIALIZABLE");

    const db = new TransactionalDatabase({
        account: 1000
    });

    const reader = db.begin(IsolationLevel.SERIALIZABLE);
    const writer = db.begin(IsolationLevel.READ_COMMITTED);

    const observed = db.read(reader, "account");

    db.write(writer, "account", 800);
    await db.commit(writer);

    console.log("Snapshot value:", observed);
    console.log("Committed value:", db.inspect().account);

    try {
        await db.commit(reader);
    } catch (error) {
        console.log("Serialization failure:", error.message);
    }
}

async function demonstrateTransfer() {
    console.log("\n5. SERIALIZABLE TRANSFER");

    const db = new TransactionalDatabase({
        accountA: 5000,
        accountB: 3000
    });

    db.on("commit", event => {
        console.log(
            "Committed transaction:",
            event.id.slice(0, 8),
            event.isolation
        );
    });

    db.on("rollback", event => {
        console.log(
            "Rolled back:",
            event.id.slice(0, 8)
        );
    });

    const service = new TransferService(db);

    await service.transfer("accountA", "accountB", 1000);

    console.log("Balances:", db.inspect());

    if (
        db.inspect().accountA !== 4000 ||
        db.inspect().accountB !== 4000
    ) {
        throw new Error("Transfer integrity failure");
    }
}

async function run() {
    console.log("DATABASE ISOLATION AND CONCURRENCY LAB");

    await demonstrateReadCommitted();
    await demonstrateRepeatableRead();
    await demonstrateConcurrentWrites();
    await demonstrateSerializable();
    await demonstrateTransfer();

    console.log("\nAll JavaScript demonstrations completed.");
}

run().catch(error => {
    console.error("Execution failed:", error.message);
    process.exitCode = 1;
});
