from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Iterable
import json
import math
import random


# PostgreSQL Index Families: B-tree, Hash, GIN, GiST, and BRIN
#
# This executable model uses repository-like event data to demonstrate why
# PostgreSQL has several index access methods instead of one universal index.
#
# PostgreSQL itself implements these access methods inside the database engine.
# The classes below model their important lookup behavior so the differences
# are visible without requiring an external package or a running PostgreSQL
# server.


@dataclass(frozen=True)
class PullRequest:
    pr_id: int
    repository_id: int
    author: str
    state: str
    title: str
    labels: tuple[str, ...]
    changed_files: int
    created_at: datetime
    merged_at: datetime | None
    risk_score: float


@dataclass
class BTreeIndex:
    """Sorted-key structure appropriate for equality, ordering, and ranges."""

    entries: list[tuple[Any, int]] = field(default_factory=list)

    def build(self, rows: Iterable[PullRequest], key_function) -> None:
        self.entries = sorted(
            (key_function(row), row.pr_id)
            for row in rows
        )

    def equal(self, key: Any) -> list[int]:
        left = bisect_left(self.entries, (key, -math.inf))
        right = bisect_right(self.entries, (key, math.inf))
        return [row_id for _, row_id in self.entries[left:right]]

    def range_query(self, lower: Any, upper: Any) -> list[int]:
        left = bisect_left(self.entries, (lower, -math.inf))
        right = bisect_right(self.entries, (upper, math.inf))
        return [row_id for _, row_id in self.entries[left:right]]

    def ordered(self, reverse: bool = False) -> list[int]:
        sequence = reversed(self.entries) if reverse else self.entries
        return [row_id for _, row_id in sequence]


@dataclass
class HashIndex:
    """Hash buckets are designed primarily for equality predicates."""

    buckets: dict[Any, list[int]] = field(default_factory=dict)

    def build(self, rows: Iterable[PullRequest], key_function) -> None:
        self.buckets.clear()
        for row in rows:
            key = key_function(row)
            self.buckets.setdefault(key, []).append(row.pr_id)

    def equal(self, key: Any) -> list[int]:
        return list(self.buckets.get(key, []))


@dataclass
class GINIndex:
    """
    Generalized Inverted Index model.

    Each token maps to rows containing that token. PostgreSQL GIN is especially
    useful for containment-style searches over arrays and JSONB documents.
    """

    posting_lists: dict[str, set[int]] = field(default_factory=dict)

    def build(self, rows: Iterable[PullRequest], key_function) -> None:
        self.posting_lists.clear()
        for row in rows:
            for token in key_function(row):
                self.posting_lists.setdefault(str(token), set()).add(row.pr_id)

    def contains_all(self, tokens: Iterable[str]) -> list[int]:
        normalized = [str(token) for token in tokens]
        if not normalized:
            return []

        lists = [
            self.posting_lists.get(token, set())
            for token in normalized
        ]
        if any(not posting for posting in lists):
            return []

        result = set.intersection(*lists)
        return sorted(result)

    def contains_any(self, tokens: Iterable[str]) -> list[int]:
        result: set[int] = set()
        for token in tokens:
            result.update(self.posting_lists.get(str(token), set()))
        return sorted(result)


@dataclass
class GiSTRangeIndex:
    """
    Simplified GiST-like index for overlapping time ranges.

    A real PostgreSQL GiST is a balanced tree with extensible operator classes.
    It can support range operators such as overlap and containment.
    """

    entries: list[tuple[datetime, datetime, int]] = field(default_factory=list)

    def build(self, rows: Iterable[PullRequest]) -> None:
        self.entries = []
        for row in rows:
            end = row.merged_at or row.created_at + timedelta(days=30)
            self.entries.append((row.created_at, end, row.pr_id))

    def overlaps(self, start: datetime, end: datetime) -> list[int]:
        matches = []
        for entry_start, entry_end, row_id in self.entries:
            if entry_start <= end and entry_end >= start:
                matches.append(row_id)
        return sorted(matches)


@dataclass
class BRINBlockSummary:
    """
    BRIN stores summaries for physical page ranges rather than one entry
    per row. This makes it compact and useful when a column is correlated
    with physical insertion order.
    """

    block_number: int
    minimum: datetime
    maximum: datetime
    row_ids: list[int]


@dataclass
class BRINIndex:
    block_size: int = 4
    blocks: list[BRINBlockSummary] = field(default_factory=list)

    def build(self, rows: Iterable[PullRequest], key_function) -> None:
        ordered = list(rows)
        self.blocks.clear()

        for offset in range(0, len(ordered), self.block_size):
            block_rows = ordered[offset:offset + self.block_size]
            values = [key_function(row) for row in block_rows]
            self.blocks.append(
                BRINBlockSummary(
                    block_number=offset // self.block_size,
                    minimum=min(values),
                    maximum=max(values),
                    row_ids=[row.pr_id for row in block_rows],
                )
            )

    def range_query(self, lower: datetime, upper: datetime) -> list[int]:
        matches: list[int] = []

        for block in self.blocks:
            # If the requested range does not intersect the summary range,
            # the entire physical block can be skipped.
            if block.maximum < lower or block.minimum > upper:
                continue
            matches.extend(block.row_ids)

        return sorted(matches)


