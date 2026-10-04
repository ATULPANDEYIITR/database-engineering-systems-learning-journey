"""
Normalization II: 1NF, 2NF, and 3NF

A self-contained executable learning program that demonstrates relational
normalization by transforming an intentionally problematic order dataset
through First Normal Form, Second Normal Form, and Third Normal Form.

The example domain is an order-management system. The normalization rules are
implemented explicitly so that functional dependencies, candidate keys,
partial dependencies, and transitive dependencies can be observed in code.

Run:
    python normalization_ii.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


def print_title(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def print_table(rows: Iterable[dict[str, Any]], columns: list[str]) -> None:
    rows = list(rows)
    if not rows:
        print("(no rows)")
        return

    widths = {
        column: max(
            len(column),
            *(len(str(row.get(column, ""))) for row in rows),
        )
        for column in columns
    }

    header = " | ".join(column.ljust(widths[column]) for column in columns)
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


def assert_unique(rows: list[dict[str, Any]], key_columns: tuple[str, ...]) -> None:
    seen: set[tuple[Any, ...]] = set()

    for row in rows:
        key = tuple(row[column] for column in key_columns)
        if key in seen:
            raise ValueError(
                f"Duplicate key {key!r} violates uniqueness for {key_columns}"
            )
        seen.add(key)


def check_atomic_values(rows: list[dict[str, Any]]) -> list[str]:
    """
    1NF requires each attribute value to contain one atomic value rather than
    a repeating group or an embedded list of values.
    """
    violations: list[str] = []

    for row_number, row in enumerate(rows, start=1):
        for column, value in row.items():
            if isinstance(value, (list, tuple, set, dict)):
                violations.append(
                    f"row {row_number}, column {column!r}: "
                    f"non-atomic value {value!r}"
                )

    return violations


def demonstrate_unstructured_relation() -> list[dict[str, Any]]:
    """
    This relation deliberately contains a repeating product group.

    A single order can therefore contain several products inside one attribute.
    Such a representation is difficult to search, constrain, index, and join.
    """
    return [
        {
            "order_id": 1001,
            "order_date": "2026-10-01",
            "customer_id": "C001",
            "customer_name": "Asha Rao",
            "customer_city": "Lucknow",
            "products": [
                {"product_id": "P101", "product_name": "Keyboard", "qty": 2},
                {"product_id": "P102", "product_name": "Mouse", "qty": 1},
            ],
        },
        {
            "order_id": 1002,
            "order_date": "2026-10-02",
            "customer_id": "C002",
            "customer_name": "Rohan Mehta",
            "customer_city": "Delhi",
            "products": [
                {"product_id": "P101", "product_name": "Keyboard", "qty": 1},
            ],
        },
    ]


def convert_to_1nf(
    non_1nf_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Flatten the repeating product group.

    Each resulting row represents one order-product combination. Every
    attribute contains one value, making the relation atomic.
    """
    rows: list[dict[str, Any]] = []

    for order in non_1nf_rows:
        for product in order["products"]:
            rows.append(
                {
                    "order_id": order["order_id"],
                    "order_date": order["order_date"],
                    "customer_id": order["customer_id"],
                    "customer_name": order["customer_name"],
                    "customer_city": order["customer_city"],
                    "product_id": product["product_id"],
                    "product_name": product["product_name"],
                    "quantity": product["qty"],
                }
            )

    return rows


def functional_dependency_holds(
    rows: list[dict[str, Any]],
    determinant: tuple[str, ...],
    dependent: str,
) -> bool:
    """
    Test a functional dependency X -> Y on the supplied instance.

    If two rows agree on X, they must agree on Y.
    """
    observed: dict[tuple[Any, ...], Any] = {}

    for row in rows:
        determinant_value = tuple(row[column] for column in determinant)
        dependent_value = row[dependent]

        if determinant_value in observed:
            if observed[determinant_value] != dependent_value:
                return False
        else:
            observed[determinant_value] = dependent_value

    return True


def find_partial_dependencies(
    rows: list[dict[str, Any]],
    composite_key: tuple[str, ...],
    non_key_columns: tuple[str, ...],
) -> list[tuple[tuple[str, ...], str]]:
    """
    Find simple partial dependencies for the educational relation.

    For a two-column composite key, a dependency on only one component of the
    key is a partial dependency.
    """
    if len(composite_key) != 2:
        raise ValueError("This demonstration expects a two-column composite key.")

    dependencies: list[tuple[tuple[str, ...], str]] = []

    for determinant in composite_key:
        for dependent in non_key_columns:
            if functional_dependency_holds(rows, (determinant,), dependent):
                dependencies.append(((determinant,), dependent))

    return dependencies


