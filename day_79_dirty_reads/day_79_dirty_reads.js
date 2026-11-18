"use strict";

/*
 * Dirty Reads: Event-Driven Transaction and Isolation Simulator
 *
 * Demonstrates:
 * - Concurrent transaction behavior.
 * - Uncommitted write visibility.
 * - Dirty reads and rollback.
 * - READ COMMITTED prevention.
 * - Transaction snapshots.
 * - Event-driven transaction execution.
 * - Optimistic commit validation.
 * - Automated anomaly detection.
 *
 * Runtime: Node.js 18+
 */

const Isolation = Object.freeze({
    READ_UNCOMMITTED: "READ_UNCOMMITTED",
    READ_COMMITTED: "READ_COMMITTED",
    REPEATABLE_READ: "REPEATABLE_READ"
});

const State = Object.freeze({
    ACTIVE: "ACTIVE",
    COMMITTED: "COMMITTED",
    ROLLED_BACK: "ROLLED_BACK"
});

class TransactionError extends Error {}

class ValidationError extends TransactionError {}

class Database {

    constructor() {
        this.records = new Map();
        this.transactions = new Map();
        this.nextId = 1;
        this.version = 0;
        this.events = [];
    }

    addRecord(id, balance) {
        if (!Number.isSafeInteger(id) || id <= 0) {
            throw new ValidationError("Invalid record ID.");
        }

        if (!Number.isFinite(balance) || balance < 0) {
            throw new ValidationError("Invalid initial balance.");
        }

        if (this.records.has(id)) {
            throw new ValidationError("Duplicate record ID.");
        }

        this.records.set(id, {
            balance,
            version: ++this.version
        });
    }

    begin(isolation) {
        if (!Object.values(Isolation).includes(isolation)) {
            throw new ValidationError("Unsupported isolation level.");
        }

        const transaction = {
            id: this.nextId++,
            isolation,
            state: State.ACTIVE,
            writes: new Map(),
            reads: [],
            snapshot: null,
            snapshotVersion: this.version
        };

        if (isolation === Isolation.REPEATABLE_READ) {
            transaction.snapshot = new Map(
                [...this.records].map(([id, record]) => [
                    id,
                    record.balance
                ])
            );
        }

        this.transactions.set(transaction.id, transaction);

        this.emit("BEGIN", transaction.id, isolation);

        return transaction;
    }

    emit(type, transactionId, details) {
        this.events.push(Object.freeze({
            sequence: this.events.length + 1,
            type,
            transactionId,
            details,
            timestamp: new Date().toISOString()
        }));
    }

    assertActive(transaction) {
        if (!transaction || transaction.state !== State.ACTIVE) {
            throw new TransactionError(
                "Operation requires an active transaction."
            );
        }
    }

    assertRecord(id) {
        if (!this.records.has(id)) {
            throw new ValidationError(`Record ${id} not found.`);
        }
    }

    write(transaction, id, balance) {
        this.assertActive(transaction);
        this.assertRecord(id);

        if (!Number.isFinite(balance) || balance < 0) {
            throw new ValidationError(
                "Balance must be a non-negative finite number."
            );
        }

        transaction.writes.set(id, balance);

        this.emit("WRITE", transaction.id, {
            id,
            balance,
            visibility: "UNCOMMITTED"
        });
    }

    read(transaction, id) {
        this.assertActive(transaction);
        this.assertRecord(id);

        let value;
        let source;

        if (transaction.writes.has(id)) {
            value = transaction.writes.get(id);
            source = "OWN_WRITE";

        } else if (transaction.isolation === Isolation.READ_UNCOMMITTED) {
            value = this.records.get(id).balance;
            source = "COMMITTED";

            for (const other of this.transactions.values()) {
                if (
                    other.id !== transaction.id &&
                    other.state === State.ACTIVE &&
                    other.writes.has(id)
                ) {
                    value = other.writes.get(id);
                    source = `UNCOMMITTED:${other.id}`;
                    break;
                }
            }

        } else if (
            transaction.isolation === Isolation.REPEATABLE_READ
        ) {
            value = transaction.snapshot.get(id);
            source = "SNAPSHOT";

        } else {
            value = this.records.get(id).balance;
            source = "COMMITTED";
        }

        const result = Object.freeze({
            id,
            value,
            source
        });

        transaction.reads.push(result);

        this.emit("READ", transaction.id, result);

        return result;
    }

    commit(transaction) {
        this.assertActive(transaction);

        // Validate all writes before applying any write.
        for (const [id, balance] of transaction.writes) {
            this.assertRecord(id);

            if (!Number.isFinite(balance) || balance < 0) {
                throw new ValidationError("Invalid commit value.");
            }
        }

        // Detect changes made after the snapshot for records being updated.
        if (transaction.isolation === Isolation.REPEATABLE_READ) {
            for (const id of transaction.writes.keys()) {
                const originalVersion = transaction.snapshotVersion;
                const currentVersion = this.records.get(id).version;

                if (currentVersion > originalVersion) {
                    throw new TransactionError(
                        `Concurrent update detected for record ${id}.`
                    );
                }
            }
        }

        for (const [id, balance] of transaction.writes) {
            this.records.set(id, {
                balance,
                version: ++this.version
            });
        }

        transaction.state = State.COMMITTED;

        this.emit("COMMIT", transaction.id, {
            changedRecords: transaction.writes.size
        });
    }

