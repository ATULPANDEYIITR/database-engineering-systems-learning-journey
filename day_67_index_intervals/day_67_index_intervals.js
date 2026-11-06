"use strict";

/*
 * Index Internals: B+ tree page management and index diagnostics.
 *
 * Provides:
 * - B+ tree insertion and search.
 * - Internal and leaf page separation.
 * - Linked-leaf range scans.
 * - Breadth-first and depth-first traversal.
 * - Page serialization and diagnostics.
 * - Asynchronous concurrent request handling.
 * - LRU buffer-pool simulation.
 *
 * Runtime: Node.js 18+
 */

const { performance } = require("node:perf_hooks");
const { randomInt } = require("node:crypto");

class IndexError extends Error {}
class DuplicateKeyError extends IndexError {}
class InvalidIndexOperation extends IndexError {}

class IndexPage {
    constructor(id, type) {
        this.id = id;
        this.type = type;
        this.keys = [];
        this.children = [];
        this.values = [];
        this.next = null;
        this.parent = null;
        this.version = 0;
    }

    get isLeaf() {
        return this.type === "LEAF";
    }
}

class BPlusIndex {
    constructor(order = 5) {
        if (!Number.isInteger(order) || order < 3) {
            throw new RangeError("Order must be an integer >= 3");
        }

        this.order = order;
        this.maxKeys = order - 1;
        this.pages = new Map();
        this.nextId = 1;
        this.count = 0;
        this.root = this.createPage("LEAF");
        this.metrics = {
            reads: 0,
            writes: 0,
            splits: 0,
            searches: 0
        };
    }

    createPage(type) {
        const page = new IndexPage(this.nextId++, type);
        this.pages.set(page.id, page);
        return page;
    }

    read(page) {
        this.metrics.reads++;
        return page;
    }

    write(page) {
        page.version++;
        this.metrics.writes++;
    }

    minimum(page) {
        while (!page.isLeaf) {
            page = page.children[0];
        }
        return page.keys[0];
    }

    refresh(page) {
        if (page.isLeaf) return;

        page.keys = page.children
            .slice(1)
            .map(child => this.minimum(child));
    }

    locateLeaf(key) {
        let page = this.root;

        while (!page.isLeaf) {
            this.read(page);

            let low = 0;
            let high = page.keys.length;

            while (low < high) {
                const middle = (low + high) >>> 1;

                if (key >= page.keys[middle]) {
                    low = middle + 1;
                } else {
                    high = middle;
                }
            }

            page = page.children[low];
        }

        return this.read(page);
    }

    lowerBound(array, value) {
        let low = 0;
        let high = array.length;

        while (low < high) {
            const middle = (low + high) >>> 1;

            if (array[middle] < value) {
                low = middle + 1;
            } else {
                high = middle;
            }
        }

        return low;
    }

    search(key) {
        this.validateKey(key);
        this.metrics.searches++;

        const leaf = this.locateLeaf(key);
        const index = this.lowerBound(leaf.keys, key);

        if (leaf.keys[index] === key) {
            return leaf.values[index];
        }

        return null;
    }

    validateKey(key) {
        if (!Number.isSafeInteger(key)) {
            throw new TypeError("Key must be a safe integer");
        }
    }

    async insert(key, value) {
        this.validateKey(key);

        if (typeof value !== "string") {
            throw new TypeError("Value must be a string");
        }

        const leaf = this.locateLeaf(key);
        const index = this.lowerBound(leaf.keys, key);

        if (leaf.keys[index] === key) {
            throw new DuplicateKeyError(`Duplicate key: ${key}`);
        }

        leaf.keys.splice(index, 0, key);
        leaf.values.splice(index, 0, value);
        this.count++;
        this.write(leaf);

        if (leaf.keys.length > this.maxKeys) {
            this.splitLeaf(leaf);
        }

        this.repairAncestors(leaf.parent);
    }

    splitLeaf(leaf) {
        const middle = Math.ceil(leaf.keys.length / 2);
        const right = this.createPage("LEAF");

        right.keys = leaf.keys.splice(middle);
        right.values = leaf.values.splice(middle);

        right.next = leaf.next;
        leaf.next = right;

        this.metrics.splits++;
        this.write(leaf);
        this.write(right);
        this.attachRightSibling(leaf, right);
    }

