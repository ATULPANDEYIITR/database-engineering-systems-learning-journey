"use strict";

/*
 * LSM Trees: Event-driven storage engine simulation.
 *
 * Features:
 * - Asynchronous write operations
 * - Append-only write-ahead log
 * - Memtable using Map
 * - Immutable sorted runs
 * - Bloom filters
 * - Sparse indexes
 * - Flush and compaction scheduling
 * - Tombstones and version resolution
 * - Range queries
 * - Storage metrics
 *
 * Runtime: Node.js 18+
 * Dependencies: None
 */

const fs = require("node:fs/promises");
const path = require("node:path");
const crypto = require("node:crypto");
const EventEmitter = require("node:events");

const Operation = Object.freeze({
    PUT: "PUT",
    DELETE: "DELETE"
});

class BloomFilter {
    constructor(capacity, falsePositiveRate = 0.01) {
        if (!Number.isInteger(capacity) || capacity < 1) {
            throw new RangeError("Invalid Bloom filter capacity");
        }

        if (!(falsePositiveRate > 0 && falsePositiveRate < 1)) {
            throw new RangeError("Invalid false positive rate");
        }

        this.bitCount = Math.max(
            8,
            Math.ceil(
                -capacity * Math.log(falsePositiveRate) /
                (Math.log(2) ** 2)
            )
        );

        this.hashCount = Math.max(
            1,
            Math.round(
                this.bitCount / capacity * Math.log(2)
            )
        );

        this.bits = new Uint8Array(
            Math.ceil(this.bitCount / 8)
        );
    }

    positions(key) {
        const digest = crypto
            .createHash("sha256")
            .update(key)
            .digest();

        const first = digest.readBigUInt64BE(0);
        const second = digest.readBigUInt64BE(8) | 1n;

        const positions = [];

        for (let i = 0; i < this.hashCount; i++) {
            const value = Number(
                (first + BigInt(i) * second) %
                BigInt(this.bitCount)
            );

            positions.push(value);
        }

        return positions;
    }

    add(key) {
        for (const position of this.positions(key)) {
            this.bits[position >> 3] |= 1 << (position & 7);
        }
    }

    mightContain(key) {
        return this.positions(key).every(position => {
            return (
                this.bits[position >> 3] &
                (1 << (position & 7))
            ) !== 0;
        });
    }
}

class MemTable {
    constructor() {
        this.entries = new Map();
        this.bytes = 0;
    }

    set(entry) {
        const previous = this.entries.get(entry.key);

        if (previous) {
            this.bytes -= Buffer.byteLength(JSON.stringify(previous));
        }

        this.entries.set(entry.key, Object.freeze({ ...entry }));
        this.bytes += Buffer.byteLength(JSON.stringify(entry));
    }

    get(key) {
        return this.entries.get(key);
    }

    size() {
        return this.entries.size;
    }

    isEmpty() {
        return this.entries.size === 0;
    }

    sortedEntries() {
        return [...this.entries.values()].sort(
            (a, b) => a.key.localeCompare(b.key)
        );
    }

    clear() {
        this.entries.clear();
        this.bytes = 0;
    }
}

class SortedRun {
    constructor(id, level, entries, indexInterval = 8) {
        if (!entries.length) {
            throw new Error("Cannot create an empty sorted run");
        }

        this.id = id;
        this.level = level;
        this.entries = [...entries].sort(
            (a, b) => a.key.localeCompare(b.key)
        );

        this.minKey = this.entries[0].key;
        this.maxKey = this.entries[this.entries.length - 1].key;

        this.bloom = new BloomFilter(this.entries.length);
        this.sparseIndex = [];
        this.indexInterval = indexInterval;

        this.entries.forEach((entry, position) => {
            this.bloom.add(entry.key);

            if (position % indexInterval === 0) {
                this.sparseIndex.push({
                    key: entry.key,
                    position
                });
            }
        });

        Object.freeze(this.entries);
    }

    get(key) {
        if (
            key < this.minKey ||
            key > this.maxKey ||
            !this.bloom.mightContain(key)
        ) {
            return undefined;
        }

        let low = 0;
        let high = this.sparseIndex.length - 1;
        let selected = -1;

        while (low <= high) {
            const middle = Math.floor((low + high) / 2);

            if (this.sparseIndex[middle].key <= key) {
                selected = middle;
                low = middle + 1;
            } else {
                high = middle - 1;
            }
        }

        const start = selected < 0
            ? 0
            : this.sparseIndex[selected].position;

        const end = Math.min(
            start + this.indexInterval,
            this.entries.length
        );

        for (let i = start; i < end; i++) {
            const entry = this.entries[i];

            if (entry.key === key) return entry;
            if (entry.key > key) break;
        }

        return undefined;
    }
}

class WriteAheadLog {
    constructor(filename) {
        this.filename = filename;
        this.handle = null;
    }

    async open() {
        await fs.mkdir(path.dirname(this.filename), {
            recursive: true
        });

        this.handle = await fs.open(this.filename, "a+");
    }

