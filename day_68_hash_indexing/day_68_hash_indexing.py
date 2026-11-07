"""
Hash Indexing: Hash Tables and Hash-Based Access

Demonstrates:
- Hash functions and bucket selection
- Separate chaining
- Collision handling
- Load factor and dynamic resizing
- Insertion, lookup, and deletion
- Tombstones and open addressing
- Duplicate-key handling
- Collision statistics
- Hash distribution analysis
- Security considerations
- Automated validation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar, Optional, Iterator
from collections import Counter
import hashlib
import json
import math
import secrets
import string


K = TypeVar("K")
V = TypeVar("V")


class HashIndexError(Exception):
    """Base exception for hash index operations."""


class InvalidKeyError(HashIndexError):
    """Raised when a key is invalid."""


@dataclass
class Entry(Generic[K, V]):
    key: K
    value: V


@dataclass
class HashStatistics:
    capacity: int
    size: int
    load_factor: float
    occupied_buckets: int
    empty_buckets: int
    maximum_chain_length: int
    average_chain_length: float
    collisions: int


class ChainedHashTable(Generic[K, V]):
    """
    Hash table using separate chaining.

    Average lookup: O(1) under a suitable hash distribution.
    Worst-case lookup: O(n).
    """

    def __init__(
        self,
        capacity: int = 8,
        max_load_factor: float = 0.75
    ) -> None:
        if capacity < 2:
            raise ValueError("Capacity must be at least 2.")

        if not 0.25 <= max_load_factor <= 2.0:
            raise ValueError("Load factor must be between 0.25 and 2.0.")

        self._buckets: list[list[Entry[K, V]]] = [
            [] for _ in range(capacity)
        ]
        self._size = 0
        self._max_load_factor = max_load_factor
        self._collisions = 0

    @property
    def capacity(self) -> int:
        return len(self._buckets)

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key: K) -> bool:
        try:
            self.get(key)
            return True
        except KeyError:
            return False

    def _validate_key(self, key: K) -> None:
        if key is None:
            raise InvalidKeyError("None is not a valid key.")

        try:
            hash(key)
        except TypeError as exc:
            raise InvalidKeyError(
                "Keys must be hashable."
            ) from exc

    def _index(self, key: K, capacity: Optional[int] = None) -> int:
        self._validate_key(key)
        actual_capacity = capacity or self.capacity
        return hash(key) % actual_capacity

    def _find_entry(self, key: K) -> Optional[Entry[K, V]]:
        index = self._index(key)

        for entry in self._buckets[index]:
            if entry.key == key:
                return entry

        return None

    def put(self, key: K, value: V) -> None:
        self._validate_key(key)

        existing = self._find_entry(key)

        if existing is not None:
            existing.value = value
            return

        if (self._size + 1) / self.capacity > self._max_load_factor:
            self._resize(self.capacity * 2)

        index = self._index(key)

        if self._buckets[index]:
            self._collisions += 1

        self._buckets[index].append(Entry(key, value))
        self._size += 1

    def get(self, key: K) -> V:
        entry = self._find_entry(key)

        if entry is None:
            raise KeyError(f"Key not found: {key!r}")

        return entry.value

    def get_or_default(self, key: K, default: V) -> V:
        entry = self._find_entry(key)
        return entry.value if entry is not None else default

    def remove(self, key: K) -> V:
        index = self._index(key)
        bucket = self._buckets[index]

        for position, entry in enumerate(bucket):
            if entry.key == key:
                removed = bucket.pop(position)
                self._size -= 1
                return removed.value

        raise KeyError(f"Key not found: {key!r}")

    def _resize(self, new_capacity: int) -> None:
        old_buckets = self._buckets

        self._buckets = [[] for _ in range(new_capacity)]
        self._size = 0

        for bucket in old_buckets:
            for entry in bucket:
                index = self._index(entry.key)
                self._buckets[index].append(entry)
                self._size += 1

    def items(self) -> Iterator[tuple[K, V]]:
        for bucket in self._buckets:
            for entry in bucket:
                yield entry.key, entry.value

    def statistics(self) -> HashStatistics:
        lengths = [len(bucket) for bucket in self._buckets]
        occupied = sum(length > 0 for length in lengths)

        return HashStatistics(
            capacity=self.capacity,
            size=self._size,
            load_factor=self._size / self.capacity,
            occupied_buckets=occupied,
            empty_buckets=self.capacity - occupied,
            maximum_chain_length=max(lengths, default=0),
            average_chain_length=(
                self._size / occupied if occupied else 0.0
            ),
            collisions=self._collisions
        )

    def display(self) -> None:
        for index, bucket in enumerate(self._buckets):
            contents = [
                f"{entry.key!r}: {entry.value!r}"
                for entry in bucket
            ]
            print(f"Bucket {index}: {contents}")


class OpenAddressHashTable(Generic[K, V]):
    """
    Linear-probing hash table.

    Uses tombstones to distinguish deleted slots from never-used slots.
    """

    EMPTY = object()
    DELETED = object()

    def __init__(self, capacity: int = 8) -> None:
        if capacity < 2:
            raise ValueError("Capacity must be at least 2.")

        self._slots: list[object] = [self.EMPTY] * capacity
        self._size = 0
        self._deleted = 0

    @property
    def capacity(self) -> int:
        return len(self._slots)

    def _index(self, key: K) -> int:
        if key is None:
            raise InvalidKeyError("None is not a valid key.")

        try:
            return hash(key) % self.capacity
        except TypeError as exc:
            raise InvalidKeyError(
                "Keys must be hashable."
            ) from exc

    def put(self, key: K, value: V) -> None:
        start = self._index(key)

        # Resize before the occupied and deleted slots become excessive.
        if (self._size + self._deleted + 1) / self.capacity > 0.65:
            self._resize(self.capacity * 2)

        first_deleted = None

        for offset in range(self.capacity):
            index = (start + offset) % self.capacity
            slot = self._slots[index]

            if slot is self.EMPTY:
                target = (
                    first_deleted if first_deleted is not None else index
                )

                if first_deleted is not None:
                    self._deleted -= 1

                self._slots[target] = Entry(key, value)
                self._size += 1
                return

            if slot is self.DELETED:
                if first_deleted is None:
                    first_deleted = index
                continue

            if slot.key == key:
                slot.value = value
                return

        if first_deleted is not None:
            self._slots[first_deleted] = Entry(key, value)
            self._deleted -= 1
            self._size += 1
            return

        self._resize(self.capacity * 2)
        self.put(key, value)

    def get(self, key: K) -> V:
        start = self._index(key)

        for offset in range(self.capacity):
            index = (start + offset) % self.capacity
            slot = self._slots[index]

            if slot is self.EMPTY:
                break

            if slot is self.DELETED:
                continue

            if slot.key == key:
                return slot.value

        raise KeyError(f"Key not found: {key!r}")

    def remove(self, key: K) -> V:
        start = self._index(key)

        for offset in range(self.capacity):
            index = (start + offset) % self.capacity
            slot = self._slots[index]

            if slot is self.EMPTY:
                break

            if slot is self.DELETED:
                continue

            if slot.key == key:
                self._slots[index] = self.DELETED
                self._size -= 1
                self._deleted += 1
                return slot.value

        raise KeyError(f"Key not found: {key!r}")

    def _resize(self, capacity: int) -> None:
        old_slots = self._slots

        self._slots = [self.EMPTY] * capacity
        self._size = 0
        self._deleted = 0

        for slot in old_slots:
            if isinstance(slot, Entry):
                self.put(slot.key, slot.value)

    def statistics(self) -> dict[str, float | int]:
        return {
            "capacity": self.capacity,
            "size": self._size,
            "deleted_slots": self._deleted,
            "load_factor": self._size / self.capacity
        }


def stable_hash(value: str) -> str:
    """Cryptographic digest for stable identifiers and integrity checks."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def demonstrate_hash_functions() -> None:
    print("\nHASH FUNCTION DEMONSTRATION")

    keys = ["customer-101", "customer-102", "customer-103"]

    for key in keys:
        print(
            f"{key}: "
            f"Python hash={hash(key)}, "
            f"SHA-256={stable_hash(key)[:20]}..."
        )

    print(
        "Note: Python hash() values for strings can vary "
        "between interpreter processes."
    )


