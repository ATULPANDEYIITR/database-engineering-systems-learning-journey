"use strict";

/*
 * Stored Procedures and Triggers
 *
 * This Node.js program models database automation as an event-driven system.
 * Procedures expose explicit business operations, while trigger-like handlers
 * automatically react to row events.
 */

const EventEmitter = require("node:events");

class DatabaseError extends Error {}
class ConstraintViolation extends DatabaseError {}
class NotFoundError extends DatabaseError {}

class RepositoryDatabase extends EventEmitter {
    constructor() {
        super();
        this.accounts = new Map();
        this.transactions = new Map();
        this.auditLog = [];
        this.nextTransactionId = 1;
        this.nextAuditId = 1;

        // Trigger registration is explicit so execution order is visible.
        this.on("beforeInsertAccount", this.validateAccount.bind(this));
        this.on("beforeUpdateAccount", this.validateBalanceChange.bind(this));
        this.on("afterUpdateAccount", this.auditAccountUpdate.bind(this));
        this.on(
            "afterInsertTransaction",
            this.applyTransactionToBalance.bind(this)
        );
    }

    emitOrThrow(eventName, ...args) {
        this.emit(eventName, ...args);
    }

    validateAccount(account) {
        if (!Number.isInteger(account.id) || account.id <= 0) {
            throw new ConstraintViolation("Account ID must be a positive integer");
        }

        if (!account.customerName || account.customerName.trim().length === 0) {
            throw new ConstraintViolation("Customer name cannot be empty");
        }

        if (!Number.isFinite(account.balance) || account.balance < 0) {
            throw new ConstraintViolation("Account balance must be non-negative");
        }
    }

    validateBalanceChange(oldAccount, newAccount) {
        const difference = Math.abs(newAccount.balance - oldAccount.balance);

        if (difference > 10000) {
            throw new ConstraintViolation(
                "A single account update cannot change balance by more than 10000"
            );
        }
    }

    auditAccountUpdate(oldAccount, newAccount) {
        this.auditLog.push({
            auditId: this.nextAuditId++,
            table: "accounts",
            rowId: newAccount.id,
            action: "UPDATE",
            oldBalance: oldAccount.balance,
            newBalance: newAccount.balance,
            changedAt: new Date().toISOString(),
        });
    }

    applyTransactionToBalance(transaction) {
        const account = this.accounts.get(transaction.accountId);

        if (!account) {
            throw new NotFoundError(
                `Account ${transaction.accountId} does not exist`
            );
        }

        const updated = { ...account };

        if (transaction.type === "CREDIT") {
            updated.balance += transaction.amount;
        } else if (transaction.type === "DEBIT") {
            updated.balance -= transaction.amount;
        } else {
            throw new ConstraintViolation(
                `Unsupported transaction type: ${transaction.type}`
            );
        }

        if (updated.balance < 0) {
            throw new ConstraintViolation("Debit would produce a negative balance");
        }

        this.updateAccount(account.id, updated.balance);
    }

    insertAccount(account) {
        if (this.accounts.has(account.id)) {
            throw new ConstraintViolation("Account ID already exists");
        }

        const normalized = {
            id: account.id,
            customerName: account.customerName.trim(),
            balance: account.balance,
            active: true,
        };

        this.emitOrThrow("beforeInsertAccount", normalized);
        this.accounts.set(normalized.id, normalized);

        return { ...normalized };
    }

    updateAccount(id, newBalance) {
        const current = this.accounts.get(id);

        if (!current) {
            throw new NotFoundError(`Account ${id} does not exist`);
        }

        const updated = {
            ...current,
            balance: newBalance,
        };

        this.emitOrThrow("beforeUpdateAccount", current, updated);
        this.accounts.set(id, updated);
        this.emitOrThrow("afterUpdateAccount", current, updated);

        return { ...updated };
    }

