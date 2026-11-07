"use strict";

/*
 * Hash Indexing: Hash Tables and Hash-Based Access
 *
 * Node.js 18+.
 *
 * Demonstrates:
 * - Map-based hash indexing
 * - Custom bucket-based hash tables
 * - Collision resolution
 * - Linear probing and tombstones
 * - Dynamic resizing
 * - Asynchronous hashing
 * - Event-driven index monitoring
 * - Validation and failure handling
 * - Hash distribution and performance metrics
 */

const { createHash, createHmac, randomBytes } = require("node:crypto");
const { EventEmitter } = require("node:events");

class IndexError extends Error {}

class InvalidKeyError extends IndexError {}

class HashIndex {
    constructor({
        capacity = 8,
        maxLoadFactor = 0.75
    } = {}) {
        if (!Number.isInteger(capacity) || capacity < 2) {
            throw new RangeError("Capacity must be at least 2.");
        }

        if (
            typeof maxLoadFactor !== "number" ||
            maxLoadFactor < 0.25 ||
            maxLoadFactor > 2
        ) {
            throw new RangeError("Invalid maximum load factor.");
        }

        this.buckets = Array.from(
            { length: capacity },
            () => []
        );

        this.size = 0;
        this.maxLoadFactor = maxLoadFactor;
        this.events = new EventEmitter();
        this.collisions = 0;
    }

    validateKey(key) {
        if (
            key === null ||
            key === undefined ||
            typeof key === "object" ||
            typeof key === "function" ||
            typeof key === "symbol"
        ) {
            throw new InvalidKeyError(
                "Keys must be non-null primitive values."
            );
        }
    }

    hash(key, capacity = this.buckets.length) {
        this.validateKey(key);

        const input = `${typeof key}:${String(key)}`;

        // FNV-1a provides a simple deterministic demonstration hash.
        let hash = 2166136261;

        for (let i = 0; i < input.length; i++) {
            hash ^= input.charCodeAt(i);
            hash = Math.imul(hash, 16777619) >>> 0;
        }

        return hash % capacity;
    }

    find(key) {
        const bucket = this.buckets[this.hash(key)];

        return bucket.find(entry => Object.is(entry.key, key));
    }

    set(key, value) {
        this.validateKey(key);

        const existing = this.find(key);

        if (existing) {
            const previousValue = existing.value;
            existing.value = value;

            this.events.emit("updated", {
                key,
                previousValue,
                value
            });

            return this;
        }

        if (
            (this.size + 1) / this.buckets.length >
            this.maxLoadFactor
        ) {
            this.resize(this.buckets.length * 2);
        }

        const index = this.hash(key);

        if (this.buckets[index].length > 0) {
            this.collisions++;
        }

        this.buckets[index].push({ key, value });
        this.size++;

        this.events.emit("inserted", { key, value });

        return this;
    }

    get(key) {
        const entry = this.find(key);

        if (!entry) {
            throw new IndexError(`Key not found: ${String(key)}`);
        }

        this.events.emit("accessed", { key });

        return entry.value;
    }

    getOrDefault(key, defaultValue) {
        const entry = this.find(key);

        return entry ? entry.value : defaultValue;
    }

    has(key) {
        return Boolean(this.find(key));
    }

    delete(key) {
        const index = this.hash(key);
        const bucket = this.buckets[index];

        const position = bucket.findIndex(
            entry => Object.is(entry.key, key)
        );

        if (position === -1) {
            return false;
        }

        const [removed] = bucket.splice(position, 1);

        this.size--;

        this.events.emit("deleted", {
            key,
            value: removed.value
        });

        return true;
    }

    resize(newCapacity) {
        const oldBuckets = this.buckets;

        this.buckets = Array.from(
            { length: newCapacity },
            () => []
        );

        this.size = 0;

        for (const bucket of oldBuckets) {
            for (const entry of bucket) {
                const index = this.hash(entry.key);

                this.buckets[index].push(entry);
                this.size++;
            }
        }

        this.events.emit("resized", {
            oldCapacity: oldBuckets.length,
            newCapacity
        });
    }

    entries() {
        return this.buckets.flatMap(
            bucket => bucket.map(
                entry => [entry.key, entry.value]
            )
        );
    }

