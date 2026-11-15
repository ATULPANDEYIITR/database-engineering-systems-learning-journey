"use strict";

/*
 * ACID Fundamentals: Transaction Processing Engine
 *
 * Node.js 18+
 *
 * Demonstrates:
 * - Atomicity through staged transaction changes.
 * - Consistency through centralized domain validation.
 * - Isolation through optimistic serializable validation.
 * - Durability through atomic file replacement.
 * - Transaction lifecycle and state transitions.
 * - Concurrent transaction conflicts.
 * - Idempotency keys.
 * - Transaction event notifications.
 *
 * No third-party dependencies.
 */

const fs = require("node:fs/promises");
const path = require("node:path");
const crypto = require("node:crypto");
const { EventEmitter } = require("node:events");

class TransactionError extends Error {}
class ConstraintViolation extends TransactionError {}
class InsufficientFunds extends TransactionError {}
class SerializationConflict extends TransactionError {}
class DuplicateTransaction extends TransactionError {}

const TransactionState = Object.freeze({
    ACTIVE: "ACTIVE",
    COMMITTED: "COMMITTED",
    ROLLED_BACK: "ROLLED_BACK"
});

function validateAmount(amount) {
    if (!Number.isSafeInteger(amount) || amount <= 0) {
        throw new ConstraintViolation(
            "Amount must be a positive integer number of cents."
        );
    }
}

function validateAccount(account) {
    if (!Number.isSafeInteger(account.id) || account.id <= 0) {
        throw new ConstraintViolation("Invalid account identifier.");
    }

    if (typeof account.owner !== "string" || !account.owner.trim()) {
        throw new ConstraintViolation("Account owner is required.");
    }

    if (!Number.isSafeInteger(account.balance) || account.balance < 0) {
        throw new ConstraintViolation("Invalid account balance.");
    }

    if (!Number.isSafeInteger(account.version) || account.version < 0) {
        throw new ConstraintViolation("Invalid account version.");
    }
}

class Transaction {
    constructor(store, id) {
        this.store = store;
        this.id = id;
        this.state = TransactionState.ACTIVE;

        // Snapshot isolates the transaction from subsequent modifications.
        this.snapshot = new Map(
            [...store.accounts.entries()].map(([key, value]) => [
                key,
                { ...value }
            ])
        );

        this.staged = new Map();
        this.originalVersions = new Map();
        this.operations = [];
        this.startedAt = Date.now();
    }

    ensureActive() {
        if (this.state !== TransactionState.ACTIVE) {
            throw new TransactionError(
                `Transaction is ${this.state}.`
            );
        }
    }

    getAccount(id) {
        this.ensureActive();

        if (this.staged.has(id)) {
            return { ...this.staged.get(id) };
        }

        const account = this.snapshot.get(id);

        if (!account) {
            throw new ConstraintViolation(
                `Account ${id} does not exist.`
            );
        }

        return { ...account };
    }

    updateAccount(account) {
        this.ensureActive();
        validateAccount(account);

        if (!this.snapshot.has(account.id)) {
            throw new ConstraintViolation("Unknown account.");
        }

        if (!this.originalVersions.has(account.id)) {
            this.originalVersions.set(
                account.id,
                this.snapshot.get(account.id).version
            );
        }

        this.staged.set(account.id, { ...account });
    }

    transfer(sourceId, destinationId, amount) {
        this.ensureActive();
        validateAmount(amount);

        if (sourceId === destinationId) {
            throw new ConstraintViolation(
                "Source and destination must differ."
            );
        }

        const source = this.getAccount(sourceId);
        const destination = this.getAccount(destinationId);

        if (source.balance < amount) {
            throw new InsufficientFunds(
                "Insufficient funds for transfer."
            );
        }

        source.balance -= amount;
        destination.balance += amount;

        if (!Number.isSafeInteger(destination.balance)) {
            throw new ConstraintViolation(
                "Destination balance exceeds safe integer range."
            );
        }

        this.updateAccount(source);
        this.updateAccount(destination);

        this.operations.push({
            type: "TRANSFER",
            sourceId,
            destinationId,
            amount
        });
    }

    rollback() {
        this.ensureActive();
        this.staged.clear();
        this.operations.length = 0;
        this.state = TransactionState.ROLLED_BACK;
    }
}

