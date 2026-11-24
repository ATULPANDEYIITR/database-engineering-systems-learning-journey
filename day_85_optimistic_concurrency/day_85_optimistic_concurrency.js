"use strict";

/*
 * Optimistic Concurrency Control
 *
 * JavaScript implementation featuring:
 * - Versioned records
 * - Compare-and-swap updates
 * - Event-driven conflict notifications
 * - Asynchronous transactions
 * - Retry policies
 * - Atomic multi-record operations
 * - Conflict classification
 * - Transaction isolation through version checks
 * - Audit events
 *
 * Run:
 *     node optimistic_concurrency.js
 */

const { randomUUID } = require("node:crypto");
const { EventEmitter } = require("node:events");


class ConcurrencyError extends Error {
    constructor(message) {
        super(message);
        this.name = "ConcurrencyError";
    }
}

class VersionConflictError extends ConcurrencyError {
    constructor(id, expected, actual) {
        super(
            `Conflict on ${id}: expected version ${expected}, actual ${actual}`
        );

        this.name = "VersionConflictError";
        this.id = id;
        this.expected = expected;
        this.actual = actual;
    }
}

class ValidationError extends Error {
    constructor(message) {
        super(message);
        this.name = "ValidationError";
    }
}

class NotFoundError extends Error {
    constructor(id) {
        super(`Record not found: ${id}`);
        this.name = "NotFoundError";
    }
}


// -------------------------------------------------------
// Domain validation
// -------------------------------------------------------

function validateRecord(data) {
    if (
        data === null ||
        typeof data !== "object" ||
        Array.isArray(data)
    ) {
        throw new ValidationError("Record must be an object.");
    }

    if (Object.hasOwn(data, "balance")) {
        if (
            typeof data.balance !== "number" ||
            !Number.isFinite(data.balance) ||
            data.balance < 0
        ) {
            throw new ValidationError(
                "Balance must be a finite non-negative number."
            );
        }
    }
}


// Structured cloning prevents callers from mutating
// stored objects through returned references.
function clone(value) {
    return structuredClone(value);
}


// -------------------------------------------------------
// Retry policy
// -------------------------------------------------------

class RetryPolicy {
    constructor({
        maxAttempts = 5,
        initialDelay = 10,
        maxDelay = 500
    } = {}) {

        if (
            !Number.isInteger(maxAttempts) ||
            maxAttempts < 1 ||
            initialDelay < 0 ||
            maxDelay < initialDelay
        ) {
            throw new ValidationError("Invalid retry configuration.");
        }

        this.maxAttempts = maxAttempts;
        this.initialDelay = initialDelay;
        this.maxDelay = maxDelay;
    }

    delay(attempt) {
        const exponential = Math.min(
            this.initialDelay * (2 ** attempt),
            this.maxDelay
        );

        return Math.random() * exponential;
    }
}


// -------------------------------------------------------
// Repository
// -------------------------------------------------------

class VersionedStore extends EventEmitter {

    #records = new Map();
    #audit = [];

    create(id, data) {

        if (typeof id !== "string" || !id.trim()) {
            throw new ValidationError("Invalid record identifier.");
        }

        validateRecord(data);

        if (this.#records.has(id)) {
            throw new ValidationError(`Duplicate record: ${id}`);
        }

        const record = {
            data: clone(data),
            version: 1,
            updatedAt: new Date().toISOString()
        };

        this.#records.set(id, record);

        return this.#snapshot(id, record);
    }

