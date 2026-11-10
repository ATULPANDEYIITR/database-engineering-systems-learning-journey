#!/usr/bin/env python3
"""
Database Checkpoints, Dirty Pages, Write-Ahead Logging, and Recovery.

Implements a database storage-engine simulation covering:
- WAL records and log sequence numbers (LSNs)
- Buffer pool and dirty-page tracking
- Fuzzy checkpoints
- Transaction state tracking
- Checkpoint metadata
- Analysis, redo, and undo recovery
- Crash simulation
- Recovery validation and reporting

Python 3.10+
Standard-library only.
"""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("database_recovery")


class LogType(Enum):
    BEGIN = "BEGIN"
    UPDATE = "UPDATE"
    COMMIT = "COMMIT"
    ABORT = "ABORT"
    END = "END"
    CHECKPOINT_BEGIN = "CHECKPOINT_BEGIN"
    CHECKPOINT_END = "CHECKPOINT_END"
    CLR = "CLR"


class TransactionState(Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"
    ENDED = "ENDED"


class RecoveryState(Enum):
    NORMAL = "NORMAL"
    CRASHED = "CRASHED"
    RECOVERING = "RECOVERING"
    RECOVERED = "RECOVERED"


@dataclass
class LogRecord:
    lsn: int
    record_type: LogType
    transaction_id: Optional[int] = None
    page_id: Optional[str] = None
    old_value: Optional[int] = None
    new_value: Optional[int] = None
    undo_next_lsn: Optional[int] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Page:
    page_id: str
    value: int
    page_lsn: int = 0
    rec_lsn: Optional[int] = None
    dirty: bool = False


@dataclass
class Transaction:
    transaction_id: int
    state: TransactionState = TransactionState.ACTIVE
    last_lsn: int = 0


@dataclass
class Checkpoint:
    begin_lsn: int
    end_lsn: int
    dirty_page_table: dict[str, int]
    transaction_table: dict[int, dict]


class WriteAheadLog:
    """Maintains ordered records and a durable log boundary."""

    def __init__(self):
        self.records: list[LogRecord] = []
        self.next_lsn = 1
        self.durable_lsn = 0

    def append(
        self,
        record_type: LogType,
        transaction_id: Optional[int] = None,
        page_id: Optional[str] = None,
        old_value: Optional[int] = None,
        new_value: Optional[int] = None,
        undo_next_lsn: Optional[int] = None,
        metadata: Optional[dict] = None
    ) -> LogRecord:
        record = LogRecord(
            lsn=self.next_lsn,
            record_type=record_type,
            transaction_id=transaction_id,
            page_id=page_id,
            old_value=old_value,
            new_value=new_value,
            undo_next_lsn=undo_next_lsn,
            metadata=metadata or {}
        )
        self.records.append(record)
        self.next_lsn += 1
        return record

    def flush(self, target_lsn: int) -> None:
        if target_lsn < self.durable_lsn:
            raise ValueError("Durable LSN cannot move backward.")

        if target_lsn >= self.next_lsn:
            raise ValueError("Cannot flush a nonexistent LSN.")

        self.durable_lsn = target_lsn
        logger.info("WAL flushed through LSN %d", target_lsn)

    def get(self, lsn: int) -> LogRecord:
        if lsn < 1 or lsn >= self.next_lsn:
            raise ValueError(f"Invalid LSN: {lsn}")

        return self.records[lsn - 1]

    def durable_records(self) -> list[LogRecord]:
        return [
            record for record in self.records
            if record.lsn <= self.durable_lsn
        ]


class BufferPool:
    """Tracks cached pages and their earliest unflushed update."""

    def __init__(self):
        self.pages: dict[str, Page] = {}

    def create_page(self, page_id: str, initial_value: int) -> None:
        if page_id in self.pages:
            raise ValueError(f"Page already exists: {page_id}")

        self.pages[page_id] = Page(
            page_id=page_id,
            value=initial_value
        )

    def get_page(self, page_id: str) -> Page:
        if page_id not in self.pages:
            raise KeyError(f"Unknown page: {page_id}")

        return self.pages[page_id]

    def update_page(
        self,
        page_id: str,
        value: int,
        lsn: int
    ) -> None:
        page = self.get_page(page_id)

        if not page.dirty:
            page.rec_lsn = lsn

        page.value = value
        page.page_lsn = lsn
        page.dirty = True

    def flush_page(self, page_id: str, wal: WriteAheadLog) -> None:
        page = self.get_page(page_id)

        if not page.dirty:
            return

        # WAL must reach stable storage before the data page.
        if wal.durable_lsn < page.page_lsn:
            raise RuntimeError(
                f"WAL violation: page {page_id} requires "
                f"LSN {page.page_lsn}, durable LSN is {wal.durable_lsn}"
            )

        logger.info("Flushing page %s at LSN %d", page_id, page.page_lsn)
        page.dirty = False
        page.rec_lsn = None

    def dirty_page_table(self) -> dict[str, int]:
        return {
            page.page_id: page.rec_lsn
            for page in self.pages.values()
            if page.dirty and page.rec_lsn is not None
        }


class DatabaseEngine:
    def __init__(self):
        self.wal = WriteAheadLog()
        self.buffer_pool = BufferPool()
        self.transactions: dict[int, Transaction] = {}
        self.checkpoints: list[Checkpoint] = []
        self.next_transaction_id = 1
        self.recovery_state = RecoveryState.NORMAL
        self.disk_pages: dict[str, int] = {}
        self.last_checkpoint: Optional[Checkpoint] = None

    def create_page(self, page_id: str, value: int) -> None:
        self.buffer_pool.create_page(page_id, value)
        self.disk_pages[page_id] = value

    def begin_transaction(self) -> int:
        transaction_id = self.next_transaction_id
        self.next_transaction_id += 1

        transaction = Transaction(transaction_id)
        record = self.wal.append(
            LogType.BEGIN,
            transaction_id=transaction_id
        )
        transaction.last_lsn = record.lsn
        self.transactions[transaction_id] = transaction

        return transaction_id

    def update(
        self,
        transaction_id: int,
        page_id: str,
        new_value: int
    ) -> None:
        transaction = self._active_transaction(transaction_id)
        page = self.buffer_pool.get_page(page_id)

        old_value = page.value

        record = self.wal.append(
            LogType.UPDATE,
            transaction_id=transaction_id,
            page_id=page_id,
            old_value=old_value,
            new_value=new_value
        )

        self.buffer_pool.update_page(
            page_id,
            new_value,
            record.lsn
        )
        transaction.last_lsn = record.lsn

    def commit(self, transaction_id: int) -> None:
        transaction = self._active_transaction(transaction_id)

        record = self.wal.append(
            LogType.COMMIT,
            transaction_id=transaction_id
        )
        transaction.last_lsn = record.lsn

        # Commit is acknowledged only after its WAL record is durable.
        self.wal.flush(record.lsn)
        transaction.state = TransactionState.COMMITTED

        end_record = self.wal.append(
            LogType.END,
            transaction_id=transaction_id
        )
        transaction.last_lsn = end_record.lsn

    def abort(self, transaction_id: int) -> None:
        transaction = self._active_transaction(transaction_id)

        record = self.wal.append(
            LogType.ABORT,
            transaction_id=transaction_id
        )
        transaction.last_lsn = record.lsn
        self.wal.flush(record.lsn)

        transaction.state = TransactionState.ABORTED

    def _active_transaction(self, transaction_id: int) -> Transaction:
        transaction = self.transactions.get(transaction_id)

        if transaction is None:
            raise KeyError(f"Unknown transaction: {transaction_id}")

        if transaction.state != TransactionState.ACTIVE:
            raise RuntimeError("Transaction is not active.")

        return transaction

    def checkpoint(self) -> Checkpoint:
        """Create a fuzzy checkpoint without flushing every data page."""

        begin = self.wal.append(LogType.CHECKPOINT_BEGIN)

        dirty_table = self.buffer_pool.dirty_page_table()

        transaction_table = {
            transaction_id: {
                "state": transaction.state.value,
                "last_lsn": transaction.last_lsn
            }
            for transaction_id, transaction in self.transactions.items()
            if transaction.state == TransactionState.ACTIVE
        }

        end = self.wal.append(
            LogType.CHECKPOINT_END,
            metadata={
                "dirty_page_table": dirty_table,
                "transaction_table": transaction_table
            }
        )

        # A complete checkpoint must be durable before it is advertised.
        self.wal.flush(end.lsn)

        checkpoint = Checkpoint(
            begin_lsn=begin.lsn,
            end_lsn=end.lsn,
            dirty_page_table=dirty_table,
            transaction_table=transaction_table
        )

        self.checkpoints.append(checkpoint)
        self.last_checkpoint = checkpoint

        logger.info(
            "Checkpoint completed: begin=%d end=%d dirty_pages=%d",
            begin.lsn,
            end.lsn,
            len(dirty_table)
        )

        return checkpoint

    def flush_page(self, page_id: str) -> None:
        page = self.buffer_pool.get_page(page_id)
        self.buffer_pool.flush_page(page_id, self.wal)
        self.disk_pages[page_id] = page.value

    def crash(self) -> None:
        """Discard volatile memory and retain only durable disk state."""

        if self.recovery_state != RecoveryState.NORMAL:
            raise RuntimeError("Engine is not running normally.")

        self.recovery_state = RecoveryState.CRASHED

        self.buffer_pool = BufferPool()
        for page_id, value in self.disk_pages.items():
            self.buffer_pool.create_page(page_id, value)

        logger.warning("Simulated database crash.")

    def recover(self) -> dict:
        if self.recovery_state != RecoveryState.CRASHED:
            raise RuntimeError("Recovery requires a crashed database.")

        self.recovery_state = RecoveryState.RECOVERING

        records = self.wal.durable_records()

        if not records:
            self.recovery_state = RecoveryState.RECOVERED
            return {"redo": 0, "undo": 0, "pages": dict(self.disk_pages)}

        # Locate the latest complete durable checkpoint.
        checkpoint = None

        for candidate in reversed(self.checkpoints):
            if candidate.end_lsn <= self.wal.durable_lsn:
                checkpoint = candidate
                break

        if checkpoint:
            redo_start = min(
                checkpoint.dirty_page_table.values(),
                default=checkpoint.end_lsn + 1
            )
            transaction_table = {
                int(transaction_id): dict(data)
                for transaction_id, data
                in checkpoint.transaction_table.items()
            }
        else:
            redo_start = 1
            transaction_table = {}

        redo_count = 0
        undo_count = 0

        # Analysis: determine transaction status after the checkpoint.
        for record in records:
            if record.lsn < redo_start:
                continue

            transaction_id = record.transaction_id

            if transaction_id is None:
                continue

            if record.record_type == LogType.BEGIN:
                transaction_table[transaction_id] = {
                    "state": TransactionState.ACTIVE.value,
                    "last_lsn": record.lsn
                }

            elif record.record_type in (
                LogType.UPDATE,
                LogType.CLR,
                LogType.COMMIT,
                LogType.ABORT,
                LogType.END
            ):
                entry = transaction_table.setdefault(
                    transaction_id,
                    {"state": "ACTIVE", "last_lsn": 0}
                )
                entry["last_lsn"] = record.lsn

                if record.record_type == LogType.COMMIT:
                    entry["state"] = TransactionState.COMMITTED.value
                elif record.record_type == LogType.ABORT:
                    entry["state"] = TransactionState.ABORTED.value
                elif record.record_type == LogType.END:
                    entry["state"] = TransactionState.ENDED.value

        # Redo: repeat history, but skip operations already reflected on disk.
        dirty_pages = (
            checkpoint.dirty_page_table if checkpoint else {}
        )

        for record in records:
            if record.lsn < redo_start:
                continue

            if record.record_type not in (LogType.UPDATE, LogType.CLR):
                continue

            page_id = record.page_id
            if page_id is None:
                continue

            if checkpoint and (
                page_id not in dirty_pages
                and record.record_type == LogType.UPDATE
            ):
                # A page not dirty at the checkpoint can still become dirty
                # through a later update. Do not skip such updates.
                if record.lsn < checkpoint.end_lsn:
                    continue

            page = self.buffer_pool.get_page(page_id)

            if page.page_lsn >= record.lsn:
                continue

            page.value = record.new_value
            page.page_lsn = record.lsn
            page.dirty = True
            page.rec_lsn = (
                page.rec_lsn
                if page.rec_lsn is not None
                else record.lsn
            )
            redo_count += 1

        # Undo all durable updates of transactions without a durable commit.
        committed = {
            transaction_id
            for transaction_id, entry in transaction_table.items()
            if entry["state"] in (
                TransactionState.COMMITTED.value,
                TransactionState.ENDED.value
            )
        }

        records_by_transaction: dict[int, list[LogRecord]] = {}

        for record in records:
            if record.transaction_id is not None:
                records_by_transaction.setdefault(
                    record.transaction_id, []
                ).append(record)

        for transaction_id, transaction_records in records_by_transaction.items():
            if transaction_id in committed:
                continue

            for record in reversed(transaction_records):
                if record.record_type not in (
                    LogType.UPDATE,
                    LogType.CLR
                ):
                    continue

                if record.page_id is None:
                    continue

                page = self.buffer_pool.get_page(record.page_id)

                if page.page_lsn >= record.lsn:
                    undo_record = self.wal.append(
                        LogType.CLR,
                        transaction_id=transaction_id,
                        page_id=record.page_id,
                        old_value=record.new_value,
                        new_value=record.old_value,
                        undo_next_lsn=None
                    )

                    page.value = record.old_value
                    page.page_lsn = undo_record.lsn
                    page.dirty = True

                    if page.rec_lsn is None:
                        page.rec_lsn = undo_record.lsn

                    undo_count += 1

            transaction = self.transactions.get(transaction_id)

            if transaction:
                transaction.state = TransactionState.ABORTED

        # Persist recovery changes in WAL before writing data pages.
        if self.wal.next_lsn > 1:
            self.wal.flush(self.wal.next_lsn - 1)

        for page_id in list(self.buffer_pool.pages):
            page = self.buffer_pool.get_page(page_id)

            if page.dirty:
                self.flush_page(page_id)

        self.recovery_state = RecoveryState.RECOVERED

        result = {
            "redo": redo_count,
            "undo": undo_count,
            "pages": {
                page_id: page.value
                for page_id, page in self.buffer_pool.pages.items()
            }
        }

        logger.info("Recovery completed: %s", result)
        return result

    def report(self) -> dict:
        return {
            "recovery_state": self.recovery_state.value,
            "durable_lsn": self.wal.durable_lsn,
            "last_generated_lsn": self.wal.next_lsn - 1,
            "dirty_pages": self.buffer_pool.dirty_page_table(),
            "transactions": {
                transaction_id: transaction.state.value
                for transaction_id, transaction
                in self.transactions.items()
            },
            "disk_pages": dict(self.disk_pages)
        }


def save_recovery_report(report: dict, path: Path) -> None:
    """Write an atomic JSON report without exposing partial output."""

    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(path.suffix + ".tmp")

    try:
        temporary.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8"
        )
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def run_demo() -> None:
    engine = DatabaseEngine()

    engine.create_page("ACCOUNT-101", 1000)
    engine.create_page("ACCOUNT-202", 2000)
    engine.create_page("ACCOUNT-303", 3000)

    # Transaction 1 commits successfully.
    transaction_1 = engine.begin_transaction()
    engine.update(transaction_1, "ACCOUNT-101", 1100)
    engine.commit(transaction_1)

    # Persist one page while keeping another page dirty.
    engine.flush_page("ACCOUNT-101")

    # Transaction 2 remains active during the checkpoint.
    transaction_2 = engine.begin_transaction()
    engine.update(transaction_2, "ACCOUNT-202", 1800)

    engine.checkpoint()

    # Transaction 3 commits after the checkpoint.
    transaction_3 = engine.begin_transaction()
    engine.update(transaction_3, "ACCOUNT-303", 3500)
    engine.commit(transaction_3)

    # Transaction 2 performs another update but does not commit.
    engine.update(transaction_2, "ACCOUNT-202", 1700)

    print("\nBEFORE CRASH")
    print(json.dumps(engine.report(), indent=2))

    engine.crash()

    print("\nRECOVERY")
    recovery_result = engine.recover()
    print(json.dumps(recovery_result, indent=2))

    assert engine.disk_pages["ACCOUNT-101"] == 1100
    assert engine.disk_pages["ACCOUNT-202"] == 2000
    assert engine.disk_pages["ACCOUNT-303"] == 3500

    print("\nVALIDATION PASSED")

    with tempfile.TemporaryDirectory() as directory:
        report_path = Path(directory) / "recovery_report.json"
        save_recovery_report(engine.report(), report_path)
        print("Report saved:", report_path)


if __name__ == "__main__":
    run_demo()
