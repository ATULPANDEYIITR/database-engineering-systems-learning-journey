#!/usr/bin/env python3
"""
Index Internals: B-trees, tree traversal, and index pages.

Implements a disk-page-inspired B+ tree with:
- Sorted leaf entries and linked leaves.
- Internal separator keys and child pointers.
- Search, insertion, deletion, range scans, and traversal.
- Page splitting, borrowing, merging, and root contraction.
- Structural validation and page statistics.
- A simple buffer-pool and LRU cache simulation.

Run:
    python index_internals.py
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional
import bisect
import json
import random


class IndexErrorBase(Exception):
    """Base exception for index operations."""


class DuplicateKeyError(IndexErrorBase):
    pass


class KeyNotFoundError(IndexErrorBase):
    pass


class IndexInvariantError(IndexErrorBase):
    pass


@dataclass
class IndexEntry:
    key: int
    value: str


@dataclass
class BPlusNode:
    page_id: int
    leaf: bool
    keys: list[int] = field(default_factory=list)
    children: list["BPlusNode"] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    next_leaf: Optional["BPlusNode"] = None
    parent: Optional["BPlusNode"] = None

    def __repr__(self) -> str:
        kind = "Leaf" if self.leaf else "Internal"
        return f"{kind}(page={self.page_id}, keys={self.keys})"


class BPlusTree:
    """
    In-memory B+ tree.

    order is the maximum number of children in an internal page.
    A leaf can contain at most order - 1 entries.
    """

    def __init__(self, order: int = 4):
        if order < 3:
            raise ValueError("B+ tree order must be at least 3")

        self.order = order
        self.max_keys = order - 1
        self.min_leaf_keys = (self.max_keys + 1) // 2
        self.min_internal_children = (order + 1) // 2
        self.next_page_id = 1
        self.root = self._new_node(True)
        self.size = 0
        self.page_reads = 0
        self.page_writes = 0

    def _new_node(self, leaf: bool) -> BPlusNode:
        node = BPlusNode(self.next_page_id, leaf)
        self.next_page_id += 1
        return node

    def _read(self, node: BPlusNode) -> BPlusNode:
        self.page_reads += 1
        return node

    def _write(self, node: BPlusNode) -> None:
        self.page_writes += 1

    def _minimum(self, node: BPlusNode) -> int:
        while not node.leaf:
            node = node.children[0]
        return node.keys[0]

    def _refresh_keys(self, node: BPlusNode) -> None:
        if node.leaf:
            return

        node.keys = [
            self._minimum(child)
            for child in node.children[1:]
        ]

    def _find_leaf(self, key: int) -> BPlusNode:
        node = self.root

        while not node.leaf:
            self._read(node)
            index = bisect.bisect_right(node.keys, key)
            node = node.children[index]

        self._read(node)
        return node

    def search(self, key: int) -> Optional[str]:
        """Return the value associated with a key."""
        leaf = self._find_leaf(key)
        index = bisect.bisect_left(leaf.keys, key)

        if index < len(leaf.keys) and leaf.keys[index] == key:
            return leaf.values[index]

        return None

    def insert(self, key: int, value: str) -> None:
        if not isinstance(key, int) or isinstance(key, bool):
            raise TypeError("Keys must be integers")

        if not isinstance(value, str):
            raise TypeError("Values must be strings")

        leaf = self._find_leaf(key)
        index = bisect.bisect_left(leaf.keys, key)

        if index < len(leaf.keys) and leaf.keys[index] == key:
            raise DuplicateKeyError(f"Duplicate key: {key}")

        leaf.keys.insert(index, key)
        leaf.values.insert(index, value)
        self.size += 1
        self._write(leaf)

        if len(leaf.keys) > self.max_keys:
            self._split_leaf(leaf)

        self._repair_ancestors(leaf.parent)

    def _split_leaf(self, leaf: BPlusNode) -> None:
        middle = len(leaf.keys) // 2
        right = self._new_node(True)

        right.keys = leaf.keys[middle:]
        right.values = leaf.values[middle:]

        leaf.keys = leaf.keys[:middle]
        leaf.values = leaf.values[:middle]

        right.next_leaf = leaf.next_leaf
        leaf.next_leaf = right

        self._write(leaf)
        self._write(right)
        self._insert_parent(leaf, right)

    def _insert_parent(
        self,
        left: BPlusNode,
        right: BPlusNode
    ) -> None:
        parent = left.parent

        if parent is None:
            parent = self._new_node(False)
            parent.children = [left, right]
            left.parent = parent
            right.parent = parent
            self._refresh_keys(parent)
            self.root = parent
            self._write(parent)
            return

        index = parent.children.index(left)
        parent.children.insert(index + 1, right)
        right.parent = parent
        self._refresh_keys(parent)
        self._write(parent)

        if len(parent.children) > self.order:
            self._split_internal(parent)

    def _split_internal(self, node: BPlusNode) -> None:
        middle = len(node.children) // 2
        right = self._new_node(False)

        right.children = node.children[middle:]
        node.children = node.children[:middle]

        for child in right.children:
            child.parent = right

        self._refresh_keys(node)
        self._refresh_keys(right)
        self._write(node)
        self._write(right)

        self._insert_parent(node, right)

    def _repair_ancestors(
        self,
        node: Optional[BPlusNode]
    ) -> None:
        while node is not None:
            self._refresh_keys(node)
            self._write(node)
            node = node.parent

    def range_scan(
        self,
        start: int,
        end: int
    ) -> list[tuple[int, str]]:
        if start > end:
            return []

        leaf = self._find_leaf(start)
        results = []

        while leaf is not None:
            self._read(leaf)

            for key, value in zip(leaf.keys, leaf.values):
                if key > end:
                    return results

                if key >= start:
                    results.append((key, value))

            leaf = leaf.next_leaf

        return results

    def traverse(self) -> list[int]:
        """Return keys in ascending order using linked leaves."""
        results = []
        node = self.root

        while not node.leaf:
            node = node.children[0]

        while node is not None:
            self._read(node)
            results.extend(node.keys)
            node = node.next_leaf

        return results

    def delete(self, key: int) -> None:
        leaf = self._find_leaf(key)
        index = bisect.bisect_left(leaf.keys, key)

        if index == len(leaf.keys) or leaf.keys[index] != key:
            raise KeyNotFoundError(f"Key not found: {key}")

        leaf.keys.pop(index)
        leaf.values.pop(index)
        self.size -= 1
        self._write(leaf)

        if leaf is self.root:
            return

        if len(leaf.keys) < self.min_leaf_keys:
            self._rebalance_leaf(leaf)

        self._repair_ancestors(leaf.parent)

    def _rebalance_leaf(self, leaf: BPlusNode) -> None:
        parent = leaf.parent
        index = parent.children.index(leaf)

        left = parent.children[index - 1] if index > 0 else None
        right = (
            parent.children[index + 1]
            if index + 1 < len(parent.children)
            else None
        )

        if left and len(left.keys) > self.min_leaf_keys:
            leaf.keys.insert(0, left.keys.pop())
            leaf.values.insert(0, left.values.pop())
            self._write(left)
            self._write(leaf)

        elif right and len(right.keys) > self.min_leaf_keys:
            leaf.keys.append(right.keys.pop(0))
            leaf.values.append(right.values.pop(0))
            self._write(right)
            self._write(leaf)

        elif left:
            left.keys.extend(leaf.keys)
            left.values.extend(leaf.values)
            left.next_leaf = leaf.next_leaf
            parent.children.pop(index)
            self._write(left)
            self._repair_internal(parent)

        elif right:
            leaf.keys.extend(right.keys)
            leaf.values.extend(right.values)
            leaf.next_leaf = right.next_leaf
            parent.children.pop(index + 1)
            self._write(leaf)
            self._repair_internal(parent)

    def _repair_internal(self, node: BPlusNode) -> None:
        if node is self.root:
            if len(node.children) == 1:
                self.root = node.children[0]
                self.root.parent = None
            else:
                self._refresh_keys(node)
            return

        self._refresh_keys(node)

        if len(node.children) >= self.min_internal_children:
            self._repair_ancestors(node.parent)
            return

        parent = node.parent
        index = parent.children.index(node)

        left = parent.children[index - 1] if index > 0 else None
        right = (
            parent.children[index + 1]
            if index + 1 < len(parent.children)
            else None
        )

        if left and len(left.children) > self.min_internal_children:
            child = left.children.pop()
            node.children.insert(0, child)
            child.parent = node

        elif right and len(right.children) > self.min_internal_children:
            child = right.children.pop(0)
            node.children.append(child)
            child.parent = node

        elif left:
            left.children.extend(node.children)
            for child in node.children:
                child.parent = left
            parent.children.pop(index)
            self._refresh_keys(left)

        elif right:
            node.children.extend(right.children)
            for child in right.children:
                child.parent = node
            parent.children.pop(index + 1)

        self._refresh_keys(parent)
        self._write(parent)
        self._repair_internal(parent)

    def page_layout(self) -> list[dict[str, Any]]:
        """Return a breadth-first representation of index pages."""
        queue = [self.root]
        pages = []

        while queue:
            node = queue.pop(0)

            pages.append({
                "page_id": node.page_id,
                "type": "leaf" if node.leaf else "internal",
                "keys": node.keys.copy(),
                "key_count": len(node.keys),
                "children": [
                    child.page_id for child in node.children
                ],
                "next_leaf": (
                    node.next_leaf.page_id
                    if node.next_leaf else None
                )
            })

            queue.extend(node.children)

        return pages

    def height(self) -> int:
        height = 0
        node = self.root

        while True:
            height += 1
            if node.leaf:
                return height
            node = node.children[0]

    def validate(self) -> bool:
        """Check ordering, occupancy, parent pointers and leaf links."""
        leaves = []
        visited = set()

        def inspect(
            node: BPlusNode,
            is_root: bool
        ) -> tuple[int, int]:
            if node.page_id in visited:
                raise IndexInvariantError("Page cycle detected")

            visited.add(node.page_id)

            if node.leaf:
                if len(node.keys) != len(node.values):
                    raise IndexInvariantError("Leaf value mismatch")

                if node.keys != sorted(set(node.keys)):
                    raise IndexInvariantError("Leaf keys are not unique")

                if not is_root and len(node.keys) < self.min_leaf_keys:
                    raise IndexInvariantError("Leaf underflow")

                if len(node.keys) > self.max_keys:
                    raise IndexInvariantError("Leaf overflow")

                leaves.append(node)
                return (
                    node.keys[0] if node.keys else float("inf"),
                    node.keys[-1] if node.keys else float("-inf")
                )

            if len(node.children) != len(node.keys) + 1:
                raise IndexInvariantError("Internal child count mismatch")

            if len(node.children) > self.order:
                raise IndexInvariantError("Internal overflow")

            if is_root:
                if len(node.children) < 2:
                    raise IndexInvariantError("Invalid internal root")
            elif len(node.children) < self.min_internal_children:
                raise IndexInvariantError("Internal underflow")

            ranges = []

            for child in node.children:
                if child.parent is not node:
                    raise IndexInvariantError("Invalid parent pointer")
                ranges.append(inspect(child, False))

            expected = [minimum for minimum, _ in ranges[1:]]

            if node.keys != expected:
                raise IndexInvariantError("Invalid separator keys")

            for i in range(len(ranges) - 1):
                if ranges[i][1] >= ranges[i + 1][0]:
                    raise IndexInvariantError("Overlapping child ranges")

            return ranges[0][0], ranges[-1][1]

        inspect(self.root, True)

        for i, leaf in enumerate(leaves):
            expected = leaves[i + 1] if i + 1 < len(leaves) else None
            if leaf.next_leaf is not expected:
                raise IndexInvariantError("Invalid leaf chain")

        if sum(len(leaf.keys) for leaf in leaves) != self.size:
            raise IndexInvariantError("Incorrect tree size")

        return True

    def statistics(self) -> dict[str, Any]:
        pages = self.page_layout()
        leaf_pages = [p for p in pages if p["type"] == "leaf"]
        internal_pages = [p for p in pages if p["type"] == "internal"]

        return {
            "records": self.size,
            "height": self.height(),
            "total_pages": len(pages),
            "leaf_pages": len(leaf_pages),
            "internal_pages": len(internal_pages),
            "page_reads": self.page_reads,
            "page_writes": self.page_writes,
            "average_leaf_occupancy": (
                sum(p["key_count"] for p in leaf_pages)
                / (len(leaf_pages) * self.max_keys)
                if leaf_pages else 0
            )
        }


class BufferPool:
    """
    LRU simulation of a database buffer pool.

    The cache stores page identifiers, not serialized page contents.
    """

    def __init__(self, capacity: int):
        if capacity < 1:
            raise ValueError("Buffer pool capacity must be positive")

        self.capacity = capacity
        self.pages: OrderedDict[int, None] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def access(self, page_id: int) -> None:
        if page_id in self.pages:
            self.hits += 1
            self.pages.move_to_end(page_id)
            return

        self.misses += 1

        if len(self.pages) >= self.capacity:
            self.pages.popitem(last=False)
            self.evictions += 1

        self.pages[page_id] = None

    def statistics(self) -> dict[str, float]:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_ratio": self.hits / total if total else 0.0
        }


def demonstrate() -> None:
    print("B+ TREE INDEX INTERNALS")
    print("=" * 60)

    tree = BPlusTree(order=4)

    records = [
        (45, "Employee-45"),
        (12, "Employee-12"),
        (78, "Employee-78"),
        (23, "Employee-23"),
        (56, "Employee-56"),
        (89, "Employee-89"),
        (34, "Employee-34"),
        (67, "Employee-67"),
        (10, "Employee-10"),
        (91, "Employee-91"),
        (28, "Employee-28"),
        (50, "Employee-50"),
        (72, "Employee-72"),
        (15, "Employee-15"),
    ]

    for key, value in records:
        tree.insert(key, value)

    print("\n1. Search")
    print("Key 56:", tree.search(56))
    print("Key 999:", tree.search(999))

    print("\n2. Sorted leaf traversal")
    print(tree.traverse())

    print("\n3. Range scan: 20 through 70")
    print(tree.range_scan(20, 70))

    print("\n4. Index page layout")
    for page in tree.page_layout():
        print(json.dumps(page))

    print("\n5. Index statistics")
    print(json.dumps(tree.statistics(), indent=2))

    print("\n6. Deletion and rebalancing")
    for key in [10, 12, 15, 23, 28]:
        tree.delete(key)
        assert tree.validate()

    print("Remaining keys:", tree.traverse())
    print("Tree valid:", tree.validate())

    print("\n7. Buffer pool simulation")
    buffer_pool = BufferPool(capacity=3)

    for page in tree.page_layout():
        buffer_pool.access(page["page_id"])

    for page in tree.page_layout()[:2]:
        buffer_pool.access(page["page_id"])

    print(json.dumps(buffer_pool.statistics(), indent=2))

    print("\n8. Randomized integrity test")
    random_tree = BPlusTree(order=5)
    keys = list(range(500))
    random.Random(42).shuffle(keys)

    for key in keys:
        random_tree.insert(key, f"value-{key}")

    assert random_tree.validate()
    assert random_tree.traverse() == list(range(500))

    random.Random(42).shuffle(keys)

    for key in keys[:250]:
        random_tree.delete(key)

    assert random_tree.validate()
    assert random_tree.traverse() == sorted(keys[250:])

    print("500 insertions and 250 deletions passed.")

    print("\n9. Edge-case validation")

    try:
        tree.insert(45, "Duplicate")
    except DuplicateKeyError as error:
        print("Duplicate rejected:", error)

    try:
        tree.delete(999)
    except KeyNotFoundError as error:
        print("Missing key rejected:", error)

    print("\nAll integrity checks passed.")


if __name__ == "__main__":
    demonstrate()