    statistics() {
        const lengths = this.buckets.map(
            bucket => bucket.length
        );

        const occupied = lengths.filter(
            length => length > 0
        );

        return {
            capacity: this.buckets.length,
            size: this.size,
            loadFactor: this.size / this.buckets.length,
            occupiedBuckets: occupied.length,
            maximumChainLength: Math.max(0, ...lengths),
            averageChainLength: occupied.length
                ? this.size / occupied.length
                : 0,
            collisions: this.collisions
        };
    }
}


class LinearProbingIndex {
    constructor(capacity = 8) {
        if (!Number.isInteger(capacity) || capacity < 2) {
            throw new RangeError("Capacity must be at least 2.");
        }

        this.capacity = capacity;
        this.slots = new Array(capacity).fill(null);
        this.size = 0;
        this.deleted = 0;
    }

    hash(key) {
        if (key === null || key === undefined) {
            throw new InvalidKeyError("Invalid key.");
        }

        const text = String(key);

        let hash = 0;

        for (let i = 0; i < text.length; i++) {
            hash = (Math.imul(hash, 31) + text.charCodeAt(i)) >>> 0;
        }

        return hash % this.capacity;
    }

    set(key, value) {
        const start = this.hash(key);

        if (
            (this.size + this.deleted + 1) / this.capacity > 0.65
        ) {
            this.resize(this.capacity * 2);
        }

        let firstDeleted = -1;

        for (let offset = 0; offset < this.capacity; offset++) {
            const index = (start + offset) % this.capacity;
            const slot = this.slots[index];

            if (slot === null) {
                const target = firstDeleted >= 0
                    ? firstDeleted
                    : index;

                if (firstDeleted >= 0) {
                    this.deleted--;
                }

                this.slots[target] = { key, value };
                this.size++;
                return;
            }

            if (slot.deleted === true) {
                if (firstDeleted === -1) {
                    firstDeleted = index;
                }

                continue;
            }

            if (Object.is(slot.key, key)) {
                slot.value = value;
                return;
            }
        }

        if (firstDeleted >= 0) {
            this.slots[firstDeleted] = { key, value };
            this.deleted--;
            this.size++;
            return;
        }

        this.resize(this.capacity * 2);
        this.set(key, value);
    }

    get(key) {
        const start = this.hash(key);

        for (let offset = 0; offset < this.capacity; offset++) {
            const index = (start + offset) % this.capacity;
            const slot = this.slots[index];

            if (slot === null) {
                break;
            }

            if (slot.deleted === true) {
                continue;
            }

            if (Object.is(slot.key, key)) {
                return slot.value;
            }
        }

        throw new IndexError(`Key not found: ${String(key)}`);
    }

    delete(key) {
        const start = this.hash(key);

        for (let offset = 0; offset < this.capacity; offset++) {
            const index = (start + offset) % this.capacity;
            const slot = this.slots[index];

            if (slot === null) {
                return false;
            }

            if (slot.deleted === true) {
                continue;
            }

            if (Object.is(slot.key, key)) {
                this.slots[index] = { deleted: true };
                this.size--;
                this.deleted++;
                return true;
            }
        }

        return false;
    }

    resize(newCapacity) {
        const oldSlots = this.slots;

        this.capacity = newCapacity;
        this.slots = new Array(newCapacity).fill(null);
        this.size = 0;
        this.deleted = 0;

        for (const slot of oldSlots) {
            if (slot && slot.deleted !== true) {
                this.set(slot.key, slot.value);
            }
        }
    }
}


class CustomerDirectory {
    constructor() {
        this.index = new HashIndex({
            capacity: 4,
            maxLoadFactor: 0.75
        });

        this.index.events.on("inserted", ({ key }) => {
            console.log(`INDEX INSERT: ${key}`);
        });

        this.index.events.on("updated", ({ key }) => {
            console.log(`INDEX UPDATE: ${key}`);
        });

        this.index.events.on("resized", event => {
            console.log("INDEX RESIZE:", event);
        });
    }