    #snapshot(id, record) {
        return Object.freeze({
            id,
            data: clone(record.data),
            version: record.version,
            updatedAt: record.updatedAt
        });
    }

    read(id) {
        const record = this.#records.get(id);

        if (!record) {
            throw new NotFoundError(id);
        }

        return this.#snapshot(id, record);
    }

    compareAndSwap(id, expectedVersion, newData, transactionId) {

        validateRecord(newData);

        if (
            !Number.isSafeInteger(expectedVersion) ||
            expectedVersion < 1
        ) {
            throw new ValidationError("Invalid expected version.");
        }

        const record = this.#records.get(id);

        if (!record) {
            throw new NotFoundError(id);
        }

        // In a single JavaScript event loop, this synchronous
        // comparison-and-update section cannot be interleaved
        // by another JavaScript callback.
        if (record.version !== expectedVersion) {

            const error = new VersionConflictError(
                id,
                expectedVersion,
                record.version
            );

            this.emit("conflict", {
                transactionId,
                id,
                expected: expectedVersion,
                actual: record.version
            });

            throw error;
        }

        const oldVersion = record.version;

        record.data = clone(newData);
        record.version++;
        record.updatedAt = new Date().toISOString();

        const event = Object.freeze({
            transactionId,
            id,
            oldVersion,
            newVersion: record.version,
            timestamp: record.updatedAt,
            operation: "UPDATE"
        });

        this.#audit.push(event);
        this.emit("committed", event);

        return this.#snapshot(id, record);
    }

    async update(id, transform, retryPolicy = new RetryPolicy()) {

        if (typeof transform !== "function") {
            throw new ValidationError("Transform must be a function.");
        }

        const transactionId = randomUUID();

        for (
            let attempt = 0;
            attempt < retryPolicy.maxAttempts;
            attempt++
        ) {

            const snapshot = this.read(id);

            // Transform may be asynchronous. It must not directly
            // mutate repository state.
            const proposed = await transform(clone(snapshot.data));

            try {
                const result = this.compareAndSwap(
                    id,
                    snapshot.version,
                    proposed,
                    transactionId
                );

                return {
                    transactionId,
                    attempts: attempt + 1,
                    result
                };

            } catch (error) {

                if (!(error instanceof VersionConflictError)) {
                    throw error;
                }

                if (attempt === retryPolicy.maxAttempts - 1) {
                    throw new ConcurrencyError(
                        `Retry limit exceeded for ${id}.`
                    );
                }

                const delay = retryPolicy.delay(attempt);

                await new Promise(resolve =>
                    setTimeout(resolve, delay)
                );
            }
        }

        throw new ConcurrencyError("Transaction could not commit.");
    }

    /*
     * Atomic multi-record transfer.
     *
     * Validation, version checking and both updates occur
     * synchronously in one critical section.
     */
    transfer(sourceId, destinationId, amount) {

        if (
            sourceId === destinationId ||
            !Number.isFinite(amount) ||
            amount <= 0
        ) {
            throw new ValidationError("Invalid transfer parameters.");
        }

        const source = this.#records.get(sourceId);
        const destination = this.#records.get(destinationId);

        if (!source) throw new NotFoundError(sourceId);
        if (!destination) throw new NotFoundError(destinationId);

        const transactionId = randomUUID();

        const sourceVersion = source.version;
        const destinationVersion = destination.version;

        const sourceData = clone(source.data);
        const destinationData = clone(destination.data);

        if (
            typeof sourceData.balance !== "number" ||
            typeof destinationData.balance !== "number"
        ) {
            throw new ValidationError("Both accounts require balances.");
        }

        if (sourceData.balance < amount) {
            throw new ValidationError("Insufficient funds.");
        }

        sourceData.balance -= amount;
        destinationData.balance += amount;

        validateRecord(sourceData);
        validateRecord(destinationData);

        // Revalidate both versions before committing either update.
        if (
            source.version !== sourceVersion ||
            destination.version !== destinationVersion
        ) {
            throw new ConcurrencyError("Transfer conflict.");
        }

        source.data = sourceData;
        destination.data = destinationData;

        source.version++;
        destination.version++;

        source.updatedAt = new Date().toISOString();
        destination.updatedAt = source.updatedAt;

        const events = [
            {
                transactionId,
                id: sourceId,
                oldVersion: sourceVersion,
                newVersion: source.version,
                operation: "TRANSFER_DEBIT",
                timestamp: source.updatedAt
            },
            {
                transactionId,
                id: destinationId,
                oldVersion: destinationVersion,
                newVersion: destination.version,
                operation: "TRANSFER_CREDIT",
                timestamp: destination.updatedAt
            }
        ];

        this.#audit.push(...events);

        for (const event of events) {
            this.emit("committed", Object.freeze(event));
        }

        return {
            transactionId,
            source: this.read(sourceId),
            destination: this.read(destinationId)
        };
    }

    audit() {
        return this.#audit.map(event => ({ ...event }));
    }
}


