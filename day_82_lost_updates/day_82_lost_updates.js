"use strict";

/*
 * Lost Updates: Event-driven concurrent write simulation.
 *
 * Demonstrates:
 * 1. Lost updates using independent stale snapshots.
 * 2. Optimistic concurrency with version validation.
 * 3. Pessimistic serialization through an asynchronous mutex.
 * 4. Conditional retries and transaction identifiers.
 * 5. Idempotency protection against duplicate requests.
 *
 * Runtime: Node.js 18+
 */

const { randomUUID } = require("node:crypto");

class ValidationError extends Error {
    constructor(message) {
        super(message);
        this.name = "ValidationError";
    }
}

class ConflictError extends Error {
    constructor(message) {
        super(message);
        this.name = "ConflictError";
    }
}

class Mutex {
    constructor() {
        this.locked = false;
        this.waiters = [];
    }

    acquire() {
        return new Promise(resolve => {
            const grant = () => {
                this.locked = true;
                let released = false;

                resolve(() => {
                    if (released) {
                        throw new Error("Lock released twice.");
                    }

                    released = true;

                    const next = this.waiters.shift();

                    if (next) {
                        next();
                    } else {
                        this.locked = false;
                    }
                });
            };

            if (!this.locked) {
                grant();
            } else {
                this.waiters.push(grant);
            }
        });
    }

    async runExclusive(operation) {
        const release = await this.acquire();

        try {
            return await operation();
        } finally {
            release();
        }
    }
}

class EventBus {
    constructor() {
        this.listeners = new Map();
    }

    on(event, callback) {
        if (typeof callback !== "function") {
            throw new ValidationError("Listener must be a function.");
        }

        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }

        this.listeners.get(event).add(callback);

        return () => this.listeners.get(event)?.delete(callback);
    }

    emit(event, payload) {
        for (const callback of this.listeners.get(event) ?? []) {
            try {
                callback(Object.freeze({ ...payload }));
            } catch (error) {
                // Observer failure must not roll back a committed write.
                console.error("Event listener failed:", error.message);
            }
        }
    }
}

class Account {
    constructor(id, owner, balance) {
        if (!Number.isSafeInteger(id) || id <= 0) {
            throw new ValidationError("Invalid account ID.");
        }

        if (typeof owner !== "string" || !owner.trim()) {
            throw new ValidationError("Account owner is required.");
        }

        if (!Number.isSafeInteger(balance) || balance < 0) {
            throw new ValidationError(
                "Balance must be a non-negative integer."
            );
        }

        this.id = id;
        this.owner = owner;
        this.balance = balance;
        this.version = 0;
    }

    snapshot() {
        return Object.freeze({
            id: this.id,
            owner: this.owner,
            balance: this.balance,
            version: this.version
        });
    }
}

class AccountService {
    constructor() {
        this.accounts = new Map();
        this.locks = new Map();
        this.idempotencyKeys = new Map();
        this.events = new EventBus();
        this.audit = [];
    }

    createAccount(account) {
        if (!(account instanceof Account)) {
            throw new ValidationError("Invalid account object.");
        }

        if (this.accounts.has(account.id)) {
            throw new ValidationError("Account already exists.");
        }

        this.accounts.set(account.id, account);
        this.locks.set(account.id, new Mutex());
    }

    getSnapshot(id) {
        const account = this.accounts.get(id);

        if (!account) {
            throw new ValidationError("Account not found.");
        }

        return account.snapshot();
    }

    validateOperation(amount, operation) {
        if (!Number.isSafeInteger(amount) || amount <= 0) {
            throw new ValidationError(
                "Amount must be a positive safe integer."
            );
        }

        if (!["deposit", "withdraw"].includes(operation)) {
            throw new ValidationError("Invalid operation.");
        }
    }