class TransactionalStore extends EventEmitter {
    constructor(filePath) {
        super();

        this.filePath = path.resolve(filePath);
        this.accounts = new Map();
        this.transactions = new Map();
        this.sequence = 0;
        this.commitVersion = 0;
        this.commitQueue = Promise.resolve();
        this.idempotency = new Map();
    }

    async initialize() {
        try {
            const raw = await fs.readFile(this.filePath, "utf8");
            const data = JSON.parse(raw);

            if (!Array.isArray(data.accounts)) {
                throw new TransactionError(
                    "Invalid persisted account structure."
                );
            }

            const loaded = new Map();

            for (const account of data.accounts) {
                validateAccount(account);

                if (loaded.has(account.id)) {
                    throw new ConstraintViolation(
                        "Duplicate persisted account."
                    );
                }

                loaded.set(account.id, { ...account });
            }

            this.accounts = loaded;
            this.commitVersion = data.commitVersion || 0;
            this.transactions = new Map(
                data.transactions || []
            );
            this.idempotency = new Map(
                data.idempotency || []
            );

            for (const [id, account] of this.accounts) {
                this.sequence = Math.max(this.sequence, id);
            }
        } catch (error) {
            if (error.code !== "ENOENT") {
                throw error;
            }
        }
    }

    createAccount(owner, initialBalance = 0) {
        if (typeof owner !== "string" || !owner.trim()) {
            throw new ConstraintViolation("Owner is required.");
        }

        if (!Number.isSafeInteger(initialBalance) || initialBalance < 0) {
            throw new ConstraintViolation(
                "Initial balance must be non-negative integer cents."
            );
        }

        const id = ++this.sequence;

        this.accounts.set(id, {
            id,
            owner: owner.trim(),
            balance: initialBalance,
            version: 0
        });

        return id;
    }

    beginTransaction() {
        const id = crypto.randomUUID();
        return new Transaction(this, id);
    }

    async withCommitLock(callback) {
        const previous = this.commitQueue;

        let release;
        this.commitQueue = new Promise(resolve => {
            release = resolve;
        });

        await previous;

        try {
            return await callback();
        } finally {
            release();
        }
    }

    async persist(accounts, transactions, idempotency, version) {
        const directory = path.dirname(this.filePath);

        await fs.mkdir(directory, { recursive: true });

        const temporaryPath =
            `${this.filePath}.${crypto.randomUUID()}.tmp`;

        const data = {
            commitVersion: version,
            accounts: [...accounts.values()],
            transactions: [...transactions.entries()],
            idempotency: [...idempotency.entries()]
        };

        let handle;

        try {
            handle = await fs.open(temporaryPath, "wx", 0o600);
            await handle.writeFile(
                JSON.stringify(data, null, 2),
                "utf8"
            );
            await handle.sync();
            await handle.close();
            handle = null;

            // Atomic replacement on filesystems supporting same-filesystem rename.
            await fs.rename(temporaryPath, this.filePath);
        } catch (error) {
            if (handle) {
                await handle.close().catch(() => {});
            }

            await fs.unlink(temporaryPath).catch(() => {});
            throw error;
        }
    }

