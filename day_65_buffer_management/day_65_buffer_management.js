"use strict";

const { EventEmitter } = require("node:events");
const { performance } = require("node:perf_hooks");

class BufferManagementError extends Error {}
class BufferFullError extends BufferManagementError {}
class PageNotFoundError extends BufferManagementError {}
class PageSizeError extends BufferManagementError {}

class BufferFrame {
    constructor(pageId, data) {
        this.pageId = pageId;
        this.data = Buffer.from(data);
        this.pinCount = 0;
        this.dirty = false;
        this.accessCount = 1;
        this.lastAccess = performance.now();
        this.state = "clean";
    }

    touch() {
        this.accessCount++;
        this.lastAccess = performance.now();
    }

    markDirty() {
        this.dirty = true;
        this.state = "dirty";
    }

    markClean() {
        this.dirty = false;
        this.state = "clean";
    }
}

class BufferPool extends EventEmitter {
    constructor({
        capacity,
        pageSize = 4096,
        loader,
        writer
    }) {
        super();

        if (!Number.isInteger(capacity) || capacity <= 0) {
            throw new RangeError("Capacity must be a positive integer.");
        }

        if (!Number.isInteger(pageSize) || pageSize <= 0) {
            throw new RangeError("Page size must be positive.");
        }

        if (typeof loader !== "function" ||
            typeof writer !== "function") {
            throw new TypeError("Loader and writer functions are required.");
        }

        this.capacity = capacity;
        this.pageSize = pageSize;
        this.loader = loader;
        this.writer = writer;

        this.frames = new Map();
        this.inFlight = new Map();

        this.stats = {
            requests: 0,
            hits: 0,
            misses: 0,
            evictions: 0,
            writes: 0,
            failedEvictions: 0
        };

        this.closed = false;
    }

    validatePageId(pageId) {
        if (!Number.isSafeInteger(pageId) || pageId < 0) {
            throw new RangeError("Page ID must be a non-negative safe integer.");
        }

        if (this.closed) {
            throw new BufferManagementError("Buffer pool is closed.");
        }
    }

    validatePage(data) {
        if (!Buffer.isBuffer(data)) {
            throw new TypeError("Storage must return a Buffer.");
        }

        if (data.length !== this.pageSize) {
            throw new PageSizeError(
                `Expected ${this.pageSize} bytes, received ${data.length}.`
            );
        }
    }

    async fetch(pageId) {
        this.validatePageId(pageId);
        this.stats.requests++;

        const cached = this.frames.get(pageId);

        if (cached) {
            this.stats.hits++;
            cached.touch();
            this.emit("hit", { pageId });
            return cached;
        }

        this.stats.misses++;

        // Concurrent requests for one page share a single storage read.
        if (this.inFlight.has(pageId)) {
            return this.inFlight.get(pageId);
        }

        const operation = this.loadAndCache(pageId);

        this.inFlight.set(pageId, operation);

        try {
            return await operation;
        } finally {
            this.inFlight.delete(pageId);
        }
    }

    async loadAndCache(pageId) {
        const start = performance.now();

        // Fetch before eviction so a failed read does not destroy cached data.
        const data = await this.loader(pageId);

        this.validatePage(data);

        const frame = new BufferFrame(pageId, data);

        if (this.frames.size >= this.capacity) {
            await this.evictOne();
        }

        this.frames.set(pageId, frame);

        this.emit("miss", {
            pageId,
            loadDurationMs: performance.now() - start
        });

        return frame;
    }

    async evictOne() {
        // Select the least recently used unpinned frame.
        const candidates = [...this.frames.values()]
            .filter(frame => frame.pinCount === 0)
            .sort((a, b) => a.lastAccess - b.lastAccess);

        if (candidates.length === 0) {
            this.stats.failedEvictions++;
            throw new BufferFullError(
                "All frames are pinned; eviction is impossible."
            );
        }

        const victim = candidates[0];

        if (victim.dirty) {
            await this.persist(victim);
        }

        this.frames.delete(victim.pageId);
        this.stats.evictions++;

        this.emit("eviction", {
            pageId: victim.pageId
        });
    }

    async persist(frame) {
        if (!frame.dirty) return;

        // Copy data so a writer cannot mutate the buffer-pool frame.
        await this.writer(
            frame.pageId,
            Buffer.from(frame.data)
        );

        frame.markClean();
        this.stats.writes++;

        this.emit("write", {
            pageId: frame.pageId
        });
    }

    async pin(pageId) {
        const frame = await this.fetch(pageId);
        frame.pinCount++;
        return frame;
    }

    unpin(pageId, dirty = false) {
        this.validatePageId(pageId);

        const frame = this.frames.get(pageId);

        if (!frame) {
            throw new PageNotFoundError(`Page ${pageId} is not cached.`);
        }

        if (frame.pinCount === 0) {
            throw new BufferManagementError("Page is not pinned.");
        }

        frame.pinCount--;

        if (dirty) {
            frame.markDirty();
        }
    }

