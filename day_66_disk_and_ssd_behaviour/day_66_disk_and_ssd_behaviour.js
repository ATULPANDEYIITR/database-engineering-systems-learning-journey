"use strict";

/*
 * Disk and SSD Behavior
 *
 * Event-driven storage workload simulator using Node.js.
 * Models sequential throughput, random IOPS, queueing,
 * concurrent requests, latency percentiles, and workload
 * comparisons.
 *
 * Run: node disk_ssd_behavior.js
 */

const { performance } = require("node:perf_hooks");
const { randomUUID } = require("node:crypto");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const Operation = Object.freeze({
    SEQUENTIAL_READ: "sequential_read",
    RANDOM_READ: "random_read",
    SEQUENTIAL_WRITE: "sequential_write",
    RANDOM_WRITE: "random_write"
});

class StorageError extends Error {
    constructor(message) {
        super(message);
        this.name = "StorageError";
    }
}

class StorageDevice {
    constructor({
        name,
        type,
        sequentialReadMBps,
        sequentialWriteMBps,
        randomReadIOPS,
        randomWriteIOPS,
        accessLatencyMs,
        maximumQueueDepth
    }) {
        const values = [
            sequentialReadMBps,
            sequentialWriteMBps,
            randomReadIOPS,
            randomWriteIOPS,
            accessLatencyMs,
            maximumQueueDepth
        ];

        if (!name || typeof name !== "string") {
            throw new StorageError("Device name is required");
        }

        if (values.some(
            value => !Number.isFinite(value) || value <= 0
        )) {
            throw new StorageError(
                "Device performance values must be positive"
            );
        }

        this.id = randomUUID();
        this.name = name;
        this.type = type;
        this.sequentialReadMBps = sequentialReadMBps;
        this.sequentialWriteMBps = sequentialWriteMBps;
        this.randomReadIOPS = randomReadIOPS;
        this.randomWriteIOPS = randomWriteIOPS;
        this.accessLatencyMs = accessLatencyMs;
        this.maximumQueueDepth = maximumQueueDepth;
    }

    serviceTime(operation, bytes) {
        if (!Object.values(Operation).includes(operation)) {
            throw new StorageError("Unsupported I/O operation");
        }

        if (!Number.isSafeInteger(bytes) || bytes <= 0) {
            throw new StorageError(
                "I/O size must be a positive safe integer"
            );
        }

        switch (operation) {
            case Operation.SEQUENTIAL_READ:
                return this.accessLatencyMs +
                    bytes / (
                        this.sequentialReadMBps * 1024 * 1024
                    ) * 1000;

            case Operation.SEQUENTIAL_WRITE:
                return this.accessLatencyMs +
                    bytes / (
                        this.sequentialWriteMBps * 1024 * 1024
                    ) * 1000;

            case Operation.RANDOM_READ:
                return this.accessLatencyMs +
                    1000 / this.randomReadIOPS;

            case Operation.RANDOM_WRITE:
                return this.accessLatencyMs +
                    1000 / this.randomWriteIOPS;

            default:
                throw new StorageError("Invalid operation");
        }
    }
}

class LatencyTracker {
    constructor() {
        this.samples = [];
        this.failures = 0;
    }

    record(latency) {
        if (!Number.isFinite(latency) || latency < 0) {
            this.failures++;
            return;
        }

        this.samples.push(latency);
    }

    percentile(p) {
        if (p < 0 || p > 1) {
            throw new StorageError("Invalid percentile");
        }

        if (this.samples.length === 0) {
            return 0;
        }

        const sorted = [...this.samples].sort((a, b) => a - b);
        const index = Math.max(
            0,
            Math.ceil(p * sorted.length) - 1
        );

        return sorted[index];
    }

    report() {
        if (this.samples.length === 0) {
            return {
                count: 0,
                averageMs: 0,
                p95Ms: 0,
                p99Ms: 0
            };
        }

        const total = this.samples.reduce(
            (sum, value) => sum + value,
            0
        );

        return {
            count: this.samples.length,
            failures: this.failures,
            averageMs: total / this.samples.length,
            p95Ms: this.percentile(0.95),
            p99Ms: this.percentile(0.99)
        };
    }
}

class StorageController {
    constructor(device) {
        this.device = device;
        this.queue = [];
        this.active = 0;
        this.sequence = 0;
        this.results = new LatencyTracker();
    }

