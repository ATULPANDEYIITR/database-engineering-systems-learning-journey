'use strict';

/*
 * NON-REPEATABLE READS
 * Concurrency behavior and isolation
 *
 * Event-driven transaction simulator.
 * Runtime: Node.js 18+
 *
 * Demonstrates:
 * - Statement-level snapshots.
 * - Transaction-level snapshots.
 * - Non-repeatable reads.
 * - Repeatable reads.
 * - Optimistic write conflicts.
 * - Serializable validation.
 * - Atomic commits and rollbacks.
 * - Asynchronous transaction interleaving.
 */

const { EventEmitter } = require('node:events');
const { randomUUID } = require('node:crypto');

const Isolation = Object.freeze({
    READ_UNCOMMITTED: 'READ UNCOMMITTED',
    READ_COMMITTED: 'READ COMMITTED',
    REPEATABLE_READ: 'REPEATABLE READ',
    SERIALIZABLE: 'SERIALIZABLE'
});

const State = Object.freeze({
    ACTIVE: 'ACTIVE',
    COMMITTED: 'COMMITTED',
    ROLLED_BACK: 'ROLLED_BACK',
    FAILED: 'FAILED'
});

class DatabaseError extends Error {}
class SerializationError extends DatabaseError {}
class WriteConflictError extends DatabaseError {}

class Mutex {
    constructor() {
        this.locked = false;
        this.waiters = [];
    }

    async acquire() {
        if (!this.locked) {
            this.locked = true;
            return;
        }

        await new Promise(resolve => this.waiters.push(resolve));
    }

    release() {
        const next = this.waiters.shift();

        if (next) {
            next();
        } else {
            this.locked = false;
        }
    }

    async runExclusive(callback) {
        await this.acquire();

        try {
            return await callback();
        } finally {
            this.release();
        }
    }
}

class Transaction {
    constructor(database, isolation) {
        this.id = randomUUID();
        this.database = database;
        this.isolation = isolation;
        this.state = State.ACTIVE;
        this.snapshot = new Map();
        this.writes = new Map();
        this.readVersions = new Map();

        for (const [id, record] of database.records) {
            this.snapshot.set(id, structuredClone(record));
        }
    }

    assertActive() {
        if (this.state !== State.ACTIVE) {
            throw new DatabaseError(
                `Transaction ${this.id} is ${this.state}`
            );
        }
    }

    async read(id) {
        this.assertActive();

        return this.database.mutex.runExclusive(() => {
            if (!this.database.records.has(id)) {
                throw new DatabaseError(`Unknown record: ${id}`);
            }

            let record;

            if (this.writes.has(id)) {
                record = this.writes.get(id);
            } else if (
                this.isolation === Isolation.READ_COMMITTED ||
                this.isolation === Isolation.READ_UNCOMMITTED
            ) {
                record = this.database.records.get(id);
            } else {
                record = this.snapshot.get(id);
            }

            this.readVersions.set(
                id,
                this.readVersions.get(id) ?? record.version
            );

            const result = structuredClone(record);

            this.database.events.emit('read', {
                transactionId: this.id,
                recordId: id,
                value: result.balance,
                version: result.version
            });

            return result;
        });
    }

    async write(id, balance) {
        this.assertActive();

        if (!Number.isFinite(balance) || balance < 0) {
            throw new DatabaseError('Invalid balance.');
        }

        if (!this.snapshot.has(id)) {
            throw new DatabaseError(`Unknown record: ${id}`);
        }

        const base = this.writes.get(id) ?? this.snapshot.get(id);

        this.writes.set(id, {
            id,
            balance,
            version: base.version
        });

        this.database.events.emit('write', {
            transactionId: this.id,
            recordId: id,
            balance
        });
    }

    async commit() {
        this.assertActive();

        return this.database.mutex.runExclusive(() => {
            for (const [id, pending] of this.writes) {
                const current = this.database.records.get(id);

                if (current.version !== pending.version) {
                    this.state = State.FAILED;
                    throw new WriteConflictError(
                        `Concurrent update detected on record ${id}`
                    );
                }
            }

            if (this.isolation === Isolation.SERIALIZABLE) {
                for (const [id, version] of this.readVersions) {
                    const current = this.database.records.get(id);

                    if (current.version !== version) {
                        this.state = State.FAILED;
                        throw new SerializationError(
                            `Read conflict on record ${id}`
                        );
                    }
                }
            }

            // All writes are validated before any are applied.
            for (const [id, pending] of this.writes) {
                const current = this.database.records.get(id);

                this.database.records.set(id, {
                    id,
                    balance: pending.balance,
                    version: current.version + 1
                });
            }

            this.state = State.COMMITTED;

            this.database.events.emit('commit', {
                transactionId: this.id
            });
        });
    }

