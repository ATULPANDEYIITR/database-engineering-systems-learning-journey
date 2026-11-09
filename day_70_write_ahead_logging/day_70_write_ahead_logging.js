'use strict';

/*
 * Write-Ahead Logging: Durability and Crash Recovery
 *
 * Node.js implementation featuring:
 * - Asynchronous WAL operations
 * - Serialized transaction execution
 * - FileHandle.sync() durability
 * - LSN-based ordering
 * - Commit and abort semantics
 * - Checkpoints
 * - Analysis, REDO, and UNDO
 * - CRC32 integrity validation
 * - Torn-tail handling
 * - Event-driven transaction monitoring
 *
 * Run: node wal_recovery.js
 */

const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { EventEmitter } = require('node:events');

const RecordType = Object.freeze({
    BEGIN: 'BEGIN',
    UPDATE: 'UPDATE',
    COMMIT: 'COMMIT',
    ABORT: 'ABORT',
    CHECKPOINT: 'CHECKPOINT'
});

class WALError extends Error {}
class CorruptLogError extends WALError {}
class TransactionError extends WALError {}
class DurabilityError extends WALError {}

function crc32(buffer) {
    let crc = 0xFFFFFFFF;

    for (const byte of buffer) {
        crc ^= byte;

        for (let bit = 0; bit < 8; bit++) {
            crc = (crc >>> 1) ^
                ((crc & 1) ? 0xEDB88320 : 0);
        }
    }

    return (crc ^ 0xFFFFFFFF) >>> 0;
}

function checksumPayload(record) {
    const payload = {
        lsn: record.lsn,
        transactionId: record.transactionId,
        type: record.type,
        key: record.key ?? null,
        oldValue: record.oldValue ?? null,
        newValue: record.newValue ?? null
    };

    return crc32(
        Buffer.from(JSON.stringify(payload), 'utf8')
    );
}

function validateRecord(record, expectedLSN) {
    if (!record || typeof record !== 'object') {
        throw new CorruptLogError('Record must be an object');
    }

    if (!Number.isSafeInteger(record.lsn) ||
        record.lsn !== expectedLSN) {
        throw new CorruptLogError(
            `Unexpected LSN: ${record.lsn}`
        );
    }

    if (!Number.isSafeInteger(record.transactionId) ||
        record.transactionId < 0) {
        throw new CorruptLogError('Invalid transaction identifier');
    }

    if (!Object.values(RecordType).includes(record.type)) {
        throw new CorruptLogError('Unknown record type');
    }

    if (record.type === RecordType.UPDATE) {
        if (typeof record.key !== 'string' ||
            record.key.length === 0 ||
            record.key.length > 128 ||
            !Number.isSafeInteger(record.newValue) ||
            (record.oldValue !== null &&
             !Number.isSafeInteger(record.oldValue))) {
            throw new CorruptLogError('Invalid update record');
        }
    }

    if (record.checksum !== checksumPayload(record)) {
        throw new CorruptLogError(
            `Checksum failure at LSN ${record.lsn}`
        );
    }

    return true;
}

class DurableWAL {
    constructor(filePath) {
        this.filePath = filePath;
        this.nextLSN = 1;
        this.records = [];
        this.handle = null;

        // A promise chain serializes concurrent append operations.
        this.queue = Promise.resolve();
    }

    async open() {
        await fs.mkdir(path.dirname(this.filePath), {
            recursive: true
        });

        this.handle = await fs.open(this.filePath, 'a+');
        await this.load();
        return this;
    }

    async load() {
        const buffer = await fs.readFile(this.filePath);
        const records = [];

        let start = 0;
        let expectedLSN = 1;

        while (start < buffer.length) {
            const end = buffer.indexOf(0x0A, start);

            if (end === -1) {
                // Ignore only an incomplete final line.
                console.warn('Discarding incomplete WAL tail.');
                break;
            }

            const line = buffer.subarray(start, end).toString('utf8');

            try {
                const record = JSON.parse(line);
                validateRecord(record, expectedLSN);
                records.push(record);
            } catch (error) {
                throw new CorruptLogError(
                    `Invalid complete WAL record: ${error.message}`
                );
            }

            expectedLSN++;
            start = end + 1;
        }

        this.records = records;
        this.nextLSN = expectedLSN;

        const validBytes = Buffer.from(
            records.map(r => JSON.stringify(r) + '\n').join(''),
            'utf8'
        );

        if (buffer.length !== validBytes.length) {
            await this.handle.truncate(validBytes.length);
            await this.handle.sync();
        }
    }

    async append(transactionId, type, fields = {}) {
        const operation = this.queue.then(async () => {
            if (!this.handle) {
                throw new DurabilityError('WAL is not open');
            }

            const record = {
                lsn: this.nextLSN,
                transactionId,
                type,
                key: fields.key ?? null,
                oldValue: fields.oldValue ?? null,
                newValue: fields.newValue ?? null
            };

            record.checksum = checksumPayload(record);

            const serialized = JSON.stringify(record) + '\n';

            try {
                await this.handle.write(
                    serialized,
                    null,
                    'utf8'
                );

                // Do not acknowledge the operation before sync succeeds.
                await this.handle.sync();
            } catch (error) {
                throw new DurabilityError(
                    `WAL persistence failed: ${error.message}`
                );
            }

            this.records.push(record);
            this.nextLSN++;

            return record;
        });

        this.queue = operation.catch(() => {});
        return operation;
    }

    async close() {
        await this.queue;

        if (this.handle) {
            await this.handle.sync();
            await this.handle.close();
            this.handle = null;
        }
    }
}

class TransactionManager extends EventEmitter {
    constructor(wal) {
        super();
        this.wal = wal;
        this.data = new Map();
        this.transactions = new Map();
        this.nextTransactionId = 1;
        this.dirtyKeys = new Set();
    }