class RepositoryIndexLab:
    def __init__(self, rows: list[PullRequest]) -> None:
        self.rows = rows
        self.by_id = {row.pr_id: row for row in rows}

        self.btree_state = BTreeIndex()
        self.btree_state.build(rows, lambda row: row.state)

        self.btree_created = BTreeIndex()
        self.btree_created.build(rows, lambda row: row.created_at)

        self.hash_repository = HashIndex()
        self.hash_repository.build(rows, lambda row: row.repository_id)

        self.gin_labels = GINIndex()
        self.gin_labels.build(rows, lambda row: row.labels)

        self.gist_lifecycle = GiSTRangeIndex()
        self.gist_lifecycle.build(rows)

        self.brin_created = BRINIndex(block_size=4)
        self.brin_created.build(rows, lambda row: row.created_at)

    def show(self, title: str, row_ids: Iterable[int]) -> None:
        selected = [self.by_id[row_id] for row_id in row_ids]
        print(f"\n{title}")
        for row in selected:
            print(
                f"  PR #{row.pr_id:<3} "
                f"{row.state:<8} "
                f"{row.author:<10} "
                f"{row.title}"
            )

    def demonstrate_btree(self) -> None:
        ids = self.btree_state.equal("open")
        self.show("B-tree equality lookup: state = 'open'", ids)

        lower = datetime(2026, 1, 1)
        upper = datetime(2026, 3, 31)
        ids = self.btree_created.range_query(lower, upper)
        self.show("B-tree range lookup: created_at within Q1 2026", ids)

        ordered = self.btree_created.ordered(reverse=True)[:3]
        self.show("B-tree ordering: newest three pull requests", ordered)

    def demonstrate_hash(self) -> None:
        ids = self.hash_repository.equal(101)
        self.show("Hash lookup: repository_id = 101", ids)

        print(
            "\nHash index limitation: repository_id >= 101 cannot use a "
            "hash index as an ordering/range structure."
        )

    def demonstrate_gin(self) -> None:
        ids = self.gin_labels.contains_all(["security", "postgresql"])
        self.show("GIN containment lookup: labels contain both tokens", ids)

        ids = self.gin_labels.contains_any(["security", "performance"])
        self.show("GIN membership lookup: labels contain either token", ids)

    def demonstrate_gist(self) -> None:
        window_start = datetime(2026, 2, 1)
        window_end = datetime(2026, 2, 15)
        ids = self.gist_lifecycle.overlaps(window_start, window_end)
        self.show("GiST range overlap: PR lifecycle intersects a time window", ids)

    def demonstrate_brin(self) -> None:
        lower = datetime(2026, 3, 1)
        upper = datetime(2026, 3, 10)
        ids = self.brin_created.range_query(lower, upper)
        self.show("BRIN range pruning: created_at intersects a narrow interval", ids)

        print(
            "\nBRIN observation: the result represents candidate physical "
            "blocks. PostgreSQL still examines rows inside qualifying blocks."
        )

    def compare_index_purposes(self) -> None:
        print("\nIndex selection guide")
        examples = [
            ("state = 'open'", "B-tree or Hash", "B-tree also supports ordering/ranges"),
            ("repository_id = 101", "Hash or B-tree", "Hash is equality-focused"),
            ("labels contains security", "GIN", "Inverted posting lists fit containment"),
            ("lifecycle overlaps interval", "GiST", "Range operators need generalized search"),
            ("created_at between dates on huge ordered table", "BRIN", "Compact block summaries exploit correlation"),
        ]

        for predicate, access_method, reason in examples:
            print(f"  {predicate:<42} -> {access_method:<17} | {reason}")

    def validate_index_design(self) -> None:
        print("\nDesign checks")

        assert set(self.btree_state.equal("open")) == {
            row.pr_id for row in self.rows if row.state == "open"
        }

        assert set(self.hash_repository.equal(102)) == {
            row.pr_id for row in self.rows if row.repository_id == 102
        }

        expected_gin = {
            row.pr_id
            for row in self.rows
            if {"security", "postgresql"}.issubset(row.labels)
        }
        assert set(self.gin_labels.contains_all(["security", "postgresql"])) == expected_gin

        print("  B-tree equality invariant: PASS")
        print("  Hash equality invariant: PASS")
        print("  GIN token intersection invariant: PASS")

    def explain_cost_model(self) -> None:
        row_count = len(self.rows)
        btree_height = math.ceil(math.log2(max(row_count, 2)))
        print("\nConceptual cost observations")
        print(f"  Rows modeled: {row_count}")
        print(f"  Approximate balanced-tree height: {btree_height}")
        print("  B-tree: logarithmic navigation plus qualifying tuples.")
        print("  Hash: near-constant expected bucket lookup, but equality only.")
        print("  GIN: posting-list work depends on token selectivity and intersections.")
        print("  GiST: tree traversal depends on bounding predicates and overlap.")
        print("  BRIN: tiny index footprint, with effectiveness tied to physical correlation.")

    def export_catalog(self) -> str:
        catalog = {
            "btree": ["state", "created_at"],
            "hash": ["repository_id"],
            "gin": ["labels"],
            "gist": ["created_at..merged_at"],
            "brin": ["created_at"],
        }
        return json.dumps(catalog, indent=2)


