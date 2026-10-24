'use strict';

/*
 * PostgreSQL transaction concepts represented as an event-driven
 * application-side transaction manager.
 *
 * The model demonstrates:
 * - BEGIN
 * - COMMIT
 * - ROLLBACK
 * - SAVEPOINT
 * - ROLLBACK TO SAVEPOINT
 * - RELEASE SAVEPOINT
 * - validation and constraint failures
 * - transaction-local state
 * - optimistic conflict detection
 *
 * No npm dependencies are required.
 */

const { EventEmitter } = require('node:events');

class ConstraintError extends Error {}
class TransactionStateError extends Error {}
class SerializationConflict extends Error {}

const TransactionState = Object.freeze({
    ACTIVE: 'ACTIVE',
    COMMITTED: 'COMMITTED',
    ROLLED_BACK: 'ROLLED_BACK',
});

function cloneAccounts(accounts) {
    return new Map(
        [...accounts.entries()].map(([id, account]) => [
            id,
            { ...account },
        ])
    );
}

class Repository {
    constructor() {
        this.accounts = new Map();
        this.auditLog = [];
        this.version = 0;
    }

    addAccount(id, owner, balance) {
        if (this.accounts.has(id)) {
            throw new ConstraintError(`duplicate account ${id}`);
        }

        if (!Number.isFinite(balance) || balance < 0) {
            throw new ConstraintError('balance must be a non-negative number');
        }

        this.accounts.set(id, {
            id,
            owner,
            balance,
            version: 0,
        });

        this.version += 1;
    }
}

class Transaction extends EventEmitter {
    constructor(repository, id) {
        super();

        this.repository = repository;
        this.id = id;
        this.state = TransactionState.ACTIVE;
        this.startVersion = repository.version;

        this.accounts = cloneAccounts(repository.accounts);
        this.auditLog = [...repository.auditLog];
        this.savepoints = new Map();
    }

    requireActive() {
        if (this.state !== TransactionState.ACTIVE) {
            throw new TransactionStateError(
                `transaction is ${this.state.toLowerCase()}`
            );
        }
    }

    account(id) {
        this.requireActive();

        const account = this.accounts.get(id);

        if (!account) {
            throw new ConstraintError(`account ${id} does not exist`);
        }

        return account;
    }

    audit(action, details) {
        this.auditLog.push({
            transactionId: this.id,
            action,
            details,
            timestamp: new Date().toISOString(),
        });

        this.emit('change', {
            transactionId: this.id,
            action,
            details,
        });
    }

    beginSavepoint(name) {
        this.requireActive();

        if (!name) {
            throw new ConstraintError('savepoint name is required');
        }

        this.savepoints.set(name, {
            accounts: cloneAccounts(this.accounts),
            auditLog: [...this.auditLog],
        });

        this.emit('savepoint', {
            transactionId: this.id,
            name,
        });
    }

    rollbackToSavepoint(name) {
        this.requireActive();

        const point = this.savepoints.get(name);

        if (!point) {
            throw new TransactionStateError(
                `savepoint ${name} does not exist`
            );
        }

        this.accounts = cloneAccounts(point.accounts);
        this.auditLog = [...point.auditLog];

        let found = false;
        for (const key of [...this.savepoints.keys()]) {
            if (key === name) {
                found = true;
                continue;
            }

            if (found) {
                this.savepoints.delete(key);
            }
        }

        this.emit('rollbackToSavepoint', {
            transactionId: this.id,
            name,
        });
    }

    releaseSavepoint(name) {
        this.requireActive();

        if (!this.savepoints.has(name)) {
            throw new TransactionStateError(
                `savepoint ${name} does not exist`
            );
        }

        this.savepoints.delete(name);

        this.emit('releaseSavepoint', {
            transactionId: this.id,
            name,
        });
    }

    deposit(id, amount) {
        const account = this.account(id);

        if (!Number.isFinite(amount) || amount <= 0) {
            throw new ConstraintError(
                'deposit amount must be positive'
            );
        }

        account.balance += amount;

        this.audit(
            'DEPOSIT',
            `account=${id}, amount=${amount.toFixed(2)}`
        );
    }

    withdraw(id, amount) {
        const account = this.account(id);

        if (!Number.isFinite(amount) || amount <= 0) {
            throw new ConstraintError(
                'withdrawal amount must be positive'
            );
        }

        if (account.balance < amount) {
            throw new ConstraintError(
                `insufficient funds for account ${id}`
            );
        }

        account.balance -= amount;

        this.audit(
            'WITHDRAW',
            `account=${id}, amount=${amount.toFixed(2)}`
        );
    }

