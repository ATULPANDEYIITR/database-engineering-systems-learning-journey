"""
Advanced SQL Aggregation: GROUPING SETS, ROLLUP, and CUBE
==========================================================

This standalone study script teaches advanced multidimensional aggregation.

Primary SQL concepts:
    - GROUP BY
    - Aggregate functions
    - GROUPING SETS
    - ROLLUP
    - CUBE
    - GROUPING()
    - GROUPING_ID()
    - NULL versus subtotal NULL
    - Hierarchical aggregation
    - Multidimensional aggregation
    - Filtering aggregated results
    - HAVING
    - ORDER BY
    - Grand totals
    - Partial grouping dimensions
    - Performance and implementation considerations

The examples use DuckDB because DuckDB implements GROUPING SETS, ROLLUP,
CUBE, GROUPING(), and GROUPING_ID() in a convenient embedded database.

Install once if DuckDB is not already available:
    python -m pip install duckdb

The script also contains a pure-Python reference implementation. This makes
the aggregation semantics visible without depending on SQL syntax alone.

Important:
    GROUPING SETS, ROLLUP, and CUBE are SQL features. Their exact syntax and
    optimizer behavior can vary somewhat between database systems.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from itertools import product
from typing import Any, Iterable

try:
    import duckdb
except ImportError:
    duckdb = None


# ---------------------------------------------------------------------------
# 1. DATA MODEL
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Sale:
    sale_id: int
    region: str
    country: str
    channel: str
    category: str
    revenue: Decimal
    quantity: int


SALES: list[Sale] = [
    Sale(1, "North", "India", "Online", "Electronics", Decimal("1200.00"), 3),
    Sale(2, "North", "India", "Retail", "Electronics", Decimal("800.00"), 2),
    Sale(3, "North", "India", "Online", "Furniture", Decimal("1500.00"), 1),
    Sale(4, "North", "Nepal", "Online", "Electronics", Decimal("700.00"), 2),
    Sale(5, "South", "India", "Online", "Electronics", Decimal("1800.00"), 4),
    Sale(6, "South", "India", "Retail", "Furniture", Decimal("2200.00"), 2),
    Sale(7, "South", "India", "Online", "Furniture", Decimal("1100.00"), 1),
    Sale(8, "South", "Sri Lanka", "Retail", "Electronics", Decimal("900.00"), 2),
    Sale(9, "West", "India", "Online", "Electronics", Decimal("2500.00"), 5),
    Sale(10, "West", "India", "Retail", "Furniture", Decimal("1700.00"), 2),
    Sale(11, "West", "Pakistan", "Online", "Furniture", Decimal("1000.00"), 1),
    Sale(12, "East", "India", "Online", "Electronics", Decimal("1300.00"), 3),
    Sale(13, "East", "India", "Retail", "Furniture", Decimal("1600.00"), 2),
    Sale(14, "East", "Bangladesh", "Online", "Electronics", Decimal("600.00"), 2),
]


# ---------------------------------------------------------------------------
# 2. BASIC AGGREGATION HELPERS
# ---------------------------------------------------------------------------

def money(value: Decimal) -> str:
    """Format a Decimal as currency-like output."""
    return f"{value:,.2f}"


def print_rows(title: str, rows: Iterable[dict[str, Any]]) -> None:
    """Print dictionary rows as a simple aligned table."""
    rows = list(rows)

    print(f"\n{'=' * 90}")
    print(title)
    print("=" * 90)

    if not rows:
        print("(no rows)")
        return

    columns = list(rows[0].keys())
    widths = {
        column: max(
            len(str(column)),
            *(len(str(row.get(column, ""))) for row in rows),
        )
        for column in columns
    }

    print(" | ".join(str(column).ljust(widths[column]) for column in columns))
    print("-+-".join("-" * widths[column] for column in columns))

    for row in rows:
        print(" | ".join(
            str(row.get(column, "")).ljust(widths[column])
            for column in columns
        ))


def sales_as_dicts() -> list[dict[str, Any]]:
    """Convert dataclass records into SQL-friendly dictionaries."""
    return [
        {
            "sale_id": sale.sale_id,
            "region": sale.region,
            "country": sale.country,
            "channel": sale.channel,
            "category": sale.category,
            "revenue": float(sale.revenue),
            "quantity": sale.quantity,
        }
        for sale in SALES
    ]


# ---------------------------------------------------------------------------
# 3. BASIC GROUP BY
# ---------------------------------------------------------------------------

def basic_group_by_region() -> list[dict[str, Any]]:
    """
    Equivalent conceptual SQL:

        SELECT region, SUM(revenue), SUM(quantity)
        FROM sales
        GROUP BY region;

    A normal GROUP BY produces one row for every distinct grouping key.
    """
    totals: dict[str, dict[str, Any]] = {}

    for sale in SALES:
        if sale.region not in totals:
            totals[sale.region] = {
                "region": sale.region,
                "revenue": Decimal("0"),
                "quantity": 0,
                "orders": 0,
            }

        totals[sale.region]["revenue"] += sale.revenue
        totals[sale.region]["quantity"] += sale.quantity
        totals[sale.region]["orders"] += 1

    result = []
    for row in totals.values():
        result.append({
            "region": row["region"],
            "revenue": money(row["revenue"]),
            "quantity": row["quantity"],
            "orders": row["orders"],
        })

    return sorted(result, key=lambda row: row["region"])


# ---------------------------------------------------------------------------
# 4. CONCEPTUAL GROUPING SETS ENGINE
# ---------------------------------------------------------------------------

def aggregate_grouping_set(
    rows: list[Sale],
    dimensions: tuple[str, ...],
) -> list[dict[str, Any]]:
    """
    Execute one grouping set using Python.

    If dimensions is:
        ("region", "channel")

    then the equivalent conceptual SQL is:

        GROUP BY region, channel

    If dimensions is:
        ()

    it represents the grand total:

        GROUP BY ()
    """
    groups: dict[tuple[Any, ...], dict[str, Any]] = defaultdict(
        lambda: {
            "revenue": Decimal("0"),
            "quantity": 0,
            "orders": 0,
        }
    )

    for sale in rows:
        key = tuple(getattr(sale, dimension) for dimension in dimensions)

        groups[key]["revenue"] += sale.revenue
        groups[key]["quantity"] += sale.quantity
        groups[key]["orders"] += 1

    output = []

    for key, aggregate in groups.items():
        row = {
            dimension: value
            for dimension, value in zip(dimensions, key)
        }

        # Missing grouping dimensions are represented as NULL-like None.
        for dimension in ("region", "channel", "category"):
            row.setdefault(dimension, None)

        row["revenue"] = aggregate["revenue"]
        row["quantity"] = aggregate["quantity"]
        row["orders"] = aggregate["orders"]
        output.append(row)

    return output


def grouping_sets(
    rows: list[Sale],
    sets: list[tuple[str, ...]],
) -> list[dict[str, Any]]:
    """
    Implement:

        GROUP BY GROUPING SETS (
            (region, channel),
            (region),
            (channel),
            ()
        )

    Each grouping set is independently aggregated, then concatenated.
    """
    result = []

    for grouping_set in sets:
        result.extend(aggregate_grouping_set(rows, grouping_set))

    return result


# ---------------------------------------------------------------------------
# 5. ROLLUP
# ---------------------------------------------------------------------------

def rollup_sets(dimensions: tuple[str, ...]) -> list[tuple[str, ...]]:
    """
    Generate the grouping sets represented by:

        ROLLUP(a, b, c)

    Semantically:

        (a, b, c)
        (a, b)
        (a)
        ()

    ROLLUP therefore represents hierarchical aggregation.
    """
    return [
        dimensions[:index]
        for index in range(len(dimensions), -1, -1)
    ]


def demonstrate_rollup_in_python() -> list[dict[str, Any]]:
    """
    Demonstrates:

        GROUP BY ROLLUP(region, channel, category)

    Notice that ROLLUP does NOT produce every possible combination.

    It produces:
        region + channel + category
        region + channel
        region
        grand total
    """
    return grouping_sets(
        SALES,
        rollup_sets(("region", "channel", "category")),
    )


# ---------------------------------------------------------------------------
# 6. CUBE
# ---------------------------------------------------------------------------

def cube_sets(dimensions: tuple[str, ...]) -> list[tuple[str, ...]]:
    """
    Generate all grouping sets represented by:

        CUBE(a, b, c)

    Every subset of dimensions is included.

    For three dimensions there are 2^3 = 8 grouping sets.
    """
    sets = []

    for include_flags in product([False, True], repeat=len(dimensions)):
        grouping_set = tuple(
            dimension
            for dimension, include in zip(dimensions, include_flags)
            if include
        )
        sets.append(grouping_set)

    # Put the most detailed grouping first, followed by simpler groupings.
    return sorted(sets, key=lambda item: (-len(item), item))


def demonstrate_cube_in_python() -> list[dict[str, Any]]:
    """
    Demonstrates:

        GROUP BY CUBE(region, channel, category)

    CUBE provides every dimensional combination, including the grand total.
    """
    return grouping_sets(
        SALES,
        cube_sets(("region", "channel", "category")),
    )


# ---------------------------------------------------------------------------
# 7. GROUPING SETS
# ---------------------------------------------------------------------------

def demonstrate_grouping_sets_in_python() -> list[dict[str, Any]]:
    """
    Demonstrates a deliberately selected set of aggregations.

    This is useful when business reporting needs specific levels rather than
    every possible combination.
    """
    sets = [
        ("region", "category"),
        ("region",),
        ("category",),
        (),
    ]

    return grouping_sets(SALES, sets)


# ---------------------------------------------------------------------------
# 8. GROUPING() AND THE NULL AMBIGUITY
# ---------------------------------------------------------------------------

def grouping_flag(
    dimension: str,
    grouping_set: tuple[str, ...],
) -> int:
    """
    SQL's GROUPING(column) returns:

        0 -> the column participates in the grouping
        1 -> the column was aggregated away

    This distinction is important because a real data value can itself be
    NULL. A NULL created by aggregation is not necessarily a data NULL.
    """
    return 0 if dimension in grouping_set else 1


def grouping_id(
    dimensions: tuple[str, ...],
    grouping_set: tuple[str, ...],
) -> int:
    """
    Build the conceptual GROUPING_ID.

    The exact bit ordering is database-specific, so this function is intended
    as a teaching model rather than a universal database implementation.

    Each missing dimension contributes one binary bit.
    """
    value = 0

    for dimension in dimensions:
        value = (value << 1) | grouping_flag(dimension, grouping_set)

    return value


def labeled_grouping_sets() -> list[dict[str, Any]]:
    dimensions = ("region", "channel", "category")
    sets = [
        ("region", "channel", "category"),
        ("region", "channel"),
        ("region",),
        (),
    ]

    rows = []

    for grouping_set in sets:
        for row in aggregate_grouping_set(SALES, grouping_set):
            row = dict(row)

            row["grouping_region"] = grouping_flag(
                "region", grouping_set
            )
            row["grouping_channel"] = grouping_flag(
                "channel", grouping_set
            )
            row["grouping_category"] = grouping_flag(
                "category", grouping_set
            )
            row["grouping_id"] = grouping_id(
                dimensions,
                grouping_set,
            )

            rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# 9. FILTERING AGGREGATED RESULTS
# ---------------------------------------------------------------------------

def filter_grouped_results(
    rows: list[dict[str, Any]],
    minimum_revenue: Decimal,
) -> list[dict[str, Any]]:
    """
    Equivalent conceptual SQL:

        HAVING SUM(revenue) >= 3000

    HAVING filters groups after aggregation.

    WHERE filters source rows before aggregation.

    Confusing WHERE and HAVING is a common SQL mistake.
    """
    return [
        row
        for row in rows
        if row["revenue"] >= minimum_revenue
    ]


# ---------------------------------------------------------------------------
# 10. DUCKDB SQL DEMONSTRATIONS
# ---------------------------------------------------------------------------

def run_duckdb_examples() -> None:
    if duckdb is None:
        print(
            "\nDuckDB is not installed. The pure-Python demonstrations were "
            "still executed. Install DuckDB to execute the actual SQL syntax."
        )
        return

    connection = duckdb.connect(database=":memory:")

    connection.execute(
        """
        CREATE TABLE sales (
            sale_id INTEGER,
            region VARCHAR,
            country VARCHAR,
            channel VARCHAR,
            category VARCHAR,
            revenue DECIMAL(12, 2),
            quantity INTEGER
        )
        """
    )

    connection.executemany(
        """
        INSERT INTO sales
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                sale.sale_id,
                sale.region,
                sale.country,
                sale.channel,
                sale.category,
                sale.revenue,
                sale.quantity,
            )
            for sale in SALES
        ],
    )

    # -----------------------------------------------------------------------
    # Normal GROUP BY
    # -----------------------------------------------------------------------
    result = connection.execute(
        """
        SELECT
            region,
            SUM(revenue) AS total_revenue,
            SUM(quantity) AS total_quantity,
            COUNT(*) AS order_count
        FROM sales
        GROUP BY region
        ORDER BY region
        """
    ).fetchall()

    print_rows(
        "DuckDB: Basic GROUP BY region",
        [
            {
                "region": region,
                "revenue": str(revenue),
                "quantity": quantity,
                "orders": orders,
            }
            for region, revenue, quantity, orders in result
        ],
    )

    # -----------------------------------------------------------------------
    # GROUPING SETS
    # -----------------------------------------------------------------------
    result = connection.execute(
        """
        SELECT
            region,
            channel,
            category,
            SUM(revenue) AS total_revenue,
            SUM(quantity) AS total_quantity,
            COUNT(*) AS order_count
        FROM sales
        GROUP BY GROUPING SETS (
            (region, channel, category),
            (region, channel),
            (region),
            ()
        )
        ORDER BY
            GROUPING(region),
            region,
            GROUPING(channel),
            channel,
            GROUPING(category),
            category
        """
    ).fetchall()

    print_rows(
        "DuckDB: GROUPING SETS",
        [
            {
                "region": region if region is not None else "ALL",
                "channel": channel if channel is not None else "ALL",
                "category": category if category is not None else "ALL",
                "revenue": str(revenue),
                "quantity": quantity,
                "orders": orders,
            }
            for (
                region,
                channel,
                category,
                revenue,
                quantity,
                orders,
            ) in result
        ],
    )

    # -----------------------------------------------------------------------
    # ROLLUP
    # -----------------------------------------------------------------------
    result = connection.execute(
        """
        SELECT
            region,
            channel,
            category,
            SUM(revenue) AS total_revenue,
            GROUPING(region) AS region_grouped,
            GROUPING(channel) AS channel_grouped,
            GROUPING(category) AS category_grouped,
            GROUPING_ID(region, channel, category) AS grouping_id
        FROM sales
        GROUP BY ROLLUP(region, channel, category)
        ORDER BY
            GROUPING(region),
            region,
            GROUPING(channel),
            channel,
            GROUPING(category),
            category
        """
    ).fetchall()

    print_rows(
        "DuckDB: ROLLUP(region, channel, category)",
        [
            {
                "region": region if region is not None else "ALL",
                "channel": channel if channel is not None else "ALL",
                "category": category if category is not None else "ALL",
                "revenue": str(revenue),
                "G(region)": region_grouped,
                "G(channel)": channel_grouped,
                "G(category)": category_grouped,
                "grouping_id": grouping_id_value,
            }
            for (
                region,
                channel,
                category,
                revenue,
                region_grouped,
                channel_grouped,
                category_grouped,
                grouping_id_value,
            ) in result
        ],
    )

    # -----------------------------------------------------------------------
    # CUBE
    # -----------------------------------------------------------------------
    result = connection.execute(
        """
        SELECT
            region,
            channel,
            category,
            SUM(revenue) AS total_revenue,
            GROUPING(region) AS region_grouped,
            GROUPING(channel) AS channel_grouped,
            GROUPING(category) AS category_grouped
        FROM sales
        GROUP BY CUBE(region, channel, category)
        ORDER BY
            GROUPING(region),
            region,
            GROUPING(channel),
            channel,
            GROUPING(category),
            category
        """
    ).fetchall()

    print_rows(
        "DuckDB: CUBE(region, channel, category)",
        [
            {
                "region": region if region is not None else "ALL",
                "channel": channel if channel is not None else "ALL",
                "category": category if category is not None else "ALL",
                "revenue": str(revenue),
                "G(region)": region_grouped,
                "G(channel)": channel_grouped,
                "G(category)": category_grouped,
            }
            for (
                region,
                channel,
                category,
                revenue,
                region_grouped,
                channel_grouped,
                category_grouped,
            ) in result
        ],
    )

    # -----------------------------------------------------------------------
    # Combining regular aggregation with HAVING
    # -----------------------------------------------------------------------
    result = connection.execute(
        """
        SELECT
            region,
            channel,
            SUM(revenue) AS total_revenue
        FROM sales
        GROUP BY GROUPING SETS (
            (region, channel),
            (region),
            ()
        )
        HAVING SUM(revenue) >= 3000
        ORDER BY total_revenue DESC
        """
    ).fetchall()

    print_rows(
        "DuckDB: GROUPING SETS + HAVING",
        [
            {
                "region": region if region is not None else "ALL",
                "channel": channel if channel is not None else "ALL",
                "revenue": str(revenue),
            }
            for region, channel, revenue in result
        ],
    )

    # -----------------------------------------------------------------------
    # Conditional labeling using GROUPING()
    # -----------------------------------------------------------------------
    result = connection.execute(
        """
        SELECT
            CASE
                WHEN GROUPING(region) = 1 THEN 'ALL REGIONS'
                ELSE region
            END AS region_label,

            CASE
                WHEN GROUPING(channel) = 1 THEN 'ALL CHANNELS'
                ELSE channel
            END AS channel_label,

            SUM(revenue) AS total_revenue
        FROM sales
        GROUP BY ROLLUP(region, channel)
        ORDER BY
            GROUPING(region),
            region,
            GROUPING(channel),
            channel
        """
    ).fetchall()

    print_rows(
        "DuckDB: Human-readable subtotal labels",
        [
            {
                "region": region,
                "channel": channel,
                "revenue": str(revenue),
            }
            for region, channel, revenue in result
        ],
    )

    connection.close()


