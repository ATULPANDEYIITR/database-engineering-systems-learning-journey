"use strict";

/*
 * VACUUM AND GARBAGE COLLECTION
 * Event-driven PostgreSQL storage lifecycle simulator.
 *
 * Demonstrates MVCC row versions, visibility horizons,
 * vacuum scheduling, freezing, storage compaction,
 * asynchronous maintenance, and failure handling.
 */

const TupleState = Object.freeze({
    LIVE: "LIVE",
    DEAD: "DEAD",
    FROZEN: "FROZEN",
    REMOVED: "REMOVED"
});

const VacuumMode = Object.freeze({
    STANDARD: "STANDARD",
    FULL: "FULL",
    FREEZE: "FREEZE"
});

class ValidationError extends Error {}
class TransactionError extends Error {}
class MaintenanceError extends Error {}

class TransactionRegistry {
    #currentXid = 1;
    #active = new Map();

    begin(owner = "application") {
        const xid = this.#currentXid++;

        this.#active.set(xid, {
            owner,
            startedAt: Date.now()
        });

        return xid;
    }

    finish(xid) {
        if (!this.#active.has(xid)) {
            throw new TransactionError(
                `Transaction ${xid} is not active`
            );
        }

        this.#active.delete(xid);
    }

    get oldestActiveXid() {
        if (this.#active.size === 0) {
            return this.#currentXid;
        }

        return Math.min(...this.#active.keys());
    }

    get currentXid() {
        return this.#currentXid;
    }

    get activeCount() {
        return this.#active.size;
    }
}

class MVCCPage {
    constructor(id, capacity) {
        this.id = id;
        this.capacity = capacity;
        this.tuples = [];
    }

    get occupied() {
        return this.tuples.filter(
            row => row.state !== TupleState.REMOVED
        ).length;
    }

    hasSpace() {
        return this.occupied < this.capacity;
    }
}

