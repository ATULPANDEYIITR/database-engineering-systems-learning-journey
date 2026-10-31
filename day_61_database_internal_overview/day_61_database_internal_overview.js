'use strict';

/*
 * Database Internals Overview
 * Query Engine, Storage Engine, and Buffer Manager
 *
 * This implementation models a page-oriented database engine with:
 * - heap pages
 * - a buffer pool using LRU replacement
 * - dirty-page management
 * - asynchronous disk I/O simulation
 * - an ordered index
 * - query planning
 * - event-driven instrumentation
 * - transaction-style updates and rollback
 *
 * Node.js standard library only.
 */

const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const EventEmitter = require('node:events');

const PAGE_CAPACITY = 6;
const BUFFER_POOL_CAPACITY = 3;

class DatabaseError extends Error {}
class PageNotFoundError extends DatabaseError {}
class DuplicateRowError extends DatabaseError {}
class TransactionError extends DatabaseError {}

class Record {
    constructor(rowId, customerId, name, balance) {
        this.rowId = rowId;
        this.customerId = customerId;
        this.name = name;
        this.balance = balance;
        this.validate();
    }

    validate() {
        if (!Number.isInteger(this.rowId) || this.rowId <= 0) {
            throw new TypeError('rowId must be a positive integer');
        }

        if (!Number.isInteger(this.customerId) || this.customerId <= 0) {
            throw new TypeError('customerId must be a positive integer');
        }

        if (typeof this.name !== 'string' ||
            this.name.length < 1 ||
            this.name.length > 80) {
            throw new TypeError('name must contain 1-80 characters');
        }

        if (!Number.isFinite(this.balance) ||
            this.balance < -10_000_000 ||
            this.balance > 10_000_000) {
            throw new TypeError('balance is outside the supported range');
        }
    }
}

class Page {
    constructor(id, type = 'heap') {
        this.id = id;
        this.type = type;
        this.records = [];
        this.dirty = false;
        this.lsn = 0;
    }

    add(record) {
        if (this.records.length >= PAGE_CAPACITY) {
            throw new DatabaseError(`page ${this.id} is full`);
        }

        this.records.push(record);
        this.dirty = true;
    }

    find(rowId) {
        return this.records.find(record => record.rowId === rowId) ?? null;
    }

    updateBalance(rowId, balance) {
        if (!Number.isFinite(balance)) {
            throw new TypeError('balance must be finite');
        }

        const record = this.find(rowId);

        if (!record) {
            return null;
        }

        const oldBalance = record.balance;
        record.balance = balance;
        this.dirty = true;

        return oldBalance;
    }
}

class DiskManager {
    constructor(filePath) {
        this.filePath = filePath;
        this.pages = new Map();
        this.nextPageId = 1;
    }

    async load() {
        try {
            const text = await fs.readFile(this.filePath, 'utf8');
            const data = JSON.parse(text);

            this.nextPageId = data.nextPageId;

            for (const rawPage of data.pages) {
                const page = new Page(rawPage.id, rawPage.type);
                page.dirty = false;
                page.lsn = rawPage.lsn;

                for (const rawRecord of rawPage.records) {
                    page.records.push(
                        new Record(
                            rawRecord.rowId,
                            rawRecord.customerId,
                            rawRecord.name,
                            rawRecord.balance
                        )
                    );
                }

                this.pages.set(page.id, page);
            }
        } catch (error) {
            if (error.code !== 'ENOENT') {
                throw error;
            }
        }
    }

    allocatePage(type = 'heap') {
        const page = new Page(this.nextPageId++, type);
        this.pages.set(page.id, page);
        return page;
    }

    async readPage(id) {
        const page = this.pages.get(id);

        if (!page) {
            throw new PageNotFoundError(`page ${id} does not exist`);
        }

        // Simulates asynchronous disk latency.
        await new Promise(resolve => setTimeout(resolve, 2));

        return structuredClone(page);
    }

    async writePage(page) {
        if (!this.pages.has(page.id)) {
            throw new PageNotFoundError(`page ${page.id} does not exist`);
        }

        const persisted = structuredClone(page);
        persisted.dirty = false;
        this.pages.set(page.id, persisted);
    }

    async flush() {
        const data = {
            nextPageId: this.nextPageId,
            pages: [...this.pages.values()]
        };

        const temporary = `${this.filePath}.tmp`;

        await fs.writeFile(
            temporary,
            JSON.stringify(data, null, 2),
            'utf8'
        );

        await fs.rename(temporary, this.filePath);
    }
}

class BufferManager extends EventEmitter {
    constructor(disk, capacity) {
        super();
        this.disk = disk;
        this.capacity = capacity;
        this.frames = new Map();
        this.hits = 0;
        this.misses = 0;
        this.evictions = 0;
        this.diskWrites = 0;
    }

