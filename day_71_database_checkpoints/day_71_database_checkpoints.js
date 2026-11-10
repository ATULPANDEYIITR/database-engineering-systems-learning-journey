"use strict";

/*
 * Database checkpoint and recovery simulator.
 *
 * Focus:
 * - Event-driven storage-engine behavior
 * - Write-ahead logging
 * - Dirty-page tracking
 * - Fuzzy checkpoint creation
 * - Durable LSN boundaries
 * - Transaction recovery
 * - Redo and undo processing
 * - Recovery coordination
 *
 * Runtime: Node.js 18+
 * Dependencies: Node.js standard library only.
 */

const { EventEmitter } = require("node:events");
const fs = require("node:fs/promises");
const path = require("node:path");
const crypto = require("node:crypto");

const LogType = Object.freeze({
    BEGIN: "BEGIN",
    UPDATE: "UPDATE",
    COMMIT: "COMMIT",
    ABORT: "ABORT",
    END: "END",
    CHECKPOINT_BEGIN: "CHECKPOINT_BEGIN",
    CHECKPOINT_END: "CHECKPOINT_END",
    CLR: "CLR"
});

const EngineState = Object.freeze({
    RUNNING: "RUNNING",
    CRASHED: "CRASHED",
    RECOVERING: "RECOVERING",
    RECOVERED: "RECOVERED"
});

class ValidationError extends Error {}
class DurabilityError extends Error {}
class RecoveryError extends Error {}

function validateIdentifier(value, label) {
    if (
        typeof value !== "string" ||
        value.length === 0 ||
        value.length > 128 ||
        !/^[A-Za-z0-9_-]+$/.test(value)
    ) {
        throw new ValidationError(`Invalid ${label}: ${value}`);
    }
}

function validateInteger(value, label) {
    if (!Number.isSafeInteger(value)) {
        throw new ValidationError(`${label} must be a safe integer.`);
    }
}

class WriteAheadLog {
    constructor() {
        this.records = [];
        this.nextLSN = 1;
        this.durableLSN = 0;
    }

    append(type, data = {}) {
        if (!Object.values(LogType).includes(type)) {
            throw new ValidationError(`Unknown log type: ${type}`);
        }

        const record = Object.freeze({
            lsn: this.nextLSN++,
            type,
            transactionId: data.transactionId ?? null,
            pageId: data.pageId ?? null,
            oldValue: data.oldValue ?? null,
            newValue: data.newValue ?? null,
            metadata: structuredClone(data.metadata ?? {})
        });

        this.records.push(record);
        return record;
    }

    flush(targetLSN) {
        validateInteger(targetLSN, "targetLSN");

        if (
            targetLSN < this.durableLSN ||
            targetLSN >= this.nextLSN
        ) {
            throw new DurabilityError(
                `Invalid WAL flush target: ${targetLSN}`
            );
        }

        this.durableLSN = targetLSN;
        return this.durableLSN;
    }

    durableRecords() {
        return this.records.filter(
            record => record.lsn <= this.durableLSN
        );
    }

    getRecord(lsn) {
        return this.records[lsn - 1] ?? null;
    }
}

class BufferPool extends EventEmitter {
    constructor() {
        super();
        this.pages = new Map();
    }

    createPage(pageId, value) {
        validateIdentifier(pageId, "page ID");
        validateInteger(value, "page value");

        if (this.pages.has(pageId)) {
            throw new ValidationError("Duplicate page ID.");
        }

        this.pages.set(pageId, {
            pageId,
            value,
            pageLSN: 0,
            recLSN: null,
            dirty: false
        });
    }

    getPage(pageId) {
        const page = this.pages.get(pageId);

        if (!page) {
            throw new ValidationError(`Page not found: ${pageId}`);
        }

        return page;
    }

    applyUpdate(pageId, value, lsn) {
        const page = this.getPage(pageId);

        if (!page.dirty) {
            page.recLSN = lsn;
        }

        page.value = value;
        page.pageLSN = lsn;
        page.dirty = true;

        this.emit("page:dirty", {
            pageId,
            recLSN: page.recLSN,
            pageLSN: page.pageLSN
        });
    }