def demonstrate_1nf(rows: list[dict[str, Any]]) -> None:
    print_title("FIRST NORMAL FORM: ATOMIC VALUES")

    print("The original relation contains a repeating products attribute.")
    original = demonstrate_unstructured_relation()

    violations = check_atomic_values(original)
    print("\n1NF violations:")
    for violation in violations:
        print(f"  {violation}")

    print("\nAfter flattening the repeating group:")
    print_table(
        rows,
        [
            "order_id",
            "product_id",
            "quantity",
            "product_name",
            "customer_id",
        ],
    )

    print("\nAtomic-value validation:")
    atomic_violations = check_atomic_values(rows)
    print("PASS" if not atomic_violations else atomic_violations)

    assert_unique(rows, ("order_id", "product_id"))
    print("Candidate key used for this relation: (order_id, product_id).")


def demonstrate_2nf(rows: list[dict[str, Any]]) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """
    2NF is relevant because the 1NF relation uses a composite key:
    (order_id, product_id).

    quantity depends on the complete key.

    order_date and customer_id depend only on order_id.
    product_name depends only on product_id.

    Those are partial dependencies, so the relation is not in 2NF.
    """
    print_title("SECOND NORMAL FORM: REMOVE PARTIAL DEPENDENCIES")

    composite_key = ("order_id", "product_id")
    non_key_columns = (
        "order_date",
        "customer_id",
        "customer_name",
        "customer_city",
        "product_name",
        "quantity",
    )

    partials = find_partial_dependencies(
        rows,
        composite_key,
        non_key_columns,
    )

    print("Composite key:", composite_key)
    print("\nObserved partial dependencies:")

    for determinant, dependent in partials:
        print(f"  {determinant} -> {dependent}")

    print(
        "\nThe important design problem is that order attributes are stored "
        "on every product line and product attributes are stored on every "
        "order containing that product."
    )

    orders = [
        {
            "order_id": row["order_id"],
            "order_date": row["order_date"],
            "customer_id": row["customer_id"],
            "customer_name": row["customer_name"],
            "customer_city": row["customer_city"],
        }
        for row in rows
    ]

    products = [
        {
            "product_id": row["product_id"],
            "product_name": row["product_name"],
        }
        for row in rows
    ]

    order_items = [
        {
            "order_id": row["order_id"],
            "product_id": row["product_id"],
            "quantity": row["quantity"],
        }
        for row in rows
    ]

    orders = deduplicate(orders, ("order_id",))
    products = deduplicate(products, ("product_id",))

    print("\nOrders relation after decomposition:")
    print_table(
        orders,
        ["order_id", "order_date", "customer_id", "customer_name", "customer_city"],
    )

    print("\nProducts relation after decomposition:")
    print_table(products, ["product_id", "product_name"])

    print("\nOrderItems relation:")
    print_table(order_items, ["order_id", "product_id", "quantity"])

    return orders, products, order_items


def deduplicate(
    rows: list[dict[str, Any]],
    key_columns: tuple[str, ...],
) -> list[dict[str, Any]]:
    """
    Deduplicate rows created by projection.

    The function deliberately rejects contradictory values for the same key.
    A projection cannot silently hide a functional-dependency violation.
    """
    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}

    for row in rows:
        key = tuple(row[column] for column in key_columns)

        if key not in by_key:
            by_key[key] = dict(row)
            continue

        if by_key[key] != row:
            raise ValueError(
                f"Lossy or inconsistent projection for key {key}: "
                f"{by_key[key]} != {row}"
            )

    return list(by_key.values())