class MVCCRelation {
    constructor(name, options = {}) {
        if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name)) {
            throw new ValidationError("Invalid relation name");
        }

        this.name = name;
        this.pageCapacity = options.pageCapacity ?? 20;

        if (!Number.isInteger(this.pageCapacity) ||
            this.pageCapacity < 1) {
            throw new ValidationError("Invalid page capacity");
        }

        this.pages = [];
        this.tupleIndex = new Map();
        this.nextTupleId = 1;
        this.deadCount = 0;
        this.version = 0;
    }

    #allocatePage() {
        const page = new MVCCPage(
            this.pages.length,
            this.pageCapacity
        );

        this.pages.push(page);
        return page;
    }

    #findAvailablePage() {
        for (let index = this.pages.length - 1; index >= 0; index--) {
            if (this.pages[index].hasSpace()) {
                return this.pages[index];
            }
        }

        return this.#allocatePage();
    }

    insert(value, xid) {
        if (typeof value !== "string" || value.trim() === "") {
            throw new ValidationError("Invalid tuple value");
        }

        if (!Number.isSafeInteger(xid) || xid < 1) {
            throw new ValidationError("Invalid transaction ID");
        }

        const page = this.#findAvailablePage();

        const tuple = {
            id: this.nextTupleId++,
            value,
            xmin: xid,
            xmax: null,
            state: TupleState.LIVE,
            pageId: page.id
        };

        page.tuples.push(tuple);
        this.tupleIndex.set(tuple.id, tuple);
        this.version++;

        return tuple.id;
    }

    #findLiveTuple(id) {
        const tuple = this.tupleIndex.get(id);

        if (!tuple || ![
            TupleState.LIVE,
            TupleState.FROZEN
        ].includes(tuple.state)) {
            throw new ValidationError(
                `Live tuple ${id} does not exist`
            );
        }

        return tuple;
    }

    delete(id, xid) {
        const tuple = this.#findLiveTuple(id);

        if (xid <= tuple.xmin) {
            throw new ValidationError(
                "Deletion transaction must follow insertion"
            );
        }

        tuple.xmax = xid;
        tuple.state = TupleState.DEAD;
        this.deadCount++;
        this.version++;
    }

    update(id, value, xid) {
        // Updating creates a new row version instead of
        // modifying the existing version in place.
        this.#findLiveTuple(id);

        this.delete(id, xid);
        return this.insert(value, xid);
    }

    statistics() {
        const rows = [...this.tupleIndex.values()];

        const live = rows.filter(
            row => [
                TupleState.LIVE,
                TupleState.FROZEN
            ].includes(row.state)
        ).length;

        const dead = rows.filter(
            row => row.state === TupleState.DEAD
        ).length;

        return {
            relation: this.name,
            live,
            dead,
            pages: this.pages.length,
            deadPercentage: Number(
                (100 * dead / Math.max(live + dead, 1)).toFixed(2)
            ),
            physicalBytes: this.pages.length * 8192
        };
    }

    vacuum(options) {
        const {
            mode = VacuumMode.STANDARD,
            oldestActiveXid,
            currentXid
        } = options;

        if (!Object.values(VacuumMode).includes(mode)) {
            throw new MaintenanceError("Invalid vacuum mode");
        }

        if (!Number.isSafeInteger(oldestActiveXid) ||
            !Number.isSafeInteger(currentXid) ||
            oldestActiveXid < 1 ||
            currentXid < oldestActiveXid) {
            throw new MaintenanceError(
                "Invalid transaction visibility horizon"
            );
        }

        const before = this.statistics();
        let removed = 0;
        let frozen = 0;

        for (const tuple of this.tupleIndex.values()) {
            if (tuple.state === TupleState.DEAD &&
                tuple.xmax < oldestActiveXid) {

                tuple.state = TupleState.REMOVED;
                removed++;
            }

            if (mode === VacuumMode.FREEZE &&
                tuple.state === TupleState.LIVE &&
                currentXid - tuple.xmin >= 100) {

                tuple.state = TupleState.FROZEN;
                frozen++;
            }
        }

        this.deadCount = [...this.tupleIndex.values()].filter(
            row => row.state === TupleState.DEAD
        ).length;

        if (mode === VacuumMode.FULL) {
            const active = [...this.tupleIndex.values()].filter(
                row => [
                    TupleState.LIVE,
                    TupleState.FROZEN
                ].includes(row.state)
            );

            this.pages = [];

            for (const tuple of active) {
                const page = this.#findAvailablePage();
                tuple.pageId = page.id;
                page.tuples.push(tuple);
            }
        }

        const after = this.statistics();

        return {
            scanned: this.tupleIndex.size,
            removed,
            frozen,
            deadRemaining: after.dead,
            pagesBefore: before.pages,
            pagesAfter: after.pages,
            bytesReleased: Math.max(
                0,
                before.physicalBytes - after.physicalBytes
            ),
            mode
        };
    }
}

class AutovacuumPolicy {
    constructor(options = {}) {
        this.threshold = options.threshold ?? 50;
        this.scaleFactor = options.scaleFactor ?? 0.20;
        this.maxDeadRatio = options.maxDeadRatio ?? 0.25;

        if (!Number.isInteger(this.threshold) ||
            this.threshold < 0 ||
            !Number.isFinite(this.scaleFactor) ||
            this.scaleFactor < 0 ||
            this.scaleFactor > 1 ||
            !Number.isFinite(this.maxDeadRatio) ||
            this.maxDeadRatio < 0 ||
            this.maxDeadRatio > 1) {
            throw new ValidationError(
                "Invalid autovacuum policy"
            );
        }
    }

    evaluate(stats) {
        const threshold =
            this.threshold + this.scaleFactor * stats.live;

        return {
            required:
                stats.dead > threshold ||
                stats.deadPercentage / 100 > this.maxDeadRatio,
            threshold,
            actualDeadTuples: stats.dead
        };
    }
}

class MaintenanceScheduler {
    constructor(policy) {
        this.policy = policy;
        this.events = [];
        this.running = false;
    }

