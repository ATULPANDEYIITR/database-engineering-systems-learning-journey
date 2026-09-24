"""
Window Functions II: ROW_NUMBER, RANK, DENSE_RANK, NTILE

A self-contained study program for learning SQL ranking window functions.

The examples use Python to model the same concepts that SQL window functions
perform over rows. No external packages are required.

Core SQL equivalents demonstrated throughout this file:

    ROW_NUMBER() OVER (
        PARTITION BY ...
        ORDER BY ...
    )

    RANK() OVER (
        PARTITION BY ...
        ORDER BY ...
    )

    DENSE_RANK() OVER (
        PARTITION BY ...
        ORDER BY ...
    )

    NTILE(n) OVER (
        PARTITION BY ...
        ORDER BY ...
    )

The Python implementations make the underlying mechanics explicit so that
the difference between the four functions can be studied without requiring
a database server.
"""

from dataclasses import dataclass
from collections import defaultdict
from math import ceil
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple


# ============================================================================
# FUNDAMENTALS
# ============================================================================

print("=" * 80)
print("WINDOW FUNCTIONS II: ROW_NUMBER, RANK, DENSE_RANK, NTILE")
print("=" * 80)

print(
    """
A window function calculates a value for each row while retaining the rows
being analyzed.

Ranking window functions usually have three important components:

1. PARTITION BY
   Divides rows into independent groups.

2. ORDER BY
   Defines the ordering used to calculate the ranking.

3. The window function itself
   Determines the value assigned to each row.

The four functions studied here differ mainly in how they handle ties:

ROW_NUMBER
    Every row gets a unique sequential number.

RANK
    Tied rows receive the same rank, and later ranks contain gaps.

DENSE_RANK
    Tied rows receive the same rank, but later ranks have no gaps.

NTILE(n)
    Rows are distributed into n approximately equal buckets.
"""
)


# ============================================================================
# SAMPLE DATA
# ============================================================================

employees = [
    {"employee_id": 101, "name": "Asha", "department": "Engineering", "salary": 125000},
    {"employee_id": 102, "name": "Bharat", "department": "Engineering", "salary": 110000},
    {"employee_id": 103, "name": "Chen", "department": "Engineering", "salary": 110000},
    {"employee_id": 104, "name": "Divya", "department": "Engineering", "salary": 95000},
    {"employee_id": 105, "name": "Ethan", "department": "Engineering", "salary": 85000},
    {"employee_id": 201, "name": "Farah", "department": "Sales", "salary": 115000},
    {"employee_id": 202, "name": "Gaurav", "department": "Sales", "salary": 100000},
    {"employee_id": 203, "name": "Hana", "department": "Sales", "salary": 100000},
    {"employee_id": 204, "name": "Ivan", "department": "Sales", "salary": 90000},
    {"employee_id": 205, "name": "Julia", "department": "Sales", "salary": 75000},
    {"employee_id": 301, "name": "Kabir", "department": "HR", "salary": 105000},
    {"employee_id": 302, "name": "Leena", "department": "HR", "salary": 90000},
    {"employee_id": 303, "name": "Manoj", "department": "HR", "salary": 90000},
    {"employee_id": 304, "name": "Nisha", "department": "HR", "salary": 70000},
]


def print_rows(rows: Sequence[Dict[str, Any]], title: str = "") -> None:
    """Print dictionaries in a compact table."""
    if title:
        print(f"\n{title}")

    if not rows:
        print("(no rows)")
        return

    columns = list(rows[0].keys())
    widths = {}

    for column in columns:
        widths[column] = max(
            len(str(column)),
            max(len(str(row.get(column, ""))) for row in rows),
        )

    header = " | ".join(str(column).ljust(widths[column]) for column in columns)
    separator = "-+-".join("-" * widths[column] for column in columns)

    print(header)
    print(separator)

    for row in rows:
        print(
            " | ".join(
                str(row.get(column, "")).ljust(widths[column])
                for column in columns
            )
        )


