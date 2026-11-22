// locks.js
// Shared Locks, Exclusive Locks, and Lock Compatibility
// Node.js 18+
//
// Event-driven asynchronous lock manager.
// Demonstrates compatibility evaluation, queued requests,
// timeout handling, lock conversion, reentrancy, and transaction cleanup.

"use strict";

const { EventEmitter } = require("node:events");

const LockMode = Object.freeze({
    SHARED: "S",
    EXCLUSIVE: "X"
});

const COMPATIBILITY = Object.freeze({
    S: Object.freeze({ S: true, X: false }),
    X: Object.freeze({ S: false, X: false })
});

class LockError extends Error {}

class LockTimeoutError extends LockError {}

class LockUpgradeError extends LockError {}

class LockManager extends EventEmitter {
    constructor() {
        super();
        this.resources = new Map();
        this.requestSequence = 0;
    }

    _validate(transactionId, resource, mode) {
        if (
            typeof transactionId !== "string" ||
            transactionId.trim() === ""
        ) {
            throw new TypeError("A valid transaction ID is required.");
        }

        if (
            typeof resource !== "string" ||
            resource.trim() === ""
        ) {
            throw new TypeError("A valid resource name is required.");
        }

        if (!Object.values(LockMode).includes(mode)) {
            throw new TypeError("Unsupported lock mode.");
        }
    }

    _state(resource) {
        if (!this.resources.has(resource)) {
            this.resources.set(resource, {
                holders: new Map(),
                queue: []
            });
        }

        return this.resources.get(resource);
    }

    _compatible(state, transactionId, mode) {
        for (const [holder, lock] of state.holders) {
            if (holder === transactionId) continue;

            if (!COMPATIBILITY[mode][lock.mode]) {
                return false;
            }
        }

        return true;
    }

    _canGrant(state, request) {
        if (!this._compatible(
            state,
            request.transactionId,
            request.mode
        )) {
            return false;
        }

        // Shared requests may join an existing shared group,
        // but exclusive requests cannot be bypassed.
        for (const earlier of state.queue) {
            if (earlier === request) break;

            if (
                earlier.mode !== LockMode.SHARED ||
                request.mode !== LockMode.SHARED
            ) {
                return false;
            }
        }

        return true;
    }

    acquire(transactionId, resource, mode, options = {}) {
        this._validate(transactionId, resource, mode);

        const timeout = options.timeout ?? 5000;

        if (!Number.isFinite(timeout) || timeout < 0) {
            throw new RangeError("Timeout must be non-negative.");
        }

        const state = this._state(resource);
        const existing = state.holders.get(transactionId);

        if (existing) {
            if (
                existing.mode === LockMode.EXCLUSIVE ||
                (
                    existing.mode === LockMode.SHARED &&
                    mode === LockMode.SHARED
                )
            ) {
                existing.count++;
                return Promise.resolve();
            }

            const otherHolders = [...state.holders.keys()]
                .filter(id => id !== transactionId);

            if (otherHolders.length > 0) {
                return Promise.reject(
                    new LockUpgradeError(
                        "Shared-to-exclusive upgrade rejected: " +
                        "other transactions still hold the resource."
                    )
                );
            }
        }

        const request = {
            id: ++this.requestSequence,
            transactionId,
            resource,
            mode,
            timer: null,
            resolve: null,
            reject: null
        };

        return new Promise((resolve, reject) => {
            request.resolve = resolve;
            request.reject = reject;

            state.queue.push(request);

            if (timeout === 0) {
                this._drain(resource);
                if (state.queue.includes(request)) {
                    this._removeRequest(state, request);
                    reject(new LockTimeoutError(
                        `Immediate acquisition failed for ${resource}.`
                    ));
                }
                return;
            }

            if (timeout !== Infinity) {
                request.timer = setTimeout(() => {
                    this._removeRequest(state, request);

                    reject(new LockTimeoutError(
                        `Timed out acquiring ${mode} on ${resource}.`
                    ));

                    this._drain(resource);
                }, timeout);
            }

            this._drain(resource);
        });
    }

    _removeRequest(state, request) {
        const index = state.queue.indexOf(request);

        if (index !== -1) {
            state.queue.splice(index, 1);
        }

        if (request.timer) {
            clearTimeout(request.timer);
        }
    }

