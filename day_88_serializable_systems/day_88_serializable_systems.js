"use strict";

/*
 * Serializable Systems
 * Event-driven strict two-phase locking and concurrency analysis.
 *
 * Runtime: Node.js 18+
 *
 * Features:
 * - Shared and exclusive locks
 * - Lock compatibility
 * - Transaction lock ownership
 * - Lock upgrades
 * - Wait queues
 * - Wait-for graph construction
 * - Deadlock detection
 * - Transaction rollback
 * - Serializable execution
 * - Asynchronous transaction scheduling
 * - Practical contention measurements
 */

const { performance } = require("node:perf_hooks");

const LockMode = Object.freeze({
    SHARED: "SHARED",
    EXCLUSIVE: "EXCLUSIVE"
});

const TransactionState = Object.freeze({
    ACTIVE: "ACTIVE",
    WAITING: "WAITING",
    COMMITTED: "COMMITTED",
    ABORTED: "ABORTED"
});

class TransactionError extends Error {
    constructor(message) {
        super(message);
        this.name = "TransactionError";
    }
}

class LockManager {

    constructor() {
        this.locks = new Map();
        this.transactions = new Map();
        this.waitQueues = new Map();
        this.metrics = {
            requests: 0,
            waits: 0,
            grants: 0,
            deadlocks: 0
        };
    }

    register(id) {

        if (this.transactions.has(id)) {
            throw new TransactionError(
                `Transaction ${id} already exists`
            );
        }

        this.transactions.set(id, {
            id,
            state: TransactionState.ACTIVE,
            heldLocks: new Map(),
            workspace: new Map(),
            undoLog: new Map()
        });
    }

    getTransaction(id) {

        const transaction = this.transactions.get(id);

        if (!transaction) {
            throw new TransactionError(
                `Unknown transaction: ${id}`
            );
        }

        if (
            transaction.state === TransactionState.COMMITTED ||
            transaction.state === TransactionState.ABORTED
        ) {
            throw new TransactionError(
                `Transaction ${id} is already finished`
            );
        }

        return transaction;
    }

    compatible(resource, transactionId, mode) {

        const holders = this.locks.get(resource) || new Map();

        for (const [holderId, holderMode] of holders) {

            if (holderId === transactionId) {
                continue;
            }

            if (
                mode === LockMode.EXCLUSIVE ||
                holderMode === LockMode.EXCLUSIVE
            ) {
                return false;
            }
        }

        return true;
    }

    acquire(id, resource, mode) {

        if (!Object.values(LockMode).includes(mode)) {
            throw new TransactionError("Invalid lock mode");
        }

        if (!resource || typeof resource !== "string") {
            throw new TransactionError("Invalid resource");
        }

        const transaction = this.getTransaction(id);
        this.metrics.requests++;

        const existing = transaction.heldLocks.get(resource);

        // An exclusive lock cannot be downgraded accidentally.
        if (existing === LockMode.EXCLUSIVE) {
            return true;
        }

        if (existing === LockMode.SHARED && mode === LockMode.SHARED) {
            return true;
        }

        if (this.compatible(resource, id, mode)) {

            this.grant(id, resource, mode);

            return true;
        }

        if (!this.waitQueues.has(resource)) {
            this.waitQueues.set(resource, []);
        }

        const queue = this.waitQueues.get(resource);

        // Repeated requests must not create duplicate wait entries.
        if (
            !queue.some(
                request => request.transactionId === id
            )
        ) {
            queue.push({
                transactionId: id,
                mode
            });
        }

        transaction.state = TransactionState.WAITING;
        this.metrics.waits++;

        return false;
    }

    grant(id, resource, mode) {

        if (!this.locks.has(resource)) {
            this.locks.set(resource, new Map());
        }

        this.locks.get(resource).set(id, mode);

        const transaction = this.getTransaction(id);

        transaction.heldLocks.set(resource, mode);
        transaction.state = TransactionState.ACTIVE;

        this.metrics.grants++;
    }

    buildWaitForGraph() {

        const graph = new Map();

        for (const [resource, queue] of this.waitQueues) {

            const holders = this.locks.get(resource) || new Map();

            for (const request of queue) {

                const id = request.transactionId;

                if (!graph.has(id)) {
                    graph.set(id, new Set());
                }

                for (const [holderId, holderMode] of holders) {

                    if (holderId === id) {
                        continue;
                    }

                    if (
                        request.mode === LockMode.EXCLUSIVE ||
                        holderMode === LockMode.EXCLUSIVE
                    ) {
                        graph.get(id).add(holderId);
                    }
                }

                // Earlier incompatible requests can also block
                // requests behind them in the queue.
                for (const earlier of queue) {

                    if (earlier === request) {
                        break;
                    }

                    if (
                        earlier.transactionId !== id &&
                        (
                            request.mode === LockMode.EXCLUSIVE ||
                            earlier.mode === LockMode.EXCLUSIVE
                        )
                    ) {
                        graph.get(id).add(
                            earlier.transactionId
                        );
                    }
                }
            }
        }

        return graph;
    }