// -------------------------------------------------------
// Conflict-aware business workflow
// -------------------------------------------------------

class InventoryService {

    constructor(store) {
        this.store = store;
    }

    async reserve(productId, quantity) {

        if (!Number.isInteger(quantity) || quantity <= 0) {
            throw new ValidationError("Quantity must be a positive integer.");
        }

        return this.store.update(
            productId,
            async product => {

                if (product.stock < quantity) {
                    throw new ValidationError("Insufficient inventory.");
                }

                product.stock -= quantity;
                product.reserved = (product.reserved || 0) + quantity;

                return product;
            },
            new RetryPolicy({
                maxAttempts: 8,
                initialDelay: 5,
                maxDelay: 100
            })
        );
    }
}


// -------------------------------------------------------
// Demonstration
// -------------------------------------------------------

async function main() {

    const store = new VersionedStore();

    store.on("conflict", event => {
        console.log("CONFLICT:", event);
    });

    store.on("committed", event => {
        console.log(
            `COMMITTED ${event.id}: ` +
            `${event.oldVersion} -> ${event.newVersion}`
        );
    });

    store.create("ACCOUNT-A", { balance: 5000 });
    store.create("ACCOUNT-B", { balance: 1000 });

    console.log("\n1. Stale version detection");

    const first = store.read("ACCOUNT-A");
    const second = store.read("ACCOUNT-A");

    store.compareAndSwap(
        "ACCOUNT-A",
        first.version,
        { balance: 4500 },
        "TX-001"
    );

    try {
        store.compareAndSwap(
            "ACCOUNT-A",
            second.version,
            { balance: 3000 },
            "TX-002"
        );
    } catch (error) {
        console.log(error.message);
    }

    console.log("\n2. Concurrent asynchronous updates");

    store.create("COUNTER", { balance: 0 });

    await Promise.all(
        Array.from({ length: 20 }, () =>
            store.update(
                "COUNTER",
                async data => {
                    await new Promise(resolve =>
                        setTimeout(resolve, Math.random() * 5)
                    );

                    data.balance++;
                    return data;
                },
                new RetryPolicy({
                    maxAttempts: 50,
                    initialDelay: 1,
                    maxDelay: 20
                })
            )
        )
    );

    console.log("Counter:", store.read("COUNTER"));

    if (store.read("COUNTER").data.balance !== 20) {
        throw new Error("Counter integrity failure.");
    }

    console.log("\n3. Atomic financial transfer");

    const transfer = store.transfer(
        "ACCOUNT-A",
        "ACCOUNT-B",
        500
    );

    console.log(transfer);

    console.log("\n4. Inventory reservation");

    store.create("PRODUCT-001", {
        stock: 100,
        reserved: 0
    });

    const inventory = new InventoryService(store);

    const reservations = await Promise.all(
        Array.from({ length: 5 }, () =>
            inventory.reserve("PRODUCT-001", 10)
        )
    );

    console.log("Successful reservations:", reservations.length);
    console.log("Inventory:", store.read("PRODUCT-001"));

    console.log("\n5. Audit records");

    console.table(store.audit());

    console.log("\nAll demonstrations completed.");
}


main().catch(error => {
    console.error("Execution failed:", error.message);
    process.exitCode = 1;
});