def demonstrate_3nf(
    orders: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    3NF addresses transitive dependencies.

    In the 2NF Orders relation:

        order_id -> customer_id
        customer_id -> customer_name, customer_city

    Therefore:

        order_id -> customer_name, customer_city

    transitively through customer_id.

    Customer attributes belong in a Customer relation.
    """
    print_title("THIRD NORMAL FORM: REMOVE TRANSITIVE DEPENDENCIES")

    print("Functional dependencies in the 2NF Orders relation:")
    print("  order_id -> customer_id")
    print("  customer_id -> customer_name, customer_city")
    print(
        "Therefore customer_name and customer_city are transitively dependent "
        "on order_id."
    )

    customers = deduplicate(
        [
            {
                "customer_id": row["customer_id"],
                "customer_name": row["customer_name"],
                "customer_city": row["customer_city"],
            }
            for row in orders
        ],
        ("customer_id",),
    )

    normalized_orders = [
        {
            "order_id": row["order_id"],
            "order_date": row["order_date"],
            "customer_id": row["customer_id"],
        }
        for row in orders
    ]

    print("\nCustomer relation:")
    print_table(customers, ["customer_id", "customer_name", "customer_city"])

    print("\nOrders relation after removing customer transitive dependency:")
    print_table(
        normalized_orders,
        ["order_id", "order_date", "customer_id"],
    )

    return normalized_orders, customers


def validate_3nf_design(
    orders: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    products: list[dict[str, Any]],
    order_items: list[dict[str, Any]],
) -> None:
    print_title("NORMALIZED DESIGN VALIDATION")

    assert_unique(orders, ("order_id",))
    assert_unique(customers, ("customer_id",))
    assert_unique(products, ("product_id",))
    assert_unique(order_items, ("order_id", "product_id"))

    customer_ids = {row["customer_id"] for row in customers}
    product_ids = {row["product_id"] for row in products}
    order_ids = {row["order_id"] for row in orders}

    for order in orders:
        if order["customer_id"] not in customer_ids:
            raise ValueError(
                f"Foreign-key violation: order {order['order_id']} "
                f"references missing customer {order['customer_id']}"
            )

    for item in order_items:
        if item["order_id"] not in order_ids:
            raise ValueError(
                f"Foreign-key violation: item references missing order "
                f"{item['order_id']}"
            )
        if item["product_id"] not in product_ids:
            raise ValueError(
                f"Foreign-key violation: item references missing product "
                f"{item['product_id']}"
            )
        if item["quantity"] <= 0:
            raise ValueError("Quantity must be greater than zero.")

    print("Primary-key uniqueness: PASS")
    print("Foreign-key consistency: PASS")
    print("Positive quantity constraint: PASS")

    assert functional_dependency_holds(
        orders,
        ("order_id",),
        "customer_id",
    )
    assert functional_dependency_holds(
        customers,
        ("customer_id",),
        "customer_name",
    )
    assert functional_dependency_holds(
        customers,
        ("customer_id",),
        "customer_city",
    )
    assert functional_dependency_holds(
        products,
        ("product_id",),
        "product_name",
    )

    print("Relevant functional dependencies: PASS")


def demonstrate_anomalies() -> None:
    print_title("ANOMALIES THAT NORMALIZATION PREVENTS")

    print(
        "Update anomaly: if a customer's city is duplicated across many order "
        "rows, changing the city requires updating every occurrence."
    )
    print(
        "Insertion anomaly: if product information exists only inside an "
        "order-line relation, adding a product before its first order may "
        "require artificial order data."
    )
    print(
        "Deletion anomaly: deleting the last order containing a product can "
        "accidentally remove the only stored description of that product."
    )

    print(
        "\nAfter decomposition, customer facts live in Customers, product facts "
        "live in Products, order facts live in Orders, and the relationship "
        "between orders and products lives in OrderItems."
    )


def demonstrate_edge_cases() -> None:
    print_title("EDGE CASES AND FAILURE CONDITIONS")

    duplicate_items = [
        {"order_id": 1001, "product_id": "P101", "quantity": 2},
        {"order_id": 1001, "product_id": "P101", "quantity": 3},
    ]

    try:
        assert_unique(duplicate_items, ("order_id", "product_id"))
    except ValueError as exc:
        print("Duplicate composite key rejected:")
        print(" ", exc)

    contradictory_customers = [
        {
            "customer_id": "C001",
            "customer_name": "Asha Rao",
            "customer_city": "Lucknow",
        },
        {
            "customer_id": "C001",
            "customer_name": "Asha Rao",
            "customer_city": "Kanpur",
        },
    ]

    try:
        deduplicate(contradictory_customers, ("customer_id",))
    except ValueError as exc:
        print("\nContradictory functional dependency rejected:")
        print(" ", exc)

    invalid_quantity = {"order_id": 1004, "product_id": "P103", "quantity": 0}
    if invalid_quantity["quantity"] <= 0:
        print("\nInvalid quantity rejected: quantity must be positive.")


@dataclass(frozen=True)
class FunctionalDependency:
    determinant: frozenset[str]
    dependent: frozenset[str]

    def describes(self) -> str:
        left = ", ".join(sorted(self.determinant))
        right = ", ".join(sorted(self.dependent))
        return f"{left} -> {right}"


def explain_normal_forms() -> None:
    print_title("NORMAL-FORM RULES")

    rules = [
        (
            "1NF",
            "Attributes contain atomic values and repeating groups are removed.",
        ),
        (
            "2NF",
            "The relation is in 1NF and every non-key attribute depends on "
            "the whole candidate key, not merely part of a composite key.",
        ),
        (
            "3NF",
            "The relation is in 2NF and non-key attributes do not depend "
            "transitively on a candidate key through another non-key attribute.",
        ),
    ]

    for name, rule in rules:
        print(f"{name}: {rule}")


def demonstrate_dependency_model() -> None:
    print_title("FUNCTIONAL DEPENDENCY MODEL")

    dependencies = [
        FunctionalDependency(
            frozenset({"order_id"}),
            frozenset({"order_date", "customer_id"}),
        ),
        FunctionalDependency(
            frozenset({"customer_id"}),
            frozenset({"customer_name", "customer_city"}),
        ),
        FunctionalDependency(
            frozenset({"product_id"}),
            frozenset({"product_name"}),
        ),
        FunctionalDependency(
            frozenset({"order_id", "product_id"}),
            frozenset({"quantity"}),
        ),
    ]

    for dependency in dependencies:
        print(dependency.describes())

    print(
        "\nThe composite dependency (order_id, product_id) -> quantity is "
        "appropriate for OrderItems, while customer and product dependencies "
        "are represented by their own relations."
    )


def demonstrate_joined_view(
    orders: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    products: list[dict[str, Any]],
    order_items: list[dict[str, Any]],
) -> None:
    print_title("RECONSTRUCTING BUSINESS INFORMATION WITH JOINS")

    customer_by_id = {row["customer_id"]: row for row in customers}
    product_by_id = {row["product_id"]: row for row in products}
    order_by_id = {row["order_id"]: row for row in orders}

    result: list[dict[str, Any]] = []

    for item in order_items:
        order = order_by_id[item["order_id"]]
        customer = customer_by_id[order["customer_id"]]
        product = product_by_id[item["product_id"]]

        result.append(
            {
                "order_id": order["order_id"],
                "order_date": order["order_date"],
                "customer": customer["customer_name"],
                "city": customer["customer_city"],
                "product": product["product_name"],
                "quantity": item["quantity"],
            }
        )

    print_table(
        result,
        [
            "order_id",
            "order_date",
            "customer",
            "city",
            "product",
            "quantity",
        ],
    )


def demonstrate_update_behavior(
    customers: list[dict[str, Any]],
    orders: list[dict[str, Any]],
) -> None:
    print_title("UPDATE BEHAVIOR AFTER NORMALIZATION")

    customer_by_id = {row["customer_id"]: row for row in customers}

    print("Before update:")
    print_table(customers, ["customer_id", "customer_name", "customer_city"])

    customer_id = "C001"
    customer_by_id[customer_id]["customer_city"] = "Kanpur"

    print("\nAfter changing C001's city once:")
    print_table(customers, ["customer_id", "customer_name", "customer_city"])

    affected_orders = [
        order["order_id"]
        for order in orders
        if order["customer_id"] == customer_id
    ]

    print(
        f"\nOrders belonging to {customer_id} now observe the same customer "
        f"fact through the relationship: {affected_orders}"
    )


def main() -> None:
    print_title("NORMALIZATION II: 1NF, 2NF, AND 3NF")
    print(
        "Domain: an order-management relation containing customers, products, "
        "orders, and order items."
    )

    explain_normal_forms()

    non_1nf = demonstrate_unstructured_relation()
    one_nf = convert_to_1nf(non_1nf)

    demonstrate_1nf(one_nf)

    orders_2nf, products_2nf, order_items_2nf = demonstrate_2nf(one_nf)

    orders_3nf, customers_3nf = demonstrate_3nf(orders_2nf)

    validate_3nf_design(
        orders_3nf,
        customers_3nf,
        products_2nf,
        order_items_2nf,
    )

    demonstrate_dependency_model()
    demonstrate_anomalies()
    demonstrate_edge_cases()

    demonstrate_joined_view(
        orders_3nf,
        customers_3nf,
        products_2nf,
        order_items_2nf,
    )

    demonstrate_update_behavior(customers_3nf, orders_3nf)

    print_title("FINAL RELATIONAL DESIGN")
    print("Customers(customer_id, customer_name, customer_city)")
    print("Orders(order_id, order_date, customer_id)")
    print("Products(product_id, product_name)")
    print("OrderItems(order_id, product_id, quantity)")
    print(
        "\nPrimary keys:"
        "\n  Customers: customer_id"
        "\n  Orders: order_id"
        "\n  Products: product_id"
        "\n  OrderItems: (order_id, product_id)"
    )
    print(
        "\nThe design separates repeating groups, partial dependencies, and "
        "transitive dependencies while preserving the ability to reconstruct "
        "the business view through joins."
    )


if __name__ == "__main__":
    main()