    async transfer(sourceId, targetId, amount) {
        this.requireActive();

        if (sourceId === targetId) {
            throw new ConstraintError(
                'source and target accounts must differ'
            );
        }

        // Async boundaries model an application workflow in which
        // independent validations or external checks may occur.
        await Promise.resolve();

        this.withdraw(sourceId, amount);
        this.deposit(targetId, amount);

        this.audit(
            'TRANSFER',
            `source=${sourceId}, target=${targetId}, amount=${amount.toFixed(2)}`
        );
    }

    commit() {
        this.requireActive();

        if (this.repository.version !== this.startVersion) {
            this.state = TransactionState.ROLLED_BACK;

            throw new SerializationConflict(
                'repository changed while transaction was active'
            );
        }

        const committedAccounts = cloneAccounts(this.accounts);

        for (const [id, account] of committedAccounts) {
            const original = this.repository.accounts.get(id);

            if (original && account.balance !== original.balance) {
                account.version = original.version + 1;
            }
        }

        this.repository.accounts = committedAccounts;
        this.repository.auditLog = [...this.auditLog];
        this.repository.version += 1;
        this.state = TransactionState.COMMITTED;

        this.emit('commit', {
            transactionId: this.id,
        });
    }

    rollback() {
        this.requireActive();

        this.accounts = cloneAccounts(this.repository.accounts);
        this.auditLog = [...this.repository.auditLog];
        this.savepoints.clear();
        this.state = TransactionState.ROLLED_BACK;

        this.emit('rollback', {
            transactionId: this.id,
        });
    }
}

class TransactionManager {
    constructor(repository) {
        this.repository = repository;
        this.nextId = 1;
    }

    begin() {
        return new Transaction(
            this.repository,
            this.nextId++
        );
    }
}

function printAccounts(repository, title) {
    console.log(`\n${title}`);
    console.log('-'.repeat(title.length));

    for (const account of repository.accounts.values()) {
        console.log(
            `${account.id}: ${account.owner.padEnd(10)} ` +
            `balance=${account.balance.toFixed(2).padStart(8)} ` +
            `version=${account.version}`
        );
    }
}

async function main() {
    const repository = new Repository();

    repository.addAccount(1, 'Alice', 1500);
    repository.addAccount(2, 'Bob', 900);
    repository.addAccount(3, 'Carol', 300);

    const manager = new TransactionManager(repository);

    printAccounts(repository, 'Initial state');

    const transaction = manager.begin();

    transaction.on('change', event => {
        console.log(
            `event: ${event.action} (${event.details})`
        );
    });

    transaction.deposit(1, 200);
    transaction.commit();

    printAccounts(repository, 'After COMMIT');

    const failed = manager.begin();

    try {
        failed.withdraw(2, 10000);
        failed.commit();
    } catch (error) {
        if (error instanceof ConstraintError) {
            console.log(`\nExpected failure: ${error.message}`);
            failed.rollback();
        } else {
            throw error;
        }
    }

    printAccounts(repository, 'After ROLLBACK');

    const savepointTransaction = manager.begin();

    savepointTransaction.deposit(1, 50);
    savepointTransaction.beginSavepoint('before_risky_operation');

    try {
        savepointTransaction.withdraw(2, 5000);
    } catch (error) {
        console.log(
            `\nSavepoint recovery: ${error.message}`
        );

        savepointTransaction.rollbackToSavepoint(
            'before_risky_operation'
        );
    }

    savepointTransaction.deposit(2, 25);
    savepointTransaction.releaseSavepoint(
        'before_risky_operation'
    );
    savepointTransaction.commit();

    printAccounts(
        repository,
        'After SAVEPOINT recovery and COMMIT'
    );

    const transferTransaction = manager.begin();

    await transferTransaction.transfer(
        1,
        3,
        125
    );

    transferTransaction.commit();

    printAccounts(
        repository,
        'After atomic transfer'
    );

    const first = manager.begin();
    const second = manager.begin();

    first.deposit(1, 10);
    first.commit();

    try {
        second.deposit(2, 10);
        second.commit();
    } catch (error) {
        if (error instanceof SerializationConflict) {
            console.log(
                `\nConflict detected: ${error.message}`
            );
        } else {
            throw error;
        }
    }

    printAccounts(
        repository,
        'After conflict detection'
    );

    if (repository.accounts.get(1).balance !== 1635) {
        throw new Error('unexpected account 1 balance');
    }

    if (repository.accounts.get(2).balance !== 925) {
        throw new Error('unexpected account 2 balance');
    }

    if (repository.accounts.get(3).balance !== 425) {
        throw new Error('unexpected account 3 balance');
    }

    console.log('\nTransaction audit');
    for (const event of repository.auditLog) {
        console.log(
            `tx=${event.transactionId} ` +
            `${event.action.padEnd(10)} ` +
            event.details
        );
    }
}

main().catch(error => {
    console.error(`Fatal error: ${error.message}`);
    process.exitCode = 1;
});
