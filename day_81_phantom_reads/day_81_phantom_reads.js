"use strict";

/**
 * Phantom Reads: Range Queries and Transaction Isolation
 *
 * Event-driven transactional simulation using Node.js.
 *
 * Features:
 * - READ COMMITTED
 * - REPEATABLE READ
 * - SERIALIZABLE
 * - Snapshot visibility
 * - Predicate-range tracking
 * - Concurrent transaction scheduling
 * - Commit conflict detection
 * - Atomic write application
 * - Asynchronous transaction execution
 */

const { EventEmitter } = require("node:events");
const assert = require("node:assert/strict");

const Isolation = Object.freeze({
    READ_COMMITTED: "READ COMMITTED",
    REPEATABLE_READ: "REPEATABLE READ",
    SERIALIZABLE: "SERIALIZABLE"
});

const State = Object.freeze({
    ACTIVE: "ACTIVE",
    COMMITTED: "COMMITTED",
    ABORTED: "ABORTED"
});

class TransactionError extends Error {}
class SerializationError extends TransactionError {}
class WriteConflictError extends TransactionError {}

function validateProduct(product) {
    if (!Number.isSafeInteger(product.id) || product.id <= 0) {
        throw new TypeError("Product ID must be a positive safe integer");
    }

    if (typeof product.name !== "string" || !product.name.trim()) {
        throw new TypeError("Product name is required");
    }

    if (!Number.isFinite(product.price) || product.price < 0) {
        throw new TypeError("Price must be a non-negative finite number");
    }

    if (typeof product.category !== "string" || !product.category.trim()) {
        throw new TypeError("Product category is required");
    }

    return Object.freeze({ ...product });
}

function cloneMap(source) {
    return new Map(
        [...source.entries()].map(([id, entry]) => [
            id,
            {
                product: { ...entry.product },
                version: entry.version
            }
        ])
    );
}

class RangePredicate {
    constructor(minimum, maximum, options = {}) {
        if (
            !Number.isFinite(minimum) ||
            !Number.isFinite(maximum) ||
            minimum > maximum
        ) {
            throw new RangeError("Invalid range boundaries");
        }

        this.minimum = minimum;
        this.maximum = maximum;
        this.includeMinimum = options.includeMinimum ?? true;
        this.includeMaximum = options.includeMaximum ?? false;
    }

    contains(value) {
        const lower = this.includeMinimum
            ? value >= this.minimum
            : value > this.minimum;

        const upper = this.includeMaximum
            ? value <= this.maximum
            : value < this.maximum;

        return lower && upper;
    }
}

class Transaction {
    constructor(id, isolation, snapshot, startVersion) {
        this.id = id;
        this.isolation = isolation;
        this.snapshot = snapshot;
        this.startVersion = startVersion;
        this.state = State.ACTIVE;
        this.writes = new Map();
        this.readPredicates = [];
    }

    ensureActive() {
        if (this.state !== State.ACTIVE) {
            throw new TransactionError(
                `Transaction ${this.id} is ${this.state}`
            );
        }
    }
}

class TransactionalStore extends EventEmitter {
    #rows = new Map();
    #version = 0;
    #transactionId = 0;
    #history = [];

