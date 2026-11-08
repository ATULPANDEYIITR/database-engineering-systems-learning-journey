#!/usr/bin/env python3
"""
LSM Trees: Log-Structured Merge Trees and Write Optimization

Implements:
- Mutable in-memory memtable
- Write-ahead log (WAL)
- Immutable sorted string tables (SSTables)
- Buffered writes and flush operations
- Point lookups and tombstones
- Bloom filters
- Sparse indexes
- Multi-level storage
- Size-tiered compaction
- Range scans
- Storage statistics and validation

Python 3.10+
Standard library only.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import os
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Iterator


class Operation(Enum):
    PUT = "PUT"
    DELETE = "DELETE"


@dataclass(frozen=True)
class Entry:
    key: str
    value: Optional[str]
    sequence: int
    operation: Operation
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.key:
            raise ValueError("Key cannot be empty")
        if self.sequence < 1:
            raise ValueError("Sequence must be positive")
        if self.operation == Operation.PUT and self.value is None:
            raise ValueError("PUT requires a value")
        if self.operation == Operation.DELETE and self.value is not None:
            raise ValueError("DELETE must not contain a value")


class BloomFilter:
    """Probabilistic membership structure with no false negatives."""

    def __init__(self, capacity: int = 1000, error_rate: float = 0.01):
        if capacity < 1:
            raise ValueError("Capacity must be positive")
        if not 0 < error_rate < 1:
            raise ValueError("Error rate must be between 0 and 1")

        self.capacity = capacity
        self.error_rate = error_rate
        self.bit_count = max(
            8,
            math.ceil(
                -capacity * math.log(error_rate) / math.log(2) ** 2
            )
        )
        self.hash_count = max(
            1,
            round(self.bit_count / capacity * math.log(2))
        )
        self.bits = bytearray((self.bit_count + 7) // 8)

    def _positions(self, key: str):
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        first = int.from_bytes(digest[:16], "big")
        second = int.from_bytes(digest[16:], "big") | 1

        for index in range(self.hash_count):
            yield (first + index * second) % self.bit_count

    def add(self, key: str):
        for position in self._positions(key):
            self.bits[position // 8] |= 1 << (position % 8)

    def might_contain(self, key: str) -> bool:
        return all(
            self.bits[position // 8] & (1 << (position % 8))
            for position in self._positions(key)
        )


@dataclass
class SSTable:
    table_id: int
    level: int
    entries: list[Entry]
    index_interval: int = 4
    bloom: BloomFilter = field(init=False)
    sparse_keys: list[str] = field(init=False)
    sparse_positions: list[int] = field(init=False)
    min_key: str = field(init=False)
    max_key: str = field(init=False)

    def __post_init__(self):
        if not self.entries:
            raise ValueError("SSTable cannot be empty")

        self.entries.sort(key=lambda entry: entry.key)

        keys = [entry.key for entry in self.entries]

        if len(keys) != len(set(keys)):
            raise ValueError("SSTable must contain unique keys")

        if self.index_interval < 1:
            raise ValueError("Index interval must be positive")

        self.min_key = keys[0]
        self.max_key = keys[-1]

        self.bloom = BloomFilter(max(len(keys), 1))
        self.sparse_keys = []
        self.sparse_positions = []

        for position, entry in enumerate(self.entries):
            self.bloom.add(entry.key)

            if position % self.index_interval == 0:
                self.sparse_keys.append(entry.key)
                self.sparse_positions.append(position)

    def get(self, key: str) -> Optional[Entry]:
        if key < self.min_key or key > self.max_key:
            return None

        if not self.bloom.might_contain(key):
            return None

        index = bisect.bisect_right(self.sparse_keys, key) - 1

        if index < 0:
            start = 0
        else:
            start = self.sparse_positions[index]

        end = min(start + self.index_interval + 1, len(self.entries))

        keys = [self.entries[i].key for i in range(start, end)]
        position = bisect.bisect_left(keys, key)

        if position < len(keys) and keys[position] == key:
            return self.entries[start + position]

        return None

    def range_scan(self, start: str, end: str) -> Iterator[Entry]:
        if start > end:
            raise ValueError("Range start must not exceed range end")

        keys = [entry.key for entry in self.entries]
        position = bisect.bisect_left(keys, start)

        while position < len(self.entries):
            entry = self.entries[position]

            if entry.key > end:
                break

            yield entry
            position += 1


class WriteAheadLog:
    """Append-only WAL with one JSON record per operation."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def append(self, entry: Entry):
        record = {
            "key": entry.key,
            "value": entry.value,
            "sequence": entry.sequence,
            "operation": entry.operation.value,
            "timestamp": entry.timestamp,
        }

        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")
            file.flush()
            os.fsync(file.fileno())

    def recover(self) -> list[Entry]:
        recovered = []

        with self.path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, 1):
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)
                    recovered.append(
                        Entry(
                            key=record["key"],
                            value=record["value"],
                            sequence=record["sequence"],
                            operation=Operation(record["operation"]),
                            timestamp=record["timestamp"],
                        )
                    )
                except (ValueError, KeyError, TypeError) as error:
                    raise RuntimeError(
                        f"Invalid WAL record at line {line_number}"
                    ) from error

        return recovered

    def truncate(self):
        with self.path.open("w", encoding="utf-8") as file:
            file.flush()
            os.fsync(file.fileno())