def analyze_distribution(keys: list[str], capacity: int) -> None:
    if capacity < 2:
        raise ValueError("Capacity must be at least 2.")

    distribution = Counter(hash(key) % capacity for key in keys)

    print("\nHASH DISTRIBUTION")
    print(f"Keys analyzed: {len(keys)}")
    print(f"Bucket capacity: {capacity}")

    for bucket in range(capacity):
        print(f"Bucket {bucket}: {distribution[bucket]} keys")

    occupied = len(distribution)
    collisions = len(keys) - occupied

    print(f"Occupied buckets: {occupied}")
    print(f"Excess keys sharing occupied buckets: {collisions}")


def demonstrate_chaining() -> None:
    print("\nSEPARATE CHAINING")

    index: ChainedHashTable[str, dict] = ChainedHashTable(
        capacity=4,
        max_load_factor=0.75
    )

    customers = [
        ("CUST-1001", {"name": "Aarav", "balance": 12500}),
        ("CUST-1002", {"name": "Diya", "balance": 18400}),
        ("CUST-1003", {"name": "Kabir", "balance": 9200}),
        ("CUST-1004", {"name": "Meera", "balance": 22100}),
        ("CUST-1005", {"name": "Ishaan", "balance": 15800})
    ]

    for key, customer in customers:
        index.put(key, customer)

    print("Customer lookup:", index.get("CUST-1003"))

    # Updating an existing key does not increase table size.
    index.put(
        "CUST-1003",
        {"name": "Kabir", "balance": 10500}
    )

    print("Updated customer:", index.get("CUST-1003"))
    print("Table statistics:", index.statistics())

    index.remove("CUST-1002")
    print("After deletion:", len(index))

    try:
        index.get("CUST-1002")
    except KeyError as error:
        print("Expected missing-key condition:", error)


