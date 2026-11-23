"use strict";

/**
 * Deadlock Management Engine
 *
 * Event-driven resource manager for single-instance resources.
 *
 * Features:
 * - Promise-based asynchronous resource acquisition
 * - FIFO resource queues
 * - Wait-for graph construction
 * - DFS deadlock detection
 * - Automatic victim selection
 * - Transaction cancellation and recovery
 * - Global resource ordering prevention
 * - EventEmitter-based monitoring
 *
 * Runtime: Node.js 18+
 * Dependencies: Node.js standard library
 */

const { EventEmitter } = require("node:events");

class DeadlockError extends Error {
    constructor(cycle) {
        super(`Deadlock detected: ${cycle.join(" -> ")}`);
        this.name = "DeadlockError";
        this.cycle = cycle;
    }
}

class TransactionError extends Error {
    constructor(message) {
        super(message);
        this.name = "TransactionError";
    }
}

class ResourceOrderError extends Error {
    constructor(message) {
        super(message);
        this.name = "ResourceOrderError";
    }
}

class Resource {
    constructor(name, order) {
        this.name = name;
        this.order = order;
        this.owner = null;
        this.queue = [];
    }
}

class Transaction {
    constructor(id, sequence) {
        this.id = id;
        this.sequence = sequence;
        this.state = "ACTIVE";
        this.held = new Set();
        this.waitingFor = null;
        this.rollbackCount = 0;
        this.pendingReject = null;
    }
}

class DeadlockManager extends EventEmitter {
    constructor({ prevention = false, automaticRecovery = true } = {}) {
        super();

        this.resources = new Map();
        this.transactions = new Map();
        this.sequence = 0;
        this.prevention = prevention;
        this.automaticRecovery = automaticRecovery;
        this.recoveryInProgress = false;
    }

    log(type, data) {
        const event = {
            type,
            timestamp: new Date().toISOString(),
            ...data
        };

        this.emit("event", event);
    }

    addResource(name, order) {
        if (!name || this.resources.has(name)) {
            throw new TypeError("Resource name must be unique.");
        }

        if (!Number.isInteger(order) || order < 0) {
            throw new TypeError("Resource order must be non-negative.");
        }

        for (const resource of this.resources.values()) {
            if (resource.order === order) {
                throw new TypeError("Resource order must be unique.");
            }
        }

        this.resources.set(name, new Resource(name, order));

        this.log("RESOURCE_REGISTERED", { name, order });
    }

    begin(id) {
        if (!id || this.transactions.has(id)) {
            throw new TransactionError(
                "Transaction ID must be unique and non-empty."
            );
        }

        const transaction = new Transaction(id, ++this.sequence);

        this.transactions.set(id, transaction);

        this.log("TRANSACTION_STARTED", { transactionId: id });

        return transaction;
    }

    getTransaction(id) {
        const transaction = this.transactions.get(id);

        if (!transaction) {
            throw new TransactionError(`Unknown transaction: ${id}`);
        }

        if (!["ACTIVE", "WAITING"].includes(transaction.state)) {
            throw new TransactionError(
                `Transaction ${id} is ${transaction.state}.`
            );
        }

        return transaction;
    }

    validateOrder(transaction, resource) {
        if (!this.prevention || transaction.held.size === 0) {
            return;
        }

        let highest = -1;

        for (const name of transaction.held) {
            highest = Math.max(
                highest,
                this.resources.get(name).order
            );
        }

        if (resource.order < highest) {
            throw new ResourceOrderError(
                `${transaction.id} requested ${resource.name} ` +
                "outside the global resource order."
            );
        }
    }

    acquire(transactionId, resourceName) {
        const transaction = this.getTransaction(transactionId);
        const resource = this.resources.get(resourceName);

        if (!resource) {
            throw new TypeError(`Unknown resource: ${resourceName}`);
        }

        if (transaction.held.has(resourceName)) {
            return Promise.resolve(true);
        }

        if (transaction.waitingFor !== null) {
            throw new TransactionError(
                "A transaction cannot issue another request while waiting."
            );
        }

        this.validateOrder(transaction, resource);

        if (resource.owner === null) {
            resource.owner = transactionId;
            transaction.held.add(resourceName);

            this.log("RESOURCE_ACQUIRED", {
                transactionId,
                resourceName
            });

            return Promise.resolve(true);
        }

        if (resource.owner === transactionId) {
            return Promise.resolve(true);
        }

        transaction.state = "WAITING";
        transaction.waitingFor = resourceName;

        return new Promise((resolve, reject) => {
            resource.queue.push({
                transactionId,
                resolve,
                reject,
                sequence: transaction.sequence
            });

            transaction.pendingReject = reject;

            this.log("RESOURCE_WAITING", {
                transactionId,
                resourceName,
                owner: resource.owner
            });

            if (this.automaticRecovery) {
                const cycles = this.detectDeadlocks();

                if (cycles.length > 0) {
                    this.recover(cycles[0]);
                }
            }
        });
    }

