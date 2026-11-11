"use strict";

/*
 * MVCC: Multi-Version Concurrency Control
 *
 * Event-driven transactional storage engine.
 *
 * Features:
 * - Snapshot visibility
 * - Transaction lifecycle
 * - Version chains
 * - Read committed and snapshot isolation
 * - Optimistic conflict detection
 * - Transaction events
 * - Asynchronous transaction execution
 * - Rollback and retry
 * - Version garbage collection
 * - Structured diagnostics
 *
 * Runtime: Node.js 18+
 */

const { EventEmitter } = require("node:events");
const fs = require("node:fs/promises");
const crypto = require("node:crypto");

const Isolation = Object.freeze({
    READ_COMMITTED: "READ_COMMITTED",
    SNAPSHOT: "SNAPSHOT",
    SERIALIZABLE: "SERIALIZABLE"
});

const State = Object.freeze({
    ACTIVE: "ACTIVE",
    COMMITTED: "COMMITTED",
    ABORTED: "ABORTED"
});

class MVCCError extends Error {}
class ConflictError extends MVCCError {}
class SerializationError extends MVCCError {}
class InvalidTransactionError extends MVCCError {}

class VersionedStore extends EventEmitter {
    #rows = new Map();
    #transactions = new Map();
    #active = new Set();
    #committed = new Set();
    #aborted = new Set();

    #nextId = 1;
    #clock = 0;

    constructor() {
        super();
        this.setMaxListeners(100);
    }

