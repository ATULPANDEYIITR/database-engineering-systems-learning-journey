"use strict";

/*
 * Transaction Lifecycle and Policy Engine
 *
 * Demonstrates:
 * - Event-driven transaction processing
 * - State transitions
 * - Commit and rollback
 * - Savepoints
 * - Asynchronous transaction execution
 * - Atomic publication of changes
 * - Optimistic concurrency control
 * - Transaction audit events
 *
 * Runtime: Node.js 18+
 *
 * Run:
 *   node transaction_lifecycle.js
 */

const { randomUUID } = require("node:crypto");
const { EventEmitter } = require("node:events");
const { writeFile } = require("node:fs/promises");

const State = Object.freeze({
    NEW: "NEW",
    ACTIVE: "ACTIVE",
    COMMITTING: "COMMITTING",
    COMMITTED: "COMMITTED",
    ROLLING_BACK: "ROLLING_BACK",
    ROLLED_BACK: "ROLLED_BACK",
    FAILED: "FAILED"
});

const transitions = Object.freeze({
    NEW: ["ACTIVE"],
    ACTIVE: ["COMMITTING", "ROLLING_BACK", "FAILED"],
    COMMITTING: ["COMMITTED", "FAILED"],
    ROLLING_BACK: ["ROLLED_BACK", "FAILED"],
    FAILED: ["ROLLING_BACK"],
    COMMITTED: [],
    ROLLED_BACK: []
});

class TransactionError extends Error {}
class ValidationError extends TransactionError {}
class InvalidStateError extends TransactionError {}
class InsufficientFundsError extends TransactionError {}
class ConcurrencyError extends TransactionError {}

function validateMoney(value) {
    if (
        typeof value !== "number" ||
        !Number.isFinite(value) ||
        value <= 0
    ) {
        throw new ValidationError(
            "Amount must be a positive finite number."
        );
    }

    // Monetary values are represented as integer cents.
    const cents = Math.round(value * 100);

    if (Math.abs(cents / 100 - value) > 0.000001) {
        throw new ValidationError("Amount supports at most two decimals.");
    }

    return cents;
}

function cloneAccounts(accounts) {
    return new Map(
        [...accounts.entries()].map(([id, account]) => [
            id,
            { ...account }
        ])
    );
}

class Transaction extends EventEmitter {
    constructor(snapshot) {
        super();

        this.id = randomUUID();
        this.state = State.NEW;
        this.workingAccounts = cloneAccounts(snapshot);
        this.originalVersions = new Map(
            [...snapshot.entries()].map(([id, account]) => [
                id,
                account.version
            ])
        );

        this.operations = [];
        this.history = [];
        this.savepoints = new Map();
        this.error = null;

        this.transition(State.ACTIVE, "Transaction started");
    }

    transition(next, description) {
        if (!transitions[this.state].includes(next)) {
            throw new InvalidStateError(
                `Invalid transition ${this.state} -> ${next}`
            );
        }

        const event = Object.freeze({
            transactionId: this.id,
            previous: this.state,
            current: next,
            description,
            timestamp: new Date().toISOString()
        });

        this.state = next;
        this.history.push(event);

        // Event consumers cannot alter the internal state through payloads.
        this.emit("stateChanged", event);

        return event;
    }

    assertActive() {
        if (this.state !== State.ACTIVE) {
            throw new InvalidStateError(
                `Operation rejected in state ${this.state}`
            );
        }
    }

    account(id) {
        const account = this.workingAccounts.get(id);

        if (!account) {
            throw new ValidationError(`Unknown account: ${id}`);
        }

        return account;
    }

    transfer(sourceId, destinationId, amount) {
        this.assertActive();

        if (sourceId === destinationId) {
            throw new ValidationError(
                "Source and destination must differ."
            );
        }

        const cents = validateMoney(amount);
        const source = this.account(sourceId);
        const destination = this.account(destinationId);

        if (source.balanceCents < cents) {
            throw new InsufficientFundsError("Insufficient funds.");
        }

        // Stage both sides together in the private working snapshot.
        source.balanceCents -= cents;
        destination.balanceCents += cents;

        this.operations.push({
            type: "TRANSFER",
            sourceId,
            destinationId,
            amountCents: cents
        });
    }