    async rollback() {
        this.assertActive();
        this.writes.clear();
        this.state = State.ROLLED_BACK;

        this.database.events.emit('rollback', {
            transactionId: this.id
        });
    }
}

class Database {
    constructor(initialRecords) {
        this.records = new Map();
        this.mutex = new Mutex();
        this.events = new EventEmitter();

        for (const record of initialRecords) {
            if (
                !Number.isInteger(record.id) ||
                !Number.isFinite(record.balance) ||
                record.balance < 0
            ) {
                throw new DatabaseError('Invalid initial record.');
            }

            if (this.records.has(record.id)) {
                throw new DatabaseError('Duplicate record identifier.');
            }

            this.records.set(record.id, {
                ...record,
                version: 1
            });
        }
    }

    begin(isolation = Isolation.READ_COMMITTED) {
        if (!Object.values(Isolation).includes(isolation)) {
            throw new DatabaseError('Unsupported isolation level.');
        }

        const transaction = new Transaction(this, isolation);

        this.events.emit('begin', {
            transactionId: transaction.id,
            isolation
        });

        return transaction;
    }

    display() {
        console.table([...this.records.values()]);
    }
}

function attachLogging(database) {
    for (const event of ['begin', 'read', 'write', 'commit', 'rollback']) {
        database.events.on(event, payload => {
            console.log(`[${event.toUpperCase()}]`, payload);
        });
    }
}

async function pause(milliseconds = 50) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
}

async function nonRepeatableRead() {
    console.log('\nEXPERIMENT 1: READ COMMITTED');

    const db = new Database([
        { id: 1, balance: 1000 }
    ]);

    attachLogging(db);

    const reader = db.begin(Isolation.READ_COMMITTED);
    const writer = db.begin(Isolation.READ_COMMITTED);

    const first = await reader.read(1);

    await writer.write(1, 1500);
    await writer.commit();

    const second = await reader.read(1);

    console.log({
        firstRead: first.balance,
        secondRead: second.balance,
        nonRepeatableRead: first.balance !== second.balance
    });

    await reader.commit();
    db.display();
}

async function repeatableRead() {
    console.log('\nEXPERIMENT 2: REPEATABLE READ');

    const db = new Database([
        { id: 1, balance: 1000 }
    ]);

    const reader = db.begin(Isolation.REPEATABLE_READ);
    const writer = db.begin(Isolation.READ_COMMITTED);

    const first = await reader.read(1);

    await writer.write(1, 1700);
    await writer.commit();

    const second = await reader.read(1);

    console.log({
        firstRead: first.balance,
        secondRead: second.balance,
        stableSnapshot: first.balance === second.balance
    });

    await reader.commit();
    db.display();
}

async function writeConflict() {
    console.log('\nEXPERIMENT 3: CONCURRENT WRITERS');

    const db = new Database([
        { id: 1, balance: 1000 }
    ]);

    const first = db.begin(Isolation.REPEATABLE_READ);
    const second = db.begin(Isolation.REPEATABLE_READ);

    await first.read(1);
    await second.read(1);

    await first.write(1, 1200);
    await second.write(1, 1300);

    await first.commit();

    try {
        await second.commit();
    } catch (error) {
        console.log(`[EXPECTED CONFLICT] ${error.message}`);
    }

    db.display();
}

async function asynchronousInterleaving() {
    console.log('\nEXPERIMENT 4: ASYNCHRONOUS INTERLEAVING');

    const db = new Database([
        { id: 1, balance: 1000 }
    ]);

    const reader = db.begin(Isolation.READ_COMMITTED);
    const writer = db.begin(Isolation.READ_COMMITTED);

    const task = (async () => {
        const first = await reader.read(1);
        await pause(100);

        const second = await reader.read(1);

        console.log(
            'Reader observed:',
            first.balance,
            'then',
            second.balance
        );

        await reader.commit();
    })();

    await pause(25);
    await writer.write(1, 2000);
    await writer.commit();

    await task;
    db.display();
}

async function rollbackExample() {
    console.log('\nEXPERIMENT 5: ROLLBACK');

    const db = new Database([
        { id: 1, balance: 1000 }
    ]);

    const tx = db.begin();

    await tx.write(1, 400);
    await tx.rollback();

    db.display();
}

async function main() {
    try {
        await nonRepeatableRead();
        await repeatableRead();
        await writeConflict();
        await asynchronousInterleaving();
        await rollbackExample();

        console.log('\nALL EXPERIMENTS COMPLETED.');
    } catch (error) {
        console.error('DATABASE FAILURE:', error.message);
        process.exitCode = 1;
    }
}

main();