    attachRightSibling(left, right) {
        let parent = left.parent;

        if (!parent) {
            parent = this.createPage("INTERNAL");
            parent.children = [left, right];
            left.parent = parent;
            right.parent = parent;
            this.refresh(parent);
            this.root = parent;
            this.write(parent);
            return;
        }

        const position = parent.children.indexOf(left);
        parent.children.splice(position + 1, 0, right);
        right.parent = parent;

        this.refresh(parent);
        this.write(parent);

        if (parent.children.length > this.order) {
            this.splitInternal(parent);
        }
    }

    splitInternal(page) {
        const middle = Math.ceil(page.children.length / 2);
        const right = this.createPage("INTERNAL");

        right.children = page.children.splice(middle);

        for (const child of right.children) {
            child.parent = right;
        }

        this.refresh(page);
        this.refresh(right);

        this.metrics.splits++;
        this.write(page);
        this.write(right);

        this.attachRightSibling(page, right);
    }

    repairAncestors(page) {
        while (page) {
            this.refresh(page);
            this.write(page);
            page = page.parent;
        }
    }

    rangeScan(start, end) {
        this.validateKey(start);
        this.validateKey(end);

        if (start > end) return [];

        const results = [];
        let leaf = this.locateLeaf(start);

        while (leaf) {
            this.read(leaf);

            for (let i = 0; i < leaf.keys.length; i++) {
                const key = leaf.keys[i];

                if (key > end) return results;

                if (key >= start) {
                    results.push({
                        key,
                        value: leaf.values[i]
                    });
                }
            }

            leaf = leaf.next;
        }

        return results;
    }

    breadthFirst() {
        const output = [];
        const queue = [this.root];

        for (let head = 0; head < queue.length; head++) {
            const page = queue[head];

            output.push({
                id: page.id,
                type: page.type,
                keys: [...page.keys],
                children: page.children.map(child => child.id),
                nextLeaf: page.next?.id ?? null
            });

            queue.push(...page.children);
        }

        return output;
    }

    depthFirst() {
        const output = [];

        const visit = page => {
            output.push({
                id: page.id,
                type: page.type,
                keys: [...page.keys]
            });

            for (const child of page.children) {
                visit(child);
            }
        };

        visit(this.root);
        return output;
    }

    leafTraversal() {
        let page = this.root;

        while (!page.isLeaf) {
            page = page.children[0];
        }

        const keys = [];

        while (page) {
            keys.push(...page.keys);
            page = page.next;
        }

        return keys;
    }

    validate() {
        const visited = new Set();
        const leaves = [];

        const inspect = (page, root = false) => {
            if (visited.has(page.id)) {
                throw new InvalidIndexOperation("Page cycle detected");
            }

            visited.add(page.id);

            if (page.isLeaf) {
                if (page.keys.length !== page.values.length) {
                    throw new InvalidIndexOperation("Leaf value mismatch");
                }

                for (let i = 1; i < page.keys.length; i++) {
                    if (page.keys[i - 1] >= page.keys[i]) {
                        throw new InvalidIndexOperation(
                            "Leaf keys must be strictly increasing"
                        );
                    }
                }

                if (page.keys.length > this.maxKeys) {
                    throw new InvalidIndexOperation("Leaf overflow");
                }

                leaves.push(page);
                return {
                    min: page.keys[0] ?? Infinity,
                    max: page.keys.at(-1) ?? -Infinity
                };
            }

            if (page.children.length !== page.keys.length + 1) {
                throw new InvalidIndexOperation(
                    "Internal page pointer count mismatch"
                );
            }

            if (page.children.length > this.order) {
                throw new InvalidIndexOperation("Internal overflow");
            }

            const ranges = page.children.map(child => {
                if (child.parent !== page) {
                    throw new InvalidIndexOperation("Invalid parent pointer");
                }

                return inspect(child);
            });

            const expected = ranges.slice(1).map(range => range.min);

            if (JSON.stringify(page.keys) !== JSON.stringify(expected)) {
                throw new InvalidIndexOperation("Invalid separators");
            }

            for (let i = 1; i < ranges.length; i++) {
                if (ranges[i - 1].max >= ranges[i].min) {
                    throw new InvalidIndexOperation("Overlapping ranges");
                }
            }

            return {
                min: ranges[0].min,
                max: ranges.at(-1).max
            };
        };

        inspect(this.root, true);

        let count = 0;

        for (let i = 0; i < leaves.length; i++) {
            const expected = leaves[i + 1] ?? null;

            if (leaves[i].next !== expected) {
                throw new InvalidIndexOperation("Invalid leaf links");
            }

            count += leaves[i].keys.length;
        }

        if (count !== this.count) {
            throw new InvalidIndexOperation("Incorrect record count");
        }

        return true;
    }

