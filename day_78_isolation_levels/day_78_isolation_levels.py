#!/usr/bin/env python3
"""
Database Transaction Isolation Levels
=====================================

Implements and demonstrates:
1. Read Uncommitted
2. Read Committed
3. Repeatable Read
4. Serializable

Includes a versioned in-memory transaction engine, transaction states,
concurrency anomalies, conflict detection, rollback, commit validation,
and executable assertions.

The simulator illustrates standard isolation concepts. PostgreSQL uses
MVCC and treats READ UNCOMMITTED as READ COMMITTED.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class IsolationLevel(Enum):
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


class TransactionState(Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class TransactionError(Exception):
    pass


class DirtyReadError(TransactionError):
    pass


class SerializationError(TransactionError):
    pass


class WriteConflictError(TransactionError):
    pass


@dataclass
class Version:
    value: Any
    transaction_id: int
    committed: bool
    version_number: int


@dataclass
class Transaction:
    transaction_id: int
    isolation: IsolationLevel
    state: TransactionState = TransactionState.ACTIVE
    snapshot: dict[str, Version] = field(default_factory=dict)
    writes: dict[str, Any] = field(default_factory=dict)
    read_versions: dict[str, int] = field(default_factory=dict)
    write_versions: dict[str, int] = field(default_factory=dict)

    def ensure_active(self) -> None:
        if self.state != TransactionState.ACTIVE:
            raise TransactionError(
                f"Transaction {self.transaction_id} is {self.state.value}"
            )


class Database:
    """
    Small versioned database used to demonstrate transaction behavior.

    Read Committed obtains a fresh committed view for every statement.
    Repeatable Read and Serializable retain a transaction snapshot.
    Uncommitted writes are tracked separately from committed data.
    """

    def __init__(self, initial_data: Optional[dict[str, Any]] = None):
        self.version_counter = 0
        self.transaction_counter = 0
        self.data: dict[str, Version] = {}
        self.transactions: dict[int, Transaction] = {}
        self.uncommitted: dict[str, dict[int, Any]] = {}
        self.commit_history: list[dict[str, Any]] = []

        for key, value in (initial_data or {}).items():
            self.version_counter += 1
            self.data[key] = Version(
                value, 0, True, self.version_counter
            )

    def begin(self, isolation: IsolationLevel) -> Transaction:
        self.transaction_counter += 1

        snapshot = deepcopy(self.data)

        transaction = Transaction(
            transaction_id=self.transaction_counter,
            isolation=isolation,
            snapshot=snapshot,
        )

        self.transactions[transaction.transaction_id] = transaction
        return transaction

    def _current_view(self, transaction: Transaction) -> dict[str, Version]:
        transaction.ensure_active()

        if transaction.isolation in (
            IsolationLevel.REPEATABLE_READ,
            IsolationLevel.SERIALIZABLE,
        ):
            return transaction.snapshot

        return self.data

    def read(self, transaction: Transaction, key: str) -> Any:
        transaction.ensure_active()

        if key in transaction.writes:
            return transaction.writes[key]

        if transaction.isolation == IsolationLevel.READ_UNCOMMITTED:
            # This is a deliberate simulator behavior. Real PostgreSQL
            # does not expose another transaction's uncommitted writes.
            for owner_id, pending in self.uncommitted.items():
                if owner_id != transaction.transaction_id and key in pending:
                    return pending[key]

        view = self._current_view(transaction)

        if key not in view:
            raise KeyError(f"Unknown database key: {key}")

        version = view[key]

        transaction.read_versions.setdefault(
            key, version.version_number
        )

        return version.value

    def write(self, transaction: Transaction, key: str, value: Any) -> None:
        transaction.ensure_active()

        if key not in self.data:
            raise KeyError(f"Unknown database key: {key}")

        transaction.writes[key] = value

        self.uncommitted.setdefault(
            transaction.transaction_id, {}
        )[key] = value

        if key not in transaction.write_versions:
            transaction.write_versions[key] = self.data[key].version_number

    def commit(self, transaction: Transaction) -> None:
        transaction.ensure_active()

        # Detect concurrent updates to the same rows.
        for key, original_version in transaction.write_versions.items():
            current_version = self.data[key].version_number

            if current_version != original_version:
                self.rollback(transaction)
                raise WriteConflictError(
                    f"Concurrent update detected for key '{key}'"
                )

        # Serializable additionally validates that values read by this
        # transaction have not changed since its snapshot.
        if transaction.isolation == IsolationLevel.SERIALIZABLE:
            for key, original_version in transaction.read_versions.items():
                if key in transaction.writes:
                    continue

                if self.data[key].version_number != original_version:
                    self.rollback(transaction)
                    raise SerializationError(
                        f"Serialization conflict on '{key}'"
                    )

        # Publish writes atomically within this simulator.
        for key, value in transaction.writes.items():
            self.version_counter += 1

            self.data[key] = Version(
                value=value,
                transaction_id=transaction.transaction_id,
                committed=True,
                version_number=self.version_counter,
            )

        transaction.state = TransactionState.COMMITTED
        self.uncommitted.pop(transaction.transaction_id, None)

        self.commit_history.append({
            "transaction_id": transaction.transaction_id,
            "isolation": transaction.isolation.value,
            "writes": deepcopy(transaction.writes),
        })

    def rollback(self, transaction: Transaction) -> None:
        transaction.ensure_active()

        transaction.writes.clear()
        transaction.state = TransactionState.ABORTED
        self.uncommitted.pop(transaction.transaction_id, None)

    def inspect(self) -> dict[str, Any]:
        return {
            key: version.value
            for key, version in self.data.items()
        }


def demonstrate_dirty_read() -> None:
    print("\n1. DIRTY READ")

    db = Database({"balance": 1000})

    writer = db.begin(IsolationLevel.READ_COMMITTED)
    reader = db.begin(IsolationLevel.READ_UNCOMMITTED)

    db.write(writer, "balance", 500)

    print("Reader observes uncommitted balance:",
          db.read(reader, "balance"))

    db.rollback(writer)

    print("Reader after writer rollback:",
          db.read(reader, "balance"))

    db.rollback(reader)

    assert db.inspect()["balance"] == 1000


def demonstrate_non_repeatable_read() -> None:
    print("\n2. NON-REPEATABLE READ")

    db = Database({"balance": 1000})

    reader = db.begin(IsolationLevel.READ_COMMITTED)
    writer = db.begin(IsolationLevel.READ_COMMITTED)

    first_read = db.read(reader, "balance")

    db.write(writer, "balance", 800)
    db.commit(writer)

    second_read = db.read(reader, "balance")

    print("First read:", first_read)
    print("Second read:", second_read)

    assert first_read != second_read

    db.rollback(reader)


def demonstrate_repeatable_read() -> None:
    print("\n3. REPEATABLE READ")

    db = Database({"balance": 1000})

    reader = db.begin(IsolationLevel.REPEATABLE_READ)
    writer = db.begin(IsolationLevel.READ_COMMITTED)

    first_read = db.read(reader, "balance")

    db.write(writer, "balance", 700)
    db.commit(writer)

    second_read = db.read(reader, "balance")

    print("First read:", first_read)
    print("Second read:", second_read)

    assert first_read == second_read
    assert db.inspect()["balance"] == 700

    db.commit(reader)


def demonstrate_write_conflict() -> None:
    print("\n4. CONCURRENT WRITE CONFLICT")

    db = Database({"stock": 50})

    first = db.begin(IsolationLevel.REPEATABLE_READ)
    second = db.begin(IsolationLevel.REPEATABLE_READ)

    db.write(first, "stock", 40)
    db.write(second, "stock", 30)

    db.commit(first)

    try:
        db.commit(second)
    except WriteConflictError as error:
        print("Expected conflict:", error)

    assert db.inspect()["stock"] == 40
    assert second.state == TransactionState.ABORTED


def demonstrate_serializable() -> None:
    print("\n5. SERIALIZABLE TRANSACTION")

    db = Database({
        "account_a": 1000,
        "account_b": 1000,
    })

    first = db.begin(IsolationLevel.SERIALIZABLE)
    second = db.begin(IsolationLevel.READ_COMMITTED)

    initial_balance = db.read(first, "account_a")

    db.write(second, "account_a", 900)
    db.commit(second)

    # The serializable transaction still sees its original snapshot.
    assert db.read(first, "account_a") == initial_balance

    try:
        db.commit(first)
        print("Read-only transaction committed.")
    except SerializationError as error:
        print("Serialization failure:", error)

    # A write based on stale data must not silently overwrite a newer value.
    third = db.begin(IsolationLevel.SERIALIZABLE)
    stale_balance = db.read(third, "account_a")

    fourth = db.begin(IsolationLevel.READ_COMMITTED)
    db.write(fourth, "account_a", 750)
    db.commit(fourth)

    db.write(third, "account_b", stale_balance)

    try:
        db.commit(third)
    except SerializationError as error:
        print("Expected serialization failure:", error)


def demonstrate_isolation_comparison() -> None:
    print("\n6. ISOLATION LEVEL COMPARISON")

    for level in IsolationLevel:
        print(f"{level.value:20} | ", end="")

        if level == IsolationLevel.READ_UNCOMMITTED:
            print("May expose dirty reads in systems that support them")
        elif level == IsolationLevel.READ_COMMITTED:
            print("Fresh committed snapshot for each statement")
        elif level == IsolationLevel.REPEATABLE_READ:
            print("Stable transaction snapshot")
        else:
            print("Serializable execution with conflict detection")


def demonstrate_transfer() -> None:
    print("\n7. ATOMIC BANK TRANSFER")

    db = Database({
        "alice": 5000,
        "bob": 3000,
    })

    transaction = db.begin(IsolationLevel.SERIALIZABLE)

    amount = 1000
    alice_balance = db.read(transaction, "alice")

    if amount <= 0:
        raise ValueError("Transfer amount must be positive")

    if alice_balance < amount:
        db.rollback(transaction)
        raise TransactionError("Insufficient funds")

    bob_balance = db.read(transaction, "bob")

    db.write(transaction, "alice", alice_balance - amount)
    db.write(transaction, "bob", bob_balance + amount)

    db.commit(transaction)

    result = db.inspect()

    print("Final balances:", result)

    assert result["alice"] == 4000
    assert result["bob"] == 4000
    assert sum(result.values()) == 8000


def run_tests() -> None:
    # Verify isolation and transaction state behavior.
    db = Database({"counter": 10})

    transaction = db.begin(IsolationLevel.READ_COMMITTED)
    db.write(transaction, "counter", 20)
    db.rollback(transaction)

    assert db.inspect()["counter"] == 10

    try:
        db.read(transaction, "counter")
        raise AssertionError("Aborted transaction should reject reads")
    except TransactionError:
        pass

    assert len(db.commit_history) == 0

    print("\nAll assertions passed.")


def main() -> None:
    print("=" * 65)
    print("DATABASE TRANSACTION ISOLATION LABORATORY")
    print("=" * 65)

    demonstrate_dirty_read()
    demonstrate_non_repeatable_read()
    demonstrate_repeatable_read()
    demonstrate_write_conflict()
    demonstrate_serializable()
    demonstrate_isolation_comparison()
    demonstrate_transfer()
    run_tests()

    print("\nFinal database transaction demonstrations completed.")


if __name__ == "__main__":
    main()