    async execute(relation, registry) {
        if (this.running) {
            throw new MaintenanceError(
                "Maintenance worker is already running"
            );
        }

        this.running = true;

        try {
            const evaluation = this.policy.evaluate(
                relation.statistics()
            );

            if (!evaluation.required) {
                return {
                    executed: false,
                    reason: "Vacuum threshold not reached"
                };
            }

            // Yield execution to allow other asynchronous tasks.
            await new Promise(resolve => setImmediate(resolve));

            const report = relation.vacuum({
                mode: VacuumMode.STANDARD,
                oldestActiveXid: registry.oldestActiveXid,
                currentXid: registry.currentXid
            });

            this.events.push({
                time: new Date().toISOString(),
                relation: relation.name,
                report
            });

            return {
                executed: true,
                report
            };
        } catch (error) {
            throw new MaintenanceError(
                `Maintenance failed: ${error.message}`
            );
        } finally {
            this.running = false;
        }
    }
}

async function main() {
    const registry = new TransactionRegistry();

    const orders = new MVCCRelation("orders", {
        pageCapacity: 10
    });

    console.log("1. INSERT OPERATIONS");

    const initialXid = registry.begin("application");

    const identifiers = [];

    for (let i = 0; i < 35; i++) {
        identifiers.push(
            orders.insert(`Order-${i}`, initialXid)
        );
    }

    registry.finish(initialXid);

    console.log(orders.statistics());

    console.log("\n2. MVCC DELETE OPERATIONS");

    const oldXid = registry.begin("long-running-report");
    const deleteXid = registry.begin("cleanup-job");

    for (const id of identifiers.slice(0, 15)) {
        orders.delete(id, deleteXid);
    }

    registry.finish(deleteXid);

    console.log(orders.statistics());

    console.log("\n3. VACUUM WITH ACTIVE SNAPSHOT");

    const firstReport = orders.vacuum({
        mode: VacuumMode.STANDARD,
        oldestActiveXid: registry.oldestActiveXid,
        currentXid: registry.currentXid
    });

    console.log(firstReport);

    console.log("\n4. COMPLETE LONG-RUNNING TRANSACTION");

    registry.finish(oldXid);

    const secondReport = orders.vacuum({
        mode: VacuumMode.STANDARD,
        oldestActiveXid: registry.oldestActiveXid,
        currentXid: registry.currentXid
    });

    console.log(secondReport);

    console.log("\n5. UPDATE OPERATIONS");

    for (const id of identifiers.slice(15, 25)) {
        const xid = registry.begin("order-update");

        orders.update(id, `Revised-${id}`, xid);

        registry.finish(xid);
    }

    console.log(orders.statistics());

    console.log("\n6. ASYNCHRONOUS AUTOVACUUM");

    const policy = new AutovacuumPolicy({
        threshold: 3,
        scaleFactor: 0.10,
        maxDeadRatio: 0.10
    });

    const scheduler = new MaintenanceScheduler(policy);

    console.log(await scheduler.execute(orders, registry));

    console.log("\n7. TRANSACTION FREEZING");

    console.log(orders.vacuum({
        mode: VacuumMode.FREEZE,
        oldestActiveXid: registry.oldestActiveXid,
        currentXid: registry.currentXid + 200
    }));

    console.log("\n8. VACUUM FULL");

    console.log(orders.vacuum({
        mode: VacuumMode.FULL,
        oldestActiveXid: registry.oldestActiveXid,
        currentXid: registry.currentXid + 200
    }));

    console.log("\n9. FINAL STATISTICS");

    console.log(orders.statistics());
    console.log("Maintenance events:", scheduler.events.length);

    console.log("\n10. FAILURE HANDLING");

    try {
        orders.delete(99999, registry.currentXid);
    } catch (error) {
        console.log(error.name, error.message);
    }

    try {
        new AutovacuumPolicy({
            scaleFactor: 5
        });
    } catch (error) {
        console.log(error.name, error.message);
    }

    if (registry.activeCount !== 0) {
        throw new TransactionError(
            "Unexpected active transactions remain"
        );
    }

    if (orders.statistics().dead < 0) {
        throw new Error("Invalid dead tuple count");
    }

    console.log("\nAll validation checks passed.");
}

main().catch(error => {
    console.error("Application failure:", error);
    process.exitCode = 1;
});