    async fetch(pageId) {
        if (this.frames.has(pageId)) {
            this.hits++;
            const page = this.frames.get(pageId);

            // Map insertion order acts as the LRU queue.
            this.frames.delete(pageId);
            this.frames.set(pageId, page);

            this.emit('bufferHit', { pageId });
            return page;
        }

        this.misses++;
        this.emit('bufferMiss', { pageId });

        if (this.frames.size >= this.capacity) {
            await this.evict();
        }

        const page = await this.disk.readPage(pageId);
        this.frames.set(pageId, page);

        return page;
    }

    async evict() {
        const oldestPageId = this.frames.keys().next().value;
        const page = this.frames.get(oldestPageId);

        this.frames.delete(oldestPageId);
        this.evictions++;

        if (page.dirty) {
            await this.disk.writePage(page);
            this.diskWrites++;
            this.emit('pageFlush', { pageId: page.id });
        }
    }

    markDirty(pageId, lsn) {
        const page = this.frames.get(pageId);

        if (!page) {
            throw new DatabaseError(
                `cannot mark nonresident page ${pageId} dirty`
            );
        }

        page.dirty = true;
        page.lsn = lsn;
    }

    async flushAll() {
        for (const page of this.frames.values()) {
            if (page.dirty) {
                await this.disk.writePage(page);
                page.dirty = false;
                this.diskWrites++;
            }
        }
    }

    stats() {
        const accesses = this.hits + this.misses;

        return {
            hits: this.hits,
            misses: this.misses,
            evictions: this.evictions,
            diskWrites: this.diskWrites,
            hitRate: accesses === 0 ? 0 : this.hits / accesses
        };
    }
}

class HeapTable {
    constructor(disk, buffer) {
        this.disk = disk;
        this.buffer = buffer;
        this.pageIds = [];
        this.rowLocator = new Map();
    }

    async initialize() {
        for (const page of this.disk.pages.values()) {
            if (page.type !== 'heap') {
                continue;
            }

            this.pageIds.push(page.id);

            for (const record of page.records) {
                this.rowLocator.set(record.rowId, page.id);
            }
        }

        this.pageIds.sort((a, b) => a - b);
    }

    async insert(record) {
        if (!(record instanceof Record)) {
            throw new TypeError('insert requires a Record');
        }

        if (this.rowLocator.has(record.rowId)) {
            throw new DuplicateRowError(
                `row ${record.rowId} already exists`
            );
        }

        let target = null;

        for (let i = this.pageIds.length - 1; i >= 0; i--) {
            const page = await this.buffer.fetch(this.pageIds[i]);

            if (page.records.length < PAGE_CAPACITY) {
                target = page;
                break;
            }
        }

        if (!target) {
            const allocated = this.disk.allocatePage('heap');
            this.pageIds.push(allocated.id);
            target = await this.buffer.fetch(allocated.id);
        }

        target.add(record);
        this.rowLocator.set(record.rowId, target.id);

        return target.id;
    }

    async get(rowId) {
        const pageId = this.rowLocator.get(rowId);

        if (pageId === undefined) {
            return null;
        }

        const page = await this.buffer.fetch(pageId);
        return page.find(rowId);
    }

    async updateBalance(rowId, newBalance) {
        const pageId = this.rowLocator.get(rowId);

        if (pageId === undefined) {
            throw new DatabaseError(`row ${rowId} does not exist`);
        }

        const page = await this.buffer.fetch(pageId);
        const oldBalance = page.updateBalance(rowId, newBalance);

        if (oldBalance === null) {
            throw new DatabaseError(`row ${rowId} is missing from page`);
        }

        return {
            pageId,
            oldBalance
        };
    }

    async scan() {
        const result = [];

        for (const pageId of this.pageIds) {
            const page = await this.buffer.fetch(pageId);
            result.push(...page.records);
        }

        return result;
    }
}

class OrderedIndex {
    constructor() {
        this.entries = [];
    }

    async build(table) {
        const rows = await table.scan();

        this.entries = rows
            .map(record => ({
                key: record.customerId,
                pageId: table.rowLocator.get(record.rowId)
            }))
            .sort((a, b) => a.key - b.key);
    }

    lookup(customerId) {
        return this.entries
            .filter(entry => entry.key === customerId)
            .map(entry => entry.pageId);
    }
}

class QueryEngine {
    constructor(table, index, buffer) {
        this.table = table;
        this.index = index;
        this.buffer = buffer;
    }

    async scanByCustomer(customerId) {
        const rows = await this.table.scan();
        return rows.filter(row => row.customerId === customerId);
    }