    findDeadlock() {

        const graph = this.buildWaitForGraph();
        const visiting = new Set();
        const visited = new Set();
        const path = [];

        function dfs(node) {

            if (visiting.has(node)) {
                return path.slice(path.indexOf(node)).concat(node);
            }

            if (visited.has(node)) {
                return null;
            }

            visiting.add(node);
            path.push(node);

            for (const neighbor of graph.get(node) || []) {

                const cycle = dfs(neighbor);

                if (cycle) {
                    return cycle;
                }
            }

            path.pop();
            visiting.delete(node);
            visited.add(node);

            return null;
        }

        for (const node of graph.keys()) {

            const cycle = dfs(node);

            if (cycle) {
                return cycle;
            }
        }

        return null;
    }

    releaseAll(id) {

        const transaction = this.transactions.get(id);

        if (!transaction) {
            return;
        }

        for (const resource of transaction.heldLocks.keys()) {

            const holders = this.locks.get(resource);

            if (holders) {
                holders.delete(id);

                if (holders.size === 0) {
                    this.locks.delete(resource);
                }
            }
        }

        transaction.heldLocks.clear();

        for (const [resource, queue] of this.waitQueues) {

            const filtered = queue.filter(
                request => request.transactionId !== id
            );

            if (filtered.length === 0) {
                this.waitQueues.delete(resource);
            } else {
                this.waitQueues.set(resource, filtered);
            }
        }

        this.processQueues();
    }

    processQueues() {

        let progress = true;

        while (progress) {

            progress = false;

            for (const [resource, queue] of this.waitQueues) {

                if (!queue.length) {
                    continue;
                }

                const request = queue[0];

                const transaction = this.transactions.get(
                    request.transactionId
                );

                if (
                    !transaction ||
                    transaction.state === TransactionState.ABORTED ||
                    transaction.state === TransactionState.COMMITTED
                ) {
                    queue.shift();
                    progress = true;
                    continue;
                }

                if (
                    this.compatible(
                        resource,
                        request.transactionId,
                        request.mode
                    )
                ) {

                    queue.shift();

                    this.grant(
                        request.transactionId,
                        resource,
                        request.mode
                    );

                    progress = true;

                    if (request.mode === LockMode.EXCLUSIVE) {
                        continue;
                    }

                    // Consecutive shared requests can be granted together.
                    while (
                        queue.length &&
                        queue[0].mode === LockMode.SHARED &&
                        this.compatible(
                            resource,
                            queue[0].transactionId,
                            LockMode.SHARED
                        )
                    ) {

                        const next = queue.shift();

                        this.grant(
                            next.transactionId,
                            resource,
                            LockMode.SHARED
                        );
                    }
                }

                if (queue.length === 0) {
                    this.waitQueues.delete(resource);
                }
            }
        }
    }

    commit(id) {

        const transaction = this.getTransaction(id);

        if (transaction.state === TransactionState.WAITING) {
            throw new TransactionError(
                "Cannot commit while waiting for a lock"
            );
        }

        transaction.state = TransactionState.COMMITTED;

        this.releaseAll(id);

        return true;
    }

    abort(id) {

        const transaction = this.getTransaction(id);

        // Uncommitted workspace is discarded.
        transaction.workspace.clear();

        transaction.state = TransactionState.ABORTED;

        this.releaseAll(id);
    }
}


class SerializableDatabase {

    constructor(initialData) {

        this.data = new Map(Object.entries(initialData));
        this.lockManager = new LockManager();
        this.version = new Map();

        for (const key of this.data.keys()) {
            this.version.set(key, 0);
        }
    }

    begin(id) {

        this.lockManager.register(id);
    }

    read(id, resource) {

        const transaction = this.lockManager.getTransaction(id);

        if (!this.data.has(resource)) {
            throw new TransactionError(
                `Resource does not exist: ${resource}`
            );
        }

        if (
            !this.lockManager.acquire(
                id,
                resource,
                LockMode.SHARED
            )
        ) {
            return {
                waiting: true,
                transactionId: id,
                resource
            };
        }

        if (transaction.workspace.has(resource)) {
            return transaction.workspace.get(resource);
        }

        return this.data.get(resource);
    }

