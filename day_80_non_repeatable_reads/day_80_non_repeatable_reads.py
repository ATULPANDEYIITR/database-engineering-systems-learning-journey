#!/usr/bin/env python3
"""
NON-REPEATABLE READS: CONCURRENCY BEHAVIOR AND ISOLATION

A self-contained transaction simulator demonstrating:
- Non-repeatable reads under READ COMMITTED.
- Stable snapshots under REPEATABLE READ.
- Serialization failures under SERIALIZABLE.
- Transaction commit and rollback.
- Concurrent updates and optimistic version checks.
- Deterministic interleaving of concurrent transactions.

Run: python non_repeatable_reads.py
"""

from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy
from typing import Any
import threading
import time


class IsolationLevel(Enum):
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


class TransactionState(Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


class DatabaseError(Exception):
    pass


class SerializationFailure(DatabaseError):
    pass


class ConcurrentModification(DatabaseError):
    pass


class TransactionError(DatabaseError):
    pass


@dataclass
class Record:
    record_id: int
    balance: float
    version: int = 1


@dataclass
class Transaction:
    transaction_id: str
    isolation: IsolationLevel
    state: TransactionState = TransactionState.ACTIVE
    snapshot: dict[int, Record] = field(default_factory=dict)
    writes: dict[int, Record] = field(default_factory=dict)
    read_versions: dict[int, int] = field(default_factory=dict)


class Database:
    def __init__(self):
        self.records: dict[int, Record] = {
            1: Record(1, 1000.0),
            2: Record(2, 2000.0),
        }
        self.lock = threading.RLock()
        self.transactions: dict[str, Transaction] = {}

    def begin(
        self,
        transaction_id: str,
        isolation: IsolationLevel
    ) -> Transaction:
        with self.lock:
            if transaction_id in self.transactions:
                raise TransactionError("Duplicate transaction identifier.")

            snapshot = deepcopy(self.records)
            tx = Transaction(
                transaction_id=transaction_id,
                isolation=isolation,
                snapshot=snapshot
            )
            self.transactions[transaction_id] = tx
            print(f"[BEGIN] {transaction_id}: {isolation.value}")
            return tx

    def _validate_active(self, tx: Transaction):
        if tx.state != TransactionState.ACTIVE:
            raise TransactionError(
                f"Transaction {tx.transaction_id} is not active."
            )

    def read(self, tx: Transaction, record_id: int) -> Record:
        with self.lock:
            self._validate_active(tx)

            if record_id not in self.records:
                raise DatabaseError(f"Record {record_id} does not exist.")

            # READ COMMITTED obtains the latest committed value
            # for each individual statement.
            if tx.isolation in (
                IsolationLevel.READ_COMMITTED,
                IsolationLevel.READ_UNCOMMITTED
            ):
                current = deepcopy(self.records[record_id])
            else:
                # REPEATABLE READ and SERIALIZABLE retain their
                # transaction-start snapshot.
                current = deepcopy(tx.snapshot[record_id])

            if record_id in tx.writes:
                current = deepcopy(tx.writes[record_id])

            tx.read_versions.setdefault(record_id, current.version)

            print(
                f"[READ] {tx.transaction_id} | "
                f"Account {record_id} | "
                f"Balance: {current.balance:.2f} | "
                f"Version: {current.version}"
            )
            return current

    def write(
        self,
        tx: Transaction,
        record_id: int,
        new_balance: float
    ):
        with self.lock:
            self._validate_active(tx)

            if record_id not in self.records:
                raise DatabaseError("Unknown account.")

            if new_balance < 0:
                raise DatabaseError("Balance cannot be negative.")

            base = tx.writes.get(
                record_id,
                tx.snapshot[record_id]
            )

            tx.writes[record_id] = Record(
                record_id,
                new_balance,
                base.version
            )

            print(
                f"[WRITE] {tx.transaction_id} | "
                f"Account {record_id} | {new_balance:.2f}"
            )

    def commit(self, tx: Transaction):
        with self.lock:
            self._validate_active(tx)

            # A concurrent modification invalidates a snapshot write.
            for record_id, pending in tx.writes.items():
                current = self.records[record_id]
                expected = pending.version

                if current.version != expected:
                    tx.state = TransactionState.FAILED
                    raise ConcurrentModification(
                        f"Account {record_id} changed from version "
                        f"{expected} to {current.version}."
                    )

            # SERIALIZABLE additionally validates the read set.
            if tx.isolation == IsolationLevel.SERIALIZABLE:
                for record_id, expected in tx.read_versions.items():
                    current = self.records[record_id]

                    if current.version != expected:
                        tx.state = TransactionState.FAILED
                        raise SerializationFailure(
                            f"Serialization conflict on account {record_id}."
                        )

            for record_id, pending in tx.writes.items():
                self.records[record_id] = Record(
                    record_id,
                    pending.balance,
                    self.records[record_id].version + 1
                )

            tx.state = TransactionState.COMMITTED
            print(f"[COMMIT] {tx.transaction_id}")

    def rollback(self, tx: Transaction):
        with self.lock:
            self._validate_active(tx)
            tx.writes.clear()
            tx.state = TransactionState.ROLLED_BACK
            print(f"[ROLLBACK] {tx.transaction_id}")

    def show(self):
        with self.lock:
            print("\nCURRENT DATABASE STATE")
            for record in self.records.values():
                print(
                    f"Account {record.record_id}: "
                    f"{record.balance:.2f}, "
                    f"version={record.version}"
                )


def demonstrate_non_repeatable_read():
    print("\n" + "=" * 65)
    print("EXPERIMENT 1: NON-REPEATABLE READ")
    print("=" * 65)

    db = Database()

    reader = db.begin("T1", IsolationLevel.READ_COMMITTED)
    writer = db.begin("T2", IsolationLevel.READ_COMMITTED)

    first = db.read(reader, 1)

    db.write(writer, 1, 1500.0)
    db.commit(writer)

    second = db.read(reader, 1)

    print("\nRESULT")
    print(f"First read:  {first.balance:.2f}")
    print(f"Second read: {second.balance:.2f}")
    print(f"Non-repeatable read: {first.balance != second.balance}")

    db.commit(reader)
    db.show()


def demonstrate_repeatable_read():
    print("\n" + "=" * 65)
    print("EXPERIMENT 2: REPEATABLE READ")
    print("=" * 65)

    db = Database()

    reader = db.begin("T3", IsolationLevel.REPEATABLE_READ)
    writer = db.begin("T4", IsolationLevel.READ_COMMITTED)

    first = db.read(reader, 1)

    db.write(writer, 1, 1800.0)
    db.commit(writer)

    second = db.read(reader, 1)

    print("\nRESULT")
    print(f"First read:  {first.balance:.2f}")
    print(f"Second read: {second.balance:.2f}")
    print(f"Stable snapshot: {first.balance == second.balance}")

    db.commit(reader)
    db.show()


def demonstrate_serialization_failure():
    print("\n" + "=" * 65)
    print("EXPERIMENT 3: SERIALIZATION CONFLICT")
    print("=" * 65)

    db = Database()

    tx1 = db.begin("T5", IsolationLevel.SERIALIZABLE)
    tx2 = db.begin("T6", IsolationLevel.READ_COMMITTED)

    original = db.read(tx1, 1)
    db.read(tx2, 1)

    db.write(tx2, 1, 2500.0)
    db.commit(tx2)

    try:
        db.read(tx1, 1)
        db.commit(tx1)
    except (SerializationFailure, ConcurrentModification) as exc:
        print(f"[CONFLICT] {exc}")

    db.show()


def demonstrate_optimistic_concurrency():
    print("\n" + "=" * 65)
    print("EXPERIMENT 4: OPTIMISTIC VERSION CONTROL")
    print("=" * 65)

    db = Database()

    first = db.begin("T7", IsolationLevel.REPEATABLE_READ)
    second = db.begin("T8", IsolationLevel.REPEATABLE_READ)

    account_a = db.read(first, 1)
    account_b = db.read(second, 1)

    db.write(first, 1, account_a.balance + 100)
    db.commit(first)

    db.write(second, 1, account_b.balance + 200)

    try:
        db.commit(second)
    except ConcurrentModification as exc:
        print(f"[REJECTED] {exc}")

    db.show()


def demonstrate_rollback():
    print("\n" + "=" * 65)
    print("EXPERIMENT 5: ATOMIC ROLLBACK")
    print("=" * 65)

    db = Database()
    tx = db.begin("T9", IsolationLevel.READ_COMMITTED)

    db.write(tx, 1, 500.0)
    db.rollback(tx)

    db.show()


def demonstrate_threaded_updates():
    print("\n" + "=" * 65)
    print("EXPERIMENT 6: THREAD-SAFE DATABASE ACCESS")
    print("=" * 65)

    db = Database()
    iterations = 100
    amount = 1.0

    def deposit():
        for _ in range(iterations):
            with db.lock:
                db.records[1].balance += amount
                db.records[1].version += 1

    threads = [
        threading.Thread(target=deposit)
        for _ in range(4)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    expected = 1000.0 + 4 * iterations * amount

    print(f"Expected balance: {expected:.2f}")
    print(f"Actual balance:   {db.records[1].balance:.2f}")

    assert db.records[1].balance == expected


def main():
    demonstrate_non_repeatable_read()
    demonstrate_repeatable_read()
    demonstrate_serialization_failure()
    demonstrate_optimistic_concurrency()
    demonstrate_rollback()
    demonstrate_threaded_updates()

    print("\nALL EXPERIMENTS COMPLETED.")


if __name__ == "__main__":
    main()
