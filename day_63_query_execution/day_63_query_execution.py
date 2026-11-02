#!/usr/bin/env python3
"""
Query Execution: operators, execution plans, and result generation.

A self-contained relational query executor using an in-memory database.
It models:
- sequential scans
- index scans
- filters
- projections
- hash joins
- nested-loop joins
- hash aggregation
- sorting
- limit
- execution-plan inspection
- result generation
- validation and execution statistics
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Iterator
from collections import defaultdict
import hashlib
import json
import time


class QueryError(Exception):
    """Base query execution error."""


class ValidationError(QueryError):
    """Raised for invalid query definitions."""


class ExecutionError(QueryError):
    """Raised for execution failures."""


class JoinType(Enum):
    INNER = "INNER"


Row = dict[str, Any]


@dataclass
class Table:
    name: str
    columns: tuple[str, ...]
    rows: list[Row]
    indexes: dict[str, dict[Any, list[int]]] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.name or not self.columns:
            raise ValidationError("Table must have a name and columns.")
        if len(set(self.columns)) != len(self.columns):
            raise ValidationError("Duplicate table columns are not allowed.")
        for row in self.rows:
            if set(row) != set(self.columns):
                raise ValidationError(f"Invalid row in table {self.name}.")

    def build_index(self, column: str) -> None:
        if column not in self.columns:
            raise ValidationError(f"Unknown column: {column}")
        index: dict[Any, list[int]] = defaultdict(list)
        for position, row in enumerate(self.rows):
            index[row[column]].append(position)
        self.indexes[column] = dict(index)


@dataclass
class ExecutionStats:
    rows_in: int = 0
    rows_out: int = 0
    comparisons: int = 0
    elapsed_ms: float = 0.0

    def finish(self, started: float, rows_out: int) -> None:
        self.rows_out = rows_out
        self.elapsed_ms = (time.perf_counter() - started) * 1000


class Operator:
    """Base iterator-style execution operator."""

    def __init__(self) -> None:
        self.stats = ExecutionStats()

    def execute(self) -> Iterator[Row]:
        raise NotImplementedError

    def run(self) -> list[Row]:
        started = time.perf_counter()
        result = list(self.execute())
        self.stats.finish(started, len(result))
        return result

    def explain(self, indent: int = 0) -> str:
        raise NotImplementedError


class SeqScan(Operator):
    def __init__(self, table: Table, alias: str | None = None) -> None:
        super().__init__()
        self.table = table
        self.alias = alias or table.name

    def execute(self) -> Iterator[Row]:
        for row in self.table.rows:
            self.stats.rows_in += 1
            yield {
                f"{self.alias}.{column}": value
                for column, value in row.items()
            }

    def explain(self, indent: int = 0) -> str:
        return " " * indent + f"Seq Scan on {self.table.name}"


class IndexScan(Operator):
    def __init__(
        self,
        table: Table,
        column: str,
        value: Any,
        alias: str | None = None,
    ) -> None:
        super().__init__()
        if column not in table.indexes:
            raise ValidationError(
                f"No index exists for {table.name}.{column}"
            )
        self.table = table
        self.column = column
        self.value = value
        self.alias = alias or table.name

    def execute(self) -> Iterator[Row]:
        positions = self.table.indexes[self.column].get(self.value, [])
        for position in positions:
            self.stats.rows_in += 1
            row = self.table.rows[position]
            yield {
                f"{self.alias}.{column}": value
                for column, value in row.items()
            }

    def explain(self, indent: int = 0) -> str:
        return (
            " " * indent
            + f"Index Scan on {self.table.name} "
              f"using {self.column} = {self.value!r}"
        )


class Filter(Operator):
    def __init__(self, child: Operator, predicate: Callable[[Row], bool],
                 description: str) -> None:
        super().__init__()
        self.child = child
        self.predicate = predicate
        self.description = description

    def execute(self) -> Iterator[Row]:
        for row in self.child.execute():
            self.stats.rows_in += 1
            if self.predicate(row):
                yield row

    def explain(self, indent: int = 0) -> str:
        return (
            " " * indent
            + f"Filter: {self.description}\n"
            + self.child.explain(indent + 2)
        )


class Project(Operator):
    def __init__(self, child: Operator,
                 expressions: dict[str, Callable[[Row], Any]]) -> None:
        super().__init__()
        self.child = child
        self.expressions = expressions

    def execute(self) -> Iterator[Row]:
        for row in self.child.execute():
            self.stats.rows_in += 1
            try:
                yield {
                    name: expression(row)
                    for name, expression in self.expressions.items()
                }
            except KeyError as exc:
                raise ExecutionError(
                    f"Projection references unknown field: {exc}"
                ) from exc

    def explain(self, indent: int = 0) -> str:
        names = ", ".join(self.expressions)
        return (
            " " * indent
            + f"Project: {names}\n"
            + self.child.explain(indent + 2)
        )


class HashJoin(Operator):
    def __init__(
        self,
        left: Operator,
        right: Operator,
        left_key: str,
        right_key: str,
        join_type: JoinType = JoinType.INNER,
    ) -> None:
        super().__init__()
        self.left = left
        self.right = right
        self.left_key = left_key
        self.right_key = right_key
        self.join_type = join_type

    def execute(self) -> Iterator[Row]:
        hash_table: dict[Any, list[Row]] = defaultdict(list)

        for right_row in self.right.execute():
            self.stats.rows_in += 1
            hash_table[right_row.get(self.right_key)].append(right_row)

        for left_row in self.left.execute():
            self.stats.rows_in += 1
            matches = hash_table.get(left_row.get(self.left_key), [])
            for right_row in matches:
                result = dict(left_row)
                for key, value in right_row.items():
                    if key in result:
                        raise ExecutionError(
                            f"Ambiguous output column: {key}"
                        )
                    result[key] = value
                yield result

    def explain(self, indent: int = 0) -> str:
        return (
            " " * indent
            + f"Hash Join ({self.join_type.value}) "
              f"{self.left_key} = {self.right_key}\n"
            + self.left.explain(indent + 2)
            + "\n"
            + self.right.explain(indent + 2)
        )


class HashAggregate(Operator):
    def __init__(
        self,
        child: Operator,
        group_key: str,
        aggregate_name: str = "count",
    ) -> None:
        super().__init__()
        self.child = child
        self.group_key = group_key
        self.aggregate_name = aggregate_name

    def execute(self) -> Iterator[Row]:
        groups: dict[Any, int] = defaultdict(int)

        for row in self.child.execute():
            self.stats.rows_in += 1
            if self.group_key not in row:
                raise ExecutionError(
                    f"Aggregation key does not exist: {self.group_key}"
                )
            groups[row[self.group_key]] += 1

        for key, count in groups.items():
            yield {
                self.group_key: key,
                self.aggregate_name: count,
            }

    def explain(self, indent: int = 0) -> str:
        return (
            " " * indent
            + f"Hash Aggregate: GROUP BY {self.group_key}\n"
            + self.child.explain(indent + 2)
        )


class Sort(Operator):
    def __init__(self, child: Operator, key: str, reverse: bool = False) -> None:
        super().__init__()
        self.child = child
        self.key = key
        self.reverse = reverse

    def execute(self) -> Iterator[Row]:
        rows = list(self.child.execute())
        self.stats.rows_in = len(rows)
        try:
            rows.sort(key=lambda row: row[self.key], reverse=self.reverse)
        except KeyError as exc:
            raise ExecutionError(f"Unknown sort key: {self.key}") from exc
        yield from rows

    def explain(self, indent: int = 0) -> str:
        direction = "DESC" if self.reverse else "ASC"
        return (
            " " * indent
            + f"Sort: {self.key} {direction}\n"
            + self.child.explain(indent + 2)
        )


class Limit(Operator):
    def __init__(self, child: Operator, limit: int) -> None:
        super().__init__()
        if limit < 0:
            raise ValidationError("LIMIT cannot be negative.")
        self.child = child
        self.limit = limit

    def execute(self) -> Iterator[Row]:
        for position, row in enumerate(self.child.execute()):
            self.stats.rows_in += 1
            if position >= self.limit:
                break
            yield row

    def explain(self, indent: int = 0) -> str:
        return (
            " " * indent
            + f"Limit: {self.limit}\n"
            + self.child.explain(indent + 2)
        )


@dataclass(frozen=True)
class Query:
    customer_status: str
    minimum_total: float
    limit: int


def validate_query(query: Query) -> None:
    if not query.customer_status:
        raise ValidationError("Customer status cannot be empty.")
    if query.minimum_total < 0:
        raise ValidationError("Minimum total cannot be negative.")
    if query.limit <= 0:
        raise ValidationError("LIMIT must be positive.")


def stable_query_id(query: Query) -> str:
    payload = json.dumps(query.__dict__, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def build_plan(
    customers: Table,
    orders: Table,
    query: Query,
) -> Operator:
    validate_query(query)

    # The indexed status predicate reduces customer rows before the join.
    customer_scan = IndexScan(
        customers,
        column="status",
        value=query.customer_status,
        alias="c",
    )

    order_scan = SeqScan(orders, alias="o")

    joined = HashJoin(
        left=customer_scan,
        right=order_scan,
        left_key="c.id",
        right_key="o.customer_id",
    )

    filtered = Filter(
        joined,
        predicate=lambda row: row["o.total"] >= query.minimum_total,
        description=f"o.total >= {query.minimum_total}",
    )

    projected = Project(
        filtered,
        {
            "customer_id": lambda row: row["c.id"],
            "customer_name": lambda row: row["c.name"],
            "order_id": lambda row: row["o.id"],
            "order_total": lambda row: row["o.total"],
        },
    )

    sorted_rows = Sort(projected, "order_total", reverse=True)

    return Limit(sorted_rows, query.limit)


def make_database() -> tuple[Table, Table]:
    customers = Table(
        name="customers",
        columns=("id", "name", "status"),
        rows=[
            {"id": 1, "name": "Asha", "status": "active"},
            {"id": 2, "name": "Bharat", "status": "active"},
            {"id": 3, "name": "Chen", "status": "inactive"},
            {"id": 4, "name": "Divya", "status": "active"},
        ],
    )

    orders = Table(
        name="orders",
        columns=("id", "customer_id", "total"),
        rows=[
            {"id": 101, "customer_id": 1, "total": 450.0},
            {"id": 102, "customer_id": 1, "total": 1200.0},
            {"id": 103, "customer_id": 2, "total": 900.0},
            {"id": 104, "customer_id": 3, "total": 2500.0},
            {"id": 105, "customer_id": 4, "total": 1750.0},
        ],
    )

    customers.validate()
    orders.validate()
    customers.build_index("status")
    orders.build_index("customer_id")

    return customers, orders


def print_results(rows: Iterable[Row]) -> None:
    rows = list(rows)
    if not rows:
        print("No rows.")
        return

    columns = list(rows[0])
    print("\nRESULT SET")
    print("-" * 72)
    print(" | ".join(columns))
    print("-" * 72)
    for row in rows:
        print(" | ".join(str(row[column]) for column in columns))


def main() -> None:
    customers, orders = make_database()

    query = Query(
        customer_status="active",
        minimum_total=800.0,
        limit=3,
    )

    query_id = stable_query_id(query)
    plan = build_plan(customers, orders, query)

    print(f"Query ID: {query_id}")
    print("\nEXECUTION PLAN")
    print(plan.explain())

    started = time.perf_counter()
    results = plan.run()
    elapsed_ms = (time.perf_counter() - started) * 1000

    print_results(results)
    print(f"\nRows returned: {len(results)}")
    print(f"Execution time: {elapsed_ms:.3f} ms")

    # Result-generation invariants.
    assert len(results) <= query.limit
    assert all(
        row["order_total"] >= query.minimum_total
        for row in results
    )
    assert all(
        row["customer_id"] in {1, 2, 4}
        for row in results
    )

    # Failure handling: invalid query must be rejected before planning.
    try:
        build_plan(customers, orders, Query("active", -1, 5))
    except ValidationError as exc:
        print(f"\nValidation failure handled: {exc}")

    # A missing index is a planning error rather than a silent fallback.
    try:
        IndexScan(customers, "name", "Asha")
    except ValidationError as exc:
        print(f"Index validation failure handled: {exc}")


if __name__ == "__main__":
    main()