def build_realistic_dataset() -> list[PullRequest]:
    base = datetime(2026, 1, 5, 9, 0)
    definitions = [
        (1, 101, "anika", "merged", "Add PostgreSQL query audit", ("database", "postgresql"), 8, 0.25, 2),
        (2, 101, "rahul", "open", "Harden authentication policy", ("security", "backend"), 15, 0.70, 8),
        (3, 102, "meera", "open", "Optimize GIN search", ("postgresql", "performance"), 11, 0.55, 18),
        (4, 102, "vikas", "closed", "Remove obsolete API", ("maintenance",), 6, 0.20, 26),
        (5, 103, "anika", "merged", "Add audit event storage", ("security", "database"), 22, 0.80, 34),
        (6, 103, "rahul", "open", "Index release metadata", ("postgresql", "release"), 10, 0.45, 42),
        (7, 101, "meera", "merged", "Improve repository metrics", ("analytics", "performance"), 19, 0.40, 51),
        (8, 102, "vikas", "open", "Protect sensitive columns", ("security", "postgresql"), 13, 0.90, 63),
        (9, 103, "anika", "merged", "Tune historical queries", ("performance", "postgresql"), 17, 0.65, 74),
        (10, 101, "rahul", "open", "Document backup verification", ("operations",), 5, 0.30, 83),
        (11, 102, "meera", "merged", "Add range-based reporting", ("postgresql", "analytics"), 14, 0.50, 94),
        (12, 103, "vikas", "open", "Review security telemetry", ("security", "analytics"), 25, 0.85, 108),
    ]

    rows = []
    for pr_id, repository_id, author, state, title, labels, files, risk, day in definitions:
        created = base + timedelta(days=day)
        merged = created + timedelta(days=2) if state == "merged" else None
        rows.append(
            PullRequest(
                pr_id=pr_id,
                repository_id=repository_id,
                author=author,
                state=state,
                title=title,
                labels=labels,
                changed_files=files,
                created_at=created,
                merged_at=merged,
                risk_score=risk,
            )
        )

    return rows


def demonstrate_physical_correlation() -> None:
    print("\nBRIN physical-correlation experiment")

    ordered_rows = build_realistic_dataset()
    random_rows = ordered_rows.copy()
    random.Random(42).shuffle(random_rows)

    ordered_brin = BRINIndex(block_size=4)
    ordered_brin.build(ordered_rows, lambda row: row.created_at)

    shuffled_brin = BRINIndex(block_size=4)
    shuffled_brin.build(random_rows, lambda row: row.created_at)

    lower = datetime(2026, 3, 1)
    upper = datetime(2026, 3, 10)

    ordered_candidates = ordered_brin.range_query(lower, upper)
    shuffled_candidates = shuffled_brin.range_query(lower, upper)

    print(f"  Candidates with insertion order correlated to created_at: {len(ordered_candidates)}")
    print(f"  Candidates after random physical ordering: {len(shuffled_candidates)}")
    print(
        "  The example illustrates why BRIN is strongest when the indexed "
        "column follows physical table order."
    )


def main() -> None:
    rows = build_realistic_dataset()
    lab = RepositoryIndexLab(rows)

    print("PostgreSQL Index Access Method Laboratory")
    print("B-tree | Hash | GIN | GiST | BRIN")

    lab.demonstrate_btree()
    lab.demonstrate_hash()
    lab.demonstrate_gin()
    lab.demonstrate_gist()
    lab.demonstrate_brin()
    lab.compare_index_purposes()
    lab.validate_index_design()
    lab.explain_cost_model()
    demonstrate_physical_correlation()

    print("\nModeled index catalog:")
    print(lab.export_catalog())

    print("\nImportant PostgreSQL production considerations")
    print("  - An index accelerates matching queries but adds storage and write cost.")
    print("  - The planner may prefer a sequential scan when a predicate is not selective.")
    print("  - ANALYZE statistics influence planner decisions.")
    print("  - GIN indexes can be write-heavy because indexed values produce posting data.")
    print("  - GiST operator classes determine which operators the index can accelerate.")
    print("  - BRIN should be chosen for large tables where physical correlation is useful.")
    print("  - Index definitions should be validated with EXPLAIN (ANALYZE, BUFFERS).")


if __name__ == "__main__":
    main()