    calculate(balance, amount, operation) {
        const result = operation === "deposit"
            ? balance + amount
            : balance - amount;

        if (!Number.isSafeInteger(result)) {
            throw new ValidationError("Balance overflow.");
        }

        if (result < 0) {
            throw new ValidationError("Insufficient funds.");
        }

        return result;
    }

    record(account, previous, operation, strategy, transactionId) {
        const event = Object.freeze({
            transactionId,
            accountId: account.id,
            operation,
            strategy,
            oldBalance: previous.balance,
            newBalance: account.balance,
            oldVersion: previous.version,
            newVersion: account.version,
            timestamp: new Date().toISOString()
        });

        this.audit.push(event);
        this.events.emit("account.updated", event);
    }

    async unsafeWrite(snapshot, amount, operation) {
        this.validateOperation(amount, operation);

        const account = this.accounts.get(snapshot.id);

        if (!account) {
            throw new ValidationError("Account not found.");
        }

        const transactionId = randomUUID();

        // Simulates an asynchronous gap between read and write.
        await new Promise(resolve => setImmediate(resolve));

        const previous = account.snapshot();

        // Incorrect: the stale snapshot is used as the new base.
        account.balance = this.calculate(
            snapshot.balance,
            amount,
            operation
        );

        account.version++;

        this.record(
            account,
            previous,
            operation,
            "unsafe",
            transactionId
        );

        return account.snapshot();
    }

    async optimisticWrite(snapshot, amount, operation) {
        this.validateOperation(amount, operation);

        const account = this.accounts.get(snapshot.id);

        if (!account) {
            throw new ValidationError("Account not found.");
        }

        const transactionId = randomUUID();

        await new Promise(resolve => setImmediate(resolve));

        const previous = account.snapshot();

        if (account.version !== snapshot.version) {
            throw new ConflictError(
                `Expected version ${snapshot.version}; ` +
                `actual version ${account.version}.`
            );
        }

        account.balance = this.calculate(
            account.balance,
            amount,
            operation
        );

        account.version++;

        this.record(
            account,
            previous,
            operation,
            "optimistic",
            transactionId
        );

        return account.snapshot();
    }

    async pessimisticWrite(id, amount, operation) {
        this.validateOperation(amount, operation);

        const lock = this.locks.get(id);
        const account = this.accounts.get(id);

        if (!lock || !account) {
            throw new ValidationError("Account not found.");
        }

        return lock.runExclusive(async () => {
            const previous = account.snapshot();

            await new Promise(resolve => setImmediate(resolve));

            account.balance = this.calculate(
                account.balance,
                amount,
                operation
            );

            account.version++;

            this.record(
                account,
                previous,
                operation,
                "pessimistic",
                randomUUID()
            );

            return account.snapshot();
        });
    }

    async retryOptimistic(
        id,
        amount,
        operation,
        maxAttempts = 4
    ) {
        if (!Number.isInteger(maxAttempts) || maxAttempts < 1) {
            throw new ValidationError("Invalid retry count.");
        }

        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            const snapshot = this.getSnapshot(id);

            try {
                return await this.optimisticWrite(
                    snapshot,
                    amount,
                    operation
                );
            } catch (error) {
                if (!(error instanceof ConflictError)) {
                    throw error;
                }

                if (attempt === maxAttempts - 1) {
                    throw error;
                }

                const delay = Math.min(
                    10 * (2 ** attempt) + Math.random() * 10,
                    200
                );

                await new Promise(resolve =>
                    setTimeout(resolve, delay)
                );
            }
        }