    statistics() {
        const pages = this.breadthFirst();
        const leaves = pages.filter(p => p.type === "LEAF");
        const internal = pages.filter(p => p.type === "INTERNAL");

        let height = 0;
        let current = this.root;

        while (current) {
            height++;
            current = current.isLeaf ? null : current.children[0];
        }

        return {
            records: this.count,
            height,
            pages: pages.length,
            leafPages: leaves.length,
            internalPages: internal.length,
            splits: this.metrics.splits,
            reads: this.metrics.reads,
            writes: this.metrics.writes
        };
    }
}

class LRUBufferPool {
    constructor(capacity) {
        if (!Number.isInteger(capacity) || capacity < 1) {
            throw new RangeError("Capacity must be positive");
        }

        this.capacity = capacity;
        this.cache = new Map();
        this.hits = 0;
        this.misses = 0;
        this.evictions = 0;
    }

    access(pageId) {
        if (this.cache.has(pageId)) {
            this.hits++;
            const value = this.cache.get(pageId);
            this.cache.delete(pageId);
            this.cache.set(pageId, value);
            return;
        }

        this.misses++;

        if (this.cache.size === this.capacity) {
            const oldest = this.cache.keys().next().value;
            this.cache.delete(oldest);
            this.evictions++;
        }

        this.cache.set(pageId, true);
    }

    report() {
        const total = this.hits + this.misses;

        return {
            hits: this.hits,
            misses: this.misses,
            evictions: this.evictions,
            hitRatio: total ? this.hits / total : 0
        };
    }
}

class IndexQueryService {
    constructor(index) {
        this.index = index;
        this.activeRequests = 0;
    }

    async execute(key) {
        this.activeRequests++;

        try {
            // Yield to the event loop to model asynchronous request handling.
            await new Promise(resolve => setImmediate(resolve));
            return this.index.search(key);
        } finally {
            this.activeRequests--;
        }
    }

    async executeBatch(keys) {
        return Promise.all(keys.map(key => this.execute(key)));
    }
}

async function main() {
    console.log("B+ TREE INDEX INTERNALS");
    console.log("=".repeat(60));

    const index = new BPlusIndex(5);

    const records = [
        [42, "Customer-A"],
        [12, "Customer-B"],
        [89, "Customer-C"],
        [23, "Customer-D"],
        [56, "Customer-E"],
        [78, "Customer-F"],
        [34, "Customer-G"],
        [67, "Customer-H"],
        [91, "Customer-I"],
        [10, "Customer-J"],
        [50, "Customer-K"],
        [72, "Customer-L"],
        [15, "Customer-M"],
        [28, "Customer-N"]
    ];

    for (const [key, value] of records) {
        await index.insert(key, value);
    }

    console.log("\nSearch:", index.search(56));
    console.log("Missing key:", index.search(999));

    console.log("\nRange scan:", index.rangeScan(20, 70));
    console.log("\nBreadth-first pages:", index.breadthFirst());
    console.log("\nDepth-first pages:", index.depthFirst());
    console.log("\nLeaf traversal:", index.leafTraversal());

    console.log("\nStatistics:", index.statistics());

    const service = new IndexQueryService(index);

    const results = await service.executeBatch([
        10, 23, 42, 56, 999
    ]);

    console.log("\nConcurrent query results:", results);

    const buffer = new LRUBufferPool(4);

    for (const page of index.breadthFirst()) {
        buffer.access(page.id);
    }

    for (const page of index.breadthFirst().slice(0, 2)) {
        buffer.access(page.id);
    }

    console.log("\nBuffer pool:", buffer.report());

    const generated = Array.from(
        { length: 300 },
        () => randomInt(1, 100000)
    );

    const stress = new BPlusIndex(8);

    for (const key of new Set(generated)) {
        await stress.insert(key, `record-${key}`);
    }

    console.log("\nStress test valid:", stress.validate());
    console.log("Stress test statistics:", stress.statistics());

    try {
        await index.insert(56, "Duplicate");
    } catch (error) {
        console.log("\nDuplicate rejected:", error.message);
    }

    try {
        index.search(Number.NaN);
    } catch (error) {
        console.log("Invalid key rejected:", error.message);
    }

    console.log("\nIntegrity validation:", index.validate());
}

main().catch(error => {
    console.error("Index execution failed:", error);
    process.exitCode = 1;
});