    async append(entry) {
        if (!this.handle) {
            throw new Error("WAL is not open");
        }

        const line = JSON.stringify(entry) + "\n";

        await this.handle.write(
            line,
            null,
            "utf8"
        );

        await this.handle.sync();
    }

    async recover() {
        const contents = await fs.readFile(
            this.filename,
            "utf8"
        );

        const recovered = [];

        for (const [index, line] of contents.split("\n").entries()) {
            if (!line.trim()) continue;

            try {
                const entry = JSON.parse(line);

                if (
                    typeof entry.key !== "string" ||
                    !Number.isSafeInteger(entry.sequence) ||
                    !Object.values(Operation).includes(entry.operation)
                ) {
                    throw new Error("Invalid record fields");
                }

                recovered.push(entry);
            } catch (error) {
                throw new Error(
                    `WAL corruption at line ${index + 1}: ${error.message}`
                );
            }
        }

        return recovered;
    }

    async close() {
        if (this.handle) {
            await this.handle.sync();
            await this.handle.close();
            this.handle = null;
        }
    }
}

class LSMStorage extends EventEmitter {
    constructor({
        directory = "./lsm-js-data",
        memtableLimit = 4,
        levelCapacity = 3,
        indexInterval = 8
    } = {}) {
        super();

        if (memtableLimit < 1 || levelCapacity < 2) {
            throw new RangeError("Invalid storage configuration");
        }

        this.directory = directory;
        this.memtableLimit = memtableLimit;
        this.levelCapacity = levelCapacity;
        this.indexInterval = indexInterval;

        this.memtable = new MemTable();
        this.levels = new Map([[0, []]]);

        this.sequence = 0;
        this.runSequence = 0;

        this.wal = new WriteAheadLog(
            path.join(directory, "operations.wal")
        );

        // Serializes mutations so concurrent requests cannot reorder
        // sequence assignment and durable log writes.
        this.writeQueue = Promise.resolve();
        this.closed = false;
    }

    async initialize() {
        await this.wal.open();
        return this;
    }

    enqueueMutation(operation) {
        if (this.closed) {
            return Promise.reject(
                new Error("Storage engine is closed")
            );
        }

        const task = this.writeQueue.then(operation);

        this.writeQueue = task.catch(() => {});

        return task;
    }

    async put(key, value) {
        return this.enqueueMutation(async () => {
            if (
                typeof key !== "string" ||
                key.length === 0 ||
                typeof value !== "string"
            ) {
                throw new TypeError("Invalid PUT arguments");
            }

            const entry = Object.freeze({
                key,
                value,
                sequence: this.sequence + 1,
                operation: Operation.PUT,
                timestamp: Date.now()
            });

            // Do not modify memory until the WAL write succeeds.
            await this.wal.append(entry);

            this.sequence = entry.sequence;
            this.memtable.set(entry);

            this.emit("write", entry);

            if (this.memtable.size() >= this.memtableLimit) {
                this.flush();
            }

            return entry.sequence;
        });
    }

    async delete(key) {
        return this.enqueueMutation(async () => {
            if (typeof key !== "string" || !key) {
                throw new TypeError("Invalid DELETE key");
            }

            const entry = Object.freeze({
                key,
                value: null,
                sequence: this.sequence + 1,
                operation: Operation.DELETE,
                timestamp: Date.now()
            });

            await this.wal.append(entry);

            this.sequence = entry.sequence;
            this.memtable.set(entry);

            this.emit("delete", entry);

            if (this.memtable.size() >= this.memtableLimit) {
                this.flush();
            }

            return entry.sequence;
        });
    }

    lookup(key) {
        if (typeof key !== "string" || !key) {
            throw new TypeError("Invalid lookup key");
        }

        let latest = this.memtable.get(key);

        for (const [, runs] of this.levels) {
            for (const run of runs) {
                const candidate = run.get(key);

                if (
                    candidate &&
                    (!latest || candidate.sequence > latest.sequence)
                ) {
                    latest = candidate;
                }
            }
        }

        if (!latest || latest.operation === Operation.DELETE) {
            return null;
        }

        return latest.value;
    }

    flush() {
        if (this.memtable.isEmpty()) return null;

        const entries = this.memtable.sortedEntries();

        const run = new SortedRun(
            ++this.runSequence,
            0,
            entries,
            this.indexInterval
        );

        this.levels.get(0).push(run);
        this.memtable.clear();

        this.emit("flush", {
            runId: run.id,
            entries: run.entries.length
        });

        this.scheduleCompaction(0);

        return run.id;
    }

    scheduleCompaction(level) {
        const runs = this.levels.get(level) || [];

        if (runs.length < this.levelCapacity) return;

        // Queue compaction outside the current synchronous mutation.
        queueMicrotask(() => {
            try {
                this.compact(level);
            } catch (error) {
                this.emit("error", error);
            }
        });
    }

