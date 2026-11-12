"""
VACUUM AND GARBAGE COLLECTION
PostgreSQL dead tuples, vacuuming, and storage reclamation.

A self-contained simulation of PostgreSQL MVCC storage management,
dead tuple accumulation, VACUUM, ANALYZE, freezing, and autovacuum.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import math
import random
import time


class TupleState(Enum):
    LIVE = "LIVE"
    DEAD = "DEAD"
    REMOVED = "REMOVED"
    FROZEN = "FROZEN"


class VacuumMode(Enum):
    STANDARD = "STANDARD"
    FULL = "FULL"
    FREEZE = "FREEZE"


@dataclass
class TupleRecord:
    tuple_id: int
    value: str
    created_xid: int
    deleted_xid: Optional[int] = None
    state: TupleState = TupleState.LIVE
    page_id: int = 0

    def mark_dead(self, xid: int) -> None:
        if self.state != TupleState.LIVE:
            raise ValueError(f"Tuple {self.tuple_id} is not live")
        if xid <= self.created_xid:
            raise ValueError("Deletion transaction must follow insertion")
        self.deleted_xid = xid
        self.state = TupleState.DEAD


@dataclass
class VacuumReport:
    scanned: int
    live: int
    dead_before: int
    removed: int
    remaining_dead: int
    pages_before: int
    pages_after: int
    space_reclaimed: int
    frozen: int
    duration_seconds: float


@dataclass
class Table:
    name: str
    page_capacity: int = 100
    tuples: list[TupleRecord] = field(default_factory=list)
    next_id: int = 1
    next_page: int = 0
    physical_pages: int = 0
    dead_tuple_count: int = 0
    frozen_xid: int = 0
    analyze_count: int = 0
    last_vacuum: Optional[float] = None

    def insert(self, value: str, xid: int) -> TupleRecord:
        if not value:
            raise ValueError("Tuple value cannot be empty")
        if xid < 1:
            raise ValueError("Transaction ID must be positive")

        live_on_page = sum(
            1 for row in self.tuples
            if row.page_id == self.next_page
            and row.state in (TupleState.LIVE, TupleState.FROZEN)
        )

        if live_on_page >= self.page_capacity:
            self.next_page += 1

        record = TupleRecord(
            tuple_id=self.next_id,
            value=value,
            created_xid=xid,
            page_id=self.next_page
        )

        self.tuples.append(record)
        self.next_id += 1
        self.physical_pages = max(
            self.physical_pages,
            self.next_page + 1
        )
        return record

    def update(self, tuple_id: int, new_value: str, xid: int) -> TupleRecord:
        if not new_value:
            raise ValueError("Updated value cannot be empty")

        old = self.get_live_tuple(tuple_id)
        old.mark_dead(xid)
        self.dead_tuple_count += 1

        return self.insert(new_value, xid)

    def delete(self, tuple_id: int, xid: int) -> None:
        record = self.get_live_tuple(tuple_id)
        record.mark_dead(xid)
        self.dead_tuple_count += 1

    def get_live_tuple(self, tuple_id: int) -> TupleRecord:
        for record in self.tuples:
            if record.tuple_id == tuple_id and record.state in (
                TupleState.LIVE, TupleState.FROZEN
            ):
                return record
        raise KeyError(f"Live tuple {tuple_id} not found")

    def statistics(self) -> dict:
        live = sum(
            row.state in (TupleState.LIVE, TupleState.FROZEN)
            for row in self.tuples
        )
        dead = sum(row.state == TupleState.DEAD for row in self.tuples)

        return {
            "table": self.name,
            "live_tuples": live,
            "dead_tuples": dead,
            "physical_pages": self.physical_pages,
            "estimated_live_pages": math.ceil(live / self.page_capacity),
            "dead_ratio": round(
                dead / max(live + dead, 1) * 100, 2
            )
        }

    def vacuum(
        self,
        mode: VacuumMode = VacuumMode.STANDARD,
        oldest_active_xid: Optional[int] = None,
        current_xid: int = 1000
    ) -> VacuumReport:

        started = time.perf_counter()

        if oldest_active_xid is None:
            oldest_active_xid = current_xid + 1

        if oldest_active_xid < 1:
            raise ValueError("Invalid oldest active transaction ID")

        pages_before = self.physical_pages
        dead_before = sum(
            row.state == TupleState.DEAD for row in self.tuples
        )

        removed = 0
        frozen = 0

        for row in self.tuples:
            # A dead tuple cannot be removed while an older transaction
            # might still need its previous row version.
            if row.state == TupleState.DEAD:
                if row.deleted_xid is not None:
                    if row.deleted_xid < oldest_active_xid:
                        row.state = TupleState.REMOVED
                        removed += 1

            # Freezing prevents old transaction IDs from becoming unsafe.
            if row.state == TupleState.LIVE:
                if current_xid - row.created_xid >= 100:
                    if mode == VacuumMode.FREEZE:
                        row.state = TupleState.FROZEN
                        frozen += 1

        self.tuples = [
            row for row in self.tuples
            if row.state != TupleState.REMOVED
        ]

        self.dead_tuple_count = sum(
            row.state == TupleState.DEAD for row in self.tuples
        )

        if mode == VacuumMode.FULL:
            # VACUUM FULL rewrites the table and compacts its physical pages.
            live = sum(
                row.state in (TupleState.LIVE, TupleState.FROZEN)
                for row in self.tuples
            )
            self.physical_pages = math.ceil(
                live / self.page_capacity
            )
            self.next_page = max(self.physical_pages - 1, 0)

            for index, row in enumerate(self.tuples):
                row.page_id = index // self.page_capacity

        pages_after = self.physical_pages
        reclaimed = max(0, pages_before - pages_after)

        self.last_vacuum = time.time()

        return VacuumReport(
            scanned=len(self.tuples) + removed,
            live=sum(
                row.state in (TupleState.LIVE, TupleState.FROZEN)
                for row in self.tuples
            ),
            dead_before=dead_before,
            removed=removed,
            remaining_dead=self.dead_tuple_count,
            pages_before=pages_before,
            pages_after=pages_after,
            space_reclaimed=reclaimed,
            frozen=frozen,
            duration_seconds=round(
                time.perf_counter() - started, 6
            )
        )

    def analyze(self) -> dict:
        stats = self.statistics()
        self.analyze_count += 1

        return {
            "table": self.name,
            "analyze_count": self.analyze_count,
            "estimated_rows": stats["live_tuples"],
            "dead_ratio": stats["dead_ratio"],
            "message": "Planner statistics refreshed"
        }


@dataclass
class AutovacuumConfig:
    enabled: bool = True
    vacuum_threshold: int = 50
    scale_factor: float = 0.20
    analyze_threshold: int = 50
    analyze_scale_factor: float = 0.10
    max_dead_ratio: float = 0.25

    def __post_init__(self):
        if self.vacuum_threshold < 0:
            raise ValueError("Vacuum threshold cannot be negative")
        if self.analyze_threshold < 0:
            raise ValueError("Analyze threshold cannot be negative")
        if not 0 <= self.scale_factor <= 1:
            raise ValueError("Invalid vacuum scale factor")
        if not 0 <= self.analyze_scale_factor <= 1:
            raise ValueError("Invalid analyze scale factor")
        if not 0 <= self.max_dead_ratio <= 1:
            raise ValueError("Invalid dead tuple ratio")


class AutovacuumWorker:
    def __init__(self, config: AutovacuumConfig):
        self.config = config
        self.history = []

    def should_vacuum(self, table: Table) -> bool:
        stats = table.statistics()
        threshold = (
            self.config.vacuum_threshold
            + self.config.scale_factor * stats["live_tuples"]
        )

        return (
            stats["dead_tuples"] > threshold
            or stats["dead_ratio"] / 100 > self.config.max_dead_ratio
        )

    def should_analyze(self, table: Table) -> bool:
        stats = table.statistics()
        threshold = (
            self.config.analyze_threshold
            + self.config.analyze_scale_factor * stats["live_tuples"]
        )
        return stats["dead_tuples"] > threshold

    def process(
        self,
        table: Table,
        current_xid: int,
        oldest_active_xid: int
    ) -> Optional[VacuumReport]:

        if not self.config.enabled:
            return None

        report = None

        if self.should_vacuum(table):
            report = table.vacuum(
                VacuumMode.STANDARD,
                oldest_active_xid,
                current_xid
            )
            self.history.append(report)

        if self.should_analyze(table):
            table.analyze()

        return report


class TransactionManager:
    """Tracks active transactions to simulate MVCC visibility horizons."""

    def __init__(self):
        self.current_xid = 1
        self.active_transactions = set()

    def begin(self) -> int:
        xid = self.current_xid
        self.current_xid += 1
        self.active_transactions.add(xid)
        return xid

    def commit(self, xid: int) -> None:
        if xid not in self.active_transactions:
            raise ValueError("Transaction is not active")
        self.active_transactions.remove(xid)

    def oldest_active_xid(self) -> int:
        return min(self.active_transactions, default=self.current_xid)


def demonstrate():
    print("=" * 65)
    print("POSTGRESQL VACUUM AND GARBAGE COLLECTION SIMULATOR")
    print("=" * 65)

    manager = TransactionManager()
    table = Table("orders", page_capacity=10)

    # Insert initial records.
    insertion_xid = manager.begin()

    for number in range(35):
        table.insert(f"Order-{number}", insertion_xid)

    manager.commit(insertion_xid)

    print("\n1. INITIAL TABLE")
    print(table.statistics())

    # Keep an older transaction open while newer rows are deleted.
    old_transaction = manager.begin()
    deletion_transaction = manager.begin()

    for tuple_id in range(1, 16):
        table.delete(tuple_id, deletion_transaction)

    manager.commit(deletion_transaction)

    print("\n2. AFTER DELETE")
    print(table.statistics())

    # Dead versions remain because the older transaction is active.
    blocked_report = table.vacuum(
        VacuumMode.STANDARD,
        manager.oldest_active_xid(),
        manager.current_xid
    )

    print("\n3. VACUUM WITH OLD TRANSACTION ACTIVE")
    print(blocked_report)

    manager.commit(old_transaction)

    # The visibility horizon advances, allowing cleanup.
    report = table.vacuum(
        VacuumMode.STANDARD,
        manager.oldest_active_xid(),
        manager.current_xid
    )

    print("\n4. VACUUM AFTER TRANSACTION COMPLETION")
    print(report)

    # Generate additional dead tuples.
    for tuple_id in range(16, 26):
        xid = manager.begin()
        table.update(tuple_id, f"Updated-Order-{tuple_id}", xid)
        manager.commit(xid)

    print("\n5. AFTER UPDATES")
    print(table.statistics())

    config = AutovacuumConfig(
        vacuum_threshold=3,
        scale_factor=0.10,
        analyze_threshold=2,
        analyze_scale_factor=0.05
    )

    worker = AutovacuumWorker(config)

    print("\n6. AUTOVACUUM")
    print("Vacuum required:", worker.should_vacuum(table))

    auto_report = worker.process(
        table,
        manager.current_xid,
        manager.oldest_active_xid()
    )
    print("Autovacuum report:", auto_report)

    print("\n7. FREEZE OPERATION")
    freeze_report = table.vacuum(
        VacuumMode.FREEZE,
        manager.oldest_active_xid(),
        manager.current_xid + 200
    )
    print(freeze_report)

    print("\n8. VACUUM FULL")
    full_report = table.vacuum(
        VacuumMode.FULL,
        manager.oldest_active_xid(),
        manager.current_xid + 200
    )
    print(full_report)

    print("\n9. FINAL STATISTICS")
    print(table.statistics())
    print(table.analyze())

    print("\n10. EDGE CASE VALIDATION")

    try:
        table.delete(99999, manager.current_xid)
    except KeyError as error:
        print("Expected error:", error)

    try:
        AutovacuumConfig(scale_factor=1.5)
    except ValueError as error:
        print("Expected configuration error:", error)

    assert table.statistics()["dead_tuples"] >= 0
    assert table.physical_pages >= 0
    assert all(
        row.state != TupleState.REMOVED
        for row in table.tuples
    )

    print("\nAll validation checks passed.")


if __name__ == "__main__":
    demonstrate()