print_rows(employees, "Original employee data")


# ============================================================================
# PARTITIONING
# ============================================================================

def partition_rows(
    rows: Sequence[Dict[str, Any]],
    partition_columns: Sequence[str],
) -> List[Tuple[Tuple[Any, ...], List[Dict[str, Any]]]]:
    """
    Simulate SQL PARTITION BY.

    Rows with identical partition-column values belong to the same partition.
    The original input order is retained within each partition.
    """
    if not partition_columns:
        return [((), list(rows))]

    partitions: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)

    for row in rows:
        key = tuple(row[column] for column in partition_columns)
        partitions[key].append(row)

    return list(partitions.items())


def sort_partition(
    rows: Sequence[Dict[str, Any]],
    order_columns: Sequence[Tuple[str, bool]],
) -> List[Dict[str, Any]]:
    """
    Sort a partition according to SQL-like ORDER BY columns.

    Each tuple is:
        (column_name, ascending)

    A deterministic secondary key can be added to break ties when a unique
    row order is required.
    """
    result = list(rows)

    for column, ascending in reversed(order_columns):
        result.sort(
            key=lambda row: row[column],
            reverse=not ascending,
        )

    return result


# ============================================================================
# ROW_NUMBER
# ============================================================================

def row_number(
    rows: Sequence[Dict[str, Any]],
    partition_columns: Sequence[str],
    order_columns: Sequence[Tuple[str, bool]],
    output_column: str = "row_number",
) -> List[Dict[str, Any]]:
    """
    Simulate:

        ROW_NUMBER() OVER (
            PARTITION BY ...
            ORDER BY ...
        )

    ROW_NUMBER always assigns a distinct sequential value to every row.
    Ties in ORDER BY do not receive the same number.

    In SQL, if ORDER BY is not deterministic, tied rows may receive different
    row numbers in an implementation-dependent order. A unique secondary
    key is therefore recommended when exact reproducibility matters.
    """
    result: List[Dict[str, Any]] = []

    for _, partition in partition_rows(rows, partition_columns):
        ordered = sort_partition(partition, order_columns)

        for position, row in enumerate(ordered, start=1):
            new_row = dict(row)
            new_row[output_column] = position
            result.append(new_row)

    return result


print_rows(
    row_number(
        employees,
        ["department"],
        [("salary", False), ("employee_id", True)],
    ),
    "ROW_NUMBER: highest salary first within each department",
)


# ============================================================================
# RANK
# ============================================================================

def rank_rows(
    rows: Sequence[Dict[str, Any]],
    partition_columns: Sequence[str],
    order_columns: Sequence[Tuple[str, bool]],
    output_column: str = "rank",
) -> List[Dict[str, Any]]:
    """
    Simulate SQL RANK().

    If multiple rows have equal ORDER BY values, they receive the same rank.

    Example:

        salaries: 100, 100, 90, 80
        RANK:       1,   1,  3,  4

    The gap occurs because two rows occupy rank 1.
    """
    result: List[Dict[str, Any]] = []

    for _, partition in partition_rows(rows, partition_columns):
        ordered = sort_partition(partition, order_columns)

        previous_key = None
        current_rank = 0

        for position, row in enumerate(ordered, start=1):
            current_key = tuple(row[column] for column, _ in order_columns)

            if position == 1:
                current_rank = 1
            elif current_key != previous_key:
                current_rank = position

            new_row = dict(row)
            new_row[output_column] = current_rank
            result.append(new_row)

            previous_key = current_key

    return result


print_rows(
    rank_rows(
        employees,
        ["department"],
        [("salary", False)],
    ),
    "RANK: tied salaries share a rank and create gaps",
)


# ============================================================================
# DENSE_RANK
# ============================================================================