    register(customer) {
        if (
            !customer ||
            typeof customer.customerId !== "string" ||
            !/^CUST-\d{4,}$/.test(customer.customerId)
        ) {
            throw new InvalidKeyError(
                "Customer ID must follow CUST-XXXX."
            );
        }

        if (
            typeof customer.name !== "string" ||
            customer.name.trim().length === 0
        ) {
            throw new TypeError("Customer name is required.");
        }

        if (
            !Number.isFinite(customer.balance) ||
            customer.balance < 0
        ) {
            throw new RangeError("Invalid customer balance.");
        }

        this.index.set(customer.customerId, {
            ...customer,
            name: customer.name.trim()
        });
    }

    find(customerId) {
        return this.index.get(customerId);
    }

    remove(customerId) {
        return this.index.delete(customerId);
    }
}


function sha256(value) {
    return createHash("sha256")
        .update(value, "utf8")
        .digest("hex");
}


async function sha256Async(value) {
    return Promise.resolve().then(() => sha256(value));
}


function demonstrateNativeMap() {
    console.log("\nNATIVE MAP");

    const index = new Map();

    index.set("EMP-101", "Engineering");
    index.set("EMP-102", "Security");
    index.set("EMP-103", "Research");

    console.log("Lookup:", index.get("EMP-102"));
    console.log("Contains key:", index.has("EMP-101"));

    index.delete("EMP-103");

    console.log("Entries:", [...index.entries()]);
}


function demonstrateHashing() {
    console.log("\nHASH FUNCTIONS");

    for (const value of ["customer-1", "customer-2"]) {
        console.log(value, sha256(value));
    }
}


async function demonstrateSecurity() {
    console.log("\nKEYED HASHING");

    const secret = randomBytes(32);

    const digest = createHmac("sha256", secret)
        .update("customer-101")
        .digest("hex");

    console.log("HMAC digest:", digest);

    console.log(
        "Asynchronous SHA-256:",
        await sha256Async("customer-101")
    );
}


function runAssertions() {
    const index = new HashIndex({ capacity: 2 });

    index.set("A", 10);
    index.set("B", 20);
    index.set("A", 15);

    console.assert(index.get("A") === 15);
    console.assert(index.size === 2);

    index.delete("A");

    console.assert(!index.has("A"));
    console.assert(index.get("B") === 20);

    const open = new LinearProbingIndex(4);

    open.set("A", 1);
    open.set("B", 2);
    open.delete("A");
    open.set("C", 3);

    console.assert(open.get("B") === 2);
    console.assert(open.get("C") === 3);

    console.log("\nAll assertions passed.");
}


async function main() {
    console.log("HASH INDEXING DEMONSTRATION");

    demonstrateNativeMap();

    console.log("\nSEPARATE CHAINING");

    const directory = new CustomerDirectory();

    const customers = [
        {
            customerId: "CUST-1001",
            name: "Aarav Sharma",
            balance: 12000
        },
        {
            customerId: "CUST-1002",
            name: "Diya Verma",
            balance: 18000
        },
        {
            customerId: "CUST-1003",
            name: "Kabir Singh",
            balance: 9500
        },
        {
            customerId: "CUST-1004",
            name: "Meera Joshi",
            balance: 22000
        }
    ];

    for (const customer of customers) {
        directory.register(customer);
    }

    console.log(
        "Customer record:",
        directory.find("CUST-1002")
    );

    console.log(
        "Index statistics:",
        directory.index.statistics()
    );

    console.log("\nLINEAR PROBING");

    const probing = new LinearProbingIndex();

    probing.set("TX-101", "Approved");
    probing.set("TX-102", "Pending");
    probing.set("TX-103", "Rejected");

    console.log("TX-102:", probing.get("TX-102"));

    probing.delete("TX-102");
    probing.set("TX-104", "Processing");

    console.log("TX-104:", probing.get("TX-104"));

    demonstrateHashing();

    await demonstrateSecurity();

    runAssertions();

    console.log("\nCOMPLEXITY");
    console.log("Average lookup: O(1)");
    console.log("Average insertion: O(1)");
    console.log("Average deletion: O(1)");
    console.log("Worst-case lookup: O(n)");
    console.log("Resizing: O(n)");
}

main().catch(error => {
    console.error("Execution failed:", error.message);
    process.exitCode = 1;
});
