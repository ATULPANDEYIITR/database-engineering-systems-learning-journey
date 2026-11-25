'use strict';

/**
 * Pessimistic Concurrency: Event-Driven Lock Manager
 *
 * Features:
 * - Shared and exclusive locks
 * - FIFO lock queues
 * - Lock upgrades
 * - Transaction-level locking
 * - Strict two-phase locking
 * - Asynchronous acquisition
 * - Lock timeout
 * - Deadlock detection
 * - Atomic resource updates
 * - Rollback and transaction cleanup
 *
 * Runtime: Node.js 18+
 */

const { EventEmitter } = require('node:events');
const { randomUUID } = require('node:crypto');

const LockMode = Object.freeze({
    SHARED: 'SHARED',
    EXCLUSIVE: 'EXCLUSIVE'
});

const TransactionState = Object.freeze({
    ACTIVE: 'ACTIVE',
    COMMITTED: 'COMMITTED',
    ABORTED: 'ABORTED'
});

class LockError extends Error {}
class LockTimeoutError extends LockError {}
class DeadlockError extends LockError {}
class TransactionError extends Error {}

class LockManager extends EventEmitter {
    constructor() {
        super();

        this.resources = new Map();
        this.transactions = new Map();
        this.waiters = new Map();
        this.waitFor = new Map();
    }

    register(transaction) {
        if (this.transactions.has(transaction.id)) {
            throw new TransactionError('Duplicate transaction');
        }

        this.transactions.set(transaction.id, transaction);
        this.waitFor.set(transaction.id, new Set());
    }

    _resource(resource) {
        if (!this.resources.has(resource)) {
            this.resources.set(resource, {
                holders: new Map(),
                queue: []
            });
        }

        return this.resources.get(resource);
    }

    _conflicts(transaction, resource, mode) {
        const state = this._resource(resource);
        const conflicts = new Set();

        for (const [id, heldMode] of state.holders) {
            if (id === transaction.id) continue;

            if (
                mode === LockMode.EXCLUSIVE ||
                heldMode === LockMode.EXCLUSIVE
            ) {
                conflicts.add(id);
            }
        }

        return conflicts;
    }

    _cycleExists(start) {
        const visiting = new Set();
        const visited = new Set();

        const dfs = node => {
            if (visiting.has(node)) return true;
            if (visited.has(node)) return false;

            visiting.add(node);

            for (const next of this.waitFor.get(node) || []) {
                if (dfs(next)) return true;
            }

            visiting.delete(node);
            visited.add(node);

            return false;
        };

        return dfs(start);
    }

    _grant(transaction, resource, mode) {
        const state = this._resource(resource);

        state.holders.set(transaction.id, mode);
        transaction.locks.set(resource, mode);

        this.emit('lockGranted', {
            transactionId: transaction.id,
            resource,
            mode
        });
    }

    acquire(transaction, resource, mode, timeoutMs = 3000) {
        if (transaction.state !== TransactionState.ACTIVE) {
            return Promise.reject(
                new TransactionError('Transaction is inactive')
            );
        }

        if (!resource || !Object.values(LockMode).includes(mode)) {
            return Promise.reject(
                new TypeError('Invalid resource or lock mode')
            );
        }

        if (!Number.isFinite(timeoutMs) || timeoutMs < 0) {
            return Promise.reject(
                new RangeError('Invalid timeout')
            );
        }

        const existing = transaction.locks.get(resource);

        if (existing === LockMode.EXCLUSIVE) {
            return Promise.resolve();
        }

        if (
            existing === LockMode.SHARED &&
            mode === LockMode.SHARED
        ) {
            return Promise.resolve();
        }

        if (!transaction.growing) {
            return Promise.reject(
                new TransactionError('Strict 2PL growing phase ended')
            );
        }

        const state = this._resource(resource);

        const conflicts = this._conflicts(
            transaction,
            resource,
            mode
        );

        const queueHasPriority = state.queue.length > 0;

        if (!conflicts.size && !queueHasPriority) {
            this._grant(transaction, resource, mode);
            return Promise.resolve();
        }

        return new Promise((resolve, reject) => {
            const waiter = {
                transaction,
                resource,
                mode,
                resolve,
                reject,
                timer: null,
                settled: false
            };

            state.queue.push(waiter);
            this.waiters.set(transaction.id, waiter);

            this._refreshWaitGraph();

            if (this._cycleExists(transaction.id)) {
                this._removeWaiter(waiter);

                reject(new DeadlockError(
                    `Deadlock detected for ${transaction.id}`
                ));

                return;
            }

            waiter.timer = setTimeout(() => {
                if (waiter.settled) return;

                this._removeWaiter(waiter);

                reject(new LockTimeoutError(
                    `Lock timeout: ${resource}`
                ));
            }, timeoutMs);

            this.emit('lockWaiting', {
                transactionId: transaction.id,
                resource,
                mode
            });
        });
    }

