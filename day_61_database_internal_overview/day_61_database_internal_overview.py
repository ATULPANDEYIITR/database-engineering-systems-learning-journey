#!/usr/bin/env python3
"""
Database Internals Overview
Query Engine, Storage Engine, and Buffer Manager

A self-contained educational simulation of a small relational database engine.
The implementation models:
- fixed-size pages and records
- heap-file storage
- a buffer pool with LRU replacement
- dirty-page tracking
- a simple B-tree-like ordered index
- a query executor using sequential and indexed access
- transaction-style write handling
- basic WAL-style logging
- validation and failure handling

No external dependencies are required.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple
import copy
import hashlib
import json
import os
import tempfile


PAGE_SIZE = 256
MAX_RECORDS_PER_PAGE = 6
BUFFER_POOL_SIZE = 3


class EngineError(Exception):
    """Base exception for database-engine failures."""


class PageFullError(EngineError):
    pass


class PageNotFoundError(EngineError):
    pass


class BufferPoolFullError(EngineError):
    pass


class TransactionError(EngineError):
    pass


class PageType(Enum):
    HEAP = "heap"
    INDEX = "index"


@dataclass(frozen=True)
class Record:
    row_id: int
    customer_id: int
    name: str
    balance: float

    def validate(self) -> None:
        if self.row_id <= 0:
            raise ValueError("row_id must be positive")
        if self.customer_id <= 0:
            raise ValueError("customer_id must be positive")
        if not self.name or len(self.name) > 80:
            raise ValueError("name must contain 1-80 characters")
        if not (-10_000_000 <= self.balance <= 10_000_000):
            raise ValueError("balance is outside the supported range")


@dataclass
class Page:
    page_id: int
    page_type: PageType
    records: List[Record] = field(default_factory=list)
    dirty: bool = False
    lsn: int = 0

    def add_record(self, record: Record) -> None:
        if len(self.records) >= MAX_RECORDS_PER_PAGE:
            raise PageFullError(f"page {self.page_id} is full")
        record.validate()
        self.records.append(record)
        self.dirty = True

    def find(self, row_id: int) -> Optional[Record]:
        return next((r for r in self.records if r.row_id == row_id), None)

    def update_balance(self, row_id: int, new_balance: float) -> bool:
        if not (-10_000_000 <= new_balance <= 10_000_000):
            raise ValueError("balance is outside the supported range")

        for index, record in enumerate(self.records):
            if record.row_id == row_id:
                self.records[index] = Record(
                    row_id=record.row_id,
                    customer_id=record.customer_id,
                    name=record.name,
                    balance=new_balance,
                )
                self.dirty = True
                return True
        return False

    def estimated_size(self) -> int:
        payload = json.dumps(
            [record.__dict__ for record in self.records],
            separators=(",", ":"),
        ).encode("utf-8")
        return len(payload)


@dataclass(frozen=True)
class BufferFrame:
    page: Page


class DiskManager:
    """Simulates persistent pages using a JSON file."""

    def __init__(self, path: str):
        self.path = path
        self.pages: Dict[int, Page] = {}
        self.next_page_id = 1
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return

        with open(self.path, "r", encoding="utf-8") as file:
            raw = json.load(file)

        self.next_page_id = raw.get("next_page_id", 1)

        for item in raw.get("pages", []):
            page = Page(
                page_id=item["page_id"],
                page_type=PageType(item["page_type"]),
                dirty=False,
                lsn=item.get("lsn", 0),
            )
            for record in item["records"]:
                page.records.append(Record(**record))
            self.pages[page.page_id] = page

    def allocate_page(self, page_type: PageType) -> Page:
        page = Page(self.next_page_id, page_type)
        self.pages[page.page_id] = page
        self.next_page_id += 1
        return page

    def read_page(self, page_id: int) -> Page:
        if page_id not in self.pages:
            raise PageNotFoundError(f"page {page_id} does not exist")
        return copy.deepcopy(self.pages[page_id])

    def write_page(self, page: Page) -> None:
        if page.page_id not in self.pages:
            raise PageNotFoundError(f"page {page.page_id} does not exist")
        persisted = copy.deepcopy(page)
        persisted.dirty = False
        self.pages[page.page_id] = persisted

    def flush(self) -> None:
        payload = {
            "next_page_id": self.next_page_id,
            "pages": [
                {
                    "page_id": page.page_id,
                    "page_type": page.page_type.value,
                    "lsn": page.lsn,
                    "records": [record.__dict__ for record in page.records],
                }
                for page in self.pages.values()
            ],
        }

        directory = os.path.dirname(os.path.abspath(self.path))
        temporary = os.path.join(directory, ".database.tmp")

        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)

        os.replace(temporary, self.path)


class BufferPool:
    """
    LRU buffer manager.

    The OrderedDict stores page_id -> Page. The first entry is the least
    recently used page and the last entry is the most recently used page.
    """

    def __init__(self, disk: DiskManager, capacity: int):
        if capacity <= 0:
            raise ValueError("buffer pool capacity must be positive")
        self.disk = disk
        self.capacity = capacity
        self.frames: OrderedDict[int, Page] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.disk_writes = 0

    def fetch(self, page_id: int) -> Page:
        if page_id in self.frames:
            self.hits += 1
            page = self.frames.pop(page_id)
            self.frames[page_id] = page
            return page

        self.misses += 1

        if len(self.frames) >= self.capacity:
            self._evict_one()

        page = self.disk.read_page(page_id)
        self.frames[page_id] = page
        return page

    def _evict_one(self) -> None:
        page_id, page = self.frames.popitem(last=False)

        if page.dirty:
            self.disk.write_page(page)
            self.disk_writes += 1

        self.evictions += 1

    def mark_dirty(self, page_id: int, lsn: int) -> None:
        page = self.fetch(page_id)
        page.dirty = True
        page.lsn = lsn

    def flush_all(self) -> None:
        for page in list(self.frames.values()):
            if page.dirty:
                self.disk.write_page(page)
                self.disk_writes += 1
                page.dirty = False

    def statistics(self) -> Dict[str, float]:
        accesses = self.hits + self.misses
        hit_rate = self.hits / accesses if accesses else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "disk_writes": self.disk_writes,
            "hit_rate": round(hit_rate, 4),
        }


@dataclass(frozen=True)
class LogRecord:
    lsn: int
    transaction_id: int
    page_id: int
    operation: str
    row_id: int
    old_balance: Optional[float]
    new_balance: Optional[float]


class WriteAheadLog:
    """
    Minimal WAL model.

    A real database persists log records before dirty data pages are allowed
    to reach durable storage. This simulation records the ordering explicitly.
    """

    def __init__(self):
        self.records: List[LogRecord] = []
        self.next_lsn = 1

    def append(
        self,
        transaction_id: int,
        page_id: int,
        operation: str,
        row_id: int,
        old_balance: Optional[float],
        new_balance: Optional[float],
    ) -> LogRecord:
        record = LogRecord(
            self.next_lsn,
            transaction_id,
            page_id,
            operation,
            row_id,
            old_balance,
            new_balance,
        )
        self.records.append(record)
        self.next_lsn += 1
        return record


class HeapTable:
    """Heap storage with a row-to-page locator."""

    def __init__(self, disk: DiskManager, buffer_pool: BufferPool):
        self.disk = disk
        self.buffer_pool = buffer_pool
        self.page_ids: List[int] = []
        self.row_locator: Dict[int, int] = {}

        for page_id, page in sorted(disk.pages.items()):
            if page.page_type == PageType.HEAP:
                self.page_ids.append(page_id)
                for record in page.records:
                    self.row_locator[record.row_id] = page_id

    def insert(self, record: Record) -> int:
        record.validate()

        if record.row_id in self.row_locator:
            raise ValueError(f"duplicate row_id {record.row_id}")

        target: Optional[Page] = None

        for page_id in reversed(self.page_ids):
            page = self.buffer_pool.fetch(page_id)
            if len(page.records) < MAX_RECORDS_PER_PAGE:
                target = page
                break

        if target is None:
            target = self.disk.allocate_page(PageType.HEAP)
            self.page_ids.append(target.page_id)
            target = self.buffer_pool.fetch(target.page_id)

        target.add_record(record)
        self.row_locator[record.row_id] = target.page_id
        return target.page_id

    def get(self, row_id: int) -> Optional[Record]:
        page_id = self.row_locator.get(row_id)
        if page_id is None:
            return None

        return self.buffer_pool.fetch(page_id).find(row_id)

    def update_balance(
        self,
        row_id: int,
        new_balance: float,
    ) -> Tuple[int, float]:
        page_id = self.row_locator.get(row_id)

        if page_id is None:
            raise KeyError(f"row {row_id} not found")

        page = self.buffer_pool.fetch(page_id)
        record = page.find(row_id)

        if record is None:
            raise EngineError("row locator points to missing record")

        old_balance = record.balance

        if not page.update_balance(row_id, new_balance):
            raise EngineError("update failed")

        return page_id, old_balance

    def scan(self) -> Iterable[Record]:
        for page_id in self.page_ids:
            page = self.buffer_pool.fetch(page_id)
            yield from page.records


class BTreeIndex:
    """
    Compact ordered index simulation.

    It uses a sorted list rather than implementing physical B-tree nodes.
    The purpose is to expose the logical index access path and its cost
    difference from scanning the heap.
    """

    def __init__(self):
        self.entries: List[Tuple[int, int]] = []

    def build(self, table: HeapTable) -> None:
        self.entries.clear()

        for record in table.scan():
            page_id = table.row_locator[record.row_id]
            self.entries.append((record.customer_id, page_id))

        self.entries.sort()

    def lookup(self, customer_id: int) -> List[int]:
        result = []

        for key, page_id in self.entries:
            if key == customer_id:
                result.append(page_id)
            elif key > customer_id:
                break

        return result


class QueryEngine:
    def __init__(self, table: HeapTable, index: BTreeIndex):
        self.table = table
        self.index = index

    def select_by_customer_scan(self, customer_id: int) -> List[Record]:
        return [
            record
            for record in self.table.scan()
            if record.customer_id == customer_id
        ]

    def select_by_customer_index(self, customer_id: int) -> List[Record]:
        page_ids = self.index.lookup(customer_id)
        result = []

        seen_pages = set()

        for page_id in page_ids:
            if page_id in seen_pages:
                continue

            seen_pages.add(page_id)
            page = self.table.buffer_pool.fetch(page_id)

            result.extend(
                record
                for record in page.records
                if record.customer_id == customer_id
            )

        return result


class Transaction:
    def __init__(
        self,
        transaction_id: int,
        table: HeapTable,
        buffer_pool: BufferPool,
        wal: WriteAheadLog,
    ):
        self.transaction_id = transaction_id
        self.table = table
        self.buffer_pool = buffer_pool
        self.wal = wal
        self.changes: List[Tuple[int, int, float]] = []
        self.active = True

    def update_balance(self, row_id: int, new_balance: float) -> None:
        if not self.active:
            raise TransactionError("transaction is not active")

        page_id, old_balance = self.table.update_balance(
            row_id,
            new_balance,
        )

        log = self.wal.append(
            self.transaction_id,
            page_id,
            "UPDATE_BALANCE",
            row_id,
            old_balance,
            new_balance,
        )

        self.buffer_pool.mark_dirty(page_id, log.lsn)
        self.changes.append((page_id, row_id, old_balance))

    def commit(self) -> None:
        if not self.active:
            raise TransactionError("transaction is not active")

        # WAL records must exist before dirty pages are flushed.
        self.buffer_pool.flush_all()
        self.active = False

    def rollback(self) -> None:
        if not self.active:
            raise TransactionError("transaction is not active")

        for page_id, row_id, old_balance in reversed(self.changes):
            page = self.buffer_pool.fetch(page_id)
            if not page.update_balance(row_id, old_balance):
                raise TransactionError(
                    f"rollback could not restore row {row_id}"
                )

        self.buffer_pool.flush_all()
        self.active = False


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def demonstrate() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database_path = os.path.join(directory, "database.json")
        disk = DiskManager(database_path)
        buffer_pool = BufferPool(disk, BUFFER_POOL_SIZE)
        table = HeapTable(disk, buffer_pool)
        index = BTreeIndex()
        query_engine = QueryEngine(table, index)
        wal = WriteAheadLog()

        customers = [
            Record(1, 101, "Asha", 1250.00),
            Record(2, 102, "Ravi", 840.00),
            Record(3, 101, "Meera", 2190.00),
            Record(4, 103, "Kabir", 450.00),
            Record(5, 104, "Nisha", 3300.00),
            Record(6, 102, "Arjun", 910.00),
            Record(7, 105, "Isha", 720.00),
            Record(8, 101, "Dev", 1500.00),
        ]

        for record in customers:
            table.insert(record)

        index.build(table)

        scan_result = query_engine.select_by_customer_scan(101)
        index_result = query_engine.select_by_customer_index(101)

        assert {
            record.row_id for record in scan_result
        } == {
            record.row_id for record in index_result
        }

        transaction = Transaction(1001, table, buffer_pool, wal)
        transaction.update_balance(1, 1750.00)
        transaction.update_balance(3, 2490.00)
        transaction.commit()

        assert table.get(1).balance == 1750.00
        assert table.get(3).balance == 2490.00

        rollback_transaction = Transaction(1002, table, buffer_pool, wal)
        rollback_transaction.update_balance(1, 9999.00)
        rollback_transaction.rollback()

        assert table.get(1).balance == 1750.00

        disk.flush()
        reloaded_disk = DiskManager(database_path)

        assert len(reloaded_disk.pages) >= 2
        assert stable_hash("database internals") != ""

        print("Database Internals Demonstration")
        print("--------------------------------")
        print(f"Heap pages: {len(table.page_ids)}")
        print(f"Rows: {sum(1 for _ in table.scan())}")
        print(f"Customer 101 rows: {len(index_result)}")
        print(f"Customer 101 balances: {[r.balance for r in index_result]}")
        print(f"WAL records: {len(wal.records)}")
        print(f"Buffer statistics: {buffer_pool.statistics()}")
        print(
            "Persisted pages after reload: "
            f"{len(reloaded_disk.pages)}"
        )

        try:
            table.insert(Record(1, 999, "Duplicate", 1.0))
        except ValueError as error:
            print(f"Validation failure handled: {error}")

        try:
            disk.read_page(999999)
        except PageNotFoundError as error:
            print(f"Storage failure handled: {error}")


if __name__ == "__main__":
    demonstrate()
