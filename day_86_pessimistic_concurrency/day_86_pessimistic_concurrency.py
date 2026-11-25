#!/usr/bin/env python3
"""
Pessimistic Concurrency: Lock-Based Approaches

Demonstrates:
- Shared and exclusive locks
- Lock compatibility
- Two-Phase Locking (2PL)
- Strict Two-Phase Locking
- Transaction isolation
- Lock timeouts
- Deadlock detection using a wait-for graph
- Atomic account transfers
- Rollback and lock release
- Concurrent execution using threads
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LockMode(Enum):
    SHARED = "SHARED"
    EXCLUSIVE = "EXCLUSIVE"


class TransactionState(Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class LockError(Exception):
    pass


class LockTimeout(LockError):
    pass


class DeadlockDetected(LockError):
    pass


class TransactionError(Exception):
    pass


@dataclass
class Lock:
    resource: str
    mode: LockMode
    holders: set[int] = field(default_factory=set)


@dataclass
class Transaction:
    transaction_id: int
    state: TransactionState = TransactionState.ACTIVE
    locks: dict[str, LockMode] = field(default_factory=dict)
    undo_log: list[tuple[str, int]] = field(default_factory=list)
    waiting_for: set[int] = field(default_factory=set)
    growing_phase: bool = True


class LockManager:
    """
    Thread-safe lock manager.

    Shared locks can coexist.
    Exclusive locks require sole ownership.

    Strict 2PL is enforced by retaining all locks until
    transaction commit or rollback.
    """

    def __init__(self):
        self.condition = threading.Condition(threading.RLock())
        self.locks: dict[str, dict[int, LockMode]] = defaultdict(dict)
        self.transactions: dict[int, Transaction] = {}

    def register(self, transaction: Transaction):
        with self.condition:
            if transaction.transaction_id in self.transactions:
                raise TransactionError("Duplicate transaction ID")
            self.transactions[transaction.transaction_id] = transaction

    def _conflicting_holders(
        self,
        transaction_id: int,
        resource: str,
        mode: LockMode
    ) -> set[int]:

        holders = self.locks[resource]
        conflicts = set()

        for holder_id, held_mode in holders.items():
            if holder_id == transaction_id:
                continue

            if mode == LockMode.EXCLUSIVE or held_mode == LockMode.EXCLUSIVE:
                conflicts.add(holder_id)

        return conflicts

    def _has_cycle(self, start: int) -> bool:
        """
        Detect cycles in the wait-for graph using DFS.
        An edge T1 -> T2 means T1 waits for T2.
        """

        visited = set()
        active = set()

        def visit(node):
            if node in active:
                return True

            if node in visited:
                return False

            visited.add(node)
            active.add(node)

            transaction = self.transactions.get(node)

            if transaction:
                for neighbor in transaction.waiting_for:
                    if visit(neighbor):
                        return True

            active.remove(node)
            return False

        return visit(start)

    def acquire(
        self,
        transaction: Transaction,
        resource: str,
        mode: LockMode,
        timeout: float = 5.0
    ):
        if timeout < 0:
            raise ValueError("Timeout cannot be negative")

        if not resource:
            raise ValueError("Resource cannot be empty")

        deadline = time.monotonic() + timeout

        with self.condition:
            if transaction.state != TransactionState.ACTIVE:
                raise TransactionError("Transaction is not active")

            existing = transaction.locks.get(resource)

            if existing == LockMode.EXCLUSIVE:
                return

            if not transaction.growing_phase:
                raise TransactionError(
                    "2PL violation: transaction cannot acquire new locks"
                )

            if existing == LockMode.SHARED and mode == LockMode.SHARED:
                return

            while True:
                if transaction.state != TransactionState.ACTIVE:
                    raise TransactionError("Transaction was terminated")

                conflicts = self._conflicting_holders(
                    transaction.transaction_id,
                    resource,
                    mode
                )

                transaction.waiting_for = conflicts

                if not conflicts:
                    transaction.waiting_for.clear()

                    # Shared-to-exclusive upgrade is atomic under the
                    # condition lock.
                    self.locks[resource][transaction.transaction_id] = mode
                    transaction.locks[resource] = mode
                    return

                if self._has_cycle(transaction.transaction_id):
                    transaction.waiting_for.clear()
                    raise DeadlockDetected(
                        f"Deadlock involving transaction "
                        f"{transaction.transaction_id}"
                    )

                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    transaction.waiting_for.clear()
                    raise LockTimeout(
                        f"Timeout acquiring {mode.value} lock on {resource}"
                    )

                self.condition.wait(remaining)

    def release_all(self, transaction: Transaction):
        with self.condition:
            for resource in list(transaction.locks):
                self.locks[resource].pop(
                    transaction.transaction_id,
                    None
                )

                if not self.locks[resource]:
                    del self.locks[resource]

            transaction.locks.clear()
            transaction.waiting_for.clear()
            self.condition.notify_all()

    def commit(self, transaction: Transaction):
        with self.condition:
            if transaction.state != TransactionState.ACTIVE:
                raise TransactionError("Cannot commit inactive transaction")

            transaction.growing_phase = False
            transaction.state = TransactionState.COMMITTED

            # Strict 2PL: locks are retained until this point.
            self.release_all(transaction)

    def rollback(self, transaction: Transaction, database):
        with self.condition:
            if transaction.state != TransactionState.ACTIVE:
                return

            for account_id, previous_balance in reversed(
                transaction.undo_log
            ):
                database[account_id] = previous_balance

            transaction.undo_log.clear()
            transaction.growing_phase = False
            transaction.state = TransactionState.ABORTED
            self.release_all(transaction)


class Bank:
    def __init__(self, initial_balances: dict[str, int]):
        if not initial_balances:
            raise ValueError("At least one account is required")

        if any(
            not account or balance < 0
            for account, balance in initial_balances.items()
        ):
            raise ValueError("Invalid initial account data")

        self.balances = dict(initial_balances)
        self.manager = LockManager()
        self._id_lock = threading.Lock()
        self._next_id = 1

    def new_transaction(self) -> Transaction:
        with self._id_lock:
            transaction = Transaction(self._next_id)
            self._next_id += 1

        self.manager.register(transaction)
        return transaction

    def transfer(
        self,
        source: str,
        destination: str,
        amount: int,
        timeout: float = 5.0
    ) -> int:

        if source == destination:
            raise ValueError("Source and destination must differ")

        if amount <= 0:
            raise ValueError("Transfer amount must be positive")

        transaction = self.new_transaction()

        try:
            # Consistent lock ordering reduces deadlock probability.
            for account in sorted([source, destination]):
                self.manager.acquire(
                    transaction,
                    f"account:{account}",
                    LockMode.EXCLUSIVE,
                    timeout
                )

            if source not in self.balances:
                raise TransactionError("Source account does not exist")

            if destination not in self.balances:
                raise TransactionError("Destination account does not exist")

            if self.balances[source] < amount:
                raise TransactionError("Insufficient funds")

            transaction.undo_log.append(
                (source, self.balances[source])
            )
            transaction.undo_log.append(
                (destination, self.balances[destination])
            )

            self.balances[source] -= amount
            self.balances[destination] += amount

            self.manager.commit(transaction)
            return transaction.transaction_id

        except Exception:
            self.manager.rollback(transaction, self.balances)
            raise

    def snapshot(self):
        return dict(self.balances)

    def total_balance(self):
        return sum(self.balances.values())


def demonstrate_lock_compatibility():
    manager = LockManager()

    t1 = Transaction(101)
    t2 = Transaction(102)
    t3 = Transaction(103)

    for transaction in (t1, t2, t3):
        manager.register(transaction)

    manager.acquire(t1, "inventory:1", LockMode.SHARED)
    manager.acquire(t2, "inventory:1", LockMode.SHARED)

    try:
        manager.acquire(
            t3,
            "inventory:1",
            LockMode.EXCLUSIVE,
            timeout=0.05
        )
    except LockTimeout:
        print("Exclusive lock correctly blocked by shared locks")

    manager.commit(t1)
    manager.commit(t2)

    manager.acquire(t3, "inventory:1", LockMode.EXCLUSIVE)
    manager.commit(t3)

    print("Lock compatibility test passed")


def demonstrate_concurrent_transfers():
    bank = Bank({
        "A": 10000,
        "B": 10000,
        "C": 10000
    })

    initial_total = bank.total_balance()
    errors = []
    error_lock = threading.Lock()

    def worker(source, destination, amount, iterations):
        for _ in range(iterations):
            try:
                bank.transfer(source, destination, amount)
            except (LockTimeout, DeadlockDetected, TransactionError) as exc:
                with error_lock:
                    errors.append(str(exc))

    threads = [
        threading.Thread(
            target=worker,
            args=("A", "B", 10, 100)
        ),
        threading.Thread(
            target=worker,
            args=("B", "C", 10, 100)
        ),
        threading.Thread(
            target=worker,
            args=("C", "A", 10, 100)
        )
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    final_total = bank.total_balance()

    assert initial_total == final_total
    assert all(balance >= 0 for balance in bank.balances.values())

    print("\nConcurrent transfer results:")
    print("Balances:", bank.snapshot())
    print("Initial total:", initial_total)
    print("Final total:", final_total)
    print("Rejected transactions:", len(errors))
    print("Atomicity and balance invariants verified")


def demonstrate_rollback():
    bank = Bank({"A": 500, "B": 100})

    before = bank.snapshot()

    try:
        bank.transfer("A", "B", 1000)
    except TransactionError as exc:
        print("\nExpected rollback:", exc)

    assert bank.snapshot() == before
    print("Rollback test passed")


def main():
    print("PESSIMISTIC CONCURRENCY: LOCK-BASED APPROACHES")
    print("=" * 55)

    demonstrate_lock_compatibility()
    demonstrate_rollback()
    demonstrate_concurrent_transfers()

    print("\nAll demonstrations completed.")


if __name__ == "__main__":
    main()