# ---------------------------------------------------------------------------
# 11. COMPARISON TABLE
# ---------------------------------------------------------------------------

def explain_structures() -> None:
    dimensions = ("region", "channel", "category")

    print("\n" + "=" * 90)
    print("STRUCTURAL COMPARISON")
    print("=" * 90)

    print(
        """
GROUP BY:
    Produces one aggregation level.

GROUPING SETS:
    Lets the query author explicitly select multiple aggregation levels.

ROLLUP:
    Produces hierarchical prefix levels.

CUBE:
    Produces every combination of the specified dimensions.

For three dimensions:

    GROUPING SETS:
        Whatever sets the query explicitly specifies.

    ROLLUP(a,b,c):
        (a,b,c), (a,b), (a), ()

    CUBE(a,b,c):
        (a,b,c), (a,b), (a,c), (b,c), (a), (b), (c), ()

CUBE has 2^n possible grouping sets for n dimensions.
That exponential growth is an important performance consideration.
"""
    )

    print("ROLLUP grouping sets:")
    for grouping_set in rollup_sets(dimensions):
        print("   ", grouping_set or "()")

    print("\nCUBE grouping sets:")
    for grouping_set in cube_sets(dimensions):
        print("   ", grouping_set or "()")

    print(f"\nCUBE grouping-set count for {len(dimensions)} dimensions: "
          f"{2 ** len(dimensions)}")