    deposit(accountId, amount) {
        this.assertActive();

        const cents = validateMoney(amount);
        const account = this.account(accountId);

        account.balanceCents += cents;

        this.operations.push({
            type: "DEPOSIT",
            accountId,
            amountCents: cents
        });
    }

    withdraw(accountId, amount) {
        this.assertActive();

        const cents = validateMoney(amount);
        const account = this.account(accountId);

        if (account.balanceCents < cents) {
            throw new InsufficientFundsError("Insufficient funds.");
        }

        account.balanceCents -= cents;

        this.operations.push({
            type: "WITHDRAW",
            accountId,
            amountCents: cents
        });
    }

    savepoint(name) {
        this.assertActive();

        if (!name || this.savepoints.has(name)) {
            throw new ValidationError("Invalid or duplicate savepoint.");
        }

        this.savepoints.set(name, {
            accounts: cloneAccounts(this.workingAccounts),
            operationCount: this.operations.length
        });

        this.operations.push({
            type: "SAVEPOINT",
            name
        });
    }

    rollbackTo(name) {
        this.assertActive();

        const point = this.savepoints.get(name);

        if (!point) {
            throw new ValidationError("Savepoint does not exist.");
        }

        this.workingAccounts = cloneAccounts(point.accounts);
        this.operations.length = point.operationCount;

        const names = [...this.savepoints.keys()];
        const index = names.indexOf(name);

        for (const later of names.slice(index + 1)) {
            this.savepoints.delete(later);
        }

        this.operations.push({
            type: "ROLLBACK_TO_SAVEPOINT",
            name
        });
    }
}

class AccountStore {
    constructor() {
        this.accounts = new Map();
        this.commitQueue = Promise.resolve();
    }

    addAccount(id, owner, balance) {
        if (!id || !owner || this.accounts.has(id)) {
            throw new ValidationError("Invalid or duplicate account.");
        }

        const cents = Math.round(balance * 100);

        if (
            !Number.isFinite(balance) ||
            balance < 0 ||
            Math.abs(cents / 100 - balance) > 0.000001
        ) {
            throw new ValidationError("Invalid initial balance.");
        }

        this.accounts.set(id, {
            id,
            owner,
            balanceCents: cents,
            version: 0
        });
    }

    snapshot() {
        return cloneAccounts(this.accounts);
    }

    begin() {
        return new Transaction(this.snapshot());
    }

    /*
     * Commits are serialized through a promise queue.
     * Version checking detects transactions that used stale snapshots.
     */
    async commit(transaction) {
        transaction.assertActive();

        transaction.transition(
            State.COMMITTING,
            "Commit validation started"
        );

        const executeCommit = async () => {
            try {
                const changed = [];

                for (const [id, staged] of transaction.workingAccounts) {
                    const current = this.accounts.get(id);

                    if (!current) {
                        throw new ConcurrencyError(
                            `Account was removed: ${id}`
                        );
                    }

                    if (
                        current.version !==
                        transaction.originalVersions.get(id)
                    ) {
                        throw new ConcurrencyError(
                            `Stale account version: ${id}`
                        );
                    }

                    if (
                        !Number.isSafeInteger(staged.balanceCents) ||
                        staged.balanceCents < 0
                    ) {
                        throw new ValidationError(
                            `Invalid balance for ${id}`
                        );
                    }

                    if (
                        staged.balanceCents !== current.balanceCents
                    ) {
                        changed.push([id, staged]);
                    }
                }

                // No asynchronous operation occurs during publication.
                for (const [id, staged] of changed) {
                    this.accounts.set(id, {
                        ...staged,
                        version: this.accounts.get(id).version + 1
                    });
                }

                transaction.transition(
                    State.COMMITTED,
                    "Changes atomically published"
                );

                return true;
            } catch (error) {
                transaction.error = error.message;

                transaction.transition(
                    State.FAILED,
                    `Commit rejected: ${error.message}`
                );

                throw error;
            }
        };

        const currentCommit = this.commitQueue.then(executeCommit);

        // Keep the queue usable even when one transaction fails.
        this.commitQueue = currentCommit.catch(() => {});

        return currentCommit;
    }