    dirtyPageTable() {
        const result = {};

        for (const page of this.pages.values()) {
            if (page.dirty) {
                result[page.pageId] = page.recLSN;
            }
        }

        return result;
    }

    flush(pageId, wal, disk) {
        const page = this.getPage(pageId);

        if (!page.dirty) {
            return false;
        }

        // Never write a data page before its WAL record is durable.
        if (wal.durableLSN < page.pageLSN) {
            throw new DurabilityError(
                `Page ${pageId} requires durable LSN ${page.pageLSN}`
            );
        }

        disk.set(pageId, page.value);

        page.dirty = false;
        page.recLSN = null;

        this.emit("page:flushed", {
            pageId,
            pageLSN: page.pageLSN
        });

        return true;
    }
}

class TransactionManager extends EventEmitter {
    constructor(wal) {
        super();
        this.wal = wal;
        this.transactions = new Map();
        this.nextId = 1;
    }

    begin() {
        const id = this.nextId++;
        const record = this.wal.append(LogType.BEGIN, {
            transactionId: id
        });

        this.transactions.set(id, {
            id,
            state: "ACTIVE",
            lastLSN: record.lsn
        });

        this.emit("transaction:begin", { id });
        return id;
    }

    getActive(id) {
        const transaction = this.transactions.get(id);

        if (!transaction || transaction.state !== "ACTIVE") {
            throw new ValidationError(
                `Transaction ${id} is not active.`
            );
        }

        return transaction;
    }

    update(id, pageId, newValue, bufferPool) {
        const transaction = this.getActive(id);
        validateInteger(newValue, "new value");

        const page = bufferPool.getPage(pageId);

        const record = this.wal.append(LogType.UPDATE, {
            transactionId: id,
            pageId,
            oldValue: page.value,
            newValue
        });

        bufferPool.applyUpdate(pageId, newValue, record.lsn);
        transaction.lastLSN = record.lsn;

        this.emit("transaction:update", {
            id,
            pageId,
            lsn: record.lsn
        });
    }

    async commit(id) {
        const transaction = this.getActive(id);

        const record = this.wal.append(LogType.COMMIT, {
            transactionId: id
        });

        transaction.lastLSN = record.lsn;

        // Simulate an asynchronous stable-storage flush.
        await Promise.resolve();
        this.wal.flush(record.lsn);

        transaction.state = "COMMITTED";

        const end = this.wal.append(LogType.END, {
            transactionId: id
        });

        transaction.lastLSN = end.lsn;
        this.emit("transaction:commit", { id, lsn: record.lsn });
    }

    abort(id) {
        const transaction = this.getActive(id);

        const record = this.wal.append(LogType.ABORT, {
            transactionId: id
        });

        this.wal.flush(record.lsn);
        transaction.state = "ABORTED";
        transaction.lastLSN = record.lsn;

        this.emit("transaction:abort", { id });
    }
}

class CheckpointManager {
    constructor(wal, bufferPool, transactionManager) {
        this.wal = wal;
        this.bufferPool = bufferPool;
        this.transactionManager = transactionManager;
        this.checkpoints = [];
    }

    createCheckpoint() {
        const begin = this.wal.append(LogType.CHECKPOINT_BEGIN);

        const dirtyPageTable = this.bufferPool.dirtyPageTable();

        const transactionTable = {};

        for (
            const [id, transaction]
            of this.transactionManager.transactions
        ) {
            if (transaction.state === "ACTIVE") {
                transactionTable[id] = {
                    state: transaction.state,
                    lastLSN: transaction.lastLSN
                };
            }
        }

        const end = this.wal.append(LogType.CHECKPOINT_END, {
            metadata: {
                dirtyPageTable,
                transactionTable
            }
        });

        this.wal.flush(end.lsn);

        const checkpoint = Object.freeze({
            beginLSN: begin.lsn,
            endLSN: end.lsn,
            dirtyPageTable,
            transactionTable
        });

        this.checkpoints.push(checkpoint);

        return checkpoint;
    }

    latestDurableCheckpoint(durableLSN) {
        return [...this.checkpoints]
            .reverse()
            .find(cp => cp.endLSN <= durableLSN) ?? null;
    }
}

class RecoveryManager extends EventEmitter {
    constructor(engine) {
        super();
        this.engine = engine;
    }

