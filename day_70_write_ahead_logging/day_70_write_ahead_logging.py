#!/usr/bin/env python3
"""
Write-Ahead Logging (WAL): Durability and Crash Recovery

Demonstrates:
- Append-only transaction logging
- Log sequence numbers (LSNs)
- Write-ahead rule
- Transaction commit records
- Checkpoints
- Crash recovery using REDO and UNDO
- Torn-record detection using CRC32
- Idempotent recovery
- Durable file persistence
- Recovery validation and failure handling

Run: python wal_recovery.py
Python: 3.10+
"""

from __future__ import annotations

import json
import os
import tempfile
import zlib
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any


class RecordType(str, Enum):
    BEGIN = "BEGIN"
    UPDATE = "UPDATE"
    COMMIT = "COMMIT"
    ABORT = "ABORT"
    CHECKPOINT = "CHECKPOINT"


class WALError(Exception):
    """Base exception for WAL operations."""


class CorruptLogError(WALError):
    """Raised when a complete WAL record fails validation."""


class DurabilityError(WALError):
    """Raised when a required persistence operation fails."""


@dataclass(frozen=True)
class WALRecord:
    lsn: int
    transaction_id: int
    record_type: RecordType
    key: str | None
    old_value: int | None
    new_value: int | None
    checksum: int

    @staticmethod
    def calculate_checksum(payload: dict[str, Any]) -> int:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return zlib.crc32(encoded) & 0xFFFFFFFF

    @classmethod
    def create(
        cls,
        lsn: int,
        transaction_id: int,
        record_type: RecordType,
        key: str | None = None,
        old_value: int | None = None,
        new_value: int | None = None,
    ) -> WALRecord:
        payload = {
            "lsn": lsn,
            "transaction_id": transaction_id,
            "record_type": record_type.value,
            "key": key,
            "old_value": old_value,
            "new_value": new_value,
        }
        return cls(
            **payload,
            record_type=record_type,
            checksum=cls.calculate_checksum(payload),
        )

    def serialize(self) -> str:
        data = asdict(self)
        data["record_type"] = self.record_type.value
        return json.dumps(data, separators=(",", ":"))

    @classmethod
    def deserialize(cls, line: str) -> WALRecord:
        try:
            data = json.loads(line)
            record_type = RecordType(data["record_type"])
            checksum = data.pop("checksum")

            expected = cls.calculate_checksum(data)
            if checksum != expected:
                raise CorruptLogError(
                    f"Checksum mismatch at LSN {data['lsn']}"
                )

            return cls(
                **data,
                record_type=record_type,
                checksum=checksum,
            )
        except CorruptLogError:
            raise
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise CorruptLogError(f"Invalid WAL record: {exc}") from exc