    seed(products) {
        for (const rawProduct of products) {
            const product = validateProduct(rawProduct);

            if (this.#rows.has(product.id)) {
                throw new WriteConflictError("Duplicate product ID");
            }

            this.#version++;

            this.#rows.set(product.id, {
                product,
                version: this.#version
            });
        }
    }

    begin(isolation = Isolation.READ_COMMITTED) {
        if (!Object.values(Isolation).includes(isolation)) {
            throw new TypeError("Unsupported isolation level");
        }

        const transaction = new Transaction(
            ++this.#transactionId,
            isolation,
            cloneMap(this.#rows),
            this.#version
        );

        this.emit("transaction:begin", {
            id: transaction.id,
            isolation
        });

        return transaction;
    }

    #visibleRows(transaction) {
        transaction.ensureActive();

        const source = transaction.isolation === Isolation.READ_COMMITTED
            ? this.#rows
            : transaction.snapshot;

        const visible = new Map(
            [...source.entries()].map(([id, entry]) => [
                id,
                entry.product
            ])
        );

        for (const [id, product] of transaction.writes) {
            if (product === null) {
                visible.delete(id);
            } else {
                visible.set(id, product);
            }
        }

        return visible;
    }

    queryRange(transaction, predicate) {
        transaction.ensureActive();

        if (!(predicate instanceof RangePredicate)) {
            throw new TypeError("A valid RangePredicate is required");
        }

        if (transaction.isolation === Isolation.SERIALIZABLE) {
            transaction.readPredicates.push(predicate);
        }

        const results = [...this.#visibleRows(transaction).values()]
            .filter(product => predicate.contains(product.price))
            .sort((a, b) => a.id - b.id);

        this.emit("query:executed", {
            transactionId: transaction.id,
            isolation: transaction.isolation,
            rows: results.length
        });

        return results;
    }

    insert(transaction, rawProduct) {
        transaction.ensureActive();

        const product = validateProduct(rawProduct);

        if (this.#visibleRows(transaction).has(product.id)) {
            throw new WriteConflictError(
                `Product ${product.id} already exists`
            );
        }

        transaction.writes.set(product.id, product);

        this.emit("write:staged", {
            transactionId: transaction.id,
            operation: "INSERT",
            productId: product.id
        });
    }

    update(transaction, rawProduct) {
        transaction.ensureActive();

        const product = validateProduct(rawProduct);

        if (!this.#visibleRows(transaction).has(product.id)) {
            throw new TransactionError("Product does not exist");
        }

        transaction.writes.set(product.id, product);
    }

    delete(transaction, id) {
        transaction.ensureActive();

        if (!this.#visibleRows(transaction).has(id)) {
            throw new TransactionError("Product does not exist");
        }

        transaction.writes.set(id, null);
    }

    #validateWriteConflicts(transaction) {
        for (const id of transaction.writes.keys()) {
            const current = this.#rows.get(id);
            const original = transaction.snapshot.get(id);

            if (transaction.isolation !== Isolation.READ_COMMITTED) {
                if (current !== undefined && original === undefined) {
                    throw new WriteConflictError(
                        `Concurrent insertion of product ${id}`
                    );
                }

                if (
                    current !== undefined &&
                    original !== undefined &&
                    current.version !== original.version
                ) {
                    throw new WriteConflictError(
                        `Concurrent modification of product ${id}`
                    );
                }

                if (current === undefined && original !== undefined) {
                    throw new WriteConflictError(
                        `Concurrent deletion of product ${id}`
                    );
                }
            } else if (!original && current) {
                throw new WriteConflictError(
                    `Concurrent insertion of product ${id}`
                );
            }
        }
    }

    #validateSerializable(transaction) {
        for (const change of this.#history) {
            if (change.version <= transaction.startVersion) {
                continue;
            }

            if (
                transaction.readPredicates.some(
                    predicate => predicate.contains(change.price)
                )
            ) {
                throw new SerializationError(
                    "A concurrent commit changed a previously read range"
                );
            }
        }
    }

    async commit(transaction) {
        transaction.ensureActive();

        try {
            this.#validateWriteConflicts(transaction);

            if (transaction.isolation === Isolation.SERIALIZABLE) {
                this.#validateSerializable(transaction);
            }

            // Validate before changing shared state.
            for (const product of transaction.writes.values()) {
                if (product !== null) {
                    validateProduct(product);
                }
            }

            // The synchronous application phase is atomic relative to
            // other JavaScript callbacks in this event loop.
            for (const [id, product] of transaction.writes) {
                this.#version++;

                if (product === null) {
                    this.#rows.delete(id);
                } else {
                    this.#rows.set(id, {
                        product,
                        version: this.#version
                    });

                    this.#history.push({
                        version: this.#version,
                        price: product.price,
                        id
                    });
                }
            }

            transaction.state = State.COMMITTED;

            this.emit("transaction:commit", {
                id: transaction.id,
                version: this.#version
            });

            return this.#version;

        } catch (error) {
            transaction.state = State.ABORTED;

            this.emit("transaction:abort", {
                id: transaction.id,
                reason: error.message
            });

            throw error;
        }
    }

    rollback(transaction) {
        transaction.ensureActive();

        transaction.writes.clear();
        transaction.state = State.ABORTED;

        this.emit("transaction:rollback", {
            id: transaction.id
        });
    }

    currentRows() {
        return [...this.#rows.values()]
            .map(entry => ({ ...entry.product }))
            .sort((a, b) => a.id - b.id);
    }
}

function display(title, rows) {
    console.log(`\n${title}`);

    console.table(rows);

    console.log(`Returned records: ${rows.length}`);
}