def dense_rank_rows(
    rows: Sequence[Dict[str, Any]],
    partition_columns: Sequence[str],
    order_columns: Sequence[Tuple[str, bool]],
    output_column: str = "dense_rank",
) -> List[Dict[str, Any]]:
    """
    Simulate SQL DENSE_RANK().

    Example:

        salaries: 100, 100, 90, 80
        DENSE_RANK: 1, 1, 2, 3

    Unlike RANK, no rank number is skipped after a tie.
    """
    result: List[Dict[str, Any]] = []

    for _, partition in partition_rows(rows, partition_columns):
        ordered = sort_partition(partition, order_columns)

        previous_key = None
        current_rank = 0

        for row in ordered:
            current_key = tuple(row[column] for column, _ in order_columns)

            if current_rank == 0 or current_key != previous_key:
                current_rank += 1

            new_row = dict(row)
            new_row[output_column] = current_rank
            result.append(new_row)

            previous_key = current_key

    return result


print_rows(
    dense_rank_rows(
        employees,
        ["department"],
        [("salary", False)],
    ),
    "DENSE_RANK: tied salaries share a rank without gaps",
)


# ============================================================================
# NTILE
# ============================================================================

def ntile_rows(
    rows: Sequence[Dict[str, Any]],
    number_of_buckets: int,
    partition_columns: Sequence[str],
    order_columns: Sequence[Tuple[str, bool]],
    output_column: str = "ntile",
) -> List[Dict[str, Any]]:
    """
    Simulate SQL NTILE(n).

    NTILE divides each ordered partition into approximately equal buckets.

    If there are q rows and n buckets:

        q = n * base_size + remainder

    The first 'remainder' buckets receive base_size + 1 rows.
    The remaining buckets receive base_size rows.

    If n > q, only q buckets can receive rows, so some bucket numbers are
    absent.
    """
    if number_of_buckets <= 0:
        raise ValueError("NTILE requires a positive bucket count.")

    result: List[Dict[str, Any]] = []

    for _, partition in partition_rows(rows, partition_columns):
        ordered = sort_partition(partition, order_columns)
        row_count = len(ordered)

        if row_count == 0:
            continue

        base_size, remainder = divmod(row_count, number_of_buckets)

        for index, row in enumerate(ordered):
            if index < (base_size + 1) * remainder:
                bucket = index // (base_size + 1) + 1
            elif base_size == 0:
                bucket = remainder
            else:
                bucket = (
                    remainder
                    + (index - (base_size + 1) * remainder) // base_size
                    + 1
                )

            new_row = dict(row)
            new_row[output_column] = bucket
            result.append(new_row)

    return result


print_rows(
    ntile_rows(
        employees,
        4,
        ["department"],
        [("salary", False), ("employee_id", True)],
    ),
    "NTILE(4): approximately equal salary groups within each department",
)


# ============================================================================
# SIDE-BY-SIDE COMPARISON
# ============================================================================

def ranking_comparison(
    rows: Sequence[Dict[str, Any]],
    partition_columns: Sequence[str],
    order_columns: Sequence[Tuple[str, bool]],
) -> List[Dict[str, Any]]:
    """
    Calculate all four ranking functions over the same logical window.
    """
    row_numbers = row_number(
        rows, partition_columns, order_columns, "_row_number"
    )
    ranks = rank_rows(
        rows, partition_columns, order_columns, "_rank"
    )
    dense_ranks = dense_rank_rows(
        rows, partition_columns, order_columns, "_dense_rank"
    )
    tiles = ntile_rows(
        rows, 4, partition_columns, order_columns, "_ntile_4"
    )

    combined = []

    for row_number_row in row_numbers:
        employee_id = row_number_row["employee_id"]

        rank_row = next(
            row for row in ranks
            if row["employee_id"] == employee_id
        )
        dense_row = next(
            row for row in dense_ranks
            if row["employee_id"] == employee_id
        )
        tile_row = next(
            row for row in tiles
            if row["employee_id"] == employee_id
        )

        combined.append(
            {
                "employee_id": employee_id,
                "name": row_number_row["name"],
                "department": row_number_row["department"],
                "salary": row_number_row["salary"],
                "ROW_NUMBER": row_number_row["_row_number"],
                "RANK": rank_row["_rank"],
                "DENSE_RANK": dense_row["_dense_rank"],
                "NTILE(4)": tile_row["_ntile_4"],
            }
        )

    return combined