# ---------------------------------------------------------------------------
# 12. EDGE CASE: EMPTY INPUT
# ---------------------------------------------------------------------------

def demonstrate_empty_input() -> None:
    """
    A grand-total aggregation can still have a semantic result even when
    there are no source rows, depending on the aggregate and database.

    SUM over no rows is commonly NULL in SQL, while COUNT(*) is 0.

    The Python reference implementation does not invent a row for an empty
    grouping set, so its behavior is deliberately different from SQL's
    aggregate semantics. This is an important reminder that a hand-written
    implementation must define empty-input behavior explicitly.
    """
    empty_rows: list[Sale] = []

    print("\n" + "=" * 90)
    print("EMPTY INPUT EDGE CASE")
    print("=" * 90)

    result = aggregate_grouping_set(empty_rows, ())
    print("Pure Python result for empty input and grouping set ():",
          result)

    print(
        "SQL aggregate semantics must be checked in the target database, "
        "especially for SUM, AVG, MIN, MAX, and COUNT."
    )


# ---------------------------------------------------------------------------
# 13. EDGE CASE: REAL NULL VALUES
# ---------------------------------------------------------------------------

def demonstrate_null_semantics() -> None:
    """
    SQL NULL and an aggregation-generated subtotal NULL are different ideas.

    Example:

        country = NULL

    can mean the source row has an unknown country.

    A ROLLUP result where country is NULL can mean:

        all countries

    GROUPING(country) distinguishes the two.
    """
    print("\n" + "=" * 90)
    print("NULL SEMANTICS")
    print("=" * 90)

    print(
        """
Source-data NULL:
    The underlying value is NULL.

Subtotal NULL:
    The grouping dimension was removed to represent an aggregate level.

Use:
    GROUPING(column) = 1

to identify a subtotal/grand-total NULL created by the grouping operation.
"""
    )


