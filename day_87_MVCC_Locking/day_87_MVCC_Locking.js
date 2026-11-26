"use strict";

/*
 * MVCC vs Locking: Event-Driven Concurrency Architecture.
 *
 * Features:
 * - Asynchronous transaction scheduling.
 * - MVCC snapshot visibility.
 * - Optimistic conflict detection.
 * - FIFO pessimistic lock queues.
 * - Lock ownership.
 * - Transaction timeouts.
 * - Atomic commit operations.
 * - Rollback and failure handling.
 * - Workload architecture evaluation.
 *
 * Runtime: Node.js 18+
 * Dependencies: Node.js standard library only.
 */

const { EventEmitter } = require("node:events");
const { randomUUID } = require("node:crypto");


class ConcurrencyError extends Error {
    constructor(message) {
        super(message);
        this.name = this.constructor.name;
    }
}

class WriteConflict extends ConcurrencyError {}
class LockTimeout extends ConcurrencyError {}
class TransactionStateError extends ConcurrencyError {}


const TransactionStatus = Object.freeze({
    ACTIVE: "ACTIVE",
    COMMITTED: "COMMITTED",
    ABORTED: "ABORTED"
});


class Metrics {
    constructor() {
        this.started = 0;
        this.committed = 0;
        this.aborted = 0;
        this.conflicts = 0;
        this.lockWaits = 0;
        this.reads = 0;
        this.writes = 0;
    }

    snapshot() {
        return Object.freeze({
            started: this.started,
            committed: this.committed,
            aborted: this.aborted,
            conflicts: this.conflicts,
            lockWaits: this.lockWaits,
            reads: this.reads,
            writes: this.writes,
            commitRate: this.started === 0
                ? 0
                : Number(
                    (this.committed / this.started * 100).toFixed(2)
                )
        });
    }
}


class EventDrivenStore extends EventEmitter {
    constructor(initialData = {}) {
        super();

        this.clock = 0;
        this.versions = new Map();
        this.metrics = new Metrics();

        for (const [key, value] of Object.entries(initialData)) {
            this.versions.set(key, [
                Object.freeze({
                    timestamp: 0,
                    value: structuredClone(value)
                })
            ]);
        }
    }

    begin() {
        this.metrics.started++;

        const transaction = {
            id: randomUUID(),
            snapshot: this.clock,
            status: TransactionStatus.ACTIVE,
            writes: new Map(),
            reads: new Set()
        };

        this.emit("transaction:begin", {
            id: transaction.id,
            snapshot: transaction.snapshot
        });

        return transaction;
    }

    assertActive(transaction) {
        if (transaction.status !== TransactionStatus.ACTIVE) {
            throw new TransactionStateError(
                `Transaction ${transaction.id} is ${transaction.status}`
            );
        }
    }

    visibleVersion(key, snapshot) {
        const versions = this.versions.get(key) || [];

        for (let i = versions.length - 1; i >= 0; i--) {
            if (versions[i].timestamp <= snapshot) {
                return versions[i];
            }
        }

        return undefined;
    }

    read(transaction, key) {
        this.assertActive(transaction);
        this.metrics.reads++;

        if (transaction.writes.has(key)) {
            return structuredClone(transaction.writes.get(key));
        }

        const version = this.visibleVersion(
            key,
            transaction.snapshot
        );

        transaction.reads.add(key);

        return version
            ? structuredClone(version.value)
            : undefined;
    }

    write(transaction, key, value) {
        this.assertActive(transaction);

        if (typeof key !== "string" || key.length === 0) {
            throw new TypeError("A non-empty string key is required");
        }

        transaction.writes.set(key, structuredClone(value));

        this.emit("transaction:write", {
            id: transaction.id,
            key
        });
    }

    commit(transaction) {
        this.assertActive(transaction);

        // Validate all writes before publishing any version.
        for (const key of transaction.writes.keys()) {
            const versions = this.versions.get(key) || [];
            const latest = versions.at(-1);

            if (
                latest &&
                latest.timestamp > transaction.snapshot
            ) {
                transaction.status = TransactionStatus.ABORTED;
                this.metrics.aborted++;
                this.metrics.conflicts++;

                this.emit("transaction:conflict", {
                    id: transaction.id,
                    key
                });

                return false;
            }
        }

        this.clock++;

        for (const [key, value] of transaction.writes) {
            if (!this.versions.has(key)) {
                this.versions.set(key, []);
            }

            this.versions.get(key).push(
                Object.freeze({
                    timestamp: this.clock,
                    value: structuredClone(value)
                })
            );

            this.metrics.writes++;
        }

        transaction.status = TransactionStatus.COMMITTED;
        this.metrics.committed++;

        this.emit("transaction:commit", {
            id: transaction.id,
            timestamp: this.clock
        });

        return true;
    }