    _removeWaiter(waiter) {
        if (waiter.settled) return;

        waiter.settled = true;
        clearTimeout(waiter.timer);

        const state = this.resources.get(waiter.resource);

        if (state) {
            state.queue = state.queue.filter(
                item => item !== waiter
            );
        }

        this.waiters.delete(waiter.transaction.id);
        this._refreshWaitGraph();
        this._process(waiter.resource);
    }

    _refreshWaitGraph() {
        this.waitFor.clear();

        for (const id of this.transactions.keys()) {
            this.waitFor.set(id, new Set());
        }

        for (const [resource, state] of this.resources) {
            for (const waiter of state.queue) {
                const blockers = this._conflicts(
                    waiter.transaction,
                    resource,
                    waiter.mode
                );

                for (const blocker of blockers) {
                    this.waitFor.get(waiter.transaction.id).add(blocker);
                }

                // Earlier incompatible waiters also block later requests.
                for (const previous of state.queue) {
                    if (previous === waiter) break;

                    if (
                        previous.mode === LockMode.EXCLUSIVE ||
                        waiter.mode === LockMode.EXCLUSIVE
                    ) {
                        this.waitFor.get(waiter.transaction.id)
                            .add(previous.transaction.id);
                    }
                }
            }
        }
    }

    _process(resource) {
        const state = this.resources.get(resource);

        if (!state) return;

        while (state.queue.length > 0) {
            const waiter = state.queue[0];

            if (waiter.settled) {
                state.queue.shift();
                continue;
            }

            if (
                waiter.transaction.state !== TransactionState.ACTIVE
            ) {
                this._removeWaiter(waiter);
                continue;
            }

            const conflicts = this._conflicts(
                waiter.transaction,
                resource,
                waiter.mode
            );

            if (conflicts.size > 0) break;

            // Preserve FIFO ordering while allowing compatible
            // shared requests to be granted together.
            state.queue.shift();
            waiter.settled = true;
            clearTimeout(waiter.timer);
            this.waiters.delete(waiter.transaction.id);

            this._grant(
                waiter.transaction,
                resource,
                waiter.mode
            );

            waiter.resolve();

            if (waiter.mode === LockMode.EXCLUSIVE) break;
        }

        this._refreshWaitGraph();
    }

    releaseAll(transaction) {
        for (const resource of transaction.locks.keys()) {
            const state = this.resources.get(resource);

            if (!state) continue;

            state.holders.delete(transaction.id);

            if (
                state.holders.size === 0 &&
                state.queue.length === 0
            ) {
                this.resources.delete(resource);
            }
        }

        transaction.locks.clear();

        for (const waiter of [...this.waiters.values()]) {
            if (waiter.transaction === transaction) {
                this._removeWaiter(waiter);
            }
        }

        this._refreshWaitGraph();

        for (const resource of this.resources.keys()) {
            this._process(resource);
        }
    }

    commit(transaction) {
        if (transaction.state !== TransactionState.ACTIVE) {
            throw new TransactionError('Cannot commit inactive transaction');
        }

        transaction.growing = false;
        transaction.state = TransactionState.COMMITTED;

        this.releaseAll(transaction);

        this.emit('committed', { transactionId: transaction.id });
    }

