"""
Join Strategy: Join Keys, Cardinality, Duplicate Rows, and NULL Behavior

This standalone study script builds a small relational-join engine using only
the Python standard library. It progresses from the basic idea of a join to
join keys, cardinality, duplicate rows, NULL behavior, outer joins, composite
keys, semi/anti joins, Cartesian products, validation, performance, and
implementation trade-offs.

The examples use None to represent SQL NULL.

Important SQL rule:
    NULL = NULL is not TRUE.
Therefore, ordinary SQL equality joins do not match two NULL join keys.
The implementation below follows that behavior unless a function explicitly
documents a different null-safe policy.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence


Row = dict[str, Any]


def print_title(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_rows(rows: Iterable[Row], title: str = "") -> None:
    rows = list(rows)
    if title:
        print(f"\n{title}")
    if not rows:
        print("(no rows)")
        return

    columns: list[str] = []
    for row in rows:
        for column in row:
            if column not in columns:
                columns.append(column)

    widths = {
        column: max(
            len(column),
            max(len(format(row.get(column), "")) for row in rows),
        )
        for column in columns
    }

    print(" | ".join(column.ljust(widths[column]) for column in columns))
    print("-+-".join("-" * widths[column] for column in columns))

    for row in rows:
        print(
            " | ".join(
                format(row.get(column), "").ljust(widths[column])
                for column in columns
            )
        )


def sql_equal(left: Any, right: Any) -> bool:
    """
    SQL-style equality for ordinary join predicates.

    Python would evaluate None == None as True.
    SQL does not: NULL = NULL evaluates to UNKNOWN rather than TRUE.

    A join predicate only accepts TRUE, so either NULL key prevents a match.
    """
    if left is None or right is None:
        return False
    return left == right


def null_safe_equal(left: Any, right: Any) -> bool:
    """
    A null-safe equality policy.

    Here two NULL values are considered equal. Some database systems provide
    an explicit null-safe comparison operator or construct for this purpose.
    This is deliberately separate from ordinary SQL equality.
    """
    return left == right


def merge_rows(
    left: Row,
    right: Row,
    left_prefix: str = "left.",
    right_prefix: str = "right.",
) -> Row:
    """
    Merge two rows without silently overwriting duplicate column names.

    Real SQL engines can expose duplicate column names in result sets depending
    on SELECT expressions. Prefixing is useful in a teaching implementation
    because it makes provenance explicit.
    """
    result: Row = {}

    for key, value in left.items():
        result[f"{left_prefix}{key}"] = value

    for key, value in right.items():
        result[f"{right_prefix}{key}"] = value

    return result


def nested_loop_inner_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: str,
    right_key: str,
    equality: Callable[[Any, Any], bool] = sql_equal,
) -> list[Row]:
    """
    Basic nested-loop inner join.

    For every left row, compare its key with every right row.

    Time complexity:
        O(N * M)

    This is conceptually simple and useful for understanding what a join
    actually means before learning optimized join strategies.
    """
    result: list[Row] = []

    for left in left_rows:
        for right in right_rows:
            if equality(left.get(left_key), right.get(right_key)):
                result.append(merge_rows(left, right))

    return result


def hash_inner_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: str,
    right_key: str,
) -> list[Row]:
    """
    Hash-based inner join.

    The right relation is indexed by its join key. Each left row then performs
    an average O(1) hash lookup.

    Expected complexity:
        O(N + M)

    Memory:
        O(M) for the hash table when the right side is indexed.

    Duplicate keys are intentionally preserved. If a key appears three times
    on the left and four times on the right, the matching key produces
    3 * 4 = 12 output rows.
    """
    index: dict[Any, list[Row]] = defaultdict(list)

    for right in right_rows:
        key = right.get(right_key)

        # SQL NULL keys do not match under ordinary equality joins.
        if key is not None:
            index[key].append(right)

    result: list[Row] = []

    for left in left_rows:
        key = left.get(left_key)

        if key is None:
            continue

        for right in index.get(key, []):
            result.append(merge_rows(left, right))

    return result


def left_outer_hash_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: str,
    right_key: str,
) -> list[Row]:
    """
    Left outer join.

    Every left row appears at least once.

    If no right-side row matches, right-side columns are emitted as None.
    A real SQL result displays these values as NULL.
    """
    index: dict[Any, list[Row]] = defaultdict(list)

    right_columns = list(right_rows[0].keys()) if right_rows else []

    for right in right_rows:
        key = right.get(right_key)
        if key is not None:
            index[key].append(right)

    result: list[Row] = []

    for left in left_rows:
        key = left.get(left_key)
        matches = [] if key is None else index.get(key, [])

        if matches:
            for right in matches:
                result.append(merge_rows(left, right))
        else:
            null_right = {column: None for column in right_columns}
            result.append(merge_rows(left, null_right))

    return result


def right_outer_hash_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: str,
    right_key: str,
) -> list[Row]:
    """
    Right outer join implemented by reversing a left outer join.

    The output prefixes still identify the original source relations.
    """
    reversed_rows = left_outer_hash_join(
        right_rows,
        left_rows,
        right_key,
        left_key,
    )

    result: list[Row] = []

    for row in reversed_rows:
        left_columns = {
            key.removeprefix("left."): value
            for key, value in row.items()
            if key.startswith("left.")
        }
        right_columns = {
            key.removeprefix("right."): value
            for key, value in row.items()
            if key.startswith("right.")
        }

        result.append(merge_rows(right_columns, left_columns, "right.", "left."))

    return result


def full_outer_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: str,
    right_key: str,
) -> list[Row]:
    """
    Full outer join.

    Keeps matched rows plus unmatched rows from both relations.

    A production database normally implements this with more specialized
    execution machinery. This implementation favors clarity.
    """
    result: list[Row] = []
    matched_right_ids: set[int] = set()

    right_columns = list(right_rows[0].keys()) if right_rows else []
    left_columns = list(left_rows[0].keys()) if left_rows else []

    for left in left_rows:
        found = False

        for index, right in enumerate(right_rows):
            if sql_equal(left.get(left_key), right.get(right_key)):
                result.append(merge_rows(left, right))
                matched_right_ids.add(index)
                found = True

        if not found:
            result.append(
                merge_rows(
                    left,
                    {column: None for column in right_columns},
                )
            )

    for index, right in enumerate(right_rows):
        if index not in matched_right_ids:
            result.append(
                merge_rows(
                    {column: None for column in left_columns},
                    right,
                )
            )

    return result


def cross_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
) -> list[Row]:
    """
    Cartesian product.

    If the inputs contain N and M rows, the result contains N*M rows.

    Cross joins can be useful, but accidental Cartesian products are a common
    production mistake because result size can grow extremely quickly.
    """
    return [
        merge_rows(left, right)
        for left in left_rows
        for right in right_rows
    ]


def semi_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: str,
    right_key: str,
) -> list[Row]:
    """
    Return left rows for which at least one matching right key exists.

    Unlike an inner join, a semi join does not multiply a left row when the
    right side contains duplicates.
    """
    right_keys = {
        row.get(right_key)
        for row in right_rows
        if row.get(right_key) is not None
    }

    return [
        row
        for row in left_rows
        if row.get(left_key) is not None and row.get(left_key) in right_keys
    ]


def anti_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: str,
    right_key: str,
) -> list[Row]:
    """
    Return left rows for which no matching right key exists.
    """
    right_keys = {
        row.get(right_key)
        for row in right_rows
        if row.get(right_key) is not None
    }

    return [
        row
        for row in left_rows
        if row.get(left_key) is None or row.get(left_key) not in right_keys
    ]


def composite_key(row: Row, columns: Sequence[str]) -> tuple[Any, ...]:
    return tuple(row.get(column) for column in columns)


def composite_hash_join(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_columns: Sequence[str],
    right_columns: Sequence[str],
) -> list[Row]:
    """
    Join on multiple columns.

    Example:
        country_code + customer_id

    SQL semantics still apply: if any component used by an ordinary equality
    predicate is NULL, that composite key does not match.
    """
    index: dict[tuple[Any, ...], list[Row]] = defaultdict(list)

    for right in right_rows:
        key = composite_key(right, right_columns)
        if all(value is not None for value in key):
            index[key].append(right)

    result: list[Row] = []

    for left in left_rows:
        key = composite_key(left, left_columns)
        if all(value is not None for value in key):
            for right in index.get(key, []):
                result.append(merge_rows(left, right))

    return result


def count_by_key(rows: Sequence[Row], key: str) -> dict[Any, int]:
    counts: dict[Any, int] = defaultdict(int)

    for row in rows:
        counts[row.get(key)] += 1

    return dict(counts)


def classify_cardinality(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: str,
    right_key: str,
) -> str:
    """
    Approximate relationship classification from observed non-NULL keys.

    1:1 means each non-NULL key occurs at most once on both sides.
    1:N means left is unique and right contains duplicates.
    N:1 means left contains duplicates and right is unique.
    N:N means both sides contain duplicate keys.

    This is data profiling, not a guarantee of a database schema constraint.
    """
    left_counts = count_by_key(left_rows, left_key)
    right_counts = count_by_key(right_rows, right_key)

    left_duplicate = any(
        key is not None and count > 1
        for key, count in left_counts.items()
    )
    right_duplicate = any(
        key is not None and count > 1
        for key, count in right_counts.items()
    )

    if not left_duplicate and not right_duplicate:
        return "1:1"
    if not left_duplicate and right_duplicate:
        return "1:N"
    if left_duplicate and not right_duplicate:
        return "N:1"
    return "N:N"


def validate_expected_one_to_one(
    rows: Sequence[Row],
    key: str,
) -> None:
    """
    Detect duplicate join keys before a join expected to be one-to-one.

    This prevents an unexpected many-to-many multiplication from silently
    changing business metrics.
    """
    counts = count_by_key(rows, key)
    duplicates = {
        value: count
        for value, count in counts.items()
        if value is not None and count > 1
    }

    if duplicates:
        raise ValueError(
            f"Expected unique key '{key}', but found duplicates: {duplicates}"
        )


def expected_join_output_upper_bound(
    left_rows: Sequence[Row],
    right_rows: Sequence[Row],
    left_key: str,
    right_key: str,
) -> int:
    """
    Calculate the exact output size for an equality inner join.

    For each key:
        output contribution = left_count(key) * right_count(key)

    This exposes the most important duplicate-row rule of joins.
    """
    left_counts = count_by_key(left_rows, left_key)
    right_counts = count_by_key(right_rows, right_key)

    total = 0

    for key, left_count in left_counts.items():
        if key is not None:
            total += left_count * right_counts.get(key, 0)

    return total


def demonstrate_basic_joins() -> None:
    print_title("1. Basic join types")

    employees = [
        {"employee_id": 1, "name": "Asha", "department_id": 10},
        {"employee_id": 2, "name": "Ravi", "department_id": 20},
        {"employee_id": 3, "name": "Meera", "department_id": 30},
        {"employee_id": 4, "name": "Kabir", "department_id": 99},
    ]

    departments = [
        {"department_id": 10, "department": "Engineering"},
        {"department_id": 20, "department": "Finance"},
        {"department_id": 30, "department": "Security"},
    ]

    inner = hash_inner_join(
        employees,
        departments,
        "department_id",
        "department_id",
    )
    print_rows(inner, "Inner join")

    left = left_outer_hash_join(
        employees,
        departments,
        "department_id",
        "department_id",
    )
    print_rows(left, "Left outer join")

    right = right_outer_hash_join(
        employees,
        departments,
        "department_id",
        "department_id",
    )
    print_rows(right, "Right outer join")

    full = full_outer_join(
        employees,
        departments,
        "department_id",
        "department_id",
    )
    print_rows(full, "Full outer join")

    cross = cross_join(
        [{"color": "red"}, {"color": "blue"}],
        [{"size": "S"}, {"size": "M"}],
    )
    print_rows(cross, "Cross join")


def demonstrate_join_keys() -> None:
    print_title("2. Join keys")

    customers = [
        {"customer_id": 101, "name": "Anita"},
        {"customer_id": 102, "name": "Bharat"},
        {"customer_id": 103, "name": "Chen"},
    ]

    orders = [
        {"order_id": "A1", "customer_id": 101, "amount": 500},
        {"order_id": "A2", "customer_id": 101, "amount": 250},
        {"order_id": "A3", "customer_id": 103, "amount": 900},
    ]

    result = hash_inner_join(
        customers,
        orders,
        "customer_id",
        "customer_id",
    )

    print_rows(result, "Customer-to-order join")

    print("\nJoin key requirements:")
    print("  - Same logical meaning on both sides.")
    print("  - Compatible data types and representations.")
    print("  - Correct granularity.")
    print("  - Appropriate NULL policy.")
    print("  - Duplicate behavior understood before aggregation.")


def demonstrate_cardinality() -> None:
    print_title("3. Cardinality and duplicate-row multiplication")

    customers = [
        {"customer_id": 1, "name": "Asha"},
        {"customer_id": 2, "name": "Ravi"},
    ]

    orders = [
        {"order_id": "O1", "customer_id": 1},
        {"order_id": "O2", "customer_id": 1},
        {"order_id": "O3", "customer_id": 1},
        {"order_id": "O4", "customer_id": 2},
    ]

    print("Cardinality:", classify_cardinality(
        customers,
        orders,
        "customer_id",
        "customer_id",
    ))

    joined = hash_inner_join(
        customers,
        orders,
        "customer_id",
        "customer_id",
    )

    print_rows(joined, "1:N join")

    many_left = [
        {"event_id": "E1", "account_id": 7},
        {"event_id": "E2", "account_id": 7},
        {"event_id": "E3", "account_id": 7},
    ]

    many_right = [
        {"transaction_id": "T1", "account_id": 7},
        {"transaction_id": "T2", "account_id": 7},
    ]

    print(
        "\nExpected N:N output:",
        expected_join_output_upper_bound(
            many_left,
            many_right,
            "account_id",
            "account_id",
        ),
        "rows",
    )

    print(
        "Reason: 3 matching left rows × 2 matching right rows = 6 output rows."
    )


def demonstrate_null_behavior() -> None:
    print_title("4. NULL behavior")

    left = [
        {"id": 1, "code": "A"},
        {"id": 2, "code": None},
        {"id": 3, "code": "B"},
    ]

    right = [
        {"record_id": 10, "code": "A"},
        {"record_id": 11, "code": None},
        {"record_id": 12, "code": "B"},
    ]

    ordinary = nested_loop_inner_join(
        left,
        right,
        "code",
        "code",
        equality=sql_equal,
    )
    print_rows(ordinary, "Ordinary SQL-style equality join")

    null_safe = nested_loop_inner_join(
        left,
        right,
        "code",
        "code",
        equality=null_safe_equal,
    )
    print_rows(null_safe, "Explicit null-safe comparison")

    print("\nPython distinction:")
    print("  None == None ->", None == None)
    print("  sql_equal(None, None) ->", sql_equal(None, None))
    print("  null_safe_equal(None, None) ->", null_safe_equal(None, None))


def demonstrate_composite_keys() -> None:
    print_title("5. Composite join keys")

    shipments = [
        {"country": "IN", "customer_id": 10, "shipment": "S1"},
        {"country": "US", "customer_id": 10, "shipment": "S2"},
        {"country": "IN", "customer_id": 20, "shipment": "S3"},
    ]

    customers = [
        {"country": "IN", "customer_id": 10, "name": "Asha"},
        {"country": "US", "customer_id": 10, "name": "John"},
        {"country": "IN", "customer_id": 20, "name": "Ravi"},
    ]

    joined = composite_hash_join(
        shipments,
        customers,
        ["country", "customer_id"],
        ["country", "customer_id"],
    )

    print_rows(joined, "Join on country + customer_id")

    print(
        "\nA composite key prevents collisions that could occur if customer_id "
        "were only unique within each country."
    )


def demonstrate_semi_and_anti_joins() -> None:
    print_title("6. Semi joins and anti joins")

    products = [
        {"product_id": 1, "product": "Keyboard"},
        {"product_id": 2, "product": "Mouse"},
        {"product_id": 3, "product": "Monitor"},
    ]

    sales = [
        {"sale_id": "S1", "product_id": 1},
        {"sale_id": "S2", "product_id": 1},
        {"sale_id": "S3", "product_id": 3},
    ]

    sold_products = semi_join(products, sales, "product_id", "product_id")
    unsold_products = anti_join(products, sales, "product_id", "product_id")

    print_rows(sold_products, "Products with at least one sale")
    print_rows(unsold_products, "Products with no sale")

    print(
        "\nSemi join avoids multiplying product 1 twice just because it has "
        "two sales."
    )


def demonstrate_data_quality() -> None:
    print_title("7. Join validation and data quality")

    supposedly_unique = [
        {"account_id": 1, "owner": "Asha"},
        {"account_id": 2, "owner": "Ravi"},
        {"account_id": 2, "owner": "Duplicate Ravi"},
    ]

    try:
        validate_expected_one_to_one(supposedly_unique, "account_id")
    except ValueError as error:
        print("Validation correctly failed:")
        print(error)

    print("\nThis type of validation is valuable before:")
    print("  - financial aggregation")
    print("  - KPI calculation")
    print("  - reporting")
    print("  - ETL pipelines")
    print("  - feature engineering")
    print("  - reconciliation")


def demonstrate_strategy_comparison() -> None:
    print_title("8. Join strategy comparison")

    left = [{"key": i, "left_value": f"L{i}"} for i in range(100)]
    right = [{"key": i, "right_value": f"R{i}"} for i in range(100)]

    nested = nested_loop_inner_join(left, right, "key", "key")
    hashed = hash_inner_join(left, right, "key", "key")

    print("Nested-loop result rows:", len(nested))
    print("Hash-join result rows:", len(hashed))

    print("\nConceptual comparison:")
    print("  Nested loop: O(N*M), low implementation complexity.")
    print("  Hash join:   expected O(N+M), additional memory for an index.")
    print("  Sort-merge:  useful when inputs are already sorted or sorting is useful.")
    print("  Index join:  useful when an indexed lookup is selective.")


def demonstrate_edge_cases() -> None:
    print_title("9. Edge cases")

    empty: list[Row] = []
    values = [{"id": 1, "value": "A"}]

    print_rows(
        hash_inner_join(empty, values, "id", "id"),
        "Empty left input",
    )

    print_rows(
        left_outer_hash_join(values, empty, "id", "id"),
        "Non-empty left input with empty right input",
    )

    print_rows(
        hash_inner_join(
            [{"id": None}],
            [{"id": None}],
            "id",
            "id",
        ),
        "Two NULL keys in ordinary equality join",
    )

    print_rows(
        nested_loop_inner_join(
            [{"id": None}],
            [{"id": None}],
            "id",
            "id",
            equality=null_safe_equal,
        ),
        "Two NULL keys with null-safe equality",
    )


@dataclass(frozen=True)
class QueryPlan:
    """
    A small conceptual representation of a join plan.

    Real database optimizers have much richer statistics and plan operators.
    This class is intentionally small so that the important decisions remain
    visible.
    """

    strategy: str
    build_side: str
    estimated_complexity: str
    memory_tradeoff: str


def choose_conceptual_strategy(
    left_size: int,
    right_size: int,
    right_is_indexed: bool = False,
    inputs_sorted: bool = False,
) -> QueryPlan:
    """
    Demonstrate simplified join-strategy reasoning.

    This is educational, not a database optimizer.
    """
    if right_is_indexed and left_size < right_size * 10:
        return QueryPlan(
            strategy="indexed lookup / nested-loop style join",
            build_side="right index",
            estimated_complexity="approximately O(left_rows * lookup_cost)",
            memory_tradeoff="depends on existing index; avoids building a new hash table",
        )

    if inputs_sorted:
        return QueryPlan(
            strategy="sort-merge join",
            build_side="neither",
            estimated_complexity="approximately O(N+M) after sorting",
            memory_tradeoff="can be memory-efficient when sorted inputs already exist",
        )

    build_side = "right" if right_size <= left_size else "left"

    return QueryPlan(
        strategy="hash join",
        build_side=build_side,
        estimated_complexity="expected O(N+M)",
        memory_tradeoff="hash table for the chosen build side",
    )


def demonstrate_query_planning() -> None:
    print_title("10. Conceptual query planning")

    scenarios = [
        (1_000_000, 100, False, False),
        (100, 1_000_000, True, False),
        (500_000, 500_000, False, True),
    ]

    for left_size, right_size, indexed, sorted_inputs in scenarios:
        plan = choose_conceptual_strategy(
            left_size,
            right_size,
            right_is_indexed=indexed,
            inputs_sorted=sorted_inputs,
        )
        print(
            f"left={left_size:,}, right={right_size:,}, "
            f"indexed={indexed}, sorted={sorted_inputs}"
        )
        print(" ", plan)


def demonstrate_real_world_case() -> None:
    print_title("11. Real-world analytical join")

    customers = [
        {"customer_id": 1, "segment": "retail"},
        {"customer_id": 2, "segment": "business"},
        {"customer_id": 3, "segment": "retail"},
    ]

    orders = [
        {"order_id": "O1", "customer_id": 1, "amount": 100},
        {"order_id": "O2", "customer_id": 1, "amount": 200},
        {"order_id": "O3", "customer_id": 2, "amount": 500},
        {"order_id": "O4", "customer_id": 2, "amount": 700},
    ]

    joined = hash_inner_join(
        customers,
        orders,
        "customer_id",
        "customer_id",
    )

    print_rows(joined, "Orders enriched with customer segment")

    totals: dict[str, float] = defaultdict(float)

    for row in joined:
        segment = row["left.segment"]
        amount = row["right.amount"]
        totals[segment] += amount

    print("\nRevenue by segment:")
    for segment, amount in sorted(totals.items()):
        print(f"  {segment}: {amount:.2f}")

    print(
        "\nThe join preserves order-level granularity. Aggregating after the "
        "join is safe here because customers are unique by customer_id."
    )


def main() -> None:
    print_title("Join Strategy Study")
    print(
        "Join keys determine which rows can match. Cardinality determines how "
        "many matches each row can produce. Duplicate keys can multiply rows. "
        "NULL requires special attention because ordinary SQL equality does "
        "not match NULL with NULL."
    )

    demonstrate_basic_joins()
    demonstrate_join_keys()
    demonstrate_cardinality()
    demonstrate_null_behavior()
    demonstrate_composite_keys()
    demonstrate_semi_and_anti_joins()
    demonstrate_data_quality()
    demonstrate_strategy_comparison()
    demonstrate_edge_cases()
    demonstrate_query_planning()
    demonstrate_real_world_case()

    print_title("Key rules to remember")
    print("1. INNER JOIN keeps matching pairs only.")
    print("2. LEFT JOIN preserves every row from the left relation.")
    print("3. RIGHT JOIN preserves every row from the right relation.")
    print("4. FULL OUTER JOIN preserves unmatched rows from both sides.")
    print("5. CROSS JOIN creates every possible pair.")
    print("6. A 1:N join legitimately multiplies rows on the N side.")
    print("7. An N:N join can multiply rows dramatically.")
    print("8. Ordinary SQL equality does not match NULL to NULL.")
    print("9. Composite keys require every key component to match.")
    print("10. Validate uniqueness when business logic expects 1:1 behavior.")
    print("11. Choose join strategy based on data size, indexes, ordering, and memory.")
    print("12. Inspect row counts before and after important joins.")


if __name__ == "__main__":
    main()