async function demonstrateReadCommitted() {
    console.log("\n=== READ COMMITTED ===");

    const store = createStore();

    const reader = store.begin(Isolation.READ_COMMITTED);
    const predicate = new RangePredicate(500, 5000);

    const first = store.queryRange(reader, predicate);

    const writer = store.begin(Isolation.READ_COMMITTED);

    store.insert(writer, {
        id: 6,
        name: "Webcam",
        price: 2500,
        category: "Electronics"
    });

    await store.commit(writer);

    const second = store.queryRange(reader, predicate);

    display("First query", first);
    display("Second query", second);

    assert.equal(first.length, 3);
    assert.equal(second.length, 4);

    await store.commit(reader);
}

async function demonstrateRepeatableRead() {
    console.log("\n=== REPEATABLE READ ===");

    const store = createStore();
    const predicate = new RangePredicate(500, 5000);

    const reader = store.begin(Isolation.REPEATABLE_READ);

    const first = store.queryRange(reader, predicate);

    const writer = store.begin(Isolation.READ_COMMITTED);

    store.insert(writer, {
        id: 6,
        name: "Webcam",
        price: 2500,
        category: "Electronics"
    });

    await store.commit(writer);

    const second = store.queryRange(reader, predicate);

    display("First query", first);
    display("Second query", second);

    assert.equal(first.length, second.length);

    await store.commit(reader);

    const later = store.begin(Isolation.REPEATABLE_READ);
    const laterResults = store.queryRange(later, predicate);

    assert.equal(laterResults.length, 4);

    display("New transaction", laterResults);

    await store.commit(later);
}

async function demonstrateSerializable() {
    console.log("\n=== SERIALIZABLE ===");

    const store = createStore();
    const predicate = new RangePredicate(500, 5000);

    const reader = store.begin(Isolation.SERIALIZABLE);

    const first = store.queryRange(reader, predicate);

    const writer = store.begin(Isolation.READ_COMMITTED);

    store.insert(writer, {
        id: 6,
        name: "Webcam",
        price: 2500,
        category: "Electronics"
    });

    await store.commit(writer);

    display("Initial range", first);

    await assert.rejects(
        store.commit(reader),
        SerializationError
    );

    console.log("Serializable transaction correctly aborted.");
}

async function demonstrateBoundaries() {
    console.log("\n=== RANGE BOUNDARIES ===");

    const store = createStore();
    const transaction = store.begin(Isolation.REPEATABLE_READ);

    const predicate = new RangePredicate(800, 6000, {
        includeMinimum: true,
        includeMaximum: false
    });

    const results = store.queryRange(transaction, predicate);

    assert.ok(results.every(
        product => product.price >= 800 && product.price < 6000
    ));

    display("Range [800, 6000)", results);

    await store.commit(transaction);
}

async function demonstrateRollback() {
    console.log("\n=== ROLLBACK ===");

    const store = createStore();
    const transaction = store.begin();

    store.insert(transaction, {
        id: 99,
        name: "Temporary",
        price: 900,
        category: "Testing"
    });

    store.rollback(transaction);

    assert.ok(!store.currentRows().some(row => row.id === 99));

    console.log("Uncommitted changes discarded.");
}

function createStore() {
    const store = new TransactionalStore();

    store.on("transaction:commit", event => {
        console.log(
            `[EVENT] Transaction ${event.id} committed at version ${event.version}`
        );
    });

    store.on("transaction:abort", event => {
        console.log(
            `[EVENT] Transaction ${event.id} aborted: ${event.reason}`
        );
    });

    store.seed([
        { id: 1, name: "Keyboard", price: 1200, category: "Electronics" },
        { id: 2, name: "Mouse", price: 800, category: "Electronics" },
        { id: 3, name: "Monitor", price: 8500, category: "Electronics" },
        { id: 4, name: "Desk", price: 6000, category: "Furniture" },
        { id: 5, name: "Notebook", price: 150, category: "Stationery" }
    ]);

    return store;
}

async function main() {
    await demonstrateReadCommitted();
    await demonstrateRepeatableRead();
    await demonstrateSerializable();
    await demonstrateBoundaries();
    await demonstrateRollback();

    console.log("\nAll transaction scenarios passed.");
}

main().catch(error => {
    console.error("Execution failed:", error);
    process.exitCode = 1;
});