        throw new ConflictError("Retry limit exceeded.");
    }

    async executeIdempotent(key, id, amount, operation) {
        if (typeof key !== "string" || !key.trim()) {
            throw new ValidationError("Idempotency key is required.");
        }

        // Duplicate requests return the original completed result.
        if (this.idempotencyKeys.has(key)) {
            const previous = this.idempotencyKeys.get(key);

            if (previous.id !== id ||
                previous.amount !== amount ||
                previous.operation !== operation) {
                throw new ValidationError(
                    "Idempotency key reused with different parameters."
                );
            }

            return previous.promise;
        }

        const promise = this.retryOptimistic(
            id,
            amount,
            operation
        );

        this.idempotencyKeys.set(key, {
            id,
            amount,
            operation,
            promise
        });

        try {
            return await promise;
        } catch (error) {
            // A failed operation must not permanently reserve the key.
            this.idempotencyKeys.delete(key);
            throw error;
        }
    }

    getAudit() {
        return this.audit.map(event => ({ ...event }));
    }
}

async function demonstrateLostUpdate() {
    console.log("\n1. Lost update");

    const service = new AccountService();
    service.createAccount(new Account(1, "Account A", 1000));

    const transactionA = service.getSnapshot(1);
    const transactionB = service.getSnapshot(1);

    await service.unsafeWrite(
        transactionA, 200, "deposit"
    );

    await service.unsafeWrite(
        transactionB, 100, "withdraw"
    );

    console.log("Expected balance: 1100");
    console.log("Actual balance:", service.getSnapshot(1).balance);

    if (service.getSnapshot(1).balance !== 900) {
        throw new Error("Lost-update demonstration failed.");
    }
}

async function demonstrateOptimisticConcurrency() {
    console.log("\n2. Optimistic concurrency");

    const service = new AccountService();
    service.createAccount(new Account(2, "Account B", 1000));

    const first = service.getSnapshot(2);
    const second = service.getSnapshot(2);

    await service.optimisticWrite(first, 200, "deposit");

    try {
        await service.optimisticWrite(second, 100, "withdraw");
    } catch (error) {
        if (!(error instanceof ConflictError)) {
            throw error;
        }

        console.log("Stale write rejected:", error.message);
    }

    await service.retryOptimistic(2, 100, "withdraw");

    console.log("Final account:", service.getSnapshot(2));
}

async function demonstratePessimisticConcurrency() {
    console.log("\n3. Pessimistic concurrency");

    const service = new AccountService();
    service.createAccount(new Account(3, "Account C", 1000));

    const operations = Array.from(
        { length: 100 },
        () => service.pessimisticWrite(3, 10, "deposit")
    );

    await Promise.all(operations);

    const result = service.getSnapshot(3);

    console.log("Expected balance: 2000");
    console.log("Actual balance:", result.balance);

    if (result.balance !== 2000) {
        throw new Error("Pessimistic locking failed.");
    }
}

async function demonstrateIdempotency() {
    console.log("\n4. Duplicate request handling");

    const service = new AccountService();
    service.createAccount(new Account(4, "Account D", 500));

    const [first, second] = await Promise.all([
        service.executeIdempotent(
            "payment-1001", 4, 100, "deposit"
        ),
        service.executeIdempotent(
            "payment-1001", 4, 100, "deposit"
        )
    ]);

    console.log("First response:", first.balance);
    console.log("Second response:", second.balance);
    console.log("Final balance:", service.getSnapshot(4).balance);

    if (service.getSnapshot(4).balance !== 600) {
        throw new Error("Idempotency failure.");
    }
}

async function main() {
    const service = new AccountService();

    service.events.on("account.updated", event => {
        console.log(
            `[EVENT] ${event.strategy}: account ${event.accountId}, ` +
            `${event.oldBalance} -> ${event.newBalance}`
        );
    });

    await demonstrateLostUpdate();
    await demonstrateOptimisticConcurrency();
    await demonstratePessimisticConcurrency();
    await demonstrateIdempotency();

    console.log("\n5. Validation and audit");

    try {
        service.createAccount(new Account(5, "Account E", 100));
        await service.pessimisticWrite(5, 200, "withdraw");
    } catch (error) {
        console.log("Operation rejected:", error.message);
    }

    console.log("Audit entries:", service.getAudit().length);
}

main().catch(error => {
    console.error("Application failure:", error);
    process.exitCode = 1;
});