    async read(pageId) {
        const frame = await this.fetch(pageId);
        return Buffer.from(frame.data);
    }

    async write(pageId, offset, payload) {
        if (!Buffer.isBuffer(payload)) {
            throw new TypeError("Payload must be a Buffer.");
        }

        if (!Number.isInteger(offset) ||
            offset < 0 ||
            offset + payload.length > this.pageSize) {
            throw new RangeError("Write exceeds page boundaries.");
        }

        const frame = await this.pin(pageId);

        try {
            payload.copy(frame.data, offset);
            frame.markDirty();
        } finally {
            this.unpin(pageId, true);
        }
    }

    async flushPage(pageId) {
        const frame = this.frames.get(pageId);

        if (!frame) {
            throw new PageNotFoundError(`Page ${pageId} is not cached.`);
        }

        if (frame.pinCount > 0) {
            throw new BufferManagementError("Cannot flush a pinned page.");
        }

        await this.persist(frame);
    }

    async flushAll() {
        const pinned = [...this.frames.values()]
            .filter(frame => frame.pinCount > 0);

        if (pinned.length > 0) {
            throw new BufferManagementError(
                "Cannot flush while pages remain pinned."
            );
        }

        for (const frame of this.frames.values()) {
            await this.persist(frame);
        }
    }

    async invalidate(pageId, discardDirty = false) {
        const frame = this.frames.get(pageId);

        if (!frame) return;

        if (frame.pinCount > 0) {
            throw new BufferManagementError("Cannot invalidate a pinned page.");
        }

        if (frame.dirty && !discardDirty) {
            await this.persist(frame);
        }

        this.frames.delete(pageId);
    }

    getStatistics() {
        const requests = this.stats.requests;

        return {
            ...this.stats,
            usedFrames: this.frames.size,
            freeFrames: this.capacity - this.frames.size,
            hitRatio: requests ? this.stats.hits / requests : 0,
            missRatio: requests ? this.stats.misses / requests : 0,
            frames: [...this.frames.values()].map(frame => ({
                pageId: frame.pageId,
                dirty: frame.dirty,
                pinCount: frame.pinCount,
                accessCount: frame.accessCount
            }))
        };
    }

    async close() {
        await this.flushAll();
        this.closed = true;
        this.emit("closed");
    }
}

async function main() {
    const storage = new Map();
    const pageSize = 128;

    const loader = async pageId => {
        await new Promise(resolve => setTimeout(resolve, 5));

        if (!storage.has(pageId)) {
            storage.set(
                pageId,
                Buffer.from(`Database page ${pageId}`)
                    .subarray(0, pageSize)
            );

            const page = Buffer.alloc(pageSize);
            Buffer.from(`Database page ${pageId}`).copy(page);
            storage.set(pageId, page);
        }

        return Buffer.from(storage.get(pageId));
    };

    const writer = async (pageId, data) => {
        await new Promise(resolve => setTimeout(resolve, 2));
        storage.set(pageId, Buffer.from(data));
        console.log(`Persisted page ${pageId}`);
    };

    const pool = new BufferPool({
        capacity: 3,
        pageSize,
        loader,
        writer
    });

    pool.on("hit", event => {
        console.log(`Cache hit: ${event.pageId}`);
    });

    pool.on("miss", event => {
        console.log(`Cache miss: ${event.pageId}`);
    });

    pool.on("eviction", event => {
        console.log(`Evicted page: ${event.pageId}`);
    });

    console.log("\n1. Concurrent page requests");

    await Promise.all([
        pool.fetch(1),
        pool.fetch(1),
        pool.fetch(1)
    ]);

    console.log("\n2. Populate the buffer pool");

    await pool.fetch(2);
    await pool.fetch(3);
    await pool.fetch(1);

    console.log("\n3. Modify a page");

    await pool.write(2, 0, Buffer.from("UPDATED RECORD"));

    console.log("\n4. Exercise LRU replacement");

    await pool.fetch(4);

    console.log("\n5. Test pinned-frame protection");

    await pool.pin(2);
    await pool.pin(3);
    await pool.pin(4);

    try {
        await pool.fetch(5);
    } catch (error) {
        console.log("Expected error:", error.message);
    }

    pool.unpin(2);
    pool.unpin(3);
    pool.unpin(4);

    console.log("\n6. Flush and inspect");

    await pool.flushAll();

    console.log(JSON.stringify(pool.getStatistics(), null, 2));

    console.log("\n7. Validate persistence");

    if (!storage.get(2).toString().startsWith("UPDATED RECORD")) {
        throw new Error("Dirty page was not persisted.");
    }

    await pool.close();

    console.log("\nBuffer management demonstration completed.");
}

main().catch(error => {
    console.error("Application failure:", error);
    process.exitCode = 1;
});