def demonstrate_open_addressing() -> None:
    print("\nOPEN ADDRESSING")

    index: OpenAddressHashTable[str, str] = (
        OpenAddressHashTable(capacity=8)
    )

    index.put("EMP-101", "Engineering")
    index.put("EMP-102", "Security")
    index.put("EMP-103", "Research")

    print("EMP-102 department:", index.get("EMP-102"))

    index.remove("EMP-102")

    try:
        index.get("EMP-102")
    except KeyError:
        print("Deleted key correctly reported as absent.")

    # A later insertion must still be able to probe past tombstones.
    index.put("EMP-104", "Operations")

    print("EMP-104 department:", index.get("EMP-104"))
    print("Open addressing statistics:", index.statistics())


def demonstrate_collision_comparison() -> None:
    print("\nCOLLISION HANDLING COMPARISON")

    keys = ["A", "B", "C", "D", "E", "F"]

    chained = ChainedHashTable[str, int](capacity=4)

    for number, key in enumerate(keys):
        chained.put(key, number)

    open_table = OpenAddressHashTable[str, int](capacity=8)

    for number, key in enumerate(keys):
        open_table.put(key, number)

    print("Chaining:", chained.statistics())
    print("Open addressing:", open_table.statistics())


def demonstrate_validation() -> None:
    print("\nVALIDATION")

    index = ChainedHashTable[str, int]()

    try:
        index.put(None, 100)  # type: ignore[arg-type]
    except InvalidKeyError as error:
        print("Invalid key rejected:", error)

    try:
        index.put(["mutable", "key"], 100)  # type: ignore[arg-type]
    except InvalidKeyError as error:
        print("Unhashable key rejected:", error)


def demonstrate_security() -> None:
    print("\nSECURITY CONSIDERATIONS")

    # A random process-local seed makes predictable collision construction
    # more difficult for an attacker.
    seed = secrets.token_bytes(16)

    def keyed_hash(key: str) -> int:
        digest = hashlib.blake2b(
            key.encode("utf-8"),
            key=seed,
            digest_size=8
        ).digest()
        return int.from_bytes(digest, "big")

    for value in ["user-1", "user-2", "user-3"]:
        print(f"{value}: {keyed_hash(value)}")

    print("Never use a non-cryptographic hash as an authentication token.")
    print("Limit untrusted input sizes and monitor collision behavior.")


def run_tests() -> None:
    table = ChainedHashTable[str, int](capacity=2)

    table.put("A", 10)
    table.put("B", 20)
    table.put("A", 15)

    assert table.get("A") == 15
    assert table.get("B") == 20
    assert len(table) == 2

    assert table.remove("A") == 15
    assert len(table) == 1

    try:
        table.get("A")
        raise AssertionError("Missing-key lookup should fail.")
    except KeyError:
        pass

    open_table = OpenAddressHashTable[str, int](capacity=4)

    open_table.put("A", 1)
    open_table.put("B", 2)
    open_table.remove("A")
    open_table.put("C", 3)

    assert open_table.get("B") == 2
    assert open_table.get("C") == 3

    # Updating an existing key must not create a duplicate.
    open_table.put("B", 22)
    assert open_table.get("B") == 22

    assert stable_hash("test") == stable_hash("test")
    assert len(stable_hash("test")) == 64

    print("\nAll automated assertions passed.")


def main() -> None:
    print("=" * 65)
    print("HASH INDEXING: PRACTICAL IMPLEMENTATION")
    print("=" * 65)

    demonstrate_hash_functions()
    demonstrate_chaining()
    demonstrate_open_addressing()
    demonstrate_collision_comparison()

    analyze_distribution(
        ["customer-1", "customer-2", "customer-3",
         "customer-4", "customer-5"],
        capacity=8
    )

    demonstrate_validation()
    demonstrate_security()
    run_tests()

    print("\nPERFORMANCE CHARACTERISTICS")
    print("Average insertion: O(1)")
    print("Average lookup:    O(1)")
    print("Average deletion:  O(1)")
    print("Worst-case access: O(n)")
    print("Resizing:          O(n)")
    print("Space complexity:  O(n + m), where m is bucket capacity.")


if __name__ == "__main__":
    main()