comparison = ranking_comparison(
    employees,
    ["department"],
    [("salary", False), ("employee_id", True)],
)

print_rows(comparison, "All four ranking functions together")


# ============================================================================
# TIE BEHAVIOR
# ============================================================================

tie_demo = [
    {"id": 1, "score": 100},
    {"id": 2, "score": 100},
    {"id": 3, "score": 90},
    {"id": 4, "score": 90},
    {"id": 5, "score": 80},
]

tie_comparison = ranking_comparison(
    [
        {
            "employee_id": row["id"],
            "name": f"Player {row['id']}",
            "department": "Competition",
            "salary": row["score"],
        }
        for row in tie_demo
    ],
    ["department"],
    [("salary", False), ("employee_id", True)],
)

print_rows(tie_comparison, "Tie behavior: 100, 100, 90, 90, 80")


# ============================================================================
# IMPORTANT DISTINCTION: TIE COLUMNS IN ORDER BY
# ============================================================================

print(
    """
ORDER BY determines what constitutes a tie.

If RANK uses only:

    ORDER BY salary DESC

then employees with equal salaries tie.

If the ranking uses:

    ORDER BY salary DESC, employee_id ASC

then employee_id becomes part of the ordering key. Since employee_id is
normally unique, equal salaries no longer form ties.

This is often useful for ROW_NUMBER because a unique secondary key makes
the result deterministic.

For RANK and DENSE_RANK, adding a unique secondary ordering column changes
the meaning of equality and therefore changes the ranking itself.
"""
)


# ============================================================================
# TOP-N PER GROUP
# ============================================================================

def top_n_per_group(
    rows: Sequence[Dict[str, Any]],
    n: int,
) -> List[Dict[str, Any]]:
    """
    Equivalent conceptually to:

        SELECT *
        FROM (
            SELECT
                ...,
                ROW_NUMBER() OVER (
                    PARTITION BY department
                    ORDER BY salary DESC, employee_id
                ) AS rn
            FROM employees
        ) ranked
        WHERE rn <= n;
    """
    ranked = row_number(
        rows,
        ["department"],
        [("salary", False), ("employee_id", True)],
        "rn",
    )

    return [row for row in ranked if row["rn"] <= n]


print_rows(
    top_n_per_group(employees, 2),
    "Top 2 employees per department using ROW_NUMBER",
)


def top_n_with_ties(
    rows: Sequence[Dict[str, Any]],
    n: int,
) -> List[Dict[str, Any]]:
    """
    Conceptually equivalent to using RANK and filtering rank <= n.

    This can return more than n rows per group when ties exist.
    """
    ranked = rank_rows(
        rows,
        ["department"],
        [("salary", False)],
        "salary_rank",
    )

    return [row for row in ranked if row["salary_rank"] <= n]


print_rows(
    top_n_with_ties(employees, 2),
    "Top 2 salary ranks per department using RANK",
)


# ============================================================================
# DISTINCT VALUE POSITIONING WITH DENSE_RANK
# ============================================================================