    rollback(transaction) {
        if (transaction.state !== TransactionState.ACTIVE) return;

        for (const [key, previousValue] of [...transaction.undo].reverse()) {
            transaction.database.set(key, previousValue);
        }

        transaction.undo.length = 0;
        transaction.growing = false;
        transaction.state = TransactionState.ABORTED;

        this.releaseAll(transaction);

        this.emit('rolledBack', {
            transactionId: transaction.id
        });
    }
}

class Transaction {
    constructor(manager, database) {
        this.id = randomUUID();
        this.manager = manager;
        this.database = database;
        this.state = TransactionState.ACTIVE;
        this.growing = true;
        this.locks = new Map();
        this.undo = [];

        manager.register(this);
    }

    async lock(resource, mode, timeoutMs = 3000) {
        return this.manager.acquire(
            this,
            resource,
            mode,
            timeoutMs
        );
    }

    write(key, value) {
        if (this.state !== TransactionState.ACTIVE) {
            throw new TransactionError('Transaction is inactive');
        }

        if (this.locks.get(key) !== LockMode.EXCLUSIVE) {
            throw new TransactionError(
                `Exclusive lock required for ${key}`
            );
        }

        if (!this.database.has(key)) {
            throw new TransactionError(`Unknown resource: ${key}`);
        }

        const previousValue = this.database.get(key);

        this.undo.push([key, previousValue]);
        this.database.set(key, value);
    }

    commit() {
        this.manager.commit(this);
    }

    rollback() {
        this.manager.rollback(this);
    }
}

class InventoryService {
    constructor(initialStock) {
        this.stock = new Map(Object.entries(initialStock));
        this.manager = new LockManager();
    }

    async reserve(product, quantity) {
        if (!Number.isInteger(quantity) || quantity <= 0) {
            throw new RangeError('Quantity must be positive');
        }

        if (!this.stock.has(product)) {
            throw new TransactionError('Unknown product');
        }

        const transaction = new Transaction(
            this.manager,
            this.stock
        );

        try {
            await transaction.lock(
                product,
                LockMode.EXCLUSIVE
            );

            const available = this.stock.get(product);

            if (available < quantity) {
                throw new TransactionError('Insufficient inventory');
            }

            transaction.write(product, available - quantity);
            transaction.commit();

            return {
                transactionId: transaction.id,
                product,
                reserved: quantity,
                remaining: this.stock.get(product)
            };

        } catch (error) {
            transaction.rollback();
            throw error;
        }
    }
}

async function main() {
    const inventory = new InventoryService({
        LAPTOP: 50,
        MONITOR: 30,
        KEYBOARD: 100
    });

    inventory.manager.on('lockGranted', event => {
        console.log('LOCK GRANTED:', event.resource, event.mode);
    });

    inventory.manager.on('committed', event => {
        console.log('COMMITTED:', event.transactionId);
    });

    inventory.manager.on('rolledBack', event => {
        console.log('ROLLED BACK:', event.transactionId);
    });

    const results = await Promise.allSettled([
        inventory.reserve('LAPTOP', 10),
        inventory.reserve('LAPTOP', 15),
        inventory.reserve('LAPTOP', 20),
        inventory.reserve('MONITOR', 5)
    ]);

    console.log('\nReservation results:');

    for (const result of results) {
        if (result.status === 'fulfilled') {
            console.log(result.value);
        } else {
            console.log('Rejected:', result.reason.message);
        }
    }

    console.log('\nFinal inventory:');

    console.log(Object.fromEntries(inventory.stock));

    const before = inventory.stock.get('KEYBOARD');

    try {
        await inventory.reserve('KEYBOARD', 1000);
    } catch (error) {
        console.log('\nExpected failure:', error.message);
    }

    if (inventory.stock.get('KEYBOARD') !== before) {
        throw new Error('Rollback invariant violated');
    }

    console.log('Rollback invariant verified');
}

main().catch(error => {
    console.error('Fatal execution error:', error);
    process.exitCode = 1;
});