class DurableWAL:
    """Append-only WAL backed by a local file."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self.records: list[WALRecord] = []
        self.next_lsn = 1
        self.load()

    def load(self) -> None:
        records = []
        expected_lsn = 1

        with self.path.open("rb") as file:
            for line_number, raw in enumerate(file, start=1):
                if not raw.endswith(b"\n"):
                    # An incomplete final record is a torn tail.
                    print(f"Discarding incomplete WAL tail at line {line_number}")
                    break

                try:
                    record = WALRecord.deserialize(
                        raw.decode("utf-8").strip()
                    )
                except (UnicodeDecodeError, CorruptLogError) as exc:
                    raise CorruptLogError(
                        f"Invalid complete record at line {line_number}: {exc}"
                    ) from exc

                if record.lsn != expected_lsn:
                    raise CorruptLogError(
                        f"Expected LSN {expected_lsn}, got {record.lsn}"
                    )

                records.append(record)
                expected_lsn += 1

        # Remove an incomplete tail before future appends.
        valid_size = sum(
            len((record.serialize() + "\n").encode("utf-8"))
            for record in records
        )
        if self.path.stat().st_size != valid_size:
            with self.path.open("r+b") as file:
                file.truncate(valid_size)
                file.flush()
                os.fsync(file.fileno())

        self.records = records
        self.next_lsn = expected_lsn

    def append(
        self,
        transaction_id: int,
        record_type: RecordType,
        key: str | None = None,
        old_value: int | None = None,
        new_value: int | None = None,
    ) -> WALRecord:
        record = WALRecord.create(
            self.next_lsn,
            transaction_id,
            record_type,
            key,
            old_value,
            new_value,
        )

        try:
            with self.path.open("ab") as file:
                file.write((record.serialize() + "\n").encode("utf-8"))
                file.flush()
                os.fsync(file.fileno())
        except OSError as exc:
            raise DurabilityError(
                f"Unable to persist LSN {record.lsn}: {exc}"
            ) from exc

        self.records.append(record)
        self.next_lsn += 1
        return record

    def truncate_after(self, lsn: int) -> None:
        """Simulate loss of an unflushed WAL tail."""
        retained = [r for r in self.records if r.lsn <= lsn]

        with self.path.open("wb") as file:
            for record in retained:
                file.write((record.serialize() + "\n").encode("utf-8"))
            file.flush()
            os.fsync(file.fileno())

        self.records = retained
        self.next_lsn = len(retained) + 1


class TransactionState(str, Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


@dataclass
class Transaction:
    transaction_id: int
    state: TransactionState = TransactionState.ACTIVE


class WALDatabase:
    """
    Educational key-value database.

    The database pages are modeled in memory. WAL records are persisted
    independently. A production database must also enforce pageLSN-based
    redo rules and coordinate page flushing with checkpoint metadata.
    """

    def __init__(self, wal: DurableWAL):
        self.wal = wal
        self.data: dict[str, int] = {}
        self.transactions: dict[int, Transaction] = {}
        self.dirty_keys: set[str] = set()
        self.next_transaction_id = 1
        self.checkpoint_lsn = 0

    def begin(self) -> Transaction:
        tx_id = self.next_transaction_id
        self.next_transaction_id += 1

        tx = Transaction(tx_id)
        self.wal.append(tx_id, RecordType.BEGIN)
        self.transactions[tx_id] = tx

        print(f"BEGIN transaction {tx_id}")
        return tx

    def update(self, tx: Transaction, key: str, value: int) -> None:
        self._validate_active(tx)

        if not key or len(key) > 128:
            raise ValueError("Key must contain 1 to 128 characters")

        old_value = self.data.get(key)
        self.wal.append(
            tx.transaction_id,
            RecordType.UPDATE,
            key,
            old_value,
            value,
        )

        # WAL is persisted before the corresponding data-page change.
        self.data[key] = value
        self.dirty_keys.add(key)

        print(f"UPDATE {key}: {old_value} -> {value}")

    def commit(self, tx: Transaction) -> None:
        self._validate_active(tx)

        # Commit is acknowledged only after its WAL record is durable.
        self.wal.append(tx.transaction_id, RecordType.COMMIT)
        tx.state = TransactionState.COMMITTED

        print(f"COMMIT transaction {tx.transaction_id}")

    def abort(self, tx: Transaction) -> None:
        self._validate_active(tx)

        for record in reversed(self.wal.records):
            if record.transaction_id != tx.transaction_id:
                continue
            if record.record_type == RecordType.UPDATE:
                if record.old_value is None:
                    self.data.pop(record.key, None)
                else:
                    self.data[record.key] = record.old_value

        self.wal.append(tx.transaction_id, RecordType.ABORT)
        tx.state = TransactionState.ABORTED
        print(f"ABORT transaction {tx.transaction_id}")

    def _validate_active(self, tx: Transaction) -> None:
        if self.transactions.get(tx.transaction_id) is not tx:
            raise WALError("Unknown transaction")
        if tx.state != TransactionState.ACTIVE:
            raise WALError("Transaction is not active")

    def checkpoint(self) -> None:
        """
        Simplified checkpoint.

        The example records a checkpoint after all current data changes.
        A production fuzzy checkpoint must also track active transactions
        and dirty pages, and must not discard WAL still needed for recovery.
        """
        record = self.wal.append(0, RecordType.CHECKPOINT)
        self.checkpoint_lsn = record.lsn
        self.dirty_keys.clear()

        print(f"CHECKPOINT at LSN {record.lsn}")

    def simulate_crash(self) -> None:
        """Discard volatile database state."""
        self.data.clear()
        self.transactions.clear()
        self.dirty_keys.clear()
        print("\n*** DATABASE CRASH ***")

    def recover(self) -> dict[str, int]:
        """
        Analysis, REDO, and UNDO recovery.

        REDO replays committed and incomplete updates from the WAL.
        UNDO reverses updates belonging to transactions without COMMIT.
        """
        records = self.wal.records

        active: set[int] = set()
        committed: set[int] = set()
        aborted: set[int] = set()

        print("\n--- ANALYSIS PHASE ---")

        for record in records:
            tx_id = record.transaction_id

            if record.record_type == RecordType.BEGIN:
                active.add(tx_id)
            elif record.record_type == RecordType.COMMIT:
                active.discard(tx_id)
                committed.add(tx_id)
            elif record.record_type == RecordType.ABORT:
                active.discard(tx_id)
                aborted.add(tx_id)

        print(f"Committed transactions: {sorted(committed)}")
        print(f"Incomplete transactions: {sorted(active)}")

        print("\n--- REDO PHASE ---")

        for record in records:
            if record.record_type != RecordType.UPDATE:
                continue

            if record.transaction_id in committed or record.transaction_id in active:
                self.data[record.key] = record.new_value
                print(
                    f"REDO LSN {record.lsn}: "
                    f"{record.key} = {record.new_value}"
                )

        print("\n--- UNDO PHASE ---")

        for record in reversed(records):
            if record.record_type != RecordType.UPDATE:
                continue

            if record.transaction_id not in active:
                continue

            if record.old_value is None:
                self.data.pop(record.key, None)
            else:
                self.data[record.key] = record.old_value

            print(
                f"UNDO LSN {record.lsn}: "
                f"{record.key} restored to {record.old_value}"
            )

        # Recovery completion is represented by durable ABORT records.
        for tx_id in sorted(active):
            self.wal.append(tx_id, RecordType.ABORT)

        print("\nRecovery completed.")
        return dict(self.data)


def run_tests() -> None:
    assert WALRecord.create(
        1, 1, RecordType.BEGIN
    ).record_type == RecordType.BEGIN

    record = WALRecord.create(
        2, 1, RecordType.UPDATE, "balance", 100, 150
    )
    assert WALRecord.deserialize(record.serialize()).new_value == 150

    corrupt = json.loads(record.serialize())
    corrupt["new_value"] = 999

    try:
        WALRecord.deserialize(json.dumps(corrupt))
        raise AssertionError("Corruption was not detected")
    except CorruptLogError:
        pass

    print("Unit validation passed.")


def demonstration() -> None:
    with tempfile.TemporaryDirectory(prefix="wal_demo_") as directory:
        wal_path = Path(directory) / "database.wal"

        wal = DurableWAL(wal_path)
        database = WALDatabase(wal)

        print("\n--- NORMAL TRANSACTION PROCESSING ---")

        tx1 = database.begin()
        database.update(tx1, "account_A", 1000)
        database.update(tx1, "account_B", 500)
        database.commit(tx1)

        tx2 = database.begin()
        database.update(tx2, "account_A", 800)
        database.update(tx2, "account_B", 700)

        # The second transaction crashes before committing.
        print("\nCurrent volatile state:", database.data)

        database.simulate_crash()

        # Reload the durable log from disk.
        recovered_wal = DurableWAL(wal_path)
        recovered_database = WALDatabase(recovered_wal)

        print("\n--- CRASH RECOVERY ---")
        result = recovered_database.recover()

        print("\nRecovered database:", result)

        assert result == {
            "account_A": 1000,
            "account_B": 500,
        }

        # Recovery is idempotent for this completed recovery scenario.
        second_recovery = WALDatabase(DurableWAL(wal_path))
        assert second_recovery.recover() == result

        print("\nAll recovery assertions passed.")


if __name__ == "__main__":
    run_tests()
    demonstration()