def salary_levels(
    rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Assign a position to each distinct salary level within a department.

    DENSE_RANK is appropriate because the result represents distinct ordered
    levels rather than physical row positions.
    """
    return dense_rank_rows(
        rows,
        ["department"],
        [("salary", False)],
        "salary_level",
    )


print_rows(
    salary_levels(employees),
    "Distinct salary levels using DENSE_RANK",
)


# ============================================================================
# QUARTILES, DECILES, AND SEGMENTATION
# ============================================================================

performance_scores = [
    {"id": index + 1, "employee": f"E{index + 1:02d}", "score": score}
    for index, score in enumerate(
        [98, 95, 92, 89, 87, 84, 82, 80, 77, 75, 73, 70]
    )
]

print_rows(
    ntile_rows(
        performance_scores,
        4,
        [],
        [("score", False), ("id", True)],
        "quartile",
    ),
    "NTILE(4): performance segmentation",
)

print_rows(
    ntile_rows(
        performance_scores,
        10,
        [],
        [("score", False), ("id", True)],
        "decile",
    ),
    "NTILE(10): performance segmentation into deciles",
)


# ============================================================================
# EDGE CASES
# ============================================================================

print("\nEDGE CASES")

empty_rows: List[Dict[str, Any]] = []

print_rows(
    row_number(empty_rows, [], [("value", True)]),
    "Empty input",
)

single_row = [{"id": 1, "value": 50}]

print_rows(
    ranking_comparison(
        [
            {
                "employee_id": 1,
                "name": "Only Row",
                "department": "Single",
                "salary": 50,
            }
        ],
        ["department"],
        [("salary", False)],
    ),
    "Single-row partition",
)

try:
    ntile_rows(
        employees,
        0,
        ["department"],
        [("salary", False)],
    )
except ValueError as error:
    print(f"Invalid NTILE(0): {error}")

print_rows(
    ntile_rows(
        single_row,
        5,
        [],
        [("value", False)],
    ),
    "NTILE(5) with only one row",
)


# ============================================================================
# NTILE MATHEMATICS
# ============================================================================

def explain_ntile_distribution(row_count: int, bucket_count: int) -> List[int]:
    """
    Return the number of rows assigned to each possible NTILE bucket.
    """
    if bucket_count <= 0:
        raise ValueError("bucket_count must be positive")

    if row_count <= 0:
        return []

    base, remainder = divmod(row_count, bucket_count)

    return [
        base + 1 if bucket <= remainder else base
        for bucket in range(1, bucket_count + 1)
    ]


print("\nNTILE DISTRIBUTION RULE")

for rows_count, buckets in [(10, 4), (11, 4), (12, 4), (5, 10), (3, 2)]:
    distribution = explain_ntile_distribution(rows_count, buckets)
    print(
        f"Rows={rows_count}, Buckets={buckets}, "
        f"distribution={distribution}, total={sum(distribution)}"
    )


# ============================================================================
# WINDOW ORDER VS FINAL OUTPUT ORDER
# ============================================================================

print(
    """
A ranking window's ORDER BY controls how the window function calculates its
value. It does not necessarily determine the final order of the query result.

Conceptually:

    SELECT
        employee_id,
        department,
        salary,
        ROW_NUMBER() OVER (
            PARTITION BY department
            ORDER BY salary DESC
        ) AS rn
    FROM employees
    ORDER BY employee_id;

The ranking is salary-based, while the final displayed result is
employee_id-based.

This distinction is important when debugging SQL queries.
"""
)


# ============================================================================
# REAL-WORLD USE CASES
# ============================================================================

use_cases = {
    "ROW_NUMBER": [
        "Top N rows per category",
        "Deduplicating records while keeping one preferred row",
        "Selecting the latest record per entity",
        "Pagination with deterministic ordering",
        "Assigning a unique sequence within groups",
    ],
    "RANK": [
        "Competition rankings",
        "Leaderboard positions with ties",
        "Top N positions where ties should be retained",
        "Sports and examination ranking",
    ],
    "DENSE_RANK": [
        "Distinct salary or price levels",
        "Leaderboard positions without gaps",
        "Finding the second-highest distinct value",
        "Categorizing observations by ordered distinct values",
    ],
    "NTILE": [
        "Quartiles",
        "Deciles",
        "Customer segmentation",
        "Risk bands",
        "Approximate equal-sized cohorts",
    ],
}

for function_name, examples in use_cases.items():
    print(f"\n{function_name}")
    for example in examples:
        print(f"  - {example}")


# ============================================================================
# SECOND-HIGHEST DISTINCT SALARY
# ============================================================================

second_highest = [
    row
    for row in dense_rank_rows(
        employees,
        ["department"],
        [("salary", False)],
        "salary_rank",
    )
    if row["salary_rank"] == 2
]

print_rows(
    second_highest,
    "Second-highest distinct salary in each department",
)


# ============================================================================
# DEDUPLICATION PATTERN
# ============================================================================

records = [
    {"record_id": 1, "customer_id": "C100", "updated_at": "2026-09-20", "value": "old"},
    {"record_id": 2, "customer_id": "C100", "updated_at": "2026-09-23", "value": "new"},
    {"record_id": 3, "customer_id": "C200", "updated_at": "2026-09-21", "value": "only"},
    {"record_id": 4, "customer_id": "C300", "updated_at": "2026-09-19", "value": "old"},
    {"record_id": 5, "customer_id": "C300", "updated_at": "2026-09-22", "value": "latest"},
]

deduplicated = row_number(
    records,
    ["customer_id"],
    [("updated_at", False), ("record_id", False)],
    "rn",
)

latest_records = [row for row in deduplicated if row["rn"] == 1]

print_rows(
    latest_records,
    "Deduplication: latest record per customer",
)


# ============================================================================
# PERFORMANCE CONSIDERATIONS
# ============================================================================

print(
    """
PERFORMANCE

Ranking window functions normally require the database engine to organize
rows according to the partition and ordering requirements.

Typical conceptual cost:

    Partitioning/grouping: depends on the execution strategy.
    Ordering: commonly O(n log n) for a set of n rows.
    Ranking after ordering: O(n).

The exact SQL execution plan depends on the database system, indexes,
statistics, data distribution, memory, and query shape.

Useful production considerations:

- Reduce unnecessary rows before applying a window function.
- Select only required columns.
- Use deterministic ORDER BY expressions when reproducibility matters.
- Inspect execution plans for large datasets.
- Understand whether indexes can help the database avoid or reduce sorting.
- Avoid using a ranking function when a simpler aggregate is sufficient.
"""
)


# ============================================================================
# COMMON MISTAKES
# ============================================================================

mistakes = [
    (
        "Confusing RANK and DENSE_RANK",
        "RANK creates gaps after ties; DENSE_RANK does not.",
    ),
    (
        "Assuming ROW_NUMBER treats ties equally",
        "ROW_NUMBER always assigns different numbers to different rows.",
    ),
    (
        "Assuming NTILE creates exactly equal buckets",
        "When rows do not divide evenly, some buckets receive one extra row.",
    ),
    (
        "Forgetting PARTITION BY",
        "Without PARTITION BY, ranking is calculated across the entire result set.",
    ),
    (
        "Using a unique tie-breaker with RANK unintentionally",
        "A unique secondary ORDER BY column can eliminate ties.",
    ),
    (
        "Filtering a window function in the same SELECT WHERE clause",
        "Window functions are normally computed after WHERE, so a subquery or CTE is used.",
    ),
    (
        "Confusing window ORDER BY with final query ORDER BY",
        "They control different aspects of the query.",
    ),
]

print("\nCOMMON MISTAKES")
for mistake, explanation in mistakes:
    print(f"\n{mistake}\n  {explanation}")


# ============================================================================
# SQL GENERATION HELPERS
# ============================================================================

def sql_row_number(
    partition_by: Sequence[str],
    order_by: Sequence[str],
) -> str:
    """Generate a readable SQL expression for ROW_NUMBER."""
    partition_sql = ", ".join(partition_by)
    order_sql = ", ".join(order_by)

    partition_clause = (
        f"PARTITION BY {partition_sql} "
        if partition_by
        else ""
    )

    return (
        "ROW_NUMBER() OVER ("
        f"{partition_clause}ORDER BY {order_sql}"
        ")"
    )


def sql_rank(
    partition_by: Sequence[str],
    order_by: Sequence[str],
) -> str:
    """Generate a readable SQL expression for RANK."""
    partition_sql = ", ".join(partition_by)
    order_sql = ", ".join(order_by)

    partition_clause = (
        f"PARTITION BY {partition_sql} "
        if partition_by
        else ""
    )

    return (
        "RANK() OVER ("
        f"{partition_clause}ORDER BY {order_sql}"
        ")"
    )


def sql_dense_rank(
    partition_by: Sequence[str],
    order_by: Sequence[str],
) -> str:
    """Generate a readable SQL expression for DENSE_RANK."""
    partition_sql = ", ".join(partition_by)
    order_sql = ", ".join(order_by)

    partition_clause = (
        f"PARTITION BY {partition_sql} "
        if partition_by
        else ""
    )

    return (
        "DENSE_RANK() OVER ("
        f"{partition_clause}ORDER BY {order_sql}"
        ")"
    )


def sql_ntile(
    buckets: int,
    partition_by: Sequence[str],
    order_by: Sequence[str],
) -> str:
    """Generate a readable SQL expression for NTILE."""
    if buckets <= 0:
        raise ValueError("NTILE bucket count must be positive.")

    partition_sql = ", ".join(partition_by)
    order_sql = ", ".join(order_by)

    partition_clause = (
        f"PARTITION BY {partition_sql} "
        if partition_by
        else ""
    )

    return (
        f"NTILE({buckets}) OVER ("
        f"{partition_clause}ORDER BY {order_sql}"
        ")"
    )


print("\nSQL SYNTAX PATTERNS")

print(
    sql_row_number(
        ["department"],
        ["salary DESC", "employee_id ASC"],
    )
)

print(
    sql_rank(
        ["department"],
        ["salary DESC"],
    )
)

print(
    sql_dense_rank(
        ["department"],
        ["salary DESC"],
    )
)

print(
    sql_ntile(
        4,
        ["department"],
        ["salary DESC", "employee_id ASC"],
    )
)


# ============================================================================
# VALIDATION TESTS
# ============================================================================

def validate_rankings() -> None:
    """Run assertions for the core ranking semantics."""
    data = [
        {"id": 1, "group": "A", "value": 100},
        {"id": 2, "group": "A", "value": 100},
        {"id": 3, "group": "A", "value": 90},
        {"id": 4, "group": "A", "value": 80},
    ]

    ordered = row_number(
        data,
        ["group"],
        [("value", False), ("id", True)],
    )
    assert [row["row_number"] for row in ordered] == [1, 2, 3, 4]

    ranked = rank_rows(
        data,
        ["group"],
        [("value", False)],
    )
    assert [row["rank"] for row in ranked] == [1, 1, 3, 4]

    dense = dense_rank_rows(
        data,
        ["group"],
        [("value", False)],
    )
    assert [row["dense_rank"] for row in dense] == [1, 1, 2, 3]

    tiles = ntile_rows(
        data,
        2,
        ["group"],
        [("value", False), ("id", True)],
    )
    assert [row["ntile"] for row in tiles] == [1, 1, 2, 2]

    separate_groups = [
        {"id": 1, "group": "A", "value": 100},
        {"id": 2, "group": "B", "value": 100},
    ]

    result = row_number(
        separate_groups,
        ["group"],
        [("value", False)],
    )

    assert [row["row_number"] for row in result] == [1, 1]

    print("\nAll ranking validation tests passed.")


validate_rankings()


# ============================================================================
# ADVANCED: GENERIC RANKING ENGINE
# ============================================================================

@dataclass(frozen=True)
class RankingSpecification:
    """
    Configuration object for reusable ranking operations.
    """

    partition_columns: Tuple[str, ...]
    order_columns: Tuple[Tuple[str, bool], ...]


class WindowRankingEngine:
    """
    Reusable ranking engine implementing four common window functions.

    This class separates configuration from execution and provides a small
    abstraction similar to how a query engine conceptually separates the
    window specification from the ranking operation.
    """

    def __init__(self, specification: RankingSpecification) -> None:
        self.specification = specification

    def row_number(
        self,
        rows: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return row_number(
            rows,
            self.specification.partition_columns,
            self.specification.order_columns,
        )

    def rank(
        self,
        rows: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return rank_rows(
            rows,
            self.specification.partition_columns,
            self.specification.order_columns,
        )

    def dense_rank(
        self,
        rows: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return dense_rank_rows(
            rows,
            self.specification.partition_columns,
            self.specification.order_columns,
        )

    def ntile(
        self,
        rows: Sequence[Dict[str, Any]],
        buckets: int,
    ) -> List[Dict[str, Any]]:
        return ntile_rows(
            rows,
            buckets,
            self.specification.partition_columns,
            self.specification.order_columns,
        )


engine = WindowRankingEngine(
    RankingSpecification(
        partition_columns=("department",),
        order_columns=(("salary", False), ("employee_id", True)),
    )
)

print_rows(
    engine.row_number(employees),
    "Reusable WindowRankingEngine",
)


# ============================================================================
# CONCEPTUAL DECISION GUIDE
# ============================================================================

print(
    """
FUNCTION SELECTION

Use ROW_NUMBER when:
    Every physical row needs a unique sequence.
    You need exactly N rows per group.
    You need deterministic deduplication.

Use RANK when:
    Equal values must share a position.
    Gaps after ties have semantic meaning.
    You are modeling competition-style positions.

Use DENSE_RANK when:
    Equal values must share a position.
    You want consecutive distinct-value positions.
    Rank gaps are not desired.

Use NTILE when:
    You need approximate equal-sized groups.
    You want quartiles, deciles, or customer segments.
    The objective is bucket assignment rather than competition ranking.
"""
)


# ============================================================================
# FINAL STUDY EXAMPLE
# ============================================================================

sales = [
    {"sale_id": 1, "region": "North", "salesperson": "A", "revenue": 90000},
    {"sale_id": 2, "region": "North", "salesperson": "B", "revenue": 85000},
    {"sale_id": 3, "region": "North", "salesperson": "C", "revenue": 85000},
    {"sale_id": 4, "region": "North", "salesperson": "D", "revenue": 70000},
    {"sale_id": 5, "region": "South", "salesperson": "E", "revenue": 95000},
    {"sale_id": 6, "region": "South", "salesperson": "F", "revenue": 95000},
    {"sale_id": 7, "region": "South", "salesperson": "G", "revenue": 80000},
    {"sale_id": 8, "region": "South", "salesperson": "H", "revenue": 60000},
]

sales_ranked = ranking_comparison(
    [
        {
            "employee_id": row["sale_id"],
            "name": row["salesperson"],
            "department": row["region"],
            "salary": row["revenue"],
        }
        for row in sales
    ],
    ["department"],
    [("salary", False), ("employee_id", True)],
)

print_rows(
    sales_ranked,
    "Final case study: regional sales ranking",
)

print(
    """
Study checkpoint:

For values 100, 100, 90, 80:

ROW_NUMBER  -> 1, 2, 3, 4
RANK        -> 1, 1, 3, 4
DENSE_RANK  -> 1, 1, 2, 3

NTILE depends on the number of rows and requested buckets rather than
following the tie-ranking rules of the other three functions.

The central distinction is therefore:

ROW_NUMBER = unique row position
RANK       = competition ranking with gaps
DENSE_RANK = competition ranking without gaps
NTILE      = approximately equal-sized bucket assignment
"""
)