    rollback(transaction) {
        this.assertActive(transaction);

        transaction.writes.clear();
        transaction.status = TransactionStatus.ABORTED;

        this.metrics.aborted++;

        this.emit("transaction:rollback", {
            id: transaction.id
        });
    }
}


class LockManager {
    constructor() {
        this.owners = new Map();
        this.queues = new Map();
    }

    acquire(key, transactionId, timeoutMs = 2000) {
        const owner = this.owners.get(key);

        if (!owner) {
            this.owners.set(key, transactionId);
            return Promise.resolve();
        }

        if (owner === transactionId) {
            return Promise.resolve();
        }

        return new Promise((resolve, reject) => {
            const queue = this.queues.get(key) || [];

            const request = {
                transactionId,
                resolve,
                reject,
                timer: null
            };

            request.timer = setTimeout(() => {
                const current = this.queues.get(key) || [];
                const index = current.indexOf(request);

                if (index !== -1) {
                    current.splice(index, 1);
                }

                reject(
                    new LockTimeout(`Lock timeout for ${key}`)
                );
            }, timeoutMs);

            queue.push(request);
            this.queues.set(key, queue);
        });
    }

    release(key, transactionId) {
        if (this.owners.get(key) !== transactionId) {
            return false;
        }

        const queue = this.queues.get(key) || [];
        const next = queue.shift();

        if (next) {
            clearTimeout(next.timer);

            // Transfer ownership before waking the next transaction.
            this.owners.set(key, next.transactionId);

            if (queue.length === 0) {
                this.queues.delete(key);
            }

            next.resolve();
        } else {
            this.owners.delete(key);
            this.queues.delete(key);
        }

        return true;
    }
}


class PessimisticStore extends EventEmitter {
    constructor(initialData = {}) {
        super();

        this.data = new Map(
            Object.entries(initialData).map(
                ([key, value]) => [key, structuredClone(value)]
            )
        );

        this.manager = new LockManager();
        this.metrics = new Metrics();
    }

    begin() {
        this.metrics.started++;

        return {
            id: randomUUID(),
            status: TransactionStatus.ACTIVE,
            writes: new Map(),
            heldLocks: new Set()
        };
    }

    assertActive(transaction) {
        if (transaction.status !== TransactionStatus.ACTIVE) {
            throw new TransactionStateError(
                `Transaction ${transaction.id} is ${transaction.status}`
            );
        }
    }

    async lock(transaction, key, timeoutMs) {
        this.assertActive(transaction);

        if (transaction.heldLocks.has(key)) {
            return;
        }

        if (this.manager.owners.has(key)) {
            this.metrics.lockWaits++;
        }

        try {
            await this.manager.acquire(
                key,
                transaction.id,
                timeoutMs
            );

            transaction.heldLocks.add(key);
        } catch (error) {
            // A failed acquisition aborts the transaction.
            this.rollback(transaction);
            throw error;
        }
    }

    async read(transaction, key, timeoutMs = 2000) {
        await this.lock(transaction, key, timeoutMs);

        this.metrics.reads++;

        if (transaction.writes.has(key)) {
            return structuredClone(transaction.writes.get(key));
        }

        return structuredClone(this.data.get(key));
    }

    async write(
        transaction,
        key,
        value,
        timeoutMs = 2000
    ) {
        await this.lock(transaction, key, timeoutMs);

        transaction.writes.set(key, structuredClone(value));
    }

    releaseAll(transaction) {
        for (const key of transaction.heldLocks) {
            this.manager.release(key, transaction.id);
        }

        transaction.heldLocks.clear();
    }

    commit(transaction) {
        this.assertActive(transaction);

        // JavaScript executes this synchronous publication without
        // another event-loop callback interleaving in the middle.
        for (const [key, value] of transaction.writes) {
            this.data.set(key, structuredClone(value));
            this.metrics.writes++;
        }

        transaction.status = TransactionStatus.COMMITTED;
        this.metrics.committed++;

        this.releaseAll(transaction);

        this.emit("transaction:commit", transaction.id);

        return true;
    }