    async begin() {
        const id = this.nextTransactionId++;

        await this.wal.append(id, RecordType.BEGIN);

        const transaction = {
            id,
            state: 'ACTIVE',
            operations: []
        };

        this.transactions.set(id, transaction);
        this.emit('transaction:begin', { id });

        return transaction;
    }

    assertActive(tx) {
        if (!tx ||
            this.transactions.get(tx.id) !== tx ||
            tx.state !== 'ACTIVE') {
            throw new TransactionError(
                'Transaction is not active'
            );
        }
    }

    async update(tx, key, value) {
        this.assertActive(tx);

        if (typeof key !== 'string' ||
            key.length === 0 ||
            key.length > 128) {
            throw new TypeError('Invalid database key');
        }

        if (!Number.isSafeInteger(value)) {
            throw new TypeError('Value must be a safe integer');
        }

        const oldValue = this.data.has(key)
            ? this.data.get(key)
            : null;

        // Persist the update record before changing database state.
        await this.wal.append(tx.id, RecordType.UPDATE, {
            key,
            oldValue,
            newValue: value
        });

        this.data.set(key, value);
        this.dirtyKeys.add(key);

        tx.operations.push({ key, oldValue, newValue: value });

        this.emit('transaction:update', {
            transactionId: tx.id,
            key,
            oldValue,
            newValue: value
        });
    }

    async commit(tx) {
        this.assertActive(tx);

        await this.wal.append(tx.id, RecordType.COMMIT);

        tx.state = 'COMMITTED';
        this.emit('transaction:commit', { id: tx.id });
    }

    async abort(tx) {
        this.assertActive(tx);

        for (const operation of [...tx.operations].reverse()) {
            if (operation.oldValue === null) {
                this.data.delete(operation.key);
            } else {
                this.data.set(operation.key, operation.oldValue);
            }
        }

        await this.wal.append(tx.id, RecordType.ABORT);

        tx.state = 'ABORTED';
        this.emit('transaction:abort', { id: tx.id });
    }

    async checkpoint() {
        await this.wal.append(0, RecordType.CHECKPOINT);
        this.dirtyKeys.clear();

        this.emit('checkpoint:complete', {
            lsn: this.wal.nextLSN - 1
        });
    }

    crash() {
        this.data.clear();
        this.transactions.clear();
        this.dirtyKeys.clear();
        this.emit('database:crash');
    }

    async recover() {
        const records = this.wal.records;

        const active = new Set();
        const committed = new Set();

        // ANALYSIS: identify transaction outcomes.
        for (const record of records) {
            const id = record.transactionId;

            switch (record.type) {
                case RecordType.BEGIN:
                    active.add(id);
                    break;

                case RecordType.COMMIT:
                    active.delete(id);
                    committed.add(id);
                    break;

                case RecordType.ABORT:
                    active.delete(id);
                    break;
            }
        }

        this.emit('recovery:analysis', {
            active: [...active],
            committed: [...committed]
        });

        // REDO: replay updates for committed and incomplete transactions.
        for (const record of records) {
            if (record.type !== RecordType.UPDATE) continue;

            if (committed.has(record.transactionId) ||
                active.has(record.transactionId)) {
                this.data.set(record.key, record.newValue);
            }
        }

        this.emit('recovery:redo', {
            keys: [...this.data.keys()]
        });

        // UNDO: reverse incomplete transactions in reverse log order.
        for (const record of [...records].reverse()) {
            if (record.type !== RecordType.UPDATE ||
                !active.has(record.transactionId)) {
                continue;
            }

            if (record.oldValue === null) {
                this.data.delete(record.key);
            } else {
                this.data.set(record.key, record.oldValue);
            }
        }

        for (const id of [...active].sort((a, b) => a - b)) {
            await this.wal.append(id, RecordType.ABORT);
        }

        this.emit('recovery:complete', {
            database: Object.fromEntries(this.data)
        });

        return new Map(this.data);
    }
}

async function run() {
    const directory = await fs.mkdtemp(
        path.join(os.tmpdir(), 'wal-example-')
    );

    const walPath = path.join(directory, 'database.wal');

    try {
        let wal = await new DurableWAL(walPath).open();
        let database = new TransactionManager(wal);

        database.on('transaction:commit', event => {
            console.log('Committed:', event.id);
        });

        database.on('recovery:complete', event => {
            console.log('Recovered state:', event.database);
        });

        console.log('\n--- TRANSACTION PROCESSING ---');

        const first = await database.begin();
        await database.update(first, 'account_A', 1000);
        await database.update(first, 'account_B', 500);
        await database.commit(first);

        const second = await database.begin();
        await database.update(second, 'account_A', 800);
        await database.update(second, 'account_B', 700);

        console.log(
            'Volatile state before crash:',
            Object.fromEntries(database.data)
        );

        database.crash();
        await wal.close();

        console.log('\n--- REOPEN AND RECOVER ---');

        wal = await new DurableWAL(walPath).open();
        database = new TransactionManager(wal);

        const recovered = await database.recover();

        if (recovered.get('account_A') !== 1000 ||
            recovered.get('account_B') !== 500) {
            throw new Error('Recovery validation failed');
        }

        // The recovery ABORT records make the next recovery idempotent.
        database.crash();

        const secondRecovery = new TransactionManager(wal);
        await secondRecovery.recover();

        if (secondRecovery.data.get('account_A') !== 1000) {
            throw new Error('Idempotent recovery validation failed');
        }

        console.log('All assertions passed.');

        await wal.close();
    } finally {
        await fs.rm(directory, {
            recursive: true,
            force: true
        });
    }
}

run().catch(error => {
    console.error('Fatal WAL error:', error);
    process.exitCode = 1;
});