    async commit(transaction, idempotencyKey = null) {
        transaction.ensureActive();

        return this.withCommitLock(async () => {
            if (idempotencyKey !== null) {
                if (
                    typeof idempotencyKey !== "string" ||
                    !idempotencyKey.trim() ||
                    idempotencyKey.length > 200
                ) {
                    throw new ConstraintViolation(
                        "Invalid idempotency key."
                    );
                }

                if (this.idempotency.has(idempotencyKey)) {
                    throw new DuplicateTransaction(
                        "This idempotency key was already committed."
                    );
                }
            }

            // Verify all observed versions before applying staged changes.
            for (const [id, expectedVersion] of
                transaction.originalVersions) {
                const current = this.accounts.get(id);

                if (!current || current.version !== expectedVersion) {
                    transaction.state = TransactionState.ROLLED_BACK;

                    throw new SerializationConflict(
                        `Account ${id} changed during the transaction.`
                    );
                }
            }

            const nextAccounts = new Map(
                [...this.accounts.entries()].map(([id, account]) => [
                    id,
                    { ...account }
                ])
            );

            for (const [id, stagedAccount] of transaction.staged) {
                const updated = {
                    ...stagedAccount,
                    version: nextAccounts.get(id).version + 1
                };

                validateAccount(updated);
                nextAccounts.set(id, updated);
            }

            // Independent accounts cannot become negative.
            for (const account of nextAccounts.values()) {
                validateAccount(account);
            }

            const nextTransactions = new Map(this.transactions);

            nextTransactions.set(transaction.id, {
                id: transaction.id,
                operations: transaction.operations,
                committedAt: new Date().toISOString()
            });

            const nextIdempotency = new Map(this.idempotency);

            if (idempotencyKey !== null) {
                nextIdempotency.set(
                    idempotencyKey,
                    transaction.id
                );
            }

            const nextVersion = this.commitVersion + 1;

            // Publish state only after persistent storage succeeds.
            await this.persist(
                nextAccounts,
                nextTransactions,
                nextIdempotency,
                nextVersion
            );

            this.accounts = nextAccounts;
            this.transactions = nextTransactions;
            this.idempotency = nextIdempotency;
            this.commitVersion = nextVersion;

            transaction.state = TransactionState.COMMITTED;

            this.emit("commit", {
                transactionId: transaction.id,
                commitVersion: nextVersion
            });

            return {
                transactionId: transaction.id,
                commitVersion: nextVersion,
                operations: transaction.operations.length
            };
        });
    }

    getAccount(id) {
        const account = this.accounts.get(id);

        if (!account) {
            throw new ConstraintViolation(
                `Account ${id} does not exist.`
            );
        }

        return Object.freeze({ ...account });
    }

    getTotalBalance() {
        return [...this.accounts.values()].reduce(
            (total, account) => total + BigInt(account.balance),
            0n
        );
    }
}

async function demonstrate() {
    const filePath = path.join(
        process.cwd(),
        "acid_accounts.json"
    );

    await fs.unlink(filePath).catch(() => {});

    const store = new TransactionalStore(filePath);
    await store.initialize();

    store.on("commit", event => {
        console.log("COMMIT EVENT:", event);
    });

    const source = store.createAccount("Treasury", 100000);
    const destination = store.createAccount("Research", 25000);

    const initialTotal = store.getTotalBalance();

    console.log("\nINITIAL ACCOUNTS");
    console.log(store.getAccount(source));
    console.log(store.getAccount(destination));

    console.log("\nATOMICITY");

    const failed = store.beginTransaction();

    try {
        failed.transfer(source, destination, 5000);

        // Explicit rollback: staged changes never reach committed state.
        failed.rollback();
    } catch (error) {
        console.error(error.message);
    }

    console.assert(store.getTotalBalance() === initialTotal);

    console.log("\nCONSISTENCY");

    const invalid = store.beginTransaction();

    try {
        invalid.transfer(source, destination, 99999999);
    } catch (error) {
        console.log("Rejected:", error.message);
        invalid.rollback();
    }

    console.log("\nISOLATION");

    const first = store.beginTransaction();
    const second = store.beginTransaction();

    first.transfer(source, destination, 1000);
    second.transfer(source, destination, 2000);

    await store.commit(first, "transfer-001");

    try {
        await store.commit(second, "transfer-002");
    } catch (error) {
        console.log("Concurrent transaction rejected:", error.message);
    }

    console.log("\nIDEMPOTENCY");

    const duplicate = store.beginTransaction();
    duplicate.transfer(source, destination, 100);

    try {
        await store.commit(duplicate, "transfer-001");
    } catch (error) {
        console.log("Duplicate rejected:", error.message);
        if (duplicate.state === TransactionState.ACTIVE) {
            duplicate.rollback();
        }
    }

    console.log("\nDURABILITY");

    const reopened = new TransactionalStore(filePath);
    await reopened.initialize();

    console.log("Recovered treasury:", reopened.getAccount(source));
    console.log("Recovered research:", reopened.getAccount(destination));

    console.assert(
        reopened.getTotalBalance() === initialTotal
    );

    console.log("\nFINAL COMMITTED BALANCES");

    console.log(reopened.getAccount(source));
    console.log(reopened.getAccount(destination));
    console.log("Total cents:", reopened.getTotalBalance().toString());

    console.log("\nACID execution completed.");
}

demonstrate().catch(error => {
    console.error("FATAL:", error);
    process.exitCode = 1;
});