# ---------------------------------------------------------------------------
# 14. PERFORMANCE DISCUSSION
# ---------------------------------------------------------------------------

def explain_performance() -> None:
    print("\n" + "=" * 90)
    print("PERFORMANCE CONSIDERATIONS")
    print("=" * 90)

    print(
        """
1. GROUPING SETS
   Can reduce the need to issue several separate aggregation queries.

2. ROLLUP
   Is useful for hierarchical dimensions such as:

       Year -> Quarter -> Month
       Region -> Country -> City
       Department -> Team -> Employee

3. CUBE
   Can become expensive because n dimensions produce 2^n grouping sets.

   5 dimensions -> 32 grouping sets
   10 dimensions -> 1,024 grouping sets
   15 dimensions -> 32,768 grouping sets

4. Cardinality
   The number of distinct combinations can be much larger than the number
   of source rows' individual dimensions.

5. Filtering
   Push selective WHERE predicates before aggregation when semantically
   correct. This reduces rows entering the aggregation.

6. HAVING
   HAVING operates on groups, so it generally cannot replace a row-level
   WHERE predicate.

7. Query planning
   Modern analytical databases can optimize multiple grouping levels,
   share intermediate work, and use specialized aggregation strategies.
   The exact optimization is database-specific.

8. Memory
   Hash-based aggregation may require memory proportional to the number
   of groups. Large cubes can therefore consume substantial resources.

9. Ordering
   ORDER BY can add a sorting cost. Do not sort large reports unless
   ordering is actually required.

10. Materialization
    Repeatedly requested summaries may justify summary tables, materialized
    views, partitions, or other database-specific techniques.
"""
    )