    _drain(resource) {
        const state = this.resources.get(resource);

        if (!state) return;

        while (state.queue.length > 0) {
            const request = state.queue[0];

            if (!this._canGrant(state, request)) {
                break;
            }

            state.queue.shift();

            if (request.timer) {
                clearTimeout(request.timer);
            }

            const previous = state.holders.get(
                request.transactionId
            );

            if (previous) {
                previous.mode = request.mode;
                previous.count = 1;
            } else {
                state.holders.set(request.transactionId, {
                    mode: request.mode,
                    count: 1
                });
            }

            this.emit("granted", {
                transactionId: request.transactionId,
                resource,
                mode: request.mode
            });

            request.resolve();

            // Continue only when the next queued request is
            // compatible with all existing holders.
        }
    }

    release(transactionId, resource) {
        const state = this.resources.get(resource);

        if (!state || !state.holders.has(transactionId)) {
            throw new LockError(
                `${transactionId} does not hold ${resource}.`
            );
        }

        const holder = state.holders.get(transactionId);
        holder.count--;

        if (holder.count === 0) {
            state.holders.delete(transactionId);
            this.emit("released", { transactionId, resource });
        }

        this._drain(resource);
    }

    releaseAll(transactionId) {
        for (const [resource, state] of this.resources) {
            if (state.holders.has(transactionId)) {
                state.holders.delete(transactionId);
                this.emit("released", { transactionId, resource });
                this._drain(resource);
            }
        }
    }

    snapshot() {
        const result = {};

        for (const [resource, state] of this.resources) {
            result[resource] = {
                holders: Object.fromEntries(
                    [...state.holders].map(([id, lock]) => [
                        id,
                        { ...lock }
                    ])
                ),
                waiting: state.queue.map(request => ({
                    transactionId: request.transactionId,
                    mode: request.mode
                }))
            };
        }

        return result;
    }
}

class Transaction {
    constructor(manager, id) {
        this.manager = manager;
        this.id = id;
        this.active = true;
    }

    _checkActive() {
        if (!this.active) {
            throw new LockError("Transaction is no longer active.");
        }
    }

    shared(resource, options) {
        this._checkActive();

        return this.manager.acquire(
            this.id,
            resource,
            LockMode.SHARED,
            options
        );
    }

    exclusive(resource, options) {
        this._checkActive();

        return this.manager.acquire(
            this.id,
            resource,
            LockMode.EXCLUSIVE,
            options
        );
    }

    release(resource) {
        this._checkActive();
        this.manager.release(this.id, resource);
    }

    commit() {
        this._checkActive();
        this.manager.releaseAll(this.id);
        this.active = false;
    }

    rollback() {
        this._checkActive();
        this.manager.releaseAll(this.id);
        this.active = false;
    }
}

async function runDemo() {
    const manager = new LockManager();

    manager.on("granted", event => {
        console.log("LOCK GRANTED:", event);
    });

    manager.on("released", event => {
        console.log("LOCK RELEASED:", event);
    });

    console.log("\n1. Compatible shared locks");

    const t1 = new Transaction(manager, "T1");
    const t2 = new Transaction(manager, "T2");

    await t1.shared("account:100");
    await t2.shared("account:100");

    console.log(JSON.stringify(manager.snapshot(), null, 2));

    console.log("\n2. Exclusive lock waits for readers");

    const t3 = new Transaction(manager, "T3");

    const exclusivePromise = t3.exclusive(
        "account:100",
        { timeout: 2000 }
    );

    await new Promise(resolve => setTimeout(resolve, 100));

    t1.commit();
    t2.commit();

    await exclusivePromise;

    console.log("T3 acquired exclusive access.");

    console.log("\n3. Transaction rollback");

    t3.rollback();

    console.log(JSON.stringify(manager.snapshot(), null, 2));

    console.log("\n4. Upgrade conflict");

    const t4 = new Transaction(manager, "inventory:20");
    const t5 = new Transaction(manager, "inventory:20");

    await t4.shared("inventory:20");
    await t5.shared("inventory:20");

    try {
        await t4.exclusive("inventory:20");
    } catch (error) {
        console.log("Expected:", error.message);
    }

    t4.rollback();
    t5.rollback();

    console.log("\n5. Timeout handling");

    const t6 = new Transaction(manager, "T6");
    const t7 = new Transaction(manager, "T7");

    await t6.exclusive("payment:500");

    try {
        await t7.exclusive(
            "payment:500",
            { timeout: 100 }
        );
    } catch (error) {
        console.log("Expected timeout:", error.message);
    }

    t6.commit();
    t7.rollback();

    console.log("\nAll demonstrations completed.");
}

runDemo().catch(error => {
    console.error("Execution failure:", error.message);
    process.exitCode = 1;
});
