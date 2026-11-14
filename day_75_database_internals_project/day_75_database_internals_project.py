#!/usr/bin/env python3
"""
Database Internals Project
Storage management, buffer pools, indexing, transactions, and query execution.

Python 3.10+
Standard-library only.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
import zlib
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator


# ============================================================
# 1. DATABASE CONFIGURATION AND DOMAIN TYPES
# ============================================================

PAGE_SIZE = 4096
MAX_PAGE_RECORDS = 64


class DatabaseError(Exception):
    pass


class ConstraintViolation(DatabaseError):
    pass


class TransactionError(DatabaseError):
    pass


class StorageError(DatabaseError):
    pass


class TransactionState(Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class PageType(Enum):
    HEAP = "HEAP"
    INDEX = "INDEX"


@dataclass
class DatabaseConfig:
    buffer_pool_capacity: int = 8
    page_size: int = PAGE_SIZE
    max_records_per_page: int = MAX_PAGE_RECORDS

    def __post_init__(self):
        if self.buffer_pool_capacity < 1:
            raise ValueError("Buffer pool capacity must be positive.")
        if self.page_size < 512:
            raise ValueError("Page size must be at least 512 bytes.")
        if self.max_records_per_page < 1:
            raise ValueError("Page capacity must be positive.")


@dataclass
class Page:
    page_id: int
    page_type: PageType
    records: list[dict[str, Any]] = field(default_factory=list)
    dirty: bool = False
    page_lsn: int = 0
    checksum: int = 0

    def calculate_checksum(self) -> int:
        payload = json.dumps(
            self.records,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return zlib.crc32(payload)

    def validate(self) -> bool:
        return self.checksum == self.calculate_checksum()

    def refresh_checksum(self) -> None:
        self.checksum = self.calculate_checksum()


# ============================================================
# 2. WRITE-AHEAD LOG
# ============================================================

@dataclass
class LogRecord:
    lsn: int
    transaction_id: int
    operation: str
    table: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    timestamp: float


class WriteAheadLog:
    """
    Records changes before modified pages become durable.

    The WAL flush position represents the highest durable LSN.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.records: list[LogRecord] = []
        self.next_lsn = 1
        self.durable_lsn = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return

        with self.path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                data = json.loads(line)
                record = LogRecord(**data)
                self.records.append(record)
                self.next_lsn = max(self.next_lsn, record.lsn + 1)
                self.durable_lsn = max(self.durable_lsn, record.lsn)

    def append(
        self,
        transaction_id: int,
        operation: str,
        table: str,
        before: dict | None,
        after: dict | None,
    ) -> int:
        lsn = self.next_lsn
        self.next_lsn += 1

        record = LogRecord(
            lsn=lsn,
            transaction_id=transaction_id,
            operation=operation,
            table=table,
            before=before,
            after=after,
            timestamp=time.time(),
        )

        self.records.append(record)

        # Append-only logging makes recovery inspection possible.
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record.__dict__) + "\n")

        return lsn

    def flush(self) -> None:
        # Opening the file in append mode and syncing establishes
        # a durability boundary before dirty data pages are written.
        with self.path.open("ab") as file:
            file.flush()
            os.fsync(file.fileno())

        if self.records:
            self.durable_lsn = self.records[-1].lsn

    def transaction_records(self, transaction_id: int) -> list[LogRecord]:
        return [
            record
            for record in self.records
            if record.transaction_id == transaction_id
        ]


# ============================================================
# 3. DISK PAGE STORAGE
# ============================================================