class LSMTree:
    """
    Educational LSM implementation.

    Level 0 contains newly flushed runs.
    Higher levels contain compacted runs.
    A sequence number determines the newest version.
    """

    def __init__(
        self,
        memtable_limit: int = 4,
        level_capacity: int = 3,
        index_interval: int = 4,
        wal_path: Optional[Path] = None,
    ):
        if memtable_limit < 1 or level_capacity < 2:
            raise ValueError("Invalid storage thresholds")

        self.memtable_limit = memtable_limit
        self.level_capacity = level_capacity
        self.index_interval = index_interval

        self.memtable: dict[str, Entry] = {}
        self.levels: dict[int, list[SSTable]] = {0: []}

        self.sequence = 0
        self.table_sequence = 0

        self.wal = WriteAheadLog(
            wal_path or Path("lsm_data") / "wal.jsonl"
        )

    def _next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence

    def put(self, key: str, value: str):
        if not isinstance(key, str) or not key:
            raise ValueError("Key must be a non-empty string")
        if not isinstance(value, str):
            raise ValueError("Value must be a string")

        entry = Entry(
            key=key,
            value=value,
            sequence=self._next_sequence(),
            operation=Operation.PUT,
        )

        # Persist the log record before acknowledging the write.
        self.wal.append(entry)
        self.memtable[key] = entry

        if len(self.memtable) >= self.memtable_limit:
            self.flush()

    def delete(self, key: str):
        if not isinstance(key, str) or not key:
            raise ValueError("Key must be a non-empty string")

        entry = Entry(
            key=key,
            value=None,
            sequence=self._next_sequence(),
            operation=Operation.DELETE,
        )

        self.wal.append(entry)
        self.memtable[key] = entry

        if len(self.memtable) >= self.memtable_limit:
            self.flush()

    def _all_entries(self) -> list[Entry]:
        entries = list(self.memtable.values())

        for tables in self.levels.values():
            for table in tables:
                entries.extend(table.entries)

        return entries

    def get(self, key: str) -> Optional[str]:
        candidates = []

        current = self.memtable.get(key)
        if current:
            candidates.append(current)

        # Search recent runs first. Sequence numbers still determine
        # the correct result when runs overlap.
        for level in sorted(self.levels):
            for table in reversed(self.levels[level]):
                entry = table.get(key)

                if entry:
                    candidates.append(entry)

        if not candidates:
            return None

        newest = max(candidates, key=lambda entry: entry.sequence)

        if newest.operation == Operation.DELETE:
            return None

        return newest.value

    def flush(self):
        if not self.memtable:
            return

        entries = sorted(
            self.memtable.values(),
            key=lambda entry: entry.key
        )

        self.table_sequence += 1

        table = SSTable(
            table_id=self.table_sequence,
            level=0,
            entries=entries,
            index_interval=self.index_interval,
        )

        self.levels.setdefault(0, []).append(table)

        self.memtable.clear()

        # The WAL is retained in this educational implementation.
        # Production systems rotate logs only after durable flushes.
        self._check_compaction(0)

    def _check_compaction(self, level: int):
        tables = self.levels.setdefault(level, [])

        if len(tables) < self.level_capacity:
            return

        self.compact(level)

    def compact(self, level: int = 0):
        tables = self.levels.setdefault(level, [])

        if len(tables) < 2:
            return

        all_entries = {}

        # Keep the newest version of every key.
        for table in tables:
            for entry in table.entries:
                previous = all_entries.get(entry.key)

                if previous is None or entry.sequence > previous.sequence:
                    all_entries[entry.key] = entry

        # Tombstones are retained because this simple model does not
        # track lower-level overlap or external snapshots.
        compacted = sorted(
            all_entries.values(),
            key=lambda entry: entry.key
        )

        if not compacted:
            return

        self.table_sequence += 1
        next_level = level + 1

        output = SSTable(
            table_id=self.table_sequence,
            level=next_level,
            entries=compacted,
            index_interval=self.index_interval,
        )

        # Replace input runs only after the output has been constructed.
        self.levels[level] = []
        self.levels.setdefault(next_level, []).append(output)

        self._check_compaction(next_level)

    def range_scan(self, start: str, end: str) -> dict[str, str]:
        if start > end:
            raise ValueError("Invalid range")

        latest = {}

        for entry in self._all_entries():
            if start <= entry.key <= end:
                previous = latest.get(entry.key)

                if previous is None or entry.sequence > previous.sequence:
                    latest[entry.key] = entry

        return {
            key: entry.value
            for key, entry in sorted(latest.items())
            if entry.operation == Operation.PUT
        }

    def recover_from_wal(self):
        """Rebuild the memtable from the complete retained WAL."""
        self.memtable.clear()
        self.sequence = 0

        for entry in self.wal.recover():
            self.sequence = max(self.sequence, entry.sequence)

            previous = self.memtable.get(entry.key)

            if previous is None or entry.sequence > previous.sequence:
                self.memtable[entry.key] = entry

        if len(self.memtable) >= self.memtable_limit:
            self.flush()

    def statistics(self) -> dict:
        total_tables = sum(len(items) for items in self.levels.values())

        return {
            "sequence": self.sequence,
            "memtable_keys": len(self.memtable),
            "sstable_count": total_tables,
            "levels": {
                level: {
                    "runs": len(tables),
                    "entries": sum(len(t.entries) for t in tables),
                }
                for level, tables in sorted(self.levels.items())
            },
            "total_physical_entries": sum(
                len(table.entries)
                for tables in self.levels.values()
                for table in tables
            ),
            "wal_bytes": self.wal.path.stat().st_size,
        }

    def validate(self):
        seen_ids = set()

        for level, tables in self.levels.items():
            for table in tables:
                if table.level != level:
                    raise AssertionError("Incorrect SSTable level")

                if table.table_id in seen_ids:
                    raise AssertionError("Duplicate SSTable ID")

                seen_ids.add(table.table_id)

                keys = [entry.key for entry in table.entries]

                if keys != sorted(keys):
                    raise AssertionError("SSTable is not sorted")

                if len(keys) != len(set(keys)):
                    raise AssertionError("Duplicate key in SSTable")

        for entry in self.memtable.values():
            if entry.sequence > self.sequence:
                raise AssertionError("Invalid sequence number")

        return True