    submit(operation, bytes) {
        // Validate before placing a request in the queue.
        this.device.serviceTime(operation, bytes);

        return new Promise((resolve, reject) => {
            this.queue.push({
                id: ++this.sequence,
                operation,
                bytes,
                submittedAt: performance.now(),
                resolve,
                reject
            });

            this.processQueue();
        });
    }

    processQueue() {
        while (
            this.active < this.device.maximumQueueDepth &&
            this.queue.length > 0
        ) {
            const request = this.queue.shift();
            this.active++;

            this.execute(request)
                .then(request.resolve)
                .catch(request.reject)
                .finally(() => {
                    this.active--;
                    this.processQueue();
                });
        }
    }

    async execute(request) {
        const start = performance.now();

        const serviceTime = this.device.serviceTime(
            request.operation,
            request.bytes
        );

        // Represents modeled device service time.
        await new Promise(resolve => {
            setTimeout(resolve, Math.max(0, serviceTime));
        });

        const end = performance.now();
        const latency = end - request.submittedAt;

        this.results.record(latency);

        return {
            requestId: request.id,
            operation: request.operation,
            bytes: request.bytes,
            queueWaitMs: Math.max(0, start - request.submittedAt),
            serviceTimeMs: serviceTime,
            measuredLatencyMs: latency,
            completionTime: end
        };
    }

    async runWorkload({
        operation,
        blockSize = 4096,
        requestCount = 100,
        concurrency = 8
    }) {
        if (!Number.isSafeInteger(requestCount) || requestCount <= 0) {
            throw new StorageError("Invalid request count");
        }

        if (!Number.isSafeInteger(concurrency) || concurrency <= 0) {
            throw new StorageError("Invalid concurrency");
        }

        if (!Number.isSafeInteger(blockSize) || blockSize <= 0) {
            throw new StorageError("Invalid block size");
        }

        const start = performance.now();
        const completed = [];

        // Limit application-side concurrency independently of
        // the device's maximum queue depth.
        for (
            let offset = 0;
            offset < requestCount;
            offset += concurrency
        ) {
            const batchSize = Math.min(
                concurrency,
                requestCount - offset
            );

            const batch = Array.from(
                { length: batchSize },
                () => this.submit(operation, blockSize)
            );

            const results = await Promise.allSettled(batch);

            for (const result of results) {
                if (result.status === "fulfilled") {
                    completed.push(result.value);
                } else {
                    this.results.failures++;
                }
            }
        }

        const elapsedSeconds = (
            performance.now() - start
        ) / 1000;

        const totalBytes = completed.reduce(
            (sum, item) => sum + item.bytes,
            0
        );

        return {
            device: this.device.name,
            operation,
            completedRequests: completed.length,
            failedRequests: requestCount - completed.length,
            totalBytes,
            elapsedSeconds,
            throughputMBps:
                totalBytes / (1024 * 1024) / elapsedSeconds,
            iops: completed.length / elapsedSeconds,
            latency: this.results.report()
        };
    }
}

function createDevices() {
    return [
        new StorageDevice({
            name: "Enterprise HDD",
            type: "HDD",
            sequentialReadMBps: 180,
            sequentialWriteMBps: 160,
            randomReadIOPS: 120,
            randomWriteIOPS: 110,
            accessLatencyMs: 8,
            maximumQueueDepth: 4
        }),
        new StorageDevice({
            name: "SATA SSD",
            type: "SATA SSD",
            sequentialReadMBps: 550,
            sequentialWriteMBps: 500,
            randomReadIOPS: 90000,
            randomWriteIOPS: 80000,
            accessLatencyMs: 0.08,
            maximumQueueDepth: 16
        }),
        new StorageDevice({
            name: "NVMe SSD",
            type: "NVMe SSD",
            sequentialReadMBps: 3500,
            sequentialWriteMBps: 3000,
            randomReadIOPS: 600000,
            randomWriteIOPS: 500000,
            accessLatencyMs: 0.02,
            maximumQueueDepth: 32
        })
    ];
}

