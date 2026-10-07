"""
Denormalization: why and when to denormalize relational data.

This executable case study starts with a normalized order model and progressively
introduces carefully selected denormalization for read-heavy workloads.

The examples use only the Python standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal
from collections import defaultdict
from copy import deepcopy
import json
import statistics
import time
from typing import Iterable


@dataclass(frozen=True)
class Customer:
    customer_id: int
    name: str
    region: str


@dataclass(frozen=True)
class Product:
    product_id: int
    name: str
    category: str
    unit_price: Decimal


@dataclass(frozen=True)
class Order:
    order_id: int
    customer_id: int
    order_date: str
    status: str


@dataclass(frozen=True)
class OrderLine:
    order_id: int
    product_id: int
    quantity: int


@dataclass
class OrderSummary:
    order_id: int
    customer_id: int
    customer_name: str
    region: str
    order_date: str
    status: str
    item_count: int
    total_amount: Decimal


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def build_normalized_data() -> tuple[
    dict[int, Customer],
    dict[int, Product],
    dict[int, Order],
    list[OrderLine],
]:
    customers = {
        1: Customer(1, "Aarav Mehta", "North"),
        2: Customer(2, "Priya Nair", "South"),
        3: Customer(3, "Kabir Singh", "North"),
        4: Customer(4, "Meera Shah", "West"),
    }

    products = {
        101: Product(101, "Mechanical Keyboard", "Peripherals", money("89.99")),
        102: Product(102, "USB-C Dock", "Peripherals", money("129.50")),
        103: Product(103, "27-inch Monitor", "Displays", money("279.00")),
        104: Product(104, "Laptop Stand", "Accessories", money("45.00")),
        105: Product(105, "Noise-Cancelling Headset", "Audio", money("159.95")),
    }

    orders = {
        5001: Order(5001, 1, "2026-09-01", "SHIPPED"),
        5002: Order(5002, 2, "2026-09-02", "PROCESSING"),
        5003: Order(5003, 1, "2026-09-03", "DELIVERED"),
        5004: Order(5004, 3, "2026-09-04", "SHIPPED"),
        5005: Order(5005, 4, "2026-09-05", "CANCELLED"),
    }

    lines = [
        OrderLine(5001, 101, 1),
        OrderLine(5001, 103, 2),
        OrderLine(5002, 102, 1),
        OrderLine(5002, 104, 2),
        OrderLine(5003, 105, 1),
        OrderLine(5003, 101, 2),
        OrderLine(5004, 103, 1),
        OrderLine(5004, 104, 1),
        OrderLine(5005, 102, 1),
    ]

    return customers, products, orders, lines


def normalized_order_summary(
    order_id: int,
    customers: dict[int, Customer],
    products: dict[int, Product],
    orders: dict[int, Order],
    lines: list[OrderLine],
) -> OrderSummary:
    """Perform the joins and aggregation required by a reporting query."""
    order = orders[order_id]
    customer = customers[order.customer_id]

    matching_lines = [line for line in lines if line.order_id == order_id]
    total = money(
        sum(
            (products[line.product_id].unit_price * line.quantity
             for line in matching_lines),
            Decimal("0"),
        )
    )

    return OrderSummary(
        order_id=order.order_id,
        customer_id=customer.customer_id,
        customer_name=customer.name,
        region=customer.region,
        order_date=order.order_date,
        status=order.status,
        item_count=sum(line.quantity for line in matching_lines),
        total_amount=total,
    )


def demonstrate_normalization() -> None:
    customers, products, orders, lines = build_normalized_data()

    print("\n=== NORMALIZED MODEL ===")
    print("Customer, product, order, and order-line facts are stored separately.")
    for order_id in orders:
        summary = normalized_order_summary(
            order_id, customers, products, orders, lines
        )
        print(
            f"Order {summary.order_id}: "
            f"{summary.customer_name}, "
            f"{summary.item_count} units, "
            f"{summary.total_amount}"
        )


def build_denormalized_order_summaries(
    customers: dict[int, Customer],
    products: dict[int, Product],
    orders: dict[int, Order],
    lines: list[OrderLine],
) -> dict[int, OrderSummary]:
    """
    Materialize a read model.

    This intentionally duplicates customer attributes and the calculated order
    total. The duplication is useful because the reporting query no longer needs
    to reconstruct the result from several normalized relations.
    """
    lines_by_order: dict[int, list[OrderLine]] = defaultdict(list)
    for line in lines:
        lines_by_order[line.order_id].append(line)

    summaries: dict[int, OrderSummary] = {}

    for order_id, order in orders.items():
        customer = customers[order.customer_id]
        order_lines = lines_by_order[order_id]
        total = money(
            sum(
                (
                    products[line.product_id].unit_price * line.quantity
                    for line in order_lines
                ),
                Decimal("0"),
            )
        )

        summaries[order_id] = OrderSummary(
            order_id=order_id,
            customer_id=customer.customer_id,
            customer_name=customer.name,
            region=customer.region,
            order_date=order.order_date,
            status=order.status,
            item_count=sum(line.quantity for line in order_lines),
            total_amount=total,
        )

    return summaries


def demonstrate_read_model() -> None:
    customers, products, orders, lines = build_normalized_data()
    summaries = build_denormalized_order_summaries(
        customers, products, orders, lines
    )

    print("\n=== DENORMALIZED READ MODEL ===")
    for summary in summaries.values():
        print(
            f"Order {summary.order_id}: "
            f"{summary.customer_name} | "
            f"{summary.region} | "
            f"{summary.total_amount}"
        )


def demonstrate_update_anomaly() -> None:
    """
    A denormalized copy creates a consistency obligation.

    Changing a customer name in the source table does not automatically change
    an already-materialized order summary.
    """
    customers, products, orders, lines = build_normalized_data()
    summaries = build_denormalized_order_summaries(
        customers, products, orders, lines
    )

    print("\n=== CONSISTENCY RISK ===")
    print("Before customer change:", summaries[5001].customer_name)

    customers[1] = Customer(1, "Aarav Mehta Kumar", "North")
    print("Normalized source:", customers[1].name)
    print("Stale read model:", summaries[5001].customer_name)

    summaries[5001] = normalized_order_summary(
        5001, customers, products, orders, lines
    )
    print("After refresh:", summaries[5001].customer_name)


def build_indexed_normalized_model() -> tuple[
    dict[int, Customer],
    dict[int, Product],
    dict[int, Order],
    dict[int, list[OrderLine]],
]:
    customers, products, orders, lines = build_normalized_data()
    indexed_lines: dict[int, list[OrderLine]] = defaultdict(list)

    for line in lines:
        indexed_lines[line.order_id].append(line)

    return customers, products, orders, indexed_lines


def indexed_normalized_order_total(
    order_id: int,
    customers: dict[int, Customer],
    products: dict[int, Product],
    orders: dict[int, Order],
    lines_by_order: dict[int, list[OrderLine]],
) -> Decimal:
    """Show that indexing can sometimes remove the need to denormalize."""
    order = orders[order_id]
    _ = customers[order.customer_id]

    return money(
        sum(
            (
                products[line.product_id].unit_price * line.quantity
                for line in lines_by_order[order_id]
            ),
            Decimal("0"),
        )
    )


def benchmark_lookup_strategies(iterations: int = 20_000) -> None:
    customers, products, orders, lines = build_normalized_data()
    summaries = build_denormalized_order_summaries(
        customers, products, orders, lines
    )
    indexed = build_indexed_normalized_model()

    start = time.perf_counter()
    for _ in range(iterations):
        for order_id in orders:
            normalized_order_summary(
                order_id, customers, products, orders, lines
            ).total_amount
    normalized_seconds = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        for order_id in orders:
            indexed_normalized_order_total(order_id, *indexed).quantize(
                Decimal("0.01")
            )
    indexed_seconds = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        for order_id in orders:
            summaries[order_id].total_amount
    denormalized_seconds = time.perf_counter() - start

    print("\n=== PERFORMANCE EXPERIMENT ===")
    print(f"Repeated normalized reconstruction: {normalized_seconds:.4f}s")
    print(f"Indexed normalized lookup:          {indexed_seconds:.4f}s")
    print(f"Denormalized read-model lookup:     {denormalized_seconds:.4f}s")
    print(
        "The benchmark is illustrative rather than a database benchmark. "
        "Real systems depend on indexes, cache behavior, query planners, "
        "network latency, storage engines, and data volume."
    )


def build_sales_dashboard(rows: Iterable[OrderSummary]) -> dict[str, dict]:
    """Aggregate a denormalized reporting model by region."""
    result: dict[str, dict] = {}

    for row in rows:
        if row.status == "CANCELLED":
            continue

        bucket = result.setdefault(
            row.region,
            {"orders": 0, "units": 0, "revenue": Decimal("0")},
        )
        bucket["orders"] += 1
        bucket["units"] += row.item_count
        bucket["revenue"] = money(bucket["revenue"] + row.total_amount)

    return result


def demonstrate_reporting_read_model() -> None:
    customers, products, orders, lines = build_normalized_data()
    summaries = build_denormalized_order_summaries(
        customers, products, orders, lines
    )

    dashboard = build_sales_dashboard(summaries.values())

    print("\n=== REPORTING READ MODEL ===")
    for region, values in dashboard.items():
        print(
            f"{region}: orders={values['orders']}, "
            f"units={values['units']}, revenue={values['revenue']}"
        )


def simulate_eventual_consistency() -> None:
    """
    A common architecture is:
    transactional source -> event/change -> materialized read model.

    The read model is allowed to lag briefly, but it must have a deterministic
    refresh strategy and observable freshness.
    """
    customers, products, orders, lines = build_normalized_data()
    read_model = build_denormalized_order_summaries(
        customers, products, orders, lines
    )

    source_version = 1
    read_model_version = 1

    print("\n=== EVENTUAL CONSISTENCY ===")
    print(f"Source version: {source_version}")
    print(f"Read model version: {read_model_version}")

    orders[5002] = Order(5002, 2, "2026-09-02", "SHIPPED")
    source_version += 1

    print("Source changed before read model refresh.")
    print(f"Source version: {source_version}")
    print(f"Read model version: {read_model_version}")

    read_model = build_denormalized_order_summaries(
        customers, products, orders, lines
    )
    read_model_version = source_version

    print("Read model refreshed.")
    print(f"Source version: {source_version}")
    print(f"Read model version: {read_model_version}")
    print(f"Order 5002 status: {read_model[5002].status}")


def validate_denormalized_total(
    summary: OrderSummary,
    customers: dict[int, Customer],
    products: dict[int, Product],
    orders: dict[int, Order],
    lines: list[OrderLine],
) -> bool:
    """
    Reconcile a denormalized aggregate against its normalized source.

    This is useful for audits, data-quality jobs, and repair processes.
    """
    source = normalized_order_summary(
        summary.order_id, customers, products, orders, lines
    )

    return (
        summary.customer_id == source.customer_id
        and summary.customer_name == source.customer_name
        and summary.region == source.region
        and summary.total_amount == source.total_amount
        and summary.item_count == source.item_count
    )


def demonstrate_reconciliation() -> None:
    customers, products, orders, lines = build_normalized_data()
    summaries = build_denormalized_order_summaries(
        customers, products, orders, lines
    )

    print("\n=== DATA RECONCILIATION ===")
    for summary in summaries.values():
        print(
            f"Order {summary.order_id}: "
            f"{validate_denormalized_total(summary, customers, products, orders, lines)}"
        )

    stale = deepcopy(summaries[5001])
    stale.total_amount = money(stale.total_amount + Decimal("10.00"))

    print(
        "Intentionally corrupted order 5001:",
        validate_denormalized_total(
            stale, customers, products, orders, lines
        ),
    )


def demonstrate_decision_rules() -> None:
    print("\n=== WHEN DENORMALIZATION IS JUSTIFIED ===")

    scenarios = [
        {
            "scenario": "Read-heavy dashboard",
            "benefit": "Precomputed aggregates reduce repeated joins and aggregation.",
            "risk": "Materialized values require refresh and reconciliation.",
            "decision": "Often appropriate",
        },
        {
            "scenario": "Frequently changing customer profile",
            "benefit": "Duplicating profile attributes has little read benefit if joins are cheap.",
            "risk": "Many copies become difficult to update consistently.",
            "decision": "Usually avoid",
        },
        {
            "scenario": "Historical reporting",
            "benefit": "Snapshot values preserve the business state used at transaction time.",
            "risk": "Historical semantics must be explicitly defined.",
            "decision": "Often appropriate",
        },
        {
            "scenario": "Small normalized schema with proper indexes",
            "benefit": "Indexes may already make joins inexpensive.",
            "risk": "Denormalization adds consistency work without enough performance gain.",
            "decision": "Benchmark first",
        },
    ]

    for scenario in scenarios:
        print(
            f"{scenario['scenario']}: {scenario['decision']}\n"
            f"  Benefit: {scenario['benefit']}\n"
            f"  Risk: {scenario['risk']}"
        )


def main() -> None:
    demonstrate_normalization()
    demonstrate_read_model()
    demonstrate_update_anomaly()
    demonstrate_reporting_read_model()
    simulate_eventual_consistency()
    demonstrate_reconciliation()
    demonstrate_decision_rules()
    benchmark_lookup_strategies()

    print("\n=== JSON REPRESENTATION OF A READ MODEL ROW ===")
    customers, products, orders, lines = build_normalized_data()
    summary = build_denormalized_order_summaries(
        customers, products, orders, lines
    )[5001]

    serializable = asdict(summary)
    serializable["total_amount"] = str(serializable["total_amount"])
    print(json.dumps(serializable, indent=2))

    print("\n=== KEY ENGINEERING PRINCIPLE ===")
    print(
        "Denormalize because a measured workload benefits from fewer joins, "
        "precomputed values, locality, or historical snapshots. Treat every "
        "duplicated fact as a consistency obligation with an explicit owner, "
        "refresh mechanism, and validation strategy."
    )


if __name__ == "__main__":
    main()