    compact(level) {
        const runs = this.levels.get(level) || [];

        if (runs.length < 2) return false;

        const merged = new Map();

        for (const run of runs) {
            for (const entry of run.entries) {
                const previous = merged.get(entry.key);

                if (!previous || entry.sequence > previous.sequence) {
                    merged.set(entry.key, entry);
                }
            }
        }

        const outputEntries = [...merged.values()].sort(
            (a, b) => a.key.localeCompare(b.key)
        );

        if (!outputEntries.length) return false;

        const nextLevel = level + 1;

        const output = new SortedRun(
            ++this.runSequence,
            nextLevel,
            outputEntries,
            this.indexInterval
        );

        // Construct the output completely before replacing input runs.
        this.levels.set(level, []);
        this.levels.set(
            nextLevel,
            [...(this.levels.get(nextLevel) || []), output]
        );

        this.emit("compaction", {
            inputLevel: level,
            outputLevel: nextLevel,
            outputEntries: outputEntries.length
        });

        this.scheduleCompaction(nextLevel);

        return true;
    }

    rangeScan(start, end) {
        if (
            typeof start !== "string" ||
            typeof end !== "string" ||
            start > end
        ) {
            throw new RangeError("Invalid range");
        }

        const latest = new Map();

        const process = entry => {
            if (entry.key < start || entry.key > end) return;

            const previous = latest.get(entry.key);

            if (!previous || entry.sequence > previous.sequence) {
                latest.set(entry.key, entry);
            }
        };

        for (const entry of this.memtable.sortedEntries()) {
            process(entry);
        }

        for (const runs of this.levels.values()) {
            for (const run of runs) {
                for (const entry of run.entries) {
                    process(entry);
                }
            }
        }

        return [...latest.values()]
            .filter(entry => entry.operation === Operation.PUT)
            .sort((a, b) => a.key.localeCompare(b.key))
            .map(entry => ({
                key: entry.key,
                value: entry.value
            }));
    }

    async recover() {
        return this.enqueueMutation(async () => {
            const records = await this.wal.recover();

            this.memtable.clear();
            this.sequence = 0;

            const latest = new Map();

            for (const entry of records) {
                if (entry.sequence <= 0) {
                    throw new Error("Invalid WAL sequence");
                }

                const previous = latest.get(entry.key);

                if (!previous || entry.sequence > previous.sequence) {
                    latest.set(entry.key, entry);
                }

                this.sequence = Math.max(
                    this.sequence,
                    entry.sequence
                );
            }

            for (const entry of latest.values()) {
                this.memtable.set(entry);
            }

            return this.memtable.size();
        });
    }

    statistics() {
        const levelStats = {};

        for (const [level, runs] of this.levels) {
            levelStats[level] = {
                runCount: runs.length,
                entries: runs.reduce(
                    (total, run) => total + run.entries.length,
                    0
                )
            };
        }

        return {
            sequence: this.sequence,
            memtableEntries: this.memtable.size(),
            memtableBytes: this.memtable.bytes,
            levels: levelStats,
            totalRuns: [...this.levels.values()]
                .reduce((total, runs) => total + runs.length, 0)
        };
    }

    async close() {
        await this.writeQueue;

        if (!this.closed) {
            this.flush();
            await this.wal.close();
            this.closed = true;
            this.emit("close");
        }
    }
}

async function main() {
    const directory = path.join(
        process.cwd(),
        "lsm-demo-data"
    );

    const storage = await new LSMStorage({
        directory,
        memtableLimit: 3,
        levelCapacity: 2,
        indexInterval: 2
    }).initialize();

    storage.on("write", entry => {
        console.log(`WRITE ${entry.key} sequence=${entry.sequence}`);
    });

    storage.on("flush", event => {
        console.log("FLUSH", event);
    });

    storage.on("compaction", event => {
        console.log("COMPACTION", event);
    });

    storage.on("error", error => {
        console.error("Background operation failed:", error.message);
    });

    try {
        await storage.put("order:101", "PENDING");
        await storage.put("order:102", "PROCESSING");
        await storage.put("order:103", "SHIPPED");

        await storage.put("order:102", "DELIVERED");
        await storage.delete("order:103");
        await storage.put("order:104", "PENDING");

        console.log("\nPOINT LOOKUPS");
        console.log("101:", storage.lookup("order:101"));
        console.log("102:", storage.lookup("order:102"));
        console.log("103:", storage.lookup("order:103"));

        console.log("\nRANGE SCAN");
        console.table(
            storage.rangeScan("order:101", "order:104")
        );

        storage.flush();
        storage.compact(0);

        console.log("\nSTATISTICS");
        console.log(
            JSON.stringify(storage.statistics(), null, 2)
        );

        console.log("\nVALIDATION");

        if (storage.lookup("order:102") !== "DELIVERED") {
            throw new Error("Latest-version lookup failed");
        }

        if (storage.lookup("order:103") !== null) {
            throw new Error("Tombstone handling failed");
        }

        console.log("All checks passed.");
    } finally {
        await storage.close();
    }
}

main().catch(error => {
    console.error("Storage engine failure:", error);
    process.exitCode = 1;
});