def run_demonstration():
    with tempfile.TemporaryDirectory() as directory:
        tree = LSMTree(
            memtable_limit=3,
            level_capacity=2,
            index_interval=2,
            wal_path=Path(directory) / "wal.jsonl",
        )

        print("\nINITIAL WRITES")
        tree.put("user:101", "Alice")
        tree.put("user:102", "Bob")
        tree.put("user:103", "Charlie")

        print("After automatic flush:", tree.statistics())

        print("\nUPDATES AND DELETIONS")
        tree.put("user:102", "Robert")
        tree.delete("user:103")
        tree.put("user:104", "Diana")

        print("user:102 =", tree.get("user:102"))
        print("user:103 =", tree.get("user:103"))
        print("user:104 =", tree.get("user:104"))

        print("\nRANGE SCAN")
        print(tree.range_scan("user:101", "user:104"))

        print("\nCOMPACTION")
        tree.flush()
        tree.compact(0)

        print(tree.statistics())

        print("\nVALIDATION")
        assert tree.validate()

        assert tree.get("user:101") == "Alice"
        assert tree.get("user:102") == "Robert"
        assert tree.get("user:103") is None
        assert tree.get("user:104") == "Diana"

        print("All LSM invariants passed.")

        print("\nWAL RECOVERY")
        recovered = LSMTree(
            memtable_limit=100,
            wal_path=Path(directory) / "wal.jsonl",
        )

        recovered.recover_from_wal()

        assert recovered.get("user:102") == "Robert"
        assert recovered.get("user:103") is None

        print("Recovery validation passed.")


if __name__ == "__main__":
    run_demonstration()