async function compareDevices() {
    const devices = createDevices();

    const workloads = [
        {
            operation: Operation.SEQUENTIAL_READ,
            blockSize: 1024 * 1024,
            requestCount: 12,
            concurrency: 4
        },
        {
            operation: Operation.RANDOM_READ,
            blockSize: 4096,
            requestCount: 60,
            concurrency: 12
        },
        {
            operation: Operation.SEQUENTIAL_WRITE,
            blockSize: 1024 * 1024,
            requestCount: 12,
            concurrency: 4
        },
        {
            operation: Operation.RANDOM_WRITE,
            blockSize: 4096,
            requestCount: 60,
            concurrency: 12
        }
    ];

    const reports = [];

    for (const device of devices) {
        for (const workload of workloads) {
            const controller = new StorageController(device);

            const report = await controller.runWorkload(workload);
            reports.push(report);
        }
    }

    return reports;
}

function printReports(reports) {
    console.log("\nSTORAGE PERFORMANCE COMPARISON");
    console.log("=".repeat(105));

    console.log(
        [
            "Device".padEnd(22),
            "Operation".padEnd(22),
            "Requests".padStart(9),
            "MB/s".padStart(12),
            "IOPS".padStart(12),
            "Avg ms".padStart(12),
            "P99 ms".padStart(12)
        ].join(" ")
    );

    console.log("-".repeat(105));

    for (const report of reports) {
        console.log(
            [
                report.device.padEnd(22),
                report.operation.padEnd(22),
                String(report.completedRequests).padStart(9),
                report.throughputMBps.toFixed(2).padStart(12),
                report.iops.toFixed(2).padStart(12),
                report.latency.averageMs.toFixed(3).padStart(12),
                report.latency.p99Ms.toFixed(3).padStart(12)
            ].join(" ")
        );
    }
}

async function actualFileBenchmark() {
    /*
     * Demonstrates real sequential file operations.
     * Node.js file reads may use operating-system caching.
     * A successful write does not necessarily mean that data
     * has reached nonvolatile storage.
     */

    const directory = await fs.mkdtemp(
        path.join(os.tmpdir(), "storage-benchmark-")
    );

    const filename = path.join(directory, "sample.bin");
    const block = Buffer.alloc(1024 * 1024, 65);
    const blockCount = 8;

    try {
        const writeStart = performance.now();

        const handle = await fs.open(filename, "w");

        try {
            for (let i = 0; i < blockCount; i++) {
                await handle.write(block);
            }

            // Requests synchronization with the storage device.
            await handle.sync();
        } finally {
            await handle.close();
        }

        const writeSeconds = (
            performance.now() - writeStart
        ) / 1000;

        const readStart = performance.now();
        const reader = await fs.open(filename, "r");

        try {
            const buffer = Buffer.alloc(1024 * 1024);

            for (let i = 0; i < blockCount; i++) {
                const result = await reader.read(
                    buffer,
                    0,
                    buffer.length,
                    i * buffer.length
                );

                if (result.bytesRead !== buffer.length) {
                    throw new StorageError("Incomplete file read");
                }
            }
        } finally {
            await reader.close();
        }

        const readSeconds = (
            performance.now() - readStart
        ) / 1000;

        const totalMB = blockCount;

        console.log("\nACTUAL FILE I/O");
        console.log(`Data size: ${totalMB} MB`);
        console.log(
            `Synchronized write: ${(totalMB / writeSeconds).toFixed(2)} MB/s`
        );
        console.log(
            `Buffered read: ${(totalMB / readSeconds).toFixed(2)} MB/s`
        );
    } finally {
        await fs.rm(directory, {
            recursive: true,
            force: true
        });
    }
}

async function runTests() {
    const device = createDevices()[1];

    if (device.serviceTime(
        Operation.RANDOM_READ,
        4096
    ) <= 0) {
        throw new Error("Invalid random I/O service time");
    }

    if (device.serviceTime(
        Operation.SEQUENTIAL_READ,
        1024 * 1024
    ) <= 0) {
        throw new Error("Invalid sequential I/O service time");
    }

    let rejected = false;

    try {
        device.serviceTime(Operation.RANDOM_READ, 0);
    } catch (error) {
        rejected = error instanceof StorageError;
    }

    if (!rejected) {
        throw new Error("Zero-byte request was accepted");
    }

    const tracker = new LatencyTracker();
    tracker.record(1);
    tracker.record(2);
    tracker.record(3);

    if (tracker.percentile(0.95) !== 3) {
        throw new Error("Percentile calculation failed");
    }

    console.log("All validation tests passed.");
}

async function main() {
    await runTests();

    const reports = await compareDevices();
    printReports(reports);

    await actualFileBenchmark();
}

main().catch(error => {
    console.error("Storage benchmark failed:", error.message);
    process.exitCode = 1;
});
