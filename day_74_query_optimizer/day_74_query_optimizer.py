#!/usr/bin/env python3
"""
Query Optimizer: Cost Estimation, Statistics and Plan Selection

A self-contained relational query optimizer simulator featuring:
- Relation and column statistics
- Cardinality estimation
- Predicate selectivity
- Sequential and index scans
- Histogram and most-common-value statistics
- Nested-loop and hash joins
- Dynamic-programming join ordering
- Cost-based execution plan selection
- Statistics freshness validation
- EXPLAIN-style plan output
- Unit-style assertions and failure handling

Runtime: Python 3.10+
Dependencies: Python standard library only
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from itertools import combinations
from typing import Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("query_optimizer")


# ============================================================
# 1. DOMAIN TYPES
# ============================================================

class ScanType(Enum):
    SEQUENTIAL = "Sequential Scan"
    INDEX = "Index Scan"


class JoinType(Enum):
    HASH = "Hash Join"
    NESTED_LOOP = "Nested Loop"


class PredicateOperator(Enum):
    EQUAL = "="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    RANGE = "BETWEEN"


class OptimizerError(Exception):
    """Base exception for optimizer failures."""


class StatisticsError(OptimizerError):
    """Raised when statistics are invalid."""


class QueryValidationError(OptimizerError):
    """Raised when query definitions are invalid."""


@dataclass(frozen=True)
class CostConfig:
    sequential_page_cost: float = 1.0
    random_page_cost: float = 4.0
    cpu_tuple_cost: float = 0.01
    cpu_operator_cost: float = 0.0025
    hash_build_cost: float = 0.015
    nested_loop_cost: float = 0.005
    cache_discount: float = 0.75

    def __post_init__(self):
        values = (
            self.sequential_page_cost,
            self.random_page_cost,
            self.cpu_tuple_cost,
            self.cpu_operator_cost,
            self.hash_build_cost,
            self.nested_loop_cost,
            self.cache_discount,
        )
        if any(not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("Cost parameters must be positive and finite.")

        if self.cache_discount > 1:
            raise ValueError("Cache discount cannot exceed 1.")


@dataclass(frozen=True)
class Histogram:
    boundaries: tuple[float, ...]

    def __post_init__(self):
        if len(self.boundaries) < 2:
            raise StatisticsError("Histogram requires at least two boundaries.")

        if any(not math.isfinite(v) for v in self.boundaries):
            raise StatisticsError("Histogram boundaries must be finite.")

        if tuple(sorted(self.boundaries)) != self.boundaries:
            raise StatisticsError("Histogram boundaries must be sorted.")

        if len(set(self.boundaries)) != len(self.boundaries):
            raise StatisticsError("Histogram boundaries must be distinct.")

    def range_selectivity(self, low: float, high: float) -> float:
        if low > high:
            raise QueryValidationError("Invalid histogram range.")

        if high <= self.boundaries[0] or low >= self.boundaries[-1]:
            return 0.0

        total = self.boundaries[-1] - self.boundaries[0]

        if total <= 0:
            return 0.0

        overlap = max(
            0.0,
            min(high, self.boundaries[-1])
            - max(low, self.boundaries[0])
        )

        return min(1.0, max(0.0, overlap / total))


@dataclass
class ColumnStatistics:
    name: str
    distinct_values: int
    null_fraction: float = 0.0
    most_common_values: dict = field(default_factory=dict)
    histogram: Optional[Histogram] = None

    def __post_init__(self):
        if not self.name:
            raise StatisticsError("Column name cannot be empty.")

        if self.distinct_values < 1:
            raise StatisticsError("Distinct value count must be positive.")

        if not 0 <= self.null_fraction <= 1:
            raise StatisticsError("Null fraction must be between 0 and 1.")

        total_mcv = sum(self.most_common_values.values())

        if total_mcv < 0 or total_mcv > 1:
            raise StatisticsError("Invalid most-common-value frequencies.")

        if any(
            not math.isfinite(float(freq)) or freq < 0 or freq > 1
            for freq in self.most_common_values.values()
        ):
            raise StatisticsError("Invalid MCV frequency.")


@dataclass
class IndexStatistics:
    column: str
    pages: int
    is_unique: bool = False
    index_only: bool = False

    def __post_init__(self):
        if self.pages < 1:
            raise StatisticsError("Index pages must be positive.")


@dataclass
class RelationStatistics:
    name: str
    row_count: int
    pages: int
    columns: dict[str, ColumnStatistics]
    indexes: dict[str, IndexStatistics] = field(default_factory=dict)
    analyzed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self):
        if not self.name:
            raise StatisticsError("Relation name cannot be empty.")

        if self.row_count < 0 or self.pages < 0:
            raise StatisticsError("Relation statistics cannot be negative.")

        if self.row_count > 0 and self.pages == 0:
            raise StatisticsError("Nonempty relation requires at least one page.")

        for key, column in self.columns.items():
            if key != column.name:
                raise StatisticsError("Column dictionary key mismatch.")

        for key, index in self.indexes.items():
            if key != index.column:
                raise StatisticsError("Index dictionary key mismatch.")

            if key not in self.columns:
                raise StatisticsError("Index references an unknown column.")


@dataclass(frozen=True)
class Predicate:
    column: str
    operator: PredicateOperator
    value: object
    upper_value: Optional[float] = None


@dataclass(frozen=True)
class JoinCondition:
    left_relation: str
    left_column: str
    right_relation: str
    right_column: str

    def __post_init__(self):
        if self.left_relation == self.right_relation:
            raise QueryValidationError(
                "Self-joins require separate relation aliases."
            )


@dataclass
class Plan:
    operation: str
    cost: float
    estimated_rows: float
    children: list[Plan] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def explain(self, depth: int = 0) -> str:
        indent = "  " * depth

        result = (
            f"{indent}{self.operation} "
            f"(cost={self.cost:.3f}, "
            f"rows={self.estimated_rows:.2f})"
        )

        if self.details:
            formatted = ", ".join(
                f"{key}={value}" for key, value in self.details.items()
            )
            result += f"\n{indent}  Details: {formatted}"

        for child in self.children:
            result += "\n" + child.explain(depth + 1)

        return result


@dataclass
class Query:
    relations: list[str]
    predicates: dict[str, list[Predicate]]
    joins: list[JoinCondition]

    def validate(self, catalog: dict[str, RelationStatistics]):
        if not self.relations:
            raise QueryValidationError("Query requires at least one relation.")

        if len(set(self.relations)) != len(self.relations):
            raise QueryValidationError("Duplicate relation names are not supported.")

        if len(self.relations) > 12:
            raise QueryValidationError(
                "Dynamic-programming optimizer supports at most 12 relations."
            )

        if set(self.predicates) - set(self.relations):
            raise QueryValidationError("Predicate references an unknown relation.")

        for relation in self.relations:
            if relation not in catalog:
                raise QueryValidationError(
                    f"Unknown relation: {relation}"
                )

            for predicate in self.predicates.get(relation, []):
                if predicate.column not in catalog[relation].columns:
                    raise QueryValidationError(
                        f"Unknown column: {relation}.{predicate.column}"
                    )

                if predicate.operator == PredicateOperator.RANGE:
                    if predicate.upper_value is None:
                        raise QueryValidationError(
                            "Range predicate requires an upper boundary."
                        )

                    if float(predicate.value) > predicate.upper_value:
                        raise QueryValidationError("Invalid range predicate.")

        for join in self.joins:
            if (
                join.left_relation not in self.relations
                or join.right_relation not in self.relations
            ):
                raise QueryValidationError("Join references an unknown relation.")

            for relation, column in (
                (join.left_relation, join.left_column),
                (join.right_relation, join.right_column),
            ):
                if column not in catalog[relation].columns:
                    raise QueryValidationError(
                        f"Unknown join column: {relation}.{column}"
                    )


# ============================================================
# 2. STATISTICS CATALOG
# ============================================================

class StatisticsCatalog:

    def __init__(self):
        self.relations: dict[str, RelationStatistics] = {}

    def register(self, statistics: RelationStatistics):
        if statistics.name in self.relations:
            raise StatisticsError(
                f"Relation already registered: {statistics.name}"
            )

        self.relations[statistics.name] = statistics

    def get(self, name: str) -> RelationStatistics:
        try:
            return self.relations[name]
        except KeyError as exc:
            raise StatisticsError(
                f"Missing statistics for {name}"
            ) from exc

    def freshness(self, relation: str, max_age_hours: int = 24) -> bool:
        if max_age_hours < 0:
            raise ValueError("Maximum age cannot be negative.")

        statistics = self.get(relation)

        return (
            datetime.now(timezone.utc) - statistics.analyzed_at
            <= timedelta(hours=max_age_hours)
        )


# ============================================================
# 3. SELECTIVITY ESTIMATION
# ============================================================

class CardinalityEstimator:

    def __init__(self, catalog: StatisticsCatalog):
        self.catalog = catalog

    def estimate_selectivity(self, relation: str, predicate: Predicate) -> float:
        statistics = self.catalog.get(relation)
        column = statistics.columns[predicate.column]

        if predicate.operator == PredicateOperator.EQUAL:

            value = predicate.value

            if value is None:
                return column.null_fraction

            if value in column.most_common_values:
                return column.most_common_values[value]

            non_null_fraction = 1.0 - column.null_fraction

            return min(
                1.0,
                non_null_fraction / column.distinct_values
            )

        if predicate.operator == PredicateOperator.LESS_THAN:
            if column.histogram is None:
                return 0.33

            return column.histogram.range_selectivity(
                column.histogram.boundaries[0],
                float(predicate.value)
            )

        if predicate.operator == PredicateOperator.GREATER_THAN:
            if column.histogram is None:
                return 0.33

            return column.histogram.range_selectivity(
                float(predicate.value),
                column.histogram.boundaries[-1]
            )

        if predicate.operator == PredicateOperator.RANGE:
            if column.histogram is None:
                return 0.25

            return column.histogram.range_selectivity(
                float(predicate.value),
                float(predicate.upper_value)
            )

        raise QueryValidationError("Unsupported predicate operator.")

    def estimate_filtered_rows(
        self,
        relation: str,
        predicates: list[Predicate]
    ) -> float:
        statistics = self.catalog.get(relation)

        if not predicates:
            return float(statistics.row_count)

        selectivities = [
            self.estimate_selectivity(relation, predicate)
            for predicate in predicates
        ]

        # Independence is a practical baseline, not a guarantee.
        combined = math.prod(selectivities)

        return max(0.0, statistics.row_count * combined)


# ============================================================
# 4. PHYSICAL ACCESS PATH COSTING
# ============================================================

class CostEstimator:

    def __init__(
        self,
        catalog: StatisticsCatalog,
        config: CostConfig
    ):
        self.catalog = catalog
        self.config = config
        self.cardinality = CardinalityEstimator(catalog)

    def scan_candidates(
        self,
        relation: str,
        predicates: list[Predicate]
    ) -> list[Plan]:

        statistics = self.catalog.get(relation)

        rows = self.cardinality.estimate_filtered_rows(
            relation,
            predicates
        )

        cfg = self.config

        sequential_cost = (
            statistics.pages * cfg.sequential_page_cost
            + statistics.row_count * cfg.cpu_tuple_cost
            + statistics.row_count
            * len(predicates)
            * cfg.cpu_operator_cost
        )

        plans = [
            Plan(
                operation=ScanType.SEQUENTIAL.value,
                cost=sequential_cost,
                estimated_rows=rows,
                details={
                    "relation": relation,
                    "predicates": len(predicates)
                }
            )
        ]

        # Only equality predicates can use this simplified index model.
        for predicate in predicates:
            index = statistics.indexes.get(predicate.column)

            if index is None or predicate.operator != PredicateOperator.EQUAL:
                continue

            if rows == 0:
                index_cost = index.pages * cfg.random_page_cost
            else:
                tree_height = max(
                    1,
                    math.ceil(math.log2(index.pages + 1))
                )

                heap_pages = (
                    rows * statistics.pages
                    / max(1, statistics.row_count)
                )

                if index.index_only:
                    heap_pages *= 0.1

                index_cost = (
                    tree_height * cfg.random_page_cost
                    + heap_pages
                    * cfg.random_page_cost
                    * cfg.cache_discount
                    + rows * cfg.cpu_tuple_cost
                )

            plans.append(
                Plan(
                    operation=ScanType.INDEX.value,
                    cost=index_cost,
                    estimated_rows=rows,
                    details={
                        "relation": relation,
                        "index_column": predicate.column,
                        "index_only": index.index_only
                    }
                )
            )

        return sorted(plans, key=lambda plan: plan.cost)

    def best_scan(
        self,
        relation: str,
        predicates: list[Predicate]
    ) -> Plan:
        return self.scan_candidates(relation, predicates)[0]


# ============================================================
# 5. JOIN CARDINALITY AND COSTING
# ============================================================

class JoinEstimator:

    def __init__(
        self,
        catalog: StatisticsCatalog,
        costs: CostEstimator
    ):
        self.catalog = catalog
        self.costs = costs
        self.config = costs.config

    def estimate_join_rows(
        self,
        left_rows: float,
        right_rows: float,
        join: JoinCondition
    ) -> float:

        left_stats = self.catalog.get(join.left_relation)
        right_stats = self.catalog.get(join.right_relation)

        left_ndv = left_stats.columns[
            join.left_column
        ].distinct_values

        right_ndv = right_stats.columns[
            join.right_column
        ].distinct_values

        denominator = max(left_ndv, right_ndv, 1)

        return (
            left_rows * right_rows / denominator
        )

    def candidates(
        self,
        left_plan: Plan,
        right_plan: Plan,
        join: JoinCondition
    ) -> list[Plan]:

        cfg = self.config

        output_rows = self.estimate_join_rows(
            left_plan.estimated_rows,
            right_plan.estimated_rows,
            join
        )

        left_rows = left_plan.estimated_rows
        right_rows = right_plan.estimated_rows

        # Hash join: build a hash table from the smaller input.
        hash_build_rows = min(left_rows, right_rows)
        hash_probe_rows = max(left_rows, right_rows)

        hash_cost = (
            left_plan.cost
            + right_plan.cost
            + hash_build_rows * cfg.hash_build_cost
            + hash_probe_rows * cfg.cpu_operator_cost
            + (left_rows + right_rows) * cfg.cpu_tuple_cost
        )

        hash_plan = Plan(
            operation=JoinType.HASH.value,
            cost=hash_cost,
            estimated_rows=output_rows,
            children=[left_plan, right_plan],
            details={
                "join": "Equality",
                "build_rows": f"{hash_build_rows:.2f}",
                "probe_rows": f"{hash_probe_rows:.2f}"
            }
        )

        # Nested-loop cost increases with outer rows multiplied by inner rows.
        nested_cost = (
            left_plan.cost
            + right_plan.cost
            + left_rows
            * right_rows
            * cfg.nested_loop_cost
            + output_rows * cfg.cpu_tuple_cost
        )

        nested_plan = Plan(
            operation=JoinType.NESTED_LOOP.value,
            cost=nested_cost,
            estimated_rows=output_rows,
            children=[left_plan, right_plan],
            details={
                "join": "Equality",
                "outer_rows": f"{left_rows:.2f}",
                "inner_rows": f"{right_rows:.2f}"
            }
        )

        return [hash_plan, nested_plan]


# ============================================================
# 6. DYNAMIC-PROGRAMMING JOIN ORDER OPTIMIZER
# ============================================================

class QueryOptimizer:

    def __init__(
        self,
        catalog: StatisticsCatalog,
        config: Optional[CostConfig] = None
    ):
        self.catalog = catalog
        self.config = config or CostConfig()
        self.costs = CostEstimator(catalog, self.config)
        self.joins = JoinEstimator(catalog, self.costs)

    def optimize(self, query: Query) -> Plan:

        query.validate(self.catalog)

        relations = query.relations
        count = len(relations)

        # DP state: subset of relations -> cheapest plan for that subset.
        dp: dict[frozenset[str], Plan] = {}

        for relation in relations:
            scan = self.costs.best_scan(
                relation,
                query.predicates.get(relation, [])
            )
            dp[frozenset([relation])] = scan

        for size in range(2, count + 1):

            for subset_tuple in combinations(relations, size):

                subset = frozenset(subset_tuple)
                best_plan = None

                # Enumerate left-deep partitions.
                for relation in subset:

                    left_subset = frozenset(
                        subset - {relation}
                    )

                    if left_subset not in dp:
                        continue

                    right_subset = frozenset([relation])

                    connecting = [
                        join for join in query.joins
                        if (
                            join.left_relation in left_subset
                            and join.right_relation in right_subset
                        ) or (
                            join.right_relation in left_subset
                            and join.left_relation in right_subset
                        )
                    ]

                    if not connecting:
                        continue

                    left_plan = dp[left_subset]
                    right_plan = dp[right_subset]

                    for condition in connecting:
                        candidates = self.joins.candidates(
                            left_plan,
                            right_plan,
                            condition
                        )

                        candidate = min(
                            candidates,
                            key=lambda plan: plan.cost
                        )

                        if (
                            best_plan is None
                            or candidate.cost < best_plan.cost
                        ):
                            best_plan = candidate

                if best_plan is not None:
                    dp[subset] = best_plan

        full_set = frozenset(relations)

        if full_set not in dp:
            raise QueryValidationError(
                "No connected join plan could be constructed."
            )

        return dp[full_set]


# ============================================================
# 7. EXAMPLE CATALOG
# ============================================================

def build_catalog() -> StatisticsCatalog:

    catalog = StatisticsCatalog()

    customers = RelationStatistics(
        name="customers",
        row_count=100_000,
        pages=1_000,
        columns={
            "customer_id": ColumnStatistics(
                "customer_id",
                distinct_values=100_000
            ),
            "region": ColumnStatistics(
                "region",
                distinct_values=10,
                most_common_values={
                    "North": 0.35,
                    "South": 0.25,
                    "East": 0.20,
                    "West": 0.15
                }
            )
        },
        indexes={
            "customer_id": IndexStatistics(
                "customer_id", 250, is_unique=True
            ),
            "region": IndexStatistics("region", 80)
        }
    )

    orders = RelationStatistics(
        name="orders",
        row_count=1_000_000,
        pages=12_000,
        columns={
            "order_id": ColumnStatistics(
                "order_id",
                distinct_values=1_000_000
            ),
            "customer_id": ColumnStatistics(
                "customer_id",
                distinct_values=100_000
            ),
            "amount": ColumnStatistics(
                "amount",
                distinct_values=50_000,
                histogram=Histogram(
                    (0, 100, 250, 500, 1000, 5000, 10000)
                )
            ),
            "status": ColumnStatistics(
                "status",
                distinct_values=4,
                most_common_values={
                    "COMPLETED": 0.65,
                    "PENDING": 0.20,
                    "CANCELLED": 0.10,
                    "FAILED": 0.05
                }
            )
        },
        indexes={
            "customer_id": IndexStatistics("customer_id", 2_000),
            "status": IndexStatistics("status", 500),
            "order_id": IndexStatistics(
                "order_id", 2_500, is_unique=True
            )
        }
    )

    payments = RelationStatistics(
        name="payments",
        row_count=850_000,
        pages=9_000,
        columns={
            "payment_id": ColumnStatistics(
                "payment_id",
                distinct_values=850_000
            ),
            "order_id": ColumnStatistics(
                "order_id",
                distinct_values=800_000
            ),
            "payment_status": ColumnStatistics(
                "payment_status",
                distinct_values=3,
                most_common_values={
                    "SUCCESS": 0.80,
                    "PENDING": 0.15,
                    "FAILED": 0.05
                }
            )
        },
        indexes={
            "order_id": IndexStatistics("order_id", 1_800),
            "payment_id": IndexStatistics(
                "payment_id", 2_000, is_unique=True
            )
        }
    )

    for relation in (customers, orders, payments):
        catalog.register(relation)

    return catalog


# ============================================================
# 8. TESTING AND EXECUTION
# ============================================================

def run_tests(optimizer: QueryOptimizer):

    estimator = optimizer.costs.cardinality

    # MCV estimate.
    north = estimator.estimate_selectivity(
        "customers",
        Predicate("region", PredicateOperator.EQUAL, "North")
    )
    assert math.isclose(north, 0.35)

    # Non-MCV equality estimate.
    unknown = estimator.estimate_selectivity(
        "customers",
        Predicate("customer_id", PredicateOperator.EQUAL, 999999)
    )
    assert math.isclose(unknown, 1 / 100000)

    # Histogram estimate.
    range_selectivity = estimator.estimate_selectivity(
        "orders",
        Predicate(
            "amount",
            PredicateOperator.RANGE,
            1000,
            upper_value=5000
        )
    )
    assert 0 <= range_selectivity <= 1

    # Invalid statistics must be rejected.
    try:
        Histogram((10, 5, 20))
        raise AssertionError("Invalid histogram was accepted.")
    except StatisticsError:
        pass

    # Unknown relation must be rejected.
    try:
        optimizer.catalog.get("missing_table")
        raise AssertionError("Unknown relation was accepted.")
    except StatisticsError:
        pass

    logger.info("All validation tests passed.")


def main():

    catalog = build_catalog()
    optimizer = QueryOptimizer(catalog)

    run_tests(optimizer)

    query = Query(
        relations=[
            "customers",
            "orders",
            "payments"
        ],
        predicates={
            "customers": [
                Predicate(
                    "region",
                    PredicateOperator.EQUAL,
                    "North"
                )
            ],
            "orders": [
                Predicate(
                    "status",
                    PredicateOperator.EQUAL,
                    "COMPLETED"
                ),
                Predicate(
                    "amount",
                    PredicateOperator.RANGE,
                    100,
                    upper_value=1000
                )
            ],
            "payments": [
                Predicate(
                    "payment_status",
                    PredicateOperator.EQUAL,
                    "SUCCESS"
                )
            ]
        },
        joins=[
            JoinCondition(
                "customers", "customer_id",
                "orders", "customer_id"
            ),
            JoinCondition(
                "orders", "order_id",
                "payments", "order_id"
            )
        ]
    )

    print("\nQUERY OPTIMIZATION REPORT")
    print("=" * 65)

    for relation in query.relations:
        stats = catalog.get(relation)

        scan_options = optimizer.costs.scan_candidates(
            relation,
            query.predicates.get(relation, [])
        )

        print(f"\nRelation: {relation}")
        print(f"Base rows: {stats.row_count}")
        print(
            "Estimated filtered rows: "
            f"{scan_options[0].estimated_rows:.2f}"
        )

        for candidate in scan_options:
            print(
                f"  {candidate.operation}: "
                f"cost={candidate.cost:.3f}"
            )

        if not catalog.freshness(relation):
            logger.warning(
                "Statistics may be stale for %s",
                relation
            )

    print("\nSELECTED EXECUTION PLAN")
    print("=" * 65)

    plan = optimizer.optimize(query)

    print(plan.explain())

    print("\nTOTAL ESTIMATED COST:", round(plan.cost, 3))
    print("ESTIMATED OUTPUT ROWS:", round(plan.estimated_rows, 2))

    print("\nOPTIMIZATION COMPLETE")


if __name__ == "__main__":
    main()