# ---------------------------------------------------------------------------
# 15. BEST PRACTICES
# ---------------------------------------------------------------------------

def explain_best_practices() -> None:
    print("\n" + "=" * 90)
    print("BEST PRACTICES")
    print("=" * 90)

    print(
        """
- Use GROUPING SETS when you know exactly which levels are required.
- Use ROLLUP for genuine hierarchies.
- Use CUBE when users need multidimensional combinations.
- Use GROUPING() to distinguish subtotal NULLs from real NULL values.
- Use GROUPING_ID() when downstream logic needs a compact level identifier.
- Keep grouping dimensions semantically meaningful.
- Avoid CUBE across unnecessary high-cardinality dimensions.
- Use WHERE for source-row filtering.
- Use HAVING for aggregate-level filtering.
- Test totals against independent calculations.
- Explicitly label subtotal and grand-total rows in reports.
- Verify GROUPING_ID bit ordering in the target database.
- Examine execution plans for production queries.
- Treat currency and financial aggregates carefully with appropriate numeric
  types rather than binary floating-point when exact decimal semantics matter.
"""
    )


# ---------------------------------------------------------------------------
# 16. MAIN STUDY PROGRAM
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 90)
    print("ADVANCED SQL AGGREGATION: GROUPING SETS, ROLLUP, CUBE")
    print("=" * 90)

    print(
        """
The sample data contains sales across:
    - Region
    - Country
    - Channel
    - Category

The demonstrations progressively move from ordinary GROUP BY to
multidimensional aggregation.
"""
    )

    # Basic aggregation.
    print_rows(
        "Pure Python: GROUP BY region",
        basic_group_by_region(),
    )

    # Explicit grouping sets.
    grouping_set_rows = demonstrate_grouping_sets_in_python()

    print_rows(
        "Pure Python: Explicit GROUPING SETS",
        [
            {
                "region": row["region"] or "ALL",
                "channel": row["channel"] or "ALL",
                "category": row["category"] or "ALL",
                "revenue": money(row["revenue"]),
                "quantity": row["quantity"],
                "orders": row["orders"],
            }
            for row in grouping_set_rows
        ],
    )

    # ROLLUP.
    rollup_rows = demonstrate_rollup_in_python()

    print_rows(
        "Pure Python: ROLLUP(region, channel, category)",
        [
            {
                "region": row["region"] or "ALL",
                "channel": row["channel"] or "ALL",
                "category": row["category"] or "ALL",
                "revenue": money(row["revenue"]),
            }
            for row in rollup_rows
        ],
    )

    # CUBE.
    cube_rows = demonstrate_cube_in_python()

    print_rows(
        "Pure Python: CUBE(region, channel, category)",
        [
            {
                "region": row["region"] or "ALL",
                "channel": row["channel"] or "ALL",
                "category": row["category"] or "ALL",
                "revenue": money(row["revenue"]),
            }
            for row in cube_rows[:25]
        ],
    )

    print(
        f"\nCUBE produced {len(cube_rows)} aggregate rows for this data set."
    )

    # GROUPING metadata.
    metadata_rows = labeled_grouping_sets()

    print_rows(
        "Pure Python: GROUPING metadata",
        [
            {
                "region": row["region"] or "ALL",
                "channel": row["channel"] or "ALL",
                "category": row["category"] or "ALL",
                "revenue": money(row["revenue"]),
                "G(region)": row["grouping_region"],
                "G(channel)": row["grouping_channel"],
                "G(category)": row["grouping_category"],
                "grouping_id": row["grouping_id"],
            }
            for row in metadata_rows
        ],
    )

    # HAVING-style filtering.
    filtered = filter_grouped_results(
        grouping_set_rows,
        Decimal("3000"),
    )

    print_rows(
        "Pure Python: HAVING SUM(revenue) >= 3000",
        [
            {
                "region": row["region"] or "ALL",
                "channel": row["channel"] or "ALL",
                "category": row["category"] or "ALL",
                "revenue": money(row["revenue"]),
            }
            for row in filtered
        ],
    )

    explain_structures()
    demonstrate_null_semantics()
    demonstrate_empty_input()
    explain_performance()
    explain_best_practices()

    # Actual SQL execution.
    run_duckdb_examples()

    print("\n" + "=" * 90)
    print("END OF STUDY PROGRAM")
    print("=" * 90)


if __name__ == "__main__":
    main()