    #tick() {
        return ++this.#clock;
    }

    #assertActive(transaction) {
        if (
            !transaction ||
            transaction.state !== State.ACTIVE ||
            this.#transactions.get(transaction.id) !== transaction
        ) {
            throw new InvalidTransactionError(
                "Transaction is not active or does not belong to this store"
            );
        }
    }

    begin(isolation = Isolation.SNAPSHOT) {
        if (!Object.values(Isolation).includes(isolation)) {
            throw new TypeError("Unsupported isolation level");
        }

        const id = this.#nextId++;
        const snapshot = new Set(this.#active);

        const transaction = {
            id,
            token: crypto.randomUUID(),
            isolation,
            snapshot,
            startTimestamp: this.#tick(),
            state: State.ACTIVE,
            writes: new Map(),
            reads: new Map()
        };

        this.#transactions.set(id, transaction);
        this.#active.add(id);

        this.emit("transaction:begin", {
            id,
            isolation,
            timestamp: this.#clock
        });

        return transaction;
    }

    #visible(version, transaction) {
        const creatorVisible =
            version.xmin === transaction.id ||
            (
                !transaction.snapshot.has(version.xmin) &&
                this.#committed.has(version.xmin)
            );

        if (!creatorVisible) {
            return false;
        }

        if (version.xmax === null) {
            return true;
        }

        if (version.xmax === transaction.id) {
            return false;
        }

        if (transaction.snapshot.has(version.xmax)) {
            return true;
        }

        return !this.#committed.has(version.xmax);
    }

    #findVisible(key, transaction) {
        const chain = this.#rows.get(key) || [];

        for (let i = chain.length - 1; i >= 0; i--) {
            const version = chain[i];

            if (this.#visible(version, transaction)) {
                return version.deleted ? null : version;
            }
        }

        return null;
    }

    #refreshSnapshot(transaction) {
        if (transaction.isolation === Isolation.READ_COMMITTED) {
            transaction.snapshot = new Set(this.#active);
        }
    }

    read(transaction, key) {
        this.#assertActive(transaction);
        this.#refreshSnapshot(transaction);

        const version = this.#findVisible(key, transaction);

        if (!transaction.reads.has(key)) {
            transaction.reads.set(
                key,
                version ? version.xmin : null
            );
        }

        const value = version ? structuredClone(version.value) : null;

        this.emit("transaction:read", {
            transactionId: transaction.id,
            key,
            version: version ? version.xmin : null
        });

        return value;
    }

    write(transaction, key, value) {
        this.#assertActive(transaction);

        if (
            typeof key !== "string" ||
            key.trim().length === 0
        ) {
            throw new TypeError("Key must be a non-empty string");
        }

        this.#refreshSnapshot(transaction);

        const version = this.#findVisible(key, transaction);

        if (!transaction.reads.has(key)) {
            transaction.reads.set(
                key,
                version ? version.xmin : null
            );
        }

        // Structured cloning prevents callers from modifying
        // buffered values after writing them.
        transaction.writes.set(key, structuredClone(value));

        this.emit("transaction:write", {
            transactionId: transaction.id,
            key
        });
    }

    delete(transaction, key) {
        this.#assertActive(transaction);
        this.#refreshSnapshot(transaction);

        const version = this.#findVisible(key, transaction);

        if (!version) {
            return false;
        }

        if (!transaction.reads.has(key)) {
            transaction.reads.set(key, version.xmin);
        }

        transaction.writes.set(key, null);

        this.emit("transaction:delete", {
            transactionId: transaction.id,
            key
        });

        return true;
    }

    #validateWrites(transaction) {
        for (const [key] of transaction.writes) {
            const chain = this.#rows.get(key) || [];

            const latest = [...chain]
                .reverse()
                .find(version => this.#committed.has(version.xmin));

            const observed = transaction.reads.get(key);

            if (latest && latest.xmin !== observed) {
                throw new ConflictError(
                    `Write conflict on ${key}: observed ${observed}, latest ${latest.xmin}`
                );
            }

            if (!latest && observed !== null) {
                throw new ConflictError(
                    `Expected an existing version for ${key}`
                );
            }
        }
    }

    #validateSerializable(transaction) {
        for (const [key, observed] of transaction.reads) {
            const chain = this.#rows.get(key) || [];

            const latest = [...chain]
                .reverse()
                .find(version => this.#committed.has(version.xmin));

            const current = latest ? latest.xmin : null;

            if (
                current !== observed &&
                !transaction.writes.has(key)
            ) {
                throw new SerializationError(
                    `Read dependency changed: ${key}`
                );
            }
        }
    }

    commit(transaction) {
        this.#assertActive(transaction);

        try {
            this.#validateWrites(transaction);

            if (transaction.isolation === Isolation.SERIALIZABLE) {
                this.#validateSerializable(transaction);
            }

            const changes = [];

            // Validation completes before any version is changed.
            for (const [key, value] of transaction.writes) {
                const chain = this.#rows.get(key) || [];

                const latest = [...chain]
                    .reverse()
                    .find(version => this.#committed.has(version.xmin));

                if (latest && latest.xmax === null) {
                    latest.xmax = transaction.id;
                }

                const version = {
                    value,
                    xmin: transaction.id,
                    xmax: null,
                    deleted: value === null,
                    timestamp: this.#tick()
                };

                chain.push(version);
                this.#rows.set(key, chain);

                changes.push(key);
            }

            transaction.state = State.COMMITTED;
            this.#committed.add(transaction.id);
            this.#active.delete(transaction.id);

            const event = {
                transactionId: transaction.id,
                changes,
                timestamp: this.#clock
            };

            this.emit("transaction:commit", event);

            return event;

        } catch (error) {
            this.rollback(transaction, error.message);
            throw error;
        }
    }

    rollback(transaction, reason = "Explicit rollback") {
        if (!transaction || transaction.state !== State.ACTIVE) {
            return false;
        }

        this.#assertActive(transaction);

        transaction.writes.clear();
        transaction.state = State.ABORTED;

        this.#active.delete(transaction.id);
        this.#aborted.add(transaction.id);
        this.#tick();

        this.emit("transaction:rollback", {
            transactionId: transaction.id,
            reason
        });

        return true;
    }

    async execute(work, options = {}) {
        const {
            isolation = Isolation.SNAPSHOT,
            retries = 0
        } = options;

        if (!Number.isInteger(retries) || retries < 0 || retries > 10) {
            throw new RangeError("Retries must be between 0 and 10");
        }

        let attempt = 0;

        while (true) {
            const transaction = this.begin(isolation);

            try {
                const result = await work(transaction);
                this.commit(transaction);
                return result;

            } catch (error) {
                if (transaction.state === State.ACTIVE) {
                    this.rollback(transaction, error.message);
                }

                const retryable =
                    error instanceof ConflictError ||
                    error instanceof SerializationError;

                if (!retryable || attempt >= retries) {
                    throw error;
                }

                attempt++;

                // Exponential backoff with random jitter.
                const delay =
                    Math.min(1000, 20 * 2 ** attempt) *
                    (0.5 + Math.random());

                await new Promise(resolve =>
                    setTimeout(resolve, delay)
                );
            }
        }
    }

    vacuum() {
        const horizon = this.#active.size
            ? Math.min(...this.#active)
            : this.#nextId;

        let removed = 0;

        for (const [key, chain] of this.#rows) {
            const retained = chain.filter(version => {
                const creatorAborted = this.#aborted.has(version.xmin);

                const obsolete =
                    version.xmax !== null &&
                    this.#committed.has(version.xmax) &&
                    version.xmax < horizon;

                if (creatorAborted || obsolete) {
                    removed++;
                    return false;
                }

                return true;
            });

            if (retained.length === 0) {
                this.#rows.delete(key);
            } else {
                this.#rows.set(key, retained);
            }
        }

        this.emit("vacuum:complete", {
            removed,
            horizon
        });

        return removed;
    }

    inspect(key) {
        return structuredClone(this.#rows.get(key) || []);
    }

    get statistics() {
        let versions = 0;

        for (const chain of this.#rows.values()) {
            versions += chain.length;
        }

        return {
            keys: this.#rows.size,
            versions,
            activeTransactions: this.#active.size,
            committedTransactions: this.#committed.size,
            abortedTransactions: this.#aborted.size
        };
    }

    async exportDiagnostics(filename) {
        const data = {
            generatedAt: new Date().toISOString(),
            statistics: this.statistics,
            rows: Object.fromEntries(this.#rows)
        };

        await fs.writeFile(
            filename,
            JSON.stringify(data, null, 2),
            { encoding: "utf8", flag: "wx", mode: 0o600 }
        );
    }
}

async function main() {
    const store = new VersionedStore();

    store.on("transaction:commit", event => {
        console.log("[COMMIT]", event);
    });

    store.on("transaction:rollback", event => {
        console.log("[ROLLBACK]", event);
    });

    store.on("vacuum:complete", event => {
        console.log("[VACUUM]", event);
    });

    console.log("\n1. Initialize accounts");

    await store.execute(async tx => {
        store.write(tx, "account-A", { balance: 1000 });
        store.write(tx, "account-B", { balance: 500 });
    });

    console.log("\n2. Demonstrate snapshot visibility");

    const reader = store.begin(Isolation.SNAPSHOT);

    console.log("Reader:", store.read(reader, "account-A"));

    await store.execute(async tx => {
        store.write(tx, "account-A", { balance: 1200 });
    });

    console.log(
        "Reader still sees:",
        store.read(reader, "account-A")
    );

    store.commit(reader);

    console.log("\n3. New snapshot");

    await store.execute(async tx => {
        console.log("New reader:", store.read(tx, "account-A"));
    });

    console.log("\n4. Concurrent write conflict");

    const first = store.begin();
    const second = store.begin();

    store.write(first, "account-B", { balance: 600 });
    store.write(second, "account-B", { balance: 700 });

    store.commit(first);

    try {
        store.commit(second);
    } catch (error) {
        console.log("Expected conflict:", error.message);
    }

    console.log("\n5. Read committed behavior");

    const readCommitted = store.begin(Isolation.READ_COMMITTED);

    console.log(store.read(readCommitted, "account-A"));

    await store.execute(async tx => {
        store.write(tx, "account-A", { balance: 1500 });
    });

    console.log(store.read(readCommitted, "account-A"));

    store.commit(readCommitted);

    console.log("\n6. Transaction retry");

    let attempts = 0;

    const result = await store.execute(async tx => {
        attempts++;
        const account = store.read(tx, "account-A");

        store.write(tx, "account-A", {
            balance: account.balance + 100
        });

        return "Updated successfully";
    }, {
        isolation: Isolation.SERIALIZABLE,
        retries: 3
    });

    console.log(result, "Attempts:", attempts);

    console.log("\n7. Version inspection");
    console.log(store.inspect("account-A"));

    console.log("\n8. Garbage collection");
    console.log("Removed:", store.vacuum());

    console.log("\n9. Storage statistics");
    console.log(store.statistics);
}

main().catch(error => {
    console.error("Application failure:", error);
    process.exitCode = 1;
});