    buildWaitForGraph() {
        const graph = new Map();

        for (const transaction of this.transactions.values()) {
            if (transaction.state !== "WAITING") {
                continue;
            }

            const resource = this.resources.get(
                transaction.waitingFor
            );

            if (resource && resource.owner !== null) {
                graph.set(
                    transaction.id,
                    new Set([resource.owner])
                );
            }
        }

        return graph;
    }

    detectDeadlocks() {
        const graph = this.buildWaitForGraph();
        const colors = new Map();
        const stack = [];
        const cycles = [];
        const signatures = new Set();

        for (const id of this.transactions.keys()) {
            colors.set(id, 0);
        }

        const canonical = cycle => {
            const rotations = cycle.map((_, index) => {
                return [
                    ...cycle.slice(index),
                    ...cycle.slice(0, index)
                ];
            });

            return rotations
                .map(rotation => rotation.join("|"))
                .sort()[0];
        };

        const visit = id => {
            colors.set(id, 1);
            stack.push(id);

            for (const next of graph.get(id) || []) {
                const color = colors.get(next) ?? 0;

                if (color === 0) {
                    visit(next);
                } else if (color === 1) {
                    const index = stack.indexOf(next);
                    const cycle = stack.slice(index);
                    const signature = canonical(cycle);

                    if (!signatures.has(signature)) {
                        signatures.add(signature);
                        cycles.push(cycle);
                    }
                }
            }

            stack.pop();
            colors.set(id, 2);
        };

        for (const [id, color] of colors) {
            if (color === 0 && graph.has(id)) {
                visit(id);
            }
        }

        return cycles;
    }

    selectVictim(cycle) {
        return cycle
            .map(id => this.transactions.get(id))
            .filter(Boolean)
            .sort((a, b) => b.sequence - a.sequence)[0];
    }

    recover(cycle) {
        if (this.recoveryInProgress || cycle.length === 0) {
            return null;
        }

        this.recoveryInProgress = true;

        try {
            const victim = this.selectVictim(cycle);

            if (!victim) {
                return null;
            }

            const error = new DeadlockError(cycle);

            this.log("DEADLOCK_DETECTED", { cycle });

            this.abort(victim.id, error);

            this.log("DEADLOCK_RECOVERED", {
                cycle,
                victim: victim.id
            });

            return victim.id;
        } finally {
            this.recoveryInProgress = false;
        }
    }

    wakeWaiter(resource) {
        while (resource.owner === null && resource.queue.length > 0) {
            const request = resource.queue.shift();

            const transaction = this.transactions.get(
                request.transactionId
            );

            if (!transaction || transaction.state !== "WAITING") {
                continue;
            }

            resource.owner = transaction.id;
            transaction.held.add(resource.name);
            transaction.waitingFor = null;
            transaction.pendingReject = null;
            transaction.state = "ACTIVE";

            this.log("RESOURCE_GRANTED", {
                transactionId: transaction.id,
                resourceName: resource.name
            });

            request.resolve(true);
        }
    }

    removePendingRequests(transactionId) {
        for (const resource of this.resources.values()) {
            resource.queue = resource.queue.filter(
                request => request.transactionId !== transactionId
            );
        }
    }

    releaseAll(transactionId) {
        const transaction = this.transactions.get(transactionId);

        if (!transaction) {
            return;
        }

        const heldResources = [...transaction.held];

        transaction.held.clear();

        for (const name of heldResources) {
            const resource = this.resources.get(name);

            if (resource.owner === transactionId) {
                resource.owner = null;
            }
        }

        // All ownership records are cleared before queue processing.
        for (const name of heldResources) {
            this.wakeWaiter(this.resources.get(name));
        }
    }