    write(id, resource, value) {

        const transaction = this.lockManager.getTransaction(id);

        if (!this.data.has(resource)) {
            throw new TransactionError(
                `Resource does not exist: ${resource}`
            );
        }

        if (!Number.isSafeInteger(value)) {
            throw new TransactionError(
                "Value must be a safe integer"
            );
        }

        if (
            !this.lockManager.acquire(
                id,
                resource,
                LockMode.EXCLUSIVE
            )
        ) {
            return {
                waiting: true,
                transactionId: id,
                resource
            };
        }

        transaction.workspace.set(resource, value);

        return true;
    }

    commit(id) {

        const transaction = this.lockManager.getTransaction(id);

        if (transaction.state === TransactionState.WAITING) {
            throw new TransactionError("Transaction is waiting");
        }

        // Changes become visible together.
        for (const [resource, value] of transaction.workspace) {
            this.data.set(resource, value);
            this.version.set(
                resource,
                this.version.get(resource) + 1
            );
        }

        return this.lockManager.commit(id);
    }

    rollback(id) {

        this.lockManager.abort(id);
    }

    snapshot() {

        return Object.fromEntries(this.data);
    }
}


async function executeTransfer(database) {

    database.begin("TRANSFER_1");

    const source = database.read(
        "TRANSFER_1",
        "ACCOUNT_A"
    );

    const destination = database.read(
        "TRANSFER_1",
        "ACCOUNT_B"
    );

    if (
        typeof source !== "number" ||
        typeof destination !== "number"
    ) {
        database.rollback("TRANSFER_1");
        throw new TransactionError("Invalid account balances");
    }

    const amount = 150;

    if (source < amount) {
        database.rollback("TRANSFER_1");
        throw new TransactionError("Insufficient funds");
    }

    database.write(
        "TRANSFER_1",
        "ACCOUNT_A",
        source - amount
    );

    database.write(
        "TRANSFER_1",
        "ACCOUNT_B",
        destination + amount
    );

    database.commit("TRANSFER_1");

    return database.snapshot();
}


function demonstrateDeadlockDetection() {

    console.log("\n=== Deadlock Detection ===");

    const manager = new LockManager();

    manager.register("T1");
    manager.register("T2");

    manager.acquire("T1", "A", LockMode.EXCLUSIVE);
    manager.acquire("T2", "B", LockMode.EXCLUSIVE);

    manager.acquire("T1", "B", LockMode.EXCLUSIVE);
    manager.acquire("T2", "A", LockMode.EXCLUSIVE);

    const cycle = manager.findDeadlock();

    console.log("Wait-for cycle:", cycle);
    console.log("Metrics:", manager.metrics);

    if (cycle) {
        manager.metrics.deadlocks++;

        // Abort one transaction as a deadlock victim.
        manager.abort("T2");

        console.log("Deadlock victim: T2");
    }

    console.log(
        "Remaining wait-for graph:",
        manager.buildWaitForGraph()
    );
}


async function demonstrateSerializableTransfer() {

    console.log("\n=== Serializable Transfer ===");

    const database = new SerializableDatabase({
        ACCOUNT_A: 1000,
        ACCOUNT_B: 500
    });

    const result = await executeTransfer(database);

    console.log("Balances:", result);

    const total = result.ACCOUNT_A + result.ACCOUNT_B;

    console.log("Total:", total);

    if (total !== 1500) {
        throw new TransactionError(
            "Account conservation invariant violated"
        );
    }
}


async function demonstrateRollback() {

    console.log("\n=== Rollback ===");

    const database = new SerializableDatabase({
        ACCOUNT_A: 100,
        ACCOUNT_B: 200
    });

    database.begin("T_ROLLBACK");

    database.read("T_ROLLBACK", "ACCOUNT_A");

    database.write(
        "T_ROLLBACK",
        "ACCOUNT_A",
        50
    );

    database.rollback("T_ROLLBACK");

    console.log("After rollback:", database.snapshot());

    if (database.snapshot().ACCOUNT_A !== 100) {
        throw new Error("Rollback failed");
    }
}


async function main() {

    const started = performance.now();

    await demonstrateSerializableTransfer();
    await demonstrateRollback();

    demonstrateDeadlockDetection();

    console.log(
        "\nElapsed milliseconds:",
        (performance.now() - started).toFixed(3)
    );

    console.log("Execution completed.");
}


main().catch(error => {
    console.error("Execution failed:", error.message);
    process.exitCode = 1;
});