    recover() {
        const engine = this.engine;

        if (engine.state !== EngineState.CRASHED) {
            throw new RecoveryError(
                "Recovery requires a crashed engine."
            );
        }

        engine.state = EngineState.RECOVERING;

        const records = engine.wal.durableRecords();

        const checkpoint =
            engine.checkpointManager.latestDurableCheckpoint(
                engine.wal.durableLSN
            );

        const dirtyPageTable = new Map(
            Object.entries(checkpoint?.dirtyPageTable ?? {})
                .map(([pageId, recLSN]) => [pageId, recLSN])
        );

        let redoStart = checkpoint
            ? Math.min(
                ...dirtyPageTable.values(),
                checkpoint.endLSN + 1
            )
            : 1;

        if (!Number.isFinite(redoStart)) {
            redoStart = 1;
        }

        const transactions = new Map(
            Object.entries(checkpoint?.transactionTable ?? {})
                .map(([id, entry]) => [
                    Number(id),
                    { ...entry }
                ])
        );

        let redoCount = 0;
        let undoCount = 0;

        // Analysis: reconstruct transaction states.
        for (const record of records) {
            if (record.lsn < redoStart || record.transactionId === null) {
                continue;
            }

            const id = record.transactionId;

            if (record.type === LogType.BEGIN) {
                transactions.set(id, {
                    state: "ACTIVE",
                    lastLSN: record.lsn
                });
                continue;
            }

            const entry = transactions.get(id) ?? {
                state: "ACTIVE",
                lastLSN: 0
            };

            entry.lastLSN = record.lsn;

            if (record.type === LogType.COMMIT) {
                entry.state = "COMMITTED";
            } else if (record.type === LogType.ABORT) {
                entry.state = "ABORTED";
            } else if (record.type === LogType.END) {
                entry.state = "ENDED";
            }

            transactions.set(id, entry);
        }

        // Redo: replay durable updates not already on disk.
        for (const record of records) {
            if (
                record.lsn < redoStart ||
                ![LogType.UPDATE, LogType.CLR].includes(record.type)
            ) {
                continue;
            }

            const page = engine.bufferPool.getPage(record.pageId);

            if (page.pageLSN >= record.lsn) {
                continue;
            }

            page.value = record.newValue;
            page.pageLSN = record.lsn;
            page.recLSN ??= record.lsn;
            page.dirty = true;

            redoCount++;
        }

        // Undo: reverse operations belonging to uncommitted transactions.
        const committed = new Set(
            [...transactions.entries()]
                .filter(([, value]) =>
                    ["COMMITTED", "ENDED"].includes(value.state)
                )
                .map(([id]) => id)
        );

        const byTransaction = new Map();

        for (const record of records) {
            if (record.transactionId === null) {
                continue;
            }

            if (!byTransaction.has(record.transactionId)) {
                byTransaction.set(record.transactionId, []);
            }

            byTransaction.get(record.transactionId).push(record);
        }

        for (const [id, txRecords] of byTransaction) {
            if (committed.has(id)) {
                continue;
            }

            for (const record of [...txRecords].reverse()) {
                if (
                    ![LogType.UPDATE, LogType.CLR].includes(record.type)
                ) {
                    continue;
                }

                const page = engine.bufferPool.getPage(record.pageId);

                if (page.pageLSN < record.lsn) {
                    continue;
                }

                const clr = engine.wal.append(LogType.CLR, {
                    transactionId: id,
                    pageId: record.pageId,
                    oldValue: record.newValue,
                    newValue: record.oldValue
                });

                page.value = record.oldValue;
                page.pageLSN = clr.lsn;
                page.recLSN ??= clr.lsn;
                page.dirty = true;

                undoCount++;
            }
        }

        // Force generated CLRs to durable storage before flushing pages.
        if (engine.wal.nextLSN > 1) {
            engine.wal.flush(engine.wal.nextLSN - 1);
        }

        for (const pageId of engine.bufferPool.pages.keys()) {
            engine.bufferPool.flush(
                pageId,
                engine.wal,
                engine.disk
            );
        }

        engine.state = EngineState.RECOVERED;

        const result = {
            redoStart,
            redoCount,
            undoCount,
            recoveredPages: Object.fromEntries(engine.disk)
        };

        this.emit("recovery:complete", result);
        return result;
    }
}