    abort(transactionId, reason = new TransactionError("Aborted")) {
        const transaction = this.getTransaction(transactionId);

        const reject = transaction.pendingReject;

        this.removePendingRequests(transactionId);

        transaction.state = "ABORTED";
        transaction.waitingFor = null;
        transaction.pendingReject = null;
        transaction.rollbackCount++;

        this.releaseAll(transactionId);

        this.log("TRANSACTION_ABORTED", {
            transactionId,
            reason: reason.message
        });

        if (reject) {
            reject(reason);
        }
    }

    release(transactionId, resourceName) {
        const transaction = this.getTransaction(transactionId);
        const resource = this.resources.get(resourceName);

        if (!resource || resource.owner !== transactionId) {
            throw new TransactionError(
                `${transactionId} does not own ${resourceName}.`
            );
        }

        resource.owner = null;
        transaction.held.delete(resourceName);

        this.log("RESOURCE_RELEASED", {
            transactionId,
            resourceName
        });

        this.wakeWaiter(resource);
    }

    commit(transactionId) {
        const transaction = this.getTransaction(transactionId);

        if (transaction.state !== "ACTIVE") {
            throw new TransactionError(
                "A waiting transaction cannot commit."
            );
        }

        transaction.state = "COMMITTED";

        this.releaseAll(transactionId);

        this.log("TRANSACTION_COMMITTED", { transactionId });
    }

    snapshot() {
        return {
            transactions: [...this.transactions.values()].map(tx => ({
                id: tx.id,
                state: tx.state,
                held: [...tx.held],
                waitingFor: tx.waitingFor
            })),

            resources: [...this.resources.values()].map(resource => ({
                name: resource.name,
                owner: resource.owner,
                queue: resource.queue.map(
                    request => request.transactionId
                )
            })),

            waitForGraph: Object.fromEntries(
                [...this.buildWaitForGraph()].map(
                    ([id, owners]) => [id, [...owners]]
                )
            )
        };
    }
}

async function demonstrateDetectionAndRecovery() {
    console.log("\nSCENARIO 1: DETECTION AND RECOVERY");

    const manager = new DeadlockManager();

    manager.on("event", event => {
        console.log(
            `[${event.type}]`,
            JSON.stringify(event)
        );
    });

    manager.addResource("DATABASE", 1);
    manager.addResource("FILE", 2);

    manager.begin("T1");
    manager.begin("T2");

    await manager.acquire("T1", "DATABASE");
    await manager.acquire("T2", "FILE");

    const pendingT1 = manager.acquire("T1", "FILE");
    const pendingT2 = manager.acquire("T2", "DATABASE");

    // Attach rejection handlers immediately.
    const outcomes = await Promise.allSettled([
        pendingT1,
        pendingT2
    ]);

    console.log("\nTRANSACTION OUTCOMES");

    outcomes.forEach((outcome, index) => {
        console.log(`Request ${index + 1}:`, outcome.status);
    });

    console.log("\nFINAL STATE");
    console.log(JSON.stringify(manager.snapshot(), null, 2));

    const active = manager.transactions.get("T1");

    if (active.state === "ACTIVE") {
        manager.commit("T1");
    }
}

async function demonstratePrevention() {
    console.log("\nSCENARIO 2: RESOURCE ORDERING");

    const manager = new DeadlockManager({
        prevention: true
    });

    manager.addResource("ACCOUNT", 1);
    manager.addResource("LEDGER", 2);
    manager.addResource("AUDIT", 3);

    manager.begin("PAYMENT_1");

    await manager.acquire("PAYMENT_1", "ACCOUNT");
    await manager.acquire("PAYMENT_1", "LEDGER");

    try {
        await manager.acquire("PAYMENT_1", "ACCOUNT");
        await manager.acquire("PAYMENT_1", "AUDIT");
    } catch (error) {
        console.log(error.message);
    }

    manager.commit("PAYMENT_1");
}

async function demonstrateValidation() {
    console.log("\nSCENARIO 3: VALIDATION");

    const manager = new DeadlockManager();

    manager.addResource("CACHE", 1);
    manager.begin("T3");

    try {
        await manager.acquire("T3", "MISSING");
    } catch (error) {
        console.log("Expected failure:", error.message);
    }

    manager.commit("T3");
}

async function main() {
    await demonstrateDetectionAndRecovery();
    await demonstratePrevention();
    await demonstrateValidation();

    console.log("\nAll JavaScript demonstrations completed.");
}

main().catch(error => {
    console.error("Fatal execution error:", error);
    process.exitCode = 1;
});
