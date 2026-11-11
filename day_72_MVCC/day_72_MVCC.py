"""
MVCC: Multi-Version Concurrency Control
A self-contained transactional database simulation.

Demonstrates:
- Transaction snapshots and visibility rules
- Multiple row versions
- Read committed and repeatable read isolation
- Optimistic concurrency control
- Write-write conflict detection
- Transaction commit and rollback
- Snapshot isolation and write skew
- Vacuum and version cleanup
- Transaction history and debugging
- Concurrent transaction simulation
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("mvcc")


class IsolationLevel(Enum):
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


class TransactionState(Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class MVCCError(Exception):
    pass


class TransactionConflict(MVCCError):
    pass


class TransactionStateError(MVCCError):
    pass


class SerializationFailure(MVCCError):
    pass


@dataclass
class Version:
    value: Any
    xmin: int
    xmax: Optional[int] = None
    deleted: bool = False


@dataclass
class Transaction:
    transaction_id: int
    snapshot: frozenset[int]
    start_timestamp: int
    isolation: IsolationLevel
    state: TransactionState = TransactionState.ACTIVE
    writes: dict[str, Any] = field(default_factory=dict)
    read_keys: set[str] = field(default_factory=set)
    observed_versions: dict[str, Optional[int]] = field(
        default_factory=dict
    )


class MVCCDatabase:
    def __init__(self):
        self._versions: dict[str, list[Version]] = {}
        self._transactions: dict[int, Transaction] = {}
        self._committed: set[int] = set()
        self._active: set[int] = set()
        self._aborted: set[int] = set()

        self._next_transaction_id = 1
        self._clock = 0
        self._lock = threading.RLock()
        self._history: list[dict[str, Any]] = []

    def _tick(self) -> int:
        self._clock += 1
        return self._clock

    def _record(self, event: str, transaction_id: int, **details):
        self._history.append({
            "timestamp": self._clock,
            "event": event,
            "transaction_id": transaction_id,
            **details,
        })

    def begin(
        self,
        isolation: IsolationLevel = IsolationLevel.REPEATABLE_READ,
    ) -> Transaction:
        with self._lock:
            transaction_id = self._next_transaction_id
            self._next_transaction_id += 1

            timestamp = self._tick()

            # The snapshot records transactions already active.
            snapshot = frozenset(self._active)

            transaction = Transaction(
                transaction_id=transaction_id,
                snapshot=snapshot,
                start_timestamp=timestamp,
                isolation=isolation,
            )

            self._transactions[transaction_id] = transaction
            self._active.add(transaction_id)

            self._record(
                "BEGIN",
                transaction_id,
                isolation=isolation.value,
                snapshot=sorted(snapshot),
            )

            return transaction

    def _check_active(self, transaction: Transaction):
        if transaction.state != TransactionState.ACTIVE:
            raise TransactionStateError(
                f"Transaction {transaction.transaction_id} is "
                f"{transaction.state.value}"
            )

    def _visible(
        self,
        version: Version,
        transaction: Transaction,
    ) -> bool:
        """
        Determine whether a version is visible to a transaction.

        A version created by another transaction is visible only
        if its creator committed before the snapshot was taken.
        """

        creator = version.xmin

        if creator == transaction.transaction_id:
            creator_visible = True
        elif creator in transaction.snapshot:
            creator_visible = False
        else:
            creator_visible = creator in self._committed

        if not creator_visible:
            return False

        if version.xmax is None:
            return True

        deleter = version.xmax

        if deleter == transaction.transaction_id:
            return False

        # An uncommitted or snapshot-invisible deletion cannot
        # hide an older version.
        if deleter in transaction.snapshot:
            return True

        if deleter not in self._committed:
            return True

        return False

    def _visible_version(
        self,
        key: str,
        transaction: Transaction,
    ) -> Optional[Version]:
        versions = self._versions.get(key, [])

        for version in reversed(versions):
            if self._visible(version, transaction):
                if version.deleted:
                    return None
                return version

        return None

    def read(
        self,
        transaction: Transaction,
        key: str,
    ) -> Optional[Any]:
        with self._lock:
            self._check_active(transaction)

            if transaction.isolation == IsolationLevel.READ_COMMITTED:
                # Each statement receives a fresh snapshot.
                transaction.snapshot = frozenset(self._active)

            transaction.read_keys.add(key)

            version = self._visible_version(key, transaction)

            transaction.observed_versions.setdefault(
                key,
                version.xmin if version else None,
            )

            value = version.value if version else None

            self._record(
                "READ",
                transaction.transaction_id,
                key=key,
                value=value,
                version=version.xmin if version else None,
            )

            return value

    def write(
        self,
        transaction: Transaction,
        key: str,
        value: Any,
    ):
        with self._lock:
            self._check_active(transaction)

            if not key or not isinstance(key, str):
                raise ValueError("Key must be a non-empty string")

            if transaction.isolation == IsolationLevel.READ_COMMITTED:
                transaction.snapshot = frozenset(self._active)

            current = self._visible_version(key, transaction)

            transaction.observed_versions.setdefault(
                key,
                current.xmin if current else None,
            )

            transaction.writes[key] = value

            self._record(
                "WRITE_BUFFERED",
                transaction.transaction_id,
                key=key,
            )

    def delete(self, transaction: Transaction, key: str):
        with self._lock:
            self._check_active(transaction)

            if transaction.isolation == IsolationLevel.READ_COMMITTED:
                transaction.snapshot = frozenset(self._active)

            current = self._visible_version(key, transaction)

            if current is None:
                return

            transaction.observed_versions.setdefault(
                key,
                current.xmin,
            )

            transaction.writes[key] = None

            self._record(
                "DELETE_BUFFERED",
                transaction.transaction_id,
                key=key,
            )

    def _check_write_conflicts(self, transaction: Transaction):
        for key in transaction.writes:
            observed = transaction.observed_versions.get(key)

            latest = self._versions.get(key, [])

            if not latest:
                if observed is not None:
                    raise TransactionConflict(
                        f"Missing observed version for {key}"
                    )
                continue

            latest_version = latest[-1]

            if latest_version.xmin == transaction.transaction_id:
                continue

            # Another committed transaction changed the row
            # after this transaction's snapshot.
            if latest_version.xmin in self._committed:
                if latest_version.xmin not in transaction.snapshot:
                    if observed != latest_version.xmin:
                        raise TransactionConflict(
                            f"Concurrent modification detected: {key}"
                        )

            if latest_version.xmax is not None:
                deleter = latest_version.xmax
                if deleter in self._committed:
                    if deleter not in transaction.snapshot:
                        raise TransactionConflict(
                            f"Concurrent deletion detected: {key}"
                        )

    def _check_serializable(self, transaction: Transaction):
        """
        Basic optimistic validation.

        This implementation detects changed read dependencies.
        It is intentionally conservative and is not a complete
        SSI implementation of PostgreSQL predicate locking.
        """

        for key in transaction.read_keys:
            if key in transaction.writes:
                continue

            observed = transaction.observed_versions.get(key)
            latest = self._versions.get(key, [])

            committed_latest = next(
                (
                    v for v in reversed(latest)
                    if v.xmin in self._committed
                    and not v.deleted
                ),
                None,
            )

            current = (
                committed_latest.xmin
                if committed_latest
                else None
            )

            if current != observed:
                raise SerializationFailure(
                    f"Serializable validation failed for {key}"
                )

    def commit(self, transaction: Transaction):
        with self._lock:
            self._check_active(transaction)

            try:
                self._check_write_conflicts(transaction)

                if transaction.isolation == IsolationLevel.SERIALIZABLE:
                    self._check_serializable(transaction)

                commit_timestamp = self._tick()

                # Validate all writes before applying any of them.
                for key in transaction.writes:
                    versions = self._versions.get(key, [])

                    if versions:
                        latest = versions[-1]

                        if latest.xmin in self._committed:
                            latest.xmax = transaction.transaction_id

                for key, value in transaction.writes.items():
                    self._versions.setdefault(key, []).append(
                        Version(
                            value=value,
                            xmin=transaction.transaction_id,
                            deleted=value is None,
                        )
                    )

                transaction.state = TransactionState.COMMITTED
                self._committed.add(transaction.transaction_id)
                self._active.remove(transaction.transaction_id)

                self._record(
                    "COMMIT",
                    transaction.transaction_id,
                    commit_timestamp=commit_timestamp,
                    writes=len(transaction.writes),
                )

                logger.info(
                    "Transaction %s committed",
                    transaction.transaction_id,
                )

            except MVCCError:
                self.rollback(transaction)
                raise

    def rollback(self, transaction: Transaction):
        with self._lock:
            if transaction.state != TransactionState.ACTIVE:
                return

            transaction.state = TransactionState.ABORTED
            transaction.writes.clear()

            self._active.discard(transaction.transaction_id)
            self._aborted.add(transaction.transaction_id)

            self._tick()

            self._record(
                "ROLLBACK",
                transaction.transaction_id,
            )

    def vacuum(self):
        """
        Remove obsolete versions that cannot be visible to any
        active transaction.

        A production database must account for replication slots,
        exported snapshots, prepared transactions and other
        visibility horizons.
        """

        with self._lock:
            oldest_active = min(
                self._active,
                default=self._next_transaction_id,
            )

            removed = 0

            for key in list(self._versions):
                versions = self._versions[key]

                retained = []

                for index, version in enumerate(versions):
                    creator_aborted = version.xmin in self._aborted

                    deleted_before_horizon = (
                        version.xmax is not None
                        and version.xmax in self._committed
                        and version.xmax < oldest_active
                    )

                    if creator_aborted or deleted_before_horizon:
                        removed += 1
                    else:
                        retained.append(version)

                if retained:
                    self._versions[key] = retained
                else:
                    del self._versions[key]

            logger.info("Vacuum removed %s obsolete versions", removed)
            return removed

    def inspect(self, key: str) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "value": version.value,
                    "xmin": version.xmin,
                    "xmax": version.xmax,
                    "deleted": version.deleted,
                }
                for version in self._versions.get(key, [])
            ]

    def history(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._history)

    def export_history(self, filename: str = "mvcc_history.json"):
        path = Path(filename)

        # Restrict the output to a normal filename in the current
        # directory to avoid unintended path traversal.
        if path.name != filename or path.is_absolute():
            raise ValueError("Only a local filename is permitted")

        path.write_text(
            json.dumps(self.history(), indent=2, default=str),
            encoding="utf-8",
        )


def demonstrate_mvcc():
    database = MVCCDatabase()

    print("\n=== 1. Initial transaction ===")

    setup = database.begin()
    database.write(setup, "account:1001", 1000)
    database.write(setup, "account:1002", 500)
    database.commit(setup)

    print("\n=== 2. Snapshot isolation ===")

    reader = database.begin(IsolationLevel.REPEATABLE_READ)
    print("Reader initial balance:", database.read(reader, "account:1001"))

    writer = database.begin()
    database.write(writer, "account:1001", 1200)
    database.commit(writer)

    print(
        "Reader sees old balance:",
        database.read(reader, "account:1001"),
    )

    database.commit(reader)

    latest = database.begin()
    print("New transaction sees:", database.read(latest, "account:1001"))
    database.commit(latest)

    print("\n=== 3. Write-write conflict ===")

    first = database.begin()
    second = database.begin()

    database.write(first, "account:1002", 600)
    database.write(second, "account:1002", 700)

    database.commit(first)

    try:
        database.commit(second)
    except TransactionConflict as error:
        print("Expected conflict:", error)

    print("\n=== 4. Rollback ===")

    failed = database.begin()
    database.write(failed, "account:1001", 999999)
    database.rollback(failed)

    verification = database.begin()
    print("Balance after rollback:", database.read(
        verification, "account:1001"
    ))
    database.commit(verification)

    print("\n=== 5. Read committed ===")

    read_committed = database.begin(IsolationLevel.READ_COMMITTED)

    print("First read:", database.read(
        read_committed, "account:1001"
    ))

    updater = database.begin()
    database.write(updater, "account:1001", 1500)
    database.commit(updater)

    print("Second read:", database.read(
        read_committed, "account:1001"
    ))

    database.commit(read_committed)

    print("\n=== 6. Version inspection ===")

    print(json.dumps(
        database.inspect("account:1001"),
        indent=2,
    ))

    print("\n=== 7. Serializable validation ===")

    serial = database.begin(IsolationLevel.SERIALIZABLE)
    print("Observed:", database.read(serial, "account:1001"))

    concurrent = database.begin()
    database.write(concurrent, "account:1001", 1700)
    database.commit(concurrent)

    try:
        database.commit(serial)
    except SerializationFailure as error:
        print("Serialization failure:", error)

    print("\n=== 8. Vacuum ===")
    print("Removed versions:", database.vacuum())

    print("\n=== 9. Transaction history ===")
    for event in database.history():
        print(event)


if __name__ == "__main__":
    demonstrate_mvcc()