    insertTransaction(accountId, amount, type) {
        if (!this.accounts.has(accountId)) {
            throw new NotFoundError(`Account ${accountId} does not exist`);
        }

        if (!Number.isFinite(amount) || amount <= 0) {
            throw new ConstraintViolation("Transaction amount must be positive");
        }

        if (!["CREDIT", "DEBIT"].includes(type)) {
            throw new ConstraintViolation("Invalid transaction type");
        }

        const transaction = {
            id: this.nextTransactionId++,
            accountId,
            amount,
            type,
            createdAt: new Date().toISOString(),
        };

        this.transactions.set(transaction.id, transaction);

        try {
            this.emitOrThrow("afterInsertTransaction", transaction);
        } catch (error) {
            this.transactions.delete(transaction.id);
            throw error;
        }

        return { ...transaction };
    }
}

/*
 * Procedure-like operation:
 * it exposes a controlled API instead of allowing callers to manipulate
 * multiple related rows independently.
 */
function createAccountProcedure(database, id, customerName, openingBalance) {
    return database.insertAccount({
        id,
        customerName,
        balance: openingBalance,
    });
}

/*
 * A transfer is treated as one logical unit. The snapshot provides
 * rollback behavior for this in-memory model.
 */
function transferProcedure(database, sourceId, destinationId, amount) {
    if (sourceId === destinationId) {
        throw new ConstraintViolation(
            "Source and destination accounts must differ"
        );
    }

    if (amount <= 0 || !Number.isFinite(amount)) {
        throw new ConstraintViolation("Transfer amount must be positive");
    }

    const sourceBefore = database.accounts.get(sourceId);
    const destinationBefore = database.accounts.get(destinationId);

    if (!sourceBefore || !destinationBefore) {
        throw new NotFoundError("Both accounts must exist");
    }

    const transactionIdsBefore = new Set(database.transactions.keys());
    const auditLengthBefore = database.auditLog.length;

    try {
        if (sourceBefore.balance < amount) {
            throw new ConstraintViolation("Insufficient funds");
        }

        database.insertTransaction(sourceId, amount, "DEBIT");
        database.insertTransaction(destinationId, amount, "CREDIT");

        return {
            source: database.accounts.get(sourceId),
            destination: database.accounts.get(destinationId),
        };
    } catch (error) {
        database.accounts.set(sourceId, sourceBefore);
        database.accounts.set(destinationId, destinationBefore);

        for (const id of database.transactions.keys()) {
            if (!transactionIdsBefore.has(id)) {
                database.transactions.delete(id);
            }
        }

        database.auditLog.length = auditLengthBefore;
        throw error;
    }
}

function printAccounts(database, title) {
    console.log(`\n${title}`);

    for (const account of database.accounts.values()) {
        console.log(
            `${account.id}: ${account.customerName} -> ${account.balance.toFixed(
                2
            )}`
        );
    }
}

function main() {
    const database = new RepositoryDatabase();

    createAccountProcedure(database, 101, "Aarav Mehta", 10000);
    createAccountProcedure(database, 102, "Meera Sharma", 5000);

    printAccounts(database, "Initial state");

    database.insertTransaction(101, 750, "CREDIT");
    database.insertTransaction(102, 500, "DEBIT");

    printAccounts(database, "After trigger-driven transactions");

    try {
        transferProcedure(database, 101, 102, 1000);
    } catch (error) {
        console.error("Transfer failed:", error.message);
    }

    printAccounts(database, "After successful transfer");

    console.log("\nAudit log");
    console.table(database.auditLog);

    console.log("\nTesting validation failure");

    try {
        createAccountProcedure(database, 103, "", 100);
    } catch (error) {
        console.error("Expected failure:", error.message);
    }

    console.log("\nTesting trigger-enforced update rule");

    try {
        database.updateAccount(101, 50000);
    } catch (error) {
        console.error("Expected failure:", error.message);
    }

    console.log("\nTesting insufficient funds");

    try {
        transferProcedure(database, 102, 101, 100000);
    } catch (error) {
        console.error("Expected failure:", error.message);
    }

    printAccounts(database, "Final state");
}

main();