    rollback(transaction) {
        if (
            ![State.ACTIVE, State.FAILED].includes(transaction.state)
        ) {
            throw new InvalidStateError("Transaction cannot be rolled back.");
        }

        transaction.transition(
            State.ROLLING_BACK,
            "Discarding staged changes"
        );

        transaction.workingAccounts = this.snapshot();
        transaction.operations = [];
        transaction.savepoints.clear();

        transaction.transition(
            State.ROLLED_BACK,
            "Rollback completed"
        );
    }

    report() {
        return [...this.accounts.values()].map(account => ({
            id: account.id,
            owner: account.owner,
            balance: (account.balanceCents / 100).toFixed(2),
            version: account.version
        }));
    }
}

class TransactionService {
    constructor(store) {
        this.store = store;
    }

    async execute(work) {
        const transaction = this.store.begin();

        transaction.on("stateChanged", event => {
            console.log(
                `[${event.transactionId.slice(0, 8)}]`,
                `${event.previous} -> ${event.current}`
            );
        });

        try {
            await work(transaction);
            await this.store.commit(transaction);

            return {
                success: true,
                transactionId: transaction.id,
                state: transaction.state
            };
        } catch (error) {
            if (
                [State.ACTIVE, State.FAILED].includes(transaction.state)
            ) {
                this.store.rollback(transaction);
            }

            return {
                success: false,
                transactionId: transaction.id,
                state: transaction.state,
                error: error.message
            };
        }
    }
}

async function main() {
    const store = new AccountStore();

    store.addAccount("ACC-001", "Alice", 10000);
    store.addAccount("ACC-002", "Bob", 5000);
    store.addAccount("ACC-003", "Charlie", 2500);

    const service = new TransactionService(store);

    console.log("\nSCENARIO 1: SUCCESSFUL COMMIT");

    const successful = await service.execute(async transaction => {
        transaction.transfer("ACC-001", "ACC-002", 1500);
        transaction.deposit("ACC-003", 250);
    });

    console.log(successful);

    console.log("\nSCENARIO 2: SAVEPOINT AND PARTIAL ROLLBACK");

    const savepointResult = await service.execute(async transaction => {
        transaction.deposit("ACC-001", 200);

        transaction.savepoint("before_withdrawal");

        transaction.withdraw("ACC-002", 300);

        transaction.rollbackTo("before_withdrawal");
    });

    console.log(savepointResult);

    console.log("\nSCENARIO 3: VALIDATION FAILURE");

    const failed = await service.execute(async transaction => {
        transaction.withdraw("ACC-002", 999999);
    });

    console.log(failed);

    console.log("\nSCENARIO 4: CONCURRENT TRANSACTIONS");

    const first = store.begin();
    const second = store.begin();

    first.deposit("ACC-001", 100);
    second.deposit("ACC-001", 200);

    await store.commit(first);

    try {
        await store.commit(second);
    } catch (error) {
        console.log("Expected conflict:", error.message);
        store.rollback(second);
    }

    console.log("\nFINAL ACCOUNT REPORT");

    console.table(store.report());

    console.log("\nSCENARIO 5: AUDIT EXPORT");

    const audit = {
        generatedAt: new Date().toISOString(),
        accounts: store.report()
    };

    await writeFile(
        "transaction_audit.json",
        JSON.stringify(audit, null, 2),
        { encoding: "utf8", flag: "w", mode: 0o600 }
    );

    console.log("Audit report written.");
}

main().catch(error => {
    console.error("Application failure:", error);
    process.exitCode = 1;
});