class DatabaseEngine extends EventEmitter {
    constructor() {
        super();

        this.state = EngineState.RUNNING;
        this.wal = new WriteAheadLog();
        this.bufferPool = new BufferPool();
        this.transactionManager = new TransactionManager(this.wal);
        this.checkpointManager = new CheckpointManager(
            this.wal,
            this.bufferPool,
            this.transactionManager
        );
        this.recoveryManager = new RecoveryManager(this);

        this.disk = new Map();
    }

    createPage(pageId, value) {
        this.ensureRunning();
        this.bufferPool.createPage(pageId, value);
        this.disk.set(pageId, value);
    }

    ensureRunning() {
        if (this.state !== EngineState.RUNNING) {
            throw new RecoveryError(
                `Engine cannot execute operations in state ${this.state}.`
            );
        }
    }

    crash() {
        this.ensureRunning();

        this.state = EngineState.CRASHED;

        const replacement = new BufferPool();

        for (const [pageId, value] of this.disk) {
            replacement.createPage(pageId, value);
        }

        this.bufferPool = replacement;

        // Update the checkpoint manager to reference the new pool.
        this.checkpointManager.bufferPool = replacement;
    }

    report() {
        return {
            state: this.state,
            durableLSN: this.wal.durableLSN,
            dirtyPages: this.bufferPool.dirtyPageTable(),
            transactions: Object.fromEntries(
                this.transactionManager.transactions
            ),
            disk: Object.fromEntries(this.disk)
        };
    }
}

async function writeReport(report, filename) {
    const directory = path.dirname(filename);
    await fs.mkdir(directory, { recursive: true });

    const temporary = `${filename}.${crypto.randomUUID()}.tmp`;

    try {
        await fs.writeFile(
            temporary,
            JSON.stringify(report, null, 2),
            { encoding: "utf8", flag: "wx" }
        );

        await fs.rename(temporary, filename);
    } catch (error) {
        await fs.rm(temporary, { force: true });
        throw error;
    }
}

async function main() {
    const database = new DatabaseEngine();

    database.on("recovery:complete", result => {
        console.log("Recovery event:", result);
    });

    database.bufferPool.on("page:dirty", event => {
        console.log("Dirty page:", event);
    });

    database.createPage("CUSTOMER_101", 1000);
    database.createPage("CUSTOMER_202", 2000);
    database.createPage("CUSTOMER_303", 3000);

    const tx1 = database.transactionManager.begin();

    database.transactionManager.update(
        tx1, "CUSTOMER_101", 1100, database.bufferPool
    );

    await database.transactionManager.commit(tx1);

    // Make the committed page persistent.
    database.wal.flush(database.wal.nextLSN - 1);
    database.bufferPool.flush(
        "CUSTOMER_101",
        database.wal,
        database.disk
    );

    const tx2 = database.transactionManager.begin();

    database.transactionManager.update(
        tx2, "CUSTOMER_202", 1800, database.bufferPool
    );

    const checkpoint =
        database.checkpointManager.createCheckpoint();

    console.log("Checkpoint:", checkpoint);

    const tx3 = database.transactionManager.begin();

    database.transactionManager.update(
        tx3, "CUSTOMER_303", 3500, database.bufferPool
    );

    await database.transactionManager.commit(tx3);

    database.transactionManager.update(
        tx2, "CUSTOMER_202", 1700, database.bufferPool
    );

    console.log("\nBefore crash:", database.report());

    database.crash();

    const recovery = database.recoveryManager.recover();

    console.log("\nAfter recovery:", recovery);

    const expected = {
        CUSTOMER_101: 1100,
        CUSTOMER_202: 2000,
        CUSTOMER_303: 3500
    };

    for (const [pageId, value] of Object.entries(expected)) {
        if (database.disk.get(pageId) !== value) {
            throw new Error(`Recovery verification failed: ${pageId}`);
        }
    }

    await writeReport(
        database.report(),
        path.join(process.cwd(), "database-recovery-report.json")
    );

    console.log("\nAll recovery assertions passed.");
}

main().catch(error => {
    console.error("Database simulation failed:", error);
    process.exitCode = 1;
});