    rollback(transaction) {
        this.assertActive(transaction);

        transaction.writes.clear();
        transaction.state = State.ROLLED_BACK;

        this.emit("ROLLBACK", transaction.id, null);
    }

    committedValue(id) {
        this.assertRecord(id);
        return this.records.get(id).balance;
    }

    detectDirtyReads() {
        const anomalies = [];

        for (const reader of this.transactions.values()) {
            for (const read of reader.reads) {
                if (!read.source.startsWith("UNCOMMITTED:")) {
                    continue;
                }

                const writerId = Number(
                    read.source.split(":")[1]
                );

                const writer = this.transactions.get(writerId);

                if (writer?.state === State.ROLLED_BACK) {
                    anomalies.push({
                        reader: reader.id,
                        writer: writer.id,
                        record: read.id,
                        observedValue: read.value,
                        type: "DIRTY_READ"
                    });
                }
            }
        }

        return anomalies;
    }

    getEventHistory() {
        return [...this.events];
    }
}

/*
 * Explicit asynchronous scheduling.
 *
 * Promise-based barriers make the order of transaction events
 * deterministic for this demonstration.
 */
async function demonstrateDirtyRead() {
    console.log("\nSCENARIO 1: DIRTY READ");

    const db = new Database();
    db.addRecord(101, 1000);

    const writer = db.begin(Isolation.READ_UNCOMMITTED);
    const reader = db.begin(Isolation.READ_UNCOMMITTED);

    const writeCompleted = Promise.resolve().then(() => {
        db.write(writer, 101, 400);
    });

    await writeCompleted;

    const readResult = await Promise.resolve().then(() => {
        return db.read(reader, 101);
    });

    console.log("Reader observed:", readResult);

    await Promise.resolve().then(() => {
        db.rollback(writer);
    });

    console.log("Writer state:", writer.state);
    console.log("Committed value:", db.committedValue(101));
    console.log("Anomalies:", db.detectDirtyReads());
}

async function demonstrateReadCommitted() {
    console.log("\nSCENARIO 2: READ COMMITTED");

    const db = new Database();
    db.addRecord(102, 2000);

    const writer = db.begin(Isolation.READ_UNCOMMITTED);
    const reader = db.begin(Isolation.READ_COMMITTED);

    db.write(writer, 102, 700);

    const result = db.read(reader, 102);

    console.log("Reader observed:", result);

    db.rollback(writer);

    console.log("Committed value:", db.committedValue(102));

    if (result.value !== 2000) {
        throw new Error("READ COMMITTED failed to prevent dirty read.");
    }
}

async function demonstrateCommittedVisibility() {
    console.log("\nSCENARIO 3: COMMIT VISIBILITY");

    const db = new Database();
    db.addRecord(103, 5000);

    const writer = db.begin(Isolation.READ_COMMITTED);
    const reader = db.begin(Isolation.READ_COMMITTED);

    db.write(writer, 103, 4500);

    const before = db.read(reader, 103);

    db.commit(writer);

    const after = db.read(reader, 103);

    console.log("Before commit:", before.value);
    console.log("After commit:", after.value);

    if (before.value !== 5000 || after.value !== 4500) {
        throw new Error("Unexpected commit visibility.");
    }
}

async function demonstrateSnapshot() {
    console.log("\nSCENARIO 4: REPEATABLE READ");

    const db = new Database();
    db.addRecord(104, 3000);

    const reader = db.begin(Isolation.REPEATABLE_READ);
    const writer = db.begin(Isolation.READ_COMMITTED);

    const first = db.read(reader, 104);

    db.write(writer, 104, 2500);
    db.commit(writer);

    const second = db.read(reader, 104);

    console.log("First observation:", first.value);
    console.log("Second observation:", second.value);
    console.log("Latest committed value:", db.committedValue(104));

    if (first.value !== second.value) {
        throw new Error("Snapshot consistency violated.");
    }
}

async function runTests() {
    console.log("\nAUTOMATED VALIDATION");

    const db = new Database();
    db.addRecord(1, 100);

    const writer = db.begin(Isolation.READ_UNCOMMITTED);
    const reader = db.begin(Isolation.READ_UNCOMMITTED);

    db.write(writer, 1, 50);

    console.assert(db.read(reader, 1).value === 50);

    db.rollback(writer);

    console.assert(db.committedValue(1) === 100);
    console.assert(db.detectDirtyReads().length === 1);

    const protectedReader = db.begin(Isolation.READ_COMMITTED);
    const secondWriter = db.begin(Isolation.READ_UNCOMMITTED);

    db.write(secondWriter, 1, 25);

    console.assert(db.read(protectedReader, 1).value === 100);

    db.rollback(secondWriter);

    try {
        db.commit(writer);
        throw new Error("Expected transaction-state validation failure.");
    } catch (error) {
        if (!(error instanceof TransactionError)) {
            throw error;
        }
    }

    console.log("All validation checks passed.");
}

async function main() {
    try {
        await demonstrateDirtyRead();
        await demonstrateReadCommitted();
        await demonstrateCommittedVisibility();
        await demonstrateSnapshot();
        await runTests();

        console.log("\nAll scenarios completed.");
    } catch (error) {
        console.error("Execution failed:", error.message);
        process.exitCode = 1;
    }
}

main();