    rollback(transaction) {
        if (transaction.status !== TransactionStatus.ACTIVE) {
            return;
        }

        transaction.writes.clear();
        transaction.status = TransactionStatus.ABORTED;

        this.metrics.aborted++;

        this.releaseAll(transaction);

        this.emit("transaction:rollback", transaction.id);
    }
}


class ArchitectureEvaluator {
    static evaluate({
        readRatio,
        contention,
        transactionDuration,
        writeHotspot
    }) {
        const values = [
            readRatio,
            contention,
            transactionDuration,
            writeHotspot
        ];

        if (values.some(value => !Number.isFinite(value))) {
            throw new TypeError("All workload parameters must be finite");
        }

        if (
            readRatio < 0 || readRatio > 1 ||
            contention < 0 || contention > 1 ||
            transactionDuration < 0 ||
            writeHotspot < 0 || writeHotspot > 1
        ) {
            throw new RangeError("Invalid workload parameter");
        }

        const mvccScore =
            60 * readRatio +
            25 * (1 - contention) +
            15 * (1 - writeHotspot) -
            Math.min(transactionDuration / 1000, 20);

        const lockingScore =
            50 * contention +
            30 * writeHotspot +
            20 * Math.min(transactionDuration / 1000, 1);

        return Object.freeze({
            mvccScore: Number(mvccScore.toFixed(2)),
            lockingScore: Number(lockingScore.toFixed(2)),
            preferredModel: mvccScore >= lockingScore
                ? "MVCC"
                : "PESSIMISTIC_LOCKING"
        });
    }
}


async function demonstrateMVCC() {
    console.log("\n=== EVENT-DRIVEN MVCC ===");

    const store = new EventDrivenStore({
        inventory: 100
    });

    store.on("transaction:conflict", event => {
        console.log("Conflict detected:", event.key);
    });

    const first = store.begin();
    const second = store.begin();

    console.log("First snapshot:", store.read(first, "inventory"));
    console.log("Second snapshot:", store.read(second, "inventory"));

    store.write(first, "inventory", 90);
    store.write(second, "inventory", 80);

    console.log("First commit:", store.commit(first));
    console.log("Second commit:", store.commit(second));

    console.log("Metrics:", store.metrics.snapshot());
}


async function demonstrateLocking() {
    console.log("\n=== ASYNCHRONOUS PESSIMISTIC LOCKING ===");

    const store = new PessimisticStore({
        stock: 50
    });

    const first = store.begin();
    const second = store.begin();

    console.log("First reads:", await store.read(first, "stock"));

    const waiting = store.read(second, "stock");

    store.write(first, "stock", 40);
    store.commit(first);

    console.log("Second reads after lock release:", await waiting);

    store.write(second, "stock", 35);
    store.commit(second);

    console.log("Final stock:", store.data.get("stock"));
    console.log("Metrics:", store.metrics.snapshot());
}


async function demonstrateFailureHandling() {
    console.log("\n=== FAILURE HANDLING ===");

    const store = new PessimisticStore({
        account: 1000
    });

    const first = store.begin();
    const second = store.begin();

    await store.read(first, "account");

    try {
        await store.read(second, "account", 100);
    } catch (error) {
        console.log("Expected failure:", error.message);
    }

    store.rollback(first);

    console.log("Second transaction:", second.status);
}


async function main() {
    await demonstrateMVCC();
    await demonstrateLocking();
    await demonstrateFailureHandling();

    console.log("\n=== ARCHITECTURE EVALUATION ===");

    const workloads = [
        {
            name: "Read-heavy analytics",
            readRatio: 0.95,
            contention: 0.1,
            transactionDuration: 100,
            writeHotspot: 0.05
        },
        {
            name: "Inventory contention",
            readRatio: 0.3,
            contention: 0.9,
            transactionDuration: 500,
            writeHotspot: 0.9
        }
    ];

    for (const workload of workloads) {
        console.log(
            workload.name,
            ArchitectureEvaluator.evaluate(workload)
        );
    }

    console.log("\nAll demonstrations completed.");
}


main().catch(error => {
    console.error("Execution failed:", error.message);
    process.exitCode = 1;
});
