#!/usr/bin/env python3
"""
Optimistic Concurrency Control: Versioning and Conflict Detection

Demonstrates:
- Version-based optimistic locking
- Read, modify, and compare-and-swap operations
- Lost-update prevention
- Concurrent transaction simulation
- Automatic retries with bounded exponential backoff
- Conflict detection and resolution
- Atomic multi-record updates
- Audit logging
- Thread-safe in-memory storage
- Unit-style assertions

Run:
    python optimistic_concurrency.py
"""

from __future__ import annotations

import logging
import random
import threading
import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("optimistic_concurrency")


# ---------------------------------------------------------
# Exceptions
# ---------------------------------------------------------

class ConcurrencyError(Exception):
    """Base concurrency exception."""


class VersionConflictError(ConcurrencyError):
    """Raised when the stored version differs from the expected version."""

    def __init__(
        self,
        record_id: str,
        expected: int,
        actual: int,
    ):
        self.record_id = record_id
        self.expected = expected
        self.actual = actual

        super().__init__(
            f"Version conflict for {record_id}: "
            f"expected {expected}, actual {actual}"
        )


class RecordNotFoundError(Exception):
    """Raised when a record does not exist."""


class ValidationError(Exception):
    """Raised when record data is invalid."""


class RetryExhaustedError(Exception):
    """Raised when all concurrency retries fail."""


# ---------------------------------------------------------
# Domain models
# ---------------------------------------------------------

class TransactionStatus(Enum):
    PENDING = "PENDING"
    COMMITTED = "COMMITTED"
    CONFLICTED = "CONFLICTED"
    ABORTED = "ABORTED"


@dataclass(frozen=True)
class Snapshot:
    record_id: str
    data: dict[str, Any]
    version: int
    updated_at: float


@dataclass
class AuditEvent:
    record_id: str
    old_version: int
    new_version: int
    operation: str
    timestamp: float
    transaction_id: str


@dataclass
class Transaction:
    transaction_id: str
    status: TransactionStatus = TransactionStatus.PENDING
    attempts: int = 0


@dataclass
class StoredRecord:
    data: dict[str, Any]
    version: int = 1
    updated_at: float = field(default_factory=time.time)


# ---------------------------------------------------------
# Validation
# ---------------------------------------------------------

