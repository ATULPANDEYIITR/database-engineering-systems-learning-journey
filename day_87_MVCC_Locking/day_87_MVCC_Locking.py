#!/usr/bin/env python3
"""
MVCC vs Locking: Transaction Concurrency and Architectural Trade-offs.

Implements:
1. Multi-Version Concurrency Control (MVCC).
2. Pessimistic exclusive-lock concurrency control.
3. Snapshot-based reads.
4. Write-write conflict detection.
5. Read-your-writes behavior.
6. Transaction commit and rollback.
7. Lock ownership and release.
8. Concurrent transaction simulations.
9. Architecture workload evaluation.

Python 3.10+
No external dependencies.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Any, Optional
import logging
import time


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)

logger = logging.getLogger("concurrency")


class ConcurrencyError(Exception):
    """Base exception for concurrency failures."""


class WriteConflict(ConcurrencyError):
    """Raised when an MVCC transaction cannot commit safely."""


class LockUnavailable(ConcurrencyError):
    """Raised when a requested exclusive lock is already owned."""


class TransactionClosed(ConcurrencyError):
    """Raised when operating on a completed transaction."""


class IsolationModel(Enum):
    MVCC = "MVCC"
    PESSIMISTIC_LOCKING = "PESSIMISTIC_LOCKING"


class TransactionState(Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


@dataclass(frozen=True)
class Version:
    commit_timestamp: int
    value: Any


@dataclass
class Transaction:
    transaction_id: int
    snapshot_timestamp: int
    state: TransactionState = TransactionState.ACTIVE
    read_set: set[str] = field(default_factory=set)
    write_set: dict[str, Any] = field(default_factory=dict)
    held_locks: set[str] = field(default_factory=set)


@dataclass
class Metrics:
    transactions_started: int = 0
    transactions_committed: int = 0
    transactions_aborted: int = 0
    conflicts: int = 0
    lock_failures: int = 0
    reads: int = 0
    writes: int = 0

    @property
    def commit_rate(self) -> float:
        if self.transactions_started == 0:
            return 0.0
        return (
            self.transactions_committed
            / self.transactions_started
            * 100
        )


class MVCCStore:
    """
    Simplified snapshot-isolation storage engine.

    Readers access the newest version visible at their snapshot.
    Writers create new versions at commit time.

    Concurrent writes to the same record are detected using
    first-committer-wins validation.

    This implementation demonstrates snapshot isolation,
    not full serializable isolation.
    """

    def __init__(self, initial_data: Optional[dict] = None):
        self._lock = RLock()
        self._clock = 0
        self._transaction_counter = 0
        self._versions: dict[str, list[Version]] = defaultdict(list)
        self.metrics = Metrics()

        for key, value in (initial_data or {}).items():
            self._versions[key].append(Version(0, value))

    def begin(self) -> Transaction:
        with self._lock:
            self._transaction_counter += 1

            transaction = Transaction(
                transaction_id=self._transaction_counter,
                snapshot_timestamp=self._clock
            )

            self.metrics.transactions_started += 1
            return transaction

    def _ensure_active(self, tx: Transaction) -> None:
        if tx.state != TransactionState.ACTIVE:
            raise TransactionClosed(
                f"Transaction {tx.transaction_id} is {tx.state.value}"
            )

    def _visible_version(
        self,
        key: str,
        snapshot_timestamp: int
    ) -> Optional[Version]:

        versions = self._versions.get(key, [])

        for version in reversed(versions):
            if version.commit_timestamp <= snapshot_timestamp:
                return version

        return None

    def read(self, tx: Transaction, key: str) -> Any:
        with self._lock:
            self._ensure_active(tx)

            if key in tx.write_set:
                self.metrics.reads += 1
                return tx.write_set[key]

            version = self._visible_version(
                key,
                tx.snapshot_timestamp
            )

            tx.read_set.add(key)
            self.metrics.reads += 1

            return None if version is None else version.value

    def write(self, tx: Transaction, key: str, value: Any) -> None:
        with self._lock:
            self._ensure_active(tx)

            tx.write_set[key] = value

    def commit(self, tx: Transaction) -> bool:
        with self._lock:
            self._ensure_active(tx)

            # Validate every modified key before publishing any version.
            for key in tx.write_set:
                latest = self._versions.get(key, [])

                if (
                    latest
                    and latest[-1].commit_timestamp
                    > tx.snapshot_timestamp
                ):
                    tx.state = TransactionState.ABORTED
                    self.metrics.transactions_aborted += 1
                    self.metrics.conflicts += 1

                    logger.warning(
                        "MVCC conflict: transaction %s, key %s",
                        tx.transaction_id,
                        key
                    )

                    return False

            # A single commit timestamp makes the write set atomic.
            self._clock += 1
            commit_timestamp = self._clock

            for key, value in tx.write_set.items():
                self._versions[key].append(
                    Version(commit_timestamp, value)
                )

                self.metrics.writes += 1

            tx.state = TransactionState.COMMITTED
            self.metrics.transactions_committed += 1

            return True

    def rollback(self, tx: Transaction) -> None:
        with self._lock:
            self._ensure_active(tx)

            tx.write_set.clear()
            tx.state = TransactionState.ABORTED
            self.metrics.transactions_aborted += 1

    def history(self, key: str) -> list[Version]:
        with self._lock:
            return list(self._versions.get(key, []))


class LockingStore:
    """
    Pessimistic exclusive-lock storage model.

    Transactions acquire exclusive locks when accessing records.
    Locks remain held until commit or rollback.

    This simplified implementation uses immediate lock failure
    instead of blocking or implementing deadlock detection.
    """

    def __init__(self, initial_data: Optional[dict] = None):
        self._data = dict(initial_data or {})
        self._lock = RLock()
        self._owners: dict[str, int] = {}
        self._transaction_counter = 0
        self.metrics = Metrics()

    def begin(self) -> Transaction:
        with self._lock:
            self._transaction_counter += 1
            self.metrics.transactions_started += 1

            return Transaction(
                transaction_id=self._transaction_counter,
                snapshot_timestamp=0
            )

    def _ensure_active(self, tx: Transaction) -> None:
        if tx.state != TransactionState.ACTIVE:
            raise TransactionClosed(
                f"Transaction {tx.transaction_id} is {tx.state.value}"
            )

    def _acquire(self, tx: Transaction, key: str) -> None:
        owner = self._owners.get(key)

        if owner is not None and owner != tx.transaction_id:
            self.metrics.lock_failures += 1
            raise LockUnavailable(
                f"Record {key} is locked by transaction {owner}"
            )

        self._owners[key] = tx.transaction_id
        tx.held_locks.add(key)

    def read(self, tx: Transaction, key: str) -> Any:
        with self._lock:
            self._ensure_active(tx)
            self._acquire(tx, key)

            self.metrics.reads += 1

            if key in tx.write_set:
                return tx.write_set[key]

            return self._data.get(key)

    def write(self, tx: Transaction, key: str, value: Any) -> None:
        with self._lock:
            self._ensure_active(tx)
            self._acquire(tx, key)

            tx.write_set[key] = value

    def _release(self, tx: Transaction) -> None:
        for key in tx.held_locks:
            if self._owners.get(key) == tx.transaction_id:
                del self._owners[key]

        tx.held_locks.clear()

    def commit(self, tx: Transaction) -> bool:
        with self._lock:
            self._ensure_active(tx)

            self._data.update(tx.write_set)
            self.metrics.writes += len(tx.write_set)

            tx.state = TransactionState.COMMITTED
            self.metrics.transactions_committed += 1

            self._release(tx)

            return True

    def rollback(self, tx: Transaction) -> None:
        with self._lock:
            self._ensure_active(tx)

            tx.write_set.clear()
            tx.state = TransactionState.ABORTED
            self.metrics.transactions_aborted += 1

            self._release(tx)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._data)


def run_mvcc_scenario() -> None:
    print("\n=== MVCC SCENARIO ===")

    store = MVCCStore({
        "account_A": 1000,
        "account_B": 500
    })

    tx1 = store.begin()
    tx2 = store.begin()

    print("Transaction 1 reads:", store.read(tx1, "account_A"))
    print("Transaction 2 reads:", store.read(tx2, "account_A"))

    store.write(tx1, "account_A", 900)
    store.write(tx2, "account_A", 800)

    print("Transaction 1 commit:", store.commit(tx1))
    print("Transaction 2 commit:", store.commit(tx2))

    # A new transaction sees the committed version.
    tx3 = store.begin()

    print("Latest account balance:", store.read(tx3, "account_A"))
    print("Historical versions:", store.history("account_A"))

    store.rollback(tx3)

    print("Metrics:", store.metrics)


def run_locking_scenario() -> None:
    print("\n=== PESSIMISTIC LOCKING SCENARIO ===")

    store = LockingStore({
        "inventory": 100
    })

    tx1 = store.begin()
    tx2 = store.begin()

    print("Transaction 1 reads:", store.read(tx1, "inventory"))

    try:
        store.read(tx2, "inventory")
    except LockUnavailable as error:
        print("Transaction 2 blocked:", error)

    store.write(tx1, "inventory", 90)
    store.commit(tx1)

    print("Transaction 1 committed.")

    # The second transaction can acquire the lock after release.
    print("Transaction 2 reads:", store.read(tx2, "inventory"))

    store.write(tx2, "inventory", 80)
    store.commit(tx2)

    print("Final inventory:", store.snapshot())
    print("Metrics:", store.metrics)


def run_rollback_scenario() -> None:
    print("\n=== ROLLBACK SCENARIO ===")

    store = MVCCStore({"balance": 500})

    tx = store.begin()
    store.write(tx, "balance", 100)

    store.rollback(tx)

    check = store.begin()
    print("Balance after rollback:", store.read(check, "balance"))
    store.rollback(check)


def evaluate_architecture(
    read_operations: int,
    write_operations: int,
    contention_level: float,
    long_transactions: bool
) -> dict:
    """
    Illustrative architectural scoring.

    Scores are comparative indicators, not measured benchmarks.
    """

    if read_operations < 0 or write_operations < 0:
        raise ValueError("Operation counts cannot be negative")

    if not 0 <= contention_level <= 1:
        raise ValueError("Contention must be between 0 and 1")

    total = read_operations + write_operations

    if total == 0:
        return {
            "mvcc_score": 0.0,
            "locking_score": 0.0,
            "recommendation": "No workload"
        }

    read_ratio = read_operations / total
    write_ratio = write_operations / total

    mvcc_score = (
        70 * read_ratio
        + 25 * (1 - contention_level)
        - 15 * write_ratio * contention_level
    )

    locking_score = (
        55 * write_ratio
        + 35 * contention_level
        + (10 if long_transactions else 0)
    )

    recommendation = (
        "Evaluate MVCC"
        if mvcc_score >= locking_score
        else "Evaluate pessimistic locking"
    )

    return {
        "mvcc_score": round(mvcc_score, 2),
        "locking_score": round(locking_score, 2),
        "recommendation": recommendation
    }


def main() -> None:
    run_mvcc_scenario()
    run_locking_scenario()
    run_rollback_scenario()

    print("\n=== ARCHITECTURAL EVALUATION ===")

    workloads = [
        {
            "name": "Read-heavy reporting",
            "reads": 9000,
            "writes": 1000,
            "contention": 0.1,
            "long_transactions": False
        },
        {
            "name": "Highly contested inventory",
            "reads": 3000,
            "writes": 7000,
            "contention": 0.9,
            "long_transactions": False
        },
        {
            "name": "Long-running business transactions",
            "reads": 6000,
            "writes": 4000,
            "contention": 0.7,
            "long_transactions": True
        }
    ]

    for workload in workloads:
        result = evaluate_architecture(
            workload["reads"],
            workload["writes"],
            workload["contention"],
            workload["long_transactions"]
        )

        print(workload["name"])
        print(result)

    # Basic executable correctness checks.
    assert evaluate_architecture(
        100, 0, 0.1, False
    )["recommendation"] == "Evaluate MVCC"

    store = MVCCStore({"x": 10})
    first = store.begin()
    second = store.begin()

    store.write(first, "x", 20)
    store.write(second, "x", 30)

    assert store.commit(first)
    assert not store.commit(second)

    print("\nAll correctness checks passed.")


if __name__ == "__main__":
    main()