    async indexedByCustomer(customerId) {
        const pageIds = [...new Set(this.index.lookup(customerId))];
        const result = [];

        for (const pageId of pageIds) {
            const page = await this.buffer.fetch(pageId);

            result.push(
                ...page.records.filter(
                    record => record.customerId === customerId
                )
            );
        }

        return result;
    }
}

class Transaction {
    constructor(id, table, buffer) {
        this.id = id;
        this.table = table;
        this.buffer = buffer;
        this.changes = [];
        this.active = true;
        this.nextLsn = 1;
    }

    async updateBalance(rowId, newBalance) {
        if (!this.active) {
            throw new TransactionError('transaction is inactive');
        }

        const change = await this.table.updateBalance(
            rowId,
            newBalance
        );

        const lsn = this.nextLsn++;

        this.buffer.markDirty(change.pageId, lsn);

        this.changes.push({
            pageId: change.pageId,
            rowId,
            oldBalance: change.oldBalance,
            newBalance
        });
    }

    async commit() {
        if (!this.active) {
            throw new TransactionError('transaction is inactive');
        }

        await this.buffer.flushAll();
        this.active = false;
    }

    async rollback() {
        if (!this.active) {
            throw new TransactionError('transaction is inactive');
        }

        for (const change of [...this.changes].reverse()) {
            const page = await this.buffer.fetch(change.pageId);
            page.updateBalance(
                change.rowId,
                change.oldBalance
            );
        }

        await this.buffer.flushAll();
        this.active = false;
    }
}

function checksum(value) {
    return crypto
        .createHash('sha256')
        .update(value)
        .digest('hex');
}

async function main() {
    const directory = await fs.mkdtemp(
        path.join(os.tmpdir(), 'db-internals-')
    );

    const databaseFile = path.join(directory, 'database.json');

    const disk = new DiskManager(databaseFile);
    await disk.load();

    const buffer = new BufferManager(
        disk,
        BUFFER_POOL_CAPACITY
    );

    buffer.on('bufferMiss', event => {
        console.log(`buffer miss: page ${event.pageId}`);
    });

    buffer.on('pageFlush', event => {
        console.log(`dirty page flushed: ${event.pageId}`);
    });

    const table = new HeapTable(disk, buffer);
    await table.initialize();

    const rows = [
        new Record(1, 101, 'Asha', 1250),
        new Record(2, 102, 'Ravi', 840),
        new Record(3, 101, 'Meera', 2190),
        new Record(4, 103, 'Kabir', 450),
        new Record(5, 104, 'Nisha', 3300),
        new Record(6, 102, 'Arjun', 910),
        new Record(7, 105, 'Isha', 720),
        new Record(8, 101, 'Dev', 1500)
    ];

    for (const row of rows) {
        await table.insert(row);
    }

    const index = new OrderedIndex();
    await index.build(table);

    const queryEngine = new QueryEngine(
        table,
        index,
        buffer
    );

    const scanRows = await queryEngine.scanByCustomer(101);
    const indexedRows = await queryEngine.indexedByCustomer(101);

    const scanIds = scanRows.map(row => row.rowId).sort();
    const indexIds = indexedRows.map(row => row.rowId).sort();

    if (JSON.stringify(scanIds) !== JSON.stringify(indexIds)) {
        throw new DatabaseError(
            'index and sequential access returned different rows'
        );
    }

    const transaction = new Transaction(
        5001,
        table,
        buffer
    );

    await transaction.updateBalance(1, 1750);
    await transaction.updateBalance(3, 2490);
    await transaction.commit();

    if ((await table.get(1)).balance !== 1750) {
        throw new DatabaseError('committed value was not retained');
    }

    const rollbackTransaction = new Transaction(
        5002,
        table,
        buffer
    );

    await rollbackTransaction.updateBalance(1, 9999);
    await rollbackTransaction.rollback();

    if ((await table.get(1)).balance !== 1750) {
        throw new DatabaseError('rollback did not restore the value');
    }

    await disk.flush();

    const reloadedDisk = new DiskManager(databaseFile);
    await reloadedDisk.load();

    console.log('\nDatabase Internals Demonstration');
    console.log('--------------------------------');
    console.log(`Heap pages: ${table.pageIds.length}`);
    console.log(`Indexed customer rows: ${indexedRows.length}`);
    console.log(`Buffer statistics:`, buffer.stats());
    console.log(`Persisted pages: ${reloadedDisk.pages.size}`);
    console.log(`Checksum: ${checksum('database internals')}`);

    try {
        await table.insert(
            new Record(1, 999, 'Duplicate', 10)
        );
    } catch (error) {
        console.log(`Validation failure handled: ${error.message}`);
    }

    try {
        await disk.readPage(999999);
    } catch (error) {
        console.log(`Storage failure handled: ${error.message}`);
    }
}

main().catch(error => {
    console.error(`Fatal database-engine error: ${error.message}`);
    process.exitCode = 1;
});