class DiskManager:
    """
    Stores one JSON-encoded page per line.

    This implementation models page serialization and durability.
    It is educational storage, not a production binary page format.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.pages: dict[int, Page] = {}
        self.read_count = 0
        self.write_count = 0
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return

        with self.path.open("r", encoding="utf-8") as file:
            for line in file:
                data = json.loads(line)
                page = Page(
                    page_id=data["page_id"],
                    page_type=PageType(data["page_type"]),
                    records=data["records"],
                    dirty=False,
                    page_lsn=data["page_lsn"],
                    checksum=data["checksum"],
                )
                if not page.validate():
                    raise StorageError(
                        f"Checksum mismatch on page {page.page_id}"
                    )
                self.pages[page.page_id] = page

    def read_page(self, page_id: int) -> Page:
        self.read_count += 1

        if page_id not in self.pages:
            raise StorageError(f"Page {page_id} does not exist.")

        page = self.pages[page_id]
        if not page.validate():
            raise StorageError(f"Corrupt page {page_id}.")

        return Page(
            page_id=page.page_id,
            page_type=page.page_type,
            records=[dict(record) for record in page.records],
            dirty=False,
            page_lsn=page.page_lsn,
            checksum=page.checksum,
        )

    def write_page(self, page: Page, durable_lsn: int) -> None:
        if page.page_lsn > durable_lsn:
            raise StorageError(
                "Write-ahead logging violation: page WAL is not durable."
            )

        page.refresh_checksum()
        page.dirty = False
        self.pages[page.page_id] = page

        temporary = self.path.with_suffix(".tmp")

        with temporary.open("w", encoding="utf-8") as file:
            for page_id in sorted(self.pages):
                current = self.pages[page_id]
                file.write(json.dumps({
                    "page_id": current.page_id,
                    "page_type": current.page_type.value,
                    "records": current.records,
                    "page_lsn": current.page_lsn,
                    "checksum": current.calculate_checksum(),
                }) + "\n")

            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary, self.path)
        self.write_count += 1

    def allocate_page(self, page_type: PageType) -> Page:
        page_id = max(self.pages, default=0) + 1
        page = Page(page_id, page_type)
        page.refresh_checksum()
        self.pages[page_id] = page
        return page


# ============================================================
# 4. BUFFER POOL AND LRU REPLACEMENT
# ============================================================

class BufferPool:
    """
    LRU buffer pool.

    A page lookup costs O(1) on average.
    LRU eviction costs O(1) on average.
    """

    def __init__(
        self,
        disk: DiskManager,
        wal: WriteAheadLog,
        capacity: int,
    ):
        self.disk = disk
        self.wal = wal
        self.capacity = capacity
        self.frames: OrderedDict[int, Page] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def fetch(self, page_id: int) -> Page:
        if page_id in self.frames:
            self.hits += 1
            self.frames.move_to_end(page_id)
            return self.frames[page_id]

        self.misses += 1

        if len(self.frames) >= self.capacity:
            self.evict()

        page = self.disk.read_page(page_id)
        self.frames[page_id] = page
        return page

    def register_new_page(self, page: Page) -> None:
        if len(self.frames) >= self.capacity:
            self.evict()

        self.frames[page.page_id] = page

    def evict(self) -> None:
        if not self.frames:
            return

        page_id, page = next(iter(self.frames.items()))

        if page.dirty:
            self.wal.flush()
            self.disk.write_page(page, self.wal.durable_lsn)

        del self.frames[page_id]
        self.evictions += 1

    def flush_all(self) -> None:
        # WAL must become durable before any dirty page is written.
        self.wal.flush()

        for page in list(self.frames.values()):
            if page.dirty:
                self.disk.write_page(page, self.wal.durable_lsn)

    def statistics(self) -> dict[str, int | float]:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_ratio": self.hits / total if total else 0.0,
        }


# ============================================================
# 5. TRANSACTIONS AND BASIC UNDO
# ============================================================

class Transaction:
    def __init__(self, transaction_id: int, database: Database):
        self.transaction_id = transaction_id
        self.database = database
        self.state = TransactionState.ACTIVE
        self.undo_actions: list[Callable[[], None]] = []

    def _ensure_active(self) -> None:
        if self.state != TransactionState.ACTIVE:
            raise TransactionError("Transaction is not active.")

    def insert(self, table: str, record: dict[str, Any]) -> None:
        self._ensure_active()
        self.database.insert(
            self.transaction_id,
            table,
            record,
            self.undo_actions,
        )

    def commit(self) -> None:
        self._ensure_active()

        # Commit record is durable before the transaction is reported
        # committed. Dirty pages can be flushed later.
        self.database.wal.append(
            self.transaction_id,
            "COMMIT",
            "",
            None,
            None,
        )
        self.database.wal.flush()
        self.database.buffer_pool.flush_all()
        self.state = TransactionState.COMMITTED
        self.undo_actions.clear()

    def rollback(self) -> None:
        self._ensure_active()

        for undo in reversed(self.undo_actions):
            undo()

        self.database.wal.append(
            self.transaction_id,
            "ABORT",
            "",
            None,
            None,
        )
        self.database.wal.flush()
        self.database.buffer_pool.flush_all()

        self.undo_actions.clear()
        self.state = TransactionState.ABORTED

    def __enter__(self) -> Transaction:
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self.state == TransactionState.ACTIVE:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        return False


# ============================================================
# 6. HEAP TABLE AND HASH INDEX
# ============================================================

class Database:
    def __init__(
        self,
        directory: str | Path,
        config: DatabaseConfig | None = None,
    ):
        self.config = config or DatabaseConfig()
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        self.disk = DiskManager(directory / "pages.jsonl")
        self.wal = WriteAheadLog(directory / "database.wal")
        self.buffer_pool = BufferPool(
            self.disk,
            self.wal,
            self.config.buffer_pool_capacity,
        )

        self.tables: dict[str, list[int]] = defaultdict(list)
        self.indexes: dict[str, dict[Any, tuple[int, int]]] = defaultdict(dict)
        self.next_transaction_id = 1
        self.next_row_id = 1

        # Rebuild table metadata from persisted heap pages.
        for page_id, page in self.disk.pages.items():
            if page.page_type == PageType.HEAP:
                table = page.records[0].get("_table") if page.records else None
                if table:
                    self.tables[table].append(page_id)
                    for slot, record in enumerate(page.records):
                        self.next_row_id = max(
                            self.next_row_id,
                            record.get("_row_id", 0) + 1,
                        )

    def begin(self) -> Transaction:
        transaction = Transaction(self.next_transaction_id, self)
        self.next_transaction_id += 1
        return transaction

    def create_index(self, table: str, column: str) -> None:
        index_name = f"{table}.{column}"

        if index_name in self.indexes:
            raise DatabaseError("Index already exists.")

        index: dict[Any, tuple[int, int]] = {}

        for page_id in self.tables[table]:
            page = self.buffer_pool.fetch(page_id)

            for slot, record in enumerate(page.records):
                if column in record:
                    value = record[column]
                    if value in index:
                        raise ConstraintViolation(
                            f"Duplicate index value: {value}"
                        )
                    index[value] = (page_id, slot)

        self.indexes[index_name] = index

    def insert(
        self,
        transaction_id: int,
        table: str,
        record: dict[str, Any],
        undo_actions: list[Callable[[], None]],
    ) -> None:
        if not table or not table.replace("_", "").isalnum():
            raise ValueError("Invalid table identifier.")

        if not isinstance(record, dict) or not record:
            raise ValueError("A non-empty record is required.")

        row = dict(record)
        row_id = self.next_row_id
        self.next_row_id += 1

        row["_row_id"] = row_id
        row["_table"] = table

        page_id = None
        page = None

        for candidate_id in self.tables[table]:
            candidate = self.buffer_pool.fetch(candidate_id)
            if len(candidate.records) < self.config.max_records_per_page:
                page_id = candidate_id
                page = candidate
                break

        if page is None:
            page = self.disk.allocate_page(PageType.HEAP)
            page_id = page.page_id
            self.tables[table].append(page_id)
            self.buffer_pool.register_new_page(page)

        slot = len(page.records)

        lsn = self.wal.append(
            transaction_id,
            "INSERT",
            table,
            None,
            row,
        )

        page.records.append(row)
        page.page_lsn = lsn
        page.dirty = True

        for index_name, index in self.indexes.items():
            index_table, column = index_name.split(".", 1)
            if index_table == table and column in row:
                value = row[column]
                if value in index:
                    page.records.pop()
                    raise ConstraintViolation(
                        f"Duplicate indexed value: {value}"
                    )
                index[value] = (page_id, slot)

        def undo() -> None:
            current = self.buffer_pool.fetch(page_id)
            if slot < len(current.records):
                removed = current.records[slot]
                current.records.pop(slot)
                current.dirty = True

                for index_name, index in self.indexes.items():
                    index_table, column = index_name.split(".", 1)
                    if index_table == table and column in removed:
                        index.pop(removed[column], None)

        undo_actions.append(undo)

    def scan(self, table: str) -> Iterator[dict[str, Any]]:
        for page_id in self.tables.get(table, []):
            page = self.buffer_pool.fetch(page_id)

            for record in page.records:
                yield {
                    key: value
                    for key, value in record.items()
                    if not key.startswith("_")
                }

    def index_lookup(
        self,
        table: str,
        column: str,
        value: Any,
    ) -> dict[str, Any] | None:
        index = self.indexes.get(f"{table}.{column}")

        if index is None:
            raise DatabaseError("Requested index does not exist.")

        location = index.get(value)
        if location is None:
            return None

        page_id, slot = location
        page = self.buffer_pool.fetch(page_id)

        if slot >= len(page.records):
            raise StorageError("Stale index entry.")

        return {
            key: item
            for key, item in page.records[slot].items()
            if not key.startswith("_")
        }


# ============================================================
# 7. QUERY EXECUTION OPERATORS
# ============================================================

@dataclass
class QueryMetrics:
    rows_in: int = 0
    rows_out: int = 0
    elapsed_seconds: float = 0.0


class Operator:
    def execute(self) -> Iterator[dict[str, Any]]:
        raise NotImplementedError


class TableScan(Operator):
    def __init__(self, database: Database, table: str):
        self.database = database
        self.table = table
        self.metrics = QueryMetrics()

    def execute(self) -> Iterator[dict[str, Any]]:
        start = time.perf_counter()

        for row in self.database.scan(self.table):
            self.metrics.rows_out += 1
            yield row

        self.metrics.elapsed_seconds = time.perf_counter() - start


class Filter(Operator):
    def __init__(
        self,
        child: Operator,
        predicate: Callable[[dict], bool],
    ):
        self.child = child
        self.predicate = predicate
        self.metrics = QueryMetrics()

    def execute(self) -> Iterator[dict[str, Any]]:
        start = time.perf_counter()

        for row in self.child.execute():
            self.metrics.rows_in += 1

            if self.predicate(row):
                self.metrics.rows_out += 1
                yield row

        self.metrics.elapsed_seconds = time.perf_counter() - start


class Project(Operator):
    def __init__(self, child: Operator, columns: list[str]):
        if not columns or len(columns) != len(set(columns)):
            raise ValueError("Projection columns must be unique.")

        self.child = child
        self.columns = columns

    def execute(self) -> Iterator[dict[str, Any]]:
        for row in self.child.execute():
            missing = set(self.columns) - row.keys()
            if missing:
                raise DatabaseError(
                    f"Unknown projection columns: {sorted(missing)}"
                )

            yield {column: row[column] for column in self.columns}


class HashJoin(Operator):
    """
    In-memory hash join with a build and probe phase.

    Expected time complexity: O(n + m).
    Memory complexity: O(n) for the build side.
    """

    def __init__(
        self,
        left: Operator,
        right: Operator,
        left_key: str,
        right_key: str,
    ):
        self.left = left
        self.right = right
        self.left_key = left_key
        self.right_key = right_key

    def execute(self) -> Iterator[dict[str, Any]]:
        hash_table: dict[Any, list[dict]] = defaultdict(list)

        for row in self.left.execute():
            hash_table[row[self.left_key]].append(row)

        for right_row in self.right.execute():
            key = right_row[self.right_key]

            for left_row in hash_table.get(key, []):
                overlap = left_row.keys() & right_row.keys()

                merged = {
                    f"left_{k}" if k in overlap else k: v
                    for k, v in left_row.items()
                }

                for k, value in right_row.items():
                    merged[
                        f"right_{k}" if k in overlap else k
                    ] = value

                yield merged


class HashAggregate(Operator):
    def __init__(
        self,
        child: Operator,
        group_column: str,
        aggregate_column: str,
    ):
        self.child = child
        self.group_column = group_column
        self.aggregate_column = aggregate_column

    def execute(self) -> Iterator[dict[str, Any]]:
        groups: dict[Any, list[float]] = defaultdict(list)

        for row in self.child.execute():
            value = row[self.aggregate_column]

            if not isinstance(value, (int, float)):
                raise DatabaseError("Aggregate column must be numeric.")

            groups[row[self.group_column]].append(value)

        for group, values in groups.items():
            yield {
                self.group_column: group,
                "count": len(values),
                "sum": sum(values),
                "average": sum(values) / len(values),
                "minimum": min(values),
                "maximum": max(values),
            }


# ============================================================
# 8. SIMPLE COST ESTIMATION
# ============================================================

@dataclass
class TableStatistics:
    row_count: int
    distinct_values: dict[str, int]

    def estimated_equality_rows(self, column: str) -> float:
        distinct = self.distinct_values.get(column, 0)
        if distinct <= 0:
            return float(self.row_count)
        return self.row_count / distinct


class QueryPlanner:
    def estimate_scan_cost(
        self,
        statistics: TableStatistics,
        rows_per_page: int,
    ) -> float:
        pages = math.ceil(
            statistics.row_count / max(1, rows_per_page)
        )
        return float(pages)

    def estimate_index_cost(
        self,
        statistics: TableStatistics,
        column: str,
    ) -> float:
        return math.log2(max(2, statistics.row_count)) + (
            statistics.estimated_equality_rows(column)
        )

    def choose_access_path(
        self,
        statistics: TableStatistics,
        column: str,
        rows_per_page: int = MAX_PAGE_RECORDS,
    ) -> str:
        scan = self.estimate_scan_cost(statistics, rows_per_page)
        index = self.estimate_index_cost(statistics, column)

        return "INDEX_SCAN" if index < scan else "TABLE_SCAN"


# ============================================================
# 9. DEMONSTRATION AND ASSERTION TESTS
# ============================================================

def run_tests(directory: Path) -> None:
    config = DatabaseConfig(buffer_pool_capacity=2)
    database = Database(directory, config)

    with database.begin() as transaction:
        transaction.insert("employees", {
            "employee_id": 101,
            "name": "Asha",
            "department": "Engineering",
            "salary": 90000,
        })
        transaction.insert("employees", {
            "employee_id": 102,
            "name": "Ravi",
            "department": "Engineering",
            "salary": 85000,
        })
        transaction.insert("employees", {
            "employee_id": 103,
            "name": "Meera",
            "department": "Research",
            "salary": 110000,
        })
        transaction.insert("employees", {
            "employee_id": 104,
            "name": "Kabir",
            "department": "Research",
            "salary": 95000,
        })

    database.create_index("employees", "employee_id")

    employee = database.index_lookup(
        "employees",
        "employee_id",
        103,
    )
    assert employee is not None
    assert employee["name"] == "Meera"

    missing = database.index_lookup(
        "employees",
        "employee_id",
        999,
    )
    assert missing is None

    # Verify rollback does not retain an inserted row.
    try:
        with database.begin() as transaction:
            transaction.insert("employees", {
                "employee_id": 105,
                "name": "Temporary",
                "department": "Testing",
                "salary": 50000,
            })
            raise RuntimeError("Simulated transaction failure")
    except RuntimeError:
        pass

    assert all(
        row["employee_id"] != 105
        for row in database.scan("employees")
    )

    scan = TableScan(database, "employees")
    filtered = Filter(
        scan,
        lambda row: row["salary"] >= 90000,
    )
    projected = Project(
        filtered,
        ["employee_id", "name", "salary"],
    )

    print("\nFILTERED QUERY RESULTS")
    results = list(projected.execute())

    for result in results:
        print(result)

    assert len(results) == 3

    aggregate = HashAggregate(
        TableScan(database, "employees"),
        "department",
        "salary",
    )

    print("\nGROUP AGGREGATION")
    for result in aggregate.execute():
        print(result)

    statistics = TableStatistics(
        row_count=10000,
        distinct_values={"employee_id": 10000},
    )

    planner = QueryPlanner()

    print("\nQUERY PLAN ESTIMATION")
    print(
        "Selected access path:",
        planner.choose_access_path(statistics, "employee_id"),
    )

    print("\nBUFFER POOL STATISTICS")
    print(database.buffer_pool.statistics())

    print("\nDISK STATISTICS")
    print({
        "reads": database.disk.read_count,
        "writes": database.disk.write_count,
    })

    print("\nWAL RECORD COUNT")
    print(len(database.wal.records))

    # Verify durable storage can be reopened.
    reopened = Database(directory, config)

    assert len(list(reopened.scan("employees"))) == 4
    print("\nPersistence verification: PASSED")


def main() -> None:
    with tempfile.TemporaryDirectory(
        prefix="database_internals_"
    ) as temporary_directory:
        run_tests(Path(temporary_directory))

    print("\nAll database internals demonstrations passed.")


if __name__ == "__main__":
    main()