def validate_data(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValidationError("Record must be a dictionary.")

    if "balance" in data:
        balance = data["balance"]

        if isinstance(balance, bool) or not isinstance(balance, (int, float)):
            raise ValidationError("Balance must be numeric.")

        if balance < 0:
            raise ValidationError("Balance cannot be negative.")

        if isinstance(balance, float):
            if not float("-inf") < balance < float("inf"):
                raise ValidationError("Balance must be finite.")


# ---------------------------------------------------------
# Optimistic concurrency repository
# ---------------------------------------------------------

class VersionedRepository:

    def __init__(self):
        self._records: dict[str, StoredRecord] = {}
        self._lock = threading.RLock()
        self._audit: list[AuditEvent] = []

    def create(
        self,
        record_id: str,
        data: dict[str, Any],
    ) -> Snapshot:

        if not record_id:
            raise ValidationError("Record ID cannot be empty.")

        validate_data(data)

        with self._lock:
            if record_id in self._records:
                raise ValidationError("Record already exists.")

            record = StoredRecord(data=dict(data))
            self._records[record_id] = record

            return self._snapshot(record_id, record)

    def _snapshot(
        self,
        record_id: str,
        record: StoredRecord,
    ) -> Snapshot:

        return Snapshot(
            record_id=record_id,
            data=dict(record.data),
            version=record.version,
            updated_at=record.updated_at,
        )

    def read(self, record_id: str) -> Snapshot:

        with self._lock:
            record = self._records.get(record_id)

            if record is None:
                raise RecordNotFoundError(record_id)

            return self._snapshot(record_id, record)

    def compare_and_swap(
        self,
        record_id: str,
        expected_version: int,
        new_data: dict[str, Any],
        transaction_id: str,
    ) -> Snapshot:

        validate_data(new_data)

        if expected_version < 1:
            raise ValidationError("Expected version must be positive.")

        # Version comparison and update happen under one lock.
        # This is the atomic compare-and-swap operation.
        with self._lock:

            record = self._records.get(record_id)

            if record is None:
                raise RecordNotFoundError(record_id)

            if record.version != expected_version:
                raise VersionConflictError(
                    record_id,
                    expected_version,
                    record.version,
                )

            old_version = record.version

            record.data = dict(new_data)
            record.version += 1
            record.updated_at = time.time()

            self._audit.append(
                AuditEvent(
                    record_id=record_id,
                    old_version=old_version,
                    new_version=record.version,
                    operation="UPDATE",
                    timestamp=record.updated_at,
                    transaction_id=transaction_id,
                )
            )

            return self._snapshot(record_id, record)

    def audit_log(self) -> list[AuditEvent]:

        with self._lock:
            return list(self._audit)

    def update_with_retry(
        self,
        record_id: str,
        operation: Callable[[dict[str, Any]], dict[str, Any]],
        max_attempts: int = 5,
        base_delay: float = 0.01,
    ) -> Snapshot:

        if max_attempts < 1:
            raise ValidationError("At least one attempt is required.")

        transaction = Transaction(
            transaction_id=f"TX-{random.getrandbits(64):016X}"
        )

        for attempt in range(max_attempts):

            transaction.attempts += 1

            snapshot = self.read(record_id)

            # Business logic executes outside the repository lock.
            updated_data = operation(dict(snapshot.data))

            try:
                result = self.compare_and_swap(
                    record_id=record_id,
                    expected_version=snapshot.version,
                    new_data=updated_data,
                    transaction_id=transaction.transaction_id,
                )

                transaction.status = TransactionStatus.COMMITTED

                logger.info(
                    "%s committed at version %d after %d attempt(s)",
                    transaction.transaction_id,
                    result.version,
                    transaction.attempts,
                )

                return result

            except VersionConflictError as error:

                transaction.status = TransactionStatus.CONFLICTED

                logger.warning("%s", error)

                if attempt == max_attempts - 1:
                    transaction.status = TransactionStatus.ABORTED

                    raise RetryExhaustedError(
                        f"Transaction {transaction.transaction_id} "
                        f"failed after {max_attempts} attempts."
                    ) from error

                # Jitter prevents repeated clients from retrying together.
                delay = base_delay * (2 ** attempt)
                delay *= random.uniform(0.5, 1.5)

                time.sleep(delay)

        raise RetryExhaustedError("Transaction failed.")

    def transfer(
        self,
        source_id: str,
        destination_id: str,
        amount: float,
        max_attempts: int = 5,
    ) -> tuple[Snapshot, Snapshot]:

        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValidationError("Transfer amount must be numeric.")

        if amount <= 0 or amount == float("inf") or amount != amount:
            raise ValidationError("Transfer amount must be positive and finite.")

        if source_id == destination_id:
            raise ValidationError("Source and destination must differ.")

        transaction_id = f"TRANSFER-{random.getrandbits(64):016X}"

        for attempt in range(max_attempts):

            # Read both records and retain their original versions.
            with self._lock:
                source = self._records.get(source_id)
                destination = self._records.get(destination_id)

                if source is None:
                    raise RecordNotFoundError(source_id)

                if destination is None:
                    raise RecordNotFoundError(destination_id)

                source_snapshot = self._snapshot(source_id, source)
                destination_snapshot = self._snapshot(
                    destination_id,
                    destination,
                )

            source_data = dict(source_snapshot.data)
            destination_data = dict(destination_snapshot.data)

            if source_data.get("balance", 0) < amount:
                raise ValidationError("Insufficient funds.")

            source_data["balance"] -= amount
            destination_data["balance"] = (
                destination_data.get("balance", 0) + amount
            )

            validate_data(source_data)
            validate_data(destination_data)

            # Both version checks and updates must be atomic.
            with self._lock:

                current_source = self._records[source_id]
                current_destination = self._records[destination_id]

                if (
                    current_source.version != source_snapshot.version
                    or current_destination.version != destination_snapshot.version
                ):
                    logger.warning(
                        "Transfer conflict on attempt %d",
                        attempt + 1,
                    )

                else:
                    old_source_version = current_source.version
                    old_destination_version = current_destination.version

                    current_source.data = source_data
                    current_destination.data = destination_data

                    current_source.version += 1
                    current_destination.version += 1

                    current_source.updated_at = time.time()
                    current_destination.updated_at = time.time()

                    self._audit.extend([
                        AuditEvent(
                            source_id,
                            old_source_version,
                            current_source.version,
                            "TRANSFER_DEBIT",
                            current_source.updated_at,
                            transaction_id,
                        ),
                        AuditEvent(
                            destination_id,
                            old_destination_version,
                            current_destination.version,
                            "TRANSFER_CREDIT",
                            current_destination.updated_at,
                            transaction_id,
                        ),
                    ])

                    return (
                        self._snapshot(source_id, current_source),
                        self._snapshot(destination_id, current_destination),
                    )

            if attempt < max_attempts - 1:
                time.sleep(0.01 * (2 ** attempt))

        raise RetryExhaustedError("Atomic transfer retries exhausted.")


# ---------------------------------------------------------
# Demonstration
# ---------------------------------------------------------

def demonstrate_basic_conflict(repository: VersionedRepository):

    print("\n1. Basic version conflict")

    first_reader = repository.read("ACCOUNT-100")
    second_reader = repository.read("ACCOUNT-100")

    repository.compare_and_swap(
        "ACCOUNT-100",
        first_reader.version,
        {"balance": 1200},
        "TX-FIRST",
    )

    try:
        repository.compare_and_swap(
            "ACCOUNT-100",
            second_reader.version,
            {"balance": 1500},
            "TX-SECOND",
        )

    except VersionConflictError as error:
        print("Conflict detected:", error)

    print("Current state:", repository.read("ACCOUNT-100"))


def demonstrate_concurrent_updates(repository: VersionedRepository):

    print("\n2. Concurrent updates")

    repository.create("COUNTER", {"balance": 0})

    def increment():
        repository.update_with_retry(
            "COUNTER",
            lambda data: {
                "balance": data["balance"] + 1
            },
            max_attempts=30,
        )

    threads = [
        threading.Thread(target=increment)
        for _ in range(20)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    result = repository.read("COUNTER")

    print("Expected balance: 20")
    print("Actual balance:", result.data["balance"])
    print("Version:", result.version)

    assert result.data["balance"] == 20


def demonstrate_atomic_transfer(repository: VersionedRepository):

    print("\n3. Atomic multi-record transfer")

    repository.create("SENDER", {"balance": 5000})
    repository.create("RECEIVER", {"balance": 1000})

    sender, receiver = repository.transfer(
        "SENDER",
        "RECEIVER",
        750,
    )

    print("Sender:", sender.data)
    print("Receiver:", receiver.data)

    assert sender.data["balance"] == 4250
    assert receiver.data["balance"] == 1750


def demonstrate_validation(repository: VersionedRepository):

    print("\n4. Validation and failure handling")

    try:
        repository.update_with_retry(
            "ACCOUNT-100",
            lambda data: {"balance": -100},
        )

    except ValidationError as error:
        print("Validation rejected:", error)

    try:
        repository.transfer(
            "SENDER",
            "RECEIVER",
            100000,
        )

    except ValidationError as error:
        print("Transfer rejected:", error)


def demonstrate_audit(repository: VersionedRepository):

    print("\n5. Audit history")

    for event in repository.audit_log():
        print(
            f"{event.transaction_id}: "
            f"{event.record_id}, "
            f"{event.old_version} -> {event.new_version}, "
            f"{event.operation}"
        )


def main():

    repository = VersionedRepository()

    repository.create(
        "ACCOUNT-100",
        {"balance": 1000},
    )

    demonstrate_basic_conflict(repository)
    demonstrate_concurrent_updates(repository)
    demonstrate_atomic_transfer(repository)
    demonstrate_validation(repository)
    demonstrate_audit(repository)

    print("\nAll concurrency demonstrations completed.")


if __name__ == "__main__":
    main()
