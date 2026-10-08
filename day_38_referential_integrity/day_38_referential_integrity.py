from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import sqlite3
import tempfile
from pathlib import Path


class ReferentialIntegrityError(Exception):
    """Raised when a relationship would violate a referential-integrity rule."""


class CascadeAction(Enum):
    RESTRICT = "RESTRICT"
    CASCADE = "CASCADE"
    SET_NULL = "SET NULL"
    SET_DEFAULT = "SET DEFAULT"


@dataclass
class Customer:
    customer_id: int
    name: str


@dataclass
class Order:
    order_id: int
    customer_id: int
    amount: float


@dataclass
class OrderItem:
    item_id: int
    order_id: int
    product: str
    quantity: int


class ReferentialIntegrityStore:
    """
    In-memory model of parent/child relationships.

    The Customer -> Order relationship uses RESTRICT semantics:
    a customer cannot be deleted while dependent orders exist.

    The Order -> OrderItem relationship uses CASCADE semantics:
    deleting an order automatically removes its dependent items.
    """

    def __init__(self) -> None:
        self.customers: Dict[int, Customer] = {}
        self.orders: Dict[int, Order] = {}
        self.items: Dict[int, OrderItem] = {}

    def add_customer(self, customer_id: int, name: str) -> None:
        if customer_id in self.customers:
            raise ReferentialIntegrityError(
                f"Customer {customer_id} already exists."
            )
        if not name.strip():
            raise ValueError("Customer name cannot be empty.")
        self.customers[customer_id] = Customer(customer_id, name.strip())

    def add_order(self, order_id: int, customer_id: int, amount: float) -> None:
        if order_id in self.orders:
            raise ReferentialIntegrityError(f"Order {order_id} already exists.")
        if customer_id not in self.customers:
            raise ReferentialIntegrityError(
                f"Cannot insert order {order_id}: customer "
                f"{customer_id} does not exist."
            )
        if amount < 0:
            raise ValueError("Order amount cannot be negative.")
        self.orders[order_id] = Order(order_id, customer_id, amount)

    def add_item(
        self,
        item_id: int,
        order_id: int,
        product: str,
        quantity: int,
    ) -> None:
        if item_id in self.items:
            raise ReferentialIntegrityError(f"Item {item_id} already exists.")
        if order_id not in self.orders:
            raise ReferentialIntegrityError(
                f"Cannot insert item {item_id}: order {order_id} does not exist."
            )
        if quantity <= 0:
            raise ValueError("Item quantity must be positive.")
        if not product.strip():
            raise ValueError("Product name cannot be empty.")

        self.items[item_id] = OrderItem(
            item_id,
            order_id,
            product.strip(),
            quantity,
        )

    def delete_customer_restrict(self, customer_id: int) -> None:
        if customer_id not in self.customers:
            raise ReferentialIntegrityError(
                f"Customer {customer_id} does not exist."
            )

        dependent_orders = [
            order.order_id
            for order in self.orders.values()
            if order.customer_id == customer_id
        ]

        if dependent_orders:
            raise ReferentialIntegrityError(
                f"RESTRICT prevented deletion of customer {customer_id}; "
                f"dependent orders exist: {dependent_orders}"
            )

        del self.customers[customer_id]

    def delete_order_cascade(self, order_id: int) -> None:
        if order_id not in self.orders:
            raise ReferentialIntegrityError(f"Order {order_id} does not exist.")

        dependent_items = [
            item.item_id
            for item in self.items.values()
            if item.order_id == order_id
        ]

        for item_id in dependent_items:
            del self.items[item_id]

        del self.orders[order_id]

    def reassign_order(self, order_id: int, new_customer_id: int) -> None:
        if order_id not in self.orders:
            raise ReferentialIntegrityError(f"Order {order_id} does not exist.")
        if new_customer_id not in self.customers:
            raise ReferentialIntegrityError(
                f"Cannot reassign order to missing customer {new_customer_id}."
            )

        order = self.orders[order_id]
        self.orders[order_id] = Order(
            order.order_id,
            new_customer_id,
            order.amount,
        )

    def delete_customer_with_cascade(self, customer_id: int) -> None:
        """
        Demonstrates a different policy.

        Customer deletion cascades to orders, and order deletion cascades
        further to order items. This produces a transitive cascade.
        """
        if customer_id not in self.customers:
            raise ReferentialIntegrityError(
                f"Customer {customer_id} does not exist."
            )

        order_ids = [
            order.order_id
            for order in self.orders.values()
            if order.customer_id == customer_id
        ]

        for order_id in order_ids:
            self.delete_order_cascade(order_id)

        del self.customers[customer_id]

    def validate(self) -> List[str]:
        errors: List[str] = []

        for order in self.orders.values():
            if order.customer_id not in self.customers:
                errors.append(
                    f"Order {order.order_id} references missing "
                    f"customer {order.customer_id}."
                )

        for item in self.items.values():
            if item.order_id not in self.orders:
                errors.append(
                    f"Item {item.item_id} references missing order "
                    f"{item.order_id}."
                )

        return errors

    def snapshot(self) -> Dict[str, int]:
        return {
            "customers": len(self.customers),
            "orders": len(self.orders),
            "items": len(self.items),
        }


def demonstrate_basic_foreign_key_relationships() -> None:
    print("\n=== Parent and child relationships ===")

    store = ReferentialIntegrityStore()
    store.add_customer(1, "Asha Industries")
    store.add_customer(2, "Northstar Systems")

    store.add_order(101, 1, 12500.00)
    store.add_order(102, 1, 8200.00)
    store.add_order(103, 2, 9100.00)

    store.add_item(1001, 101, "Network Switch", 2)
    store.add_item(1002, 101, "Fiber Module", 4)
    store.add_item(1003, 102, "Firewall License", 1)

    print("State:", store.snapshot())
    print("Integrity errors:", store.validate())

    try:
        store.add_order(104, 999, 500.00)
    except ReferentialIntegrityError as exc:
        print("Rejected invalid child:", exc)


def demonstrate_restrict_and_cascade() -> None:
    print("\n=== RESTRICT and CASCADE ===")

    store = ReferentialIntegrityStore()
    store.add_customer(10, "Acme Manufacturing")
    store.add_order(501, 10, 45000.00)
    store.add_item(9001, 501, "Industrial Sensor", 10)
    store.add_item(9002, 501, "Gateway", 2)

    try:
        store.delete_customer_restrict(10)
    except ReferentialIntegrityError as exc:
        print("RESTRICT:", exc)

    print("Before deleting order:", store.snapshot())
    store.delete_order_cascade(501)
    print("After deleting order with CASCADE:", store.snapshot())

    store.delete_customer_restrict(10)
    print("Customer can now be deleted because no child orders remain.")
    print("Final state:", store.snapshot())


def demonstrate_transitive_cascade() -> None:
    print("\n=== Transitive CASCADE ===")

    store = ReferentialIntegrityStore()
    store.add_customer(20, "Cascade Test Corp")
    store.add_order(601, 20, 1000.00)
    store.add_order(602, 20, 2000.00)
    store.add_item(9101, 601, "Part A", 3)
    store.add_item(9102, 601, "Part B", 4)
    store.add_item(9103, 602, "Part C", 5)

    print("Before customer deletion:", store.snapshot())
    store.delete_customer_with_cascade(20)
    print("After customer -> orders -> items cascade:", store.snapshot())


def demonstrate_set_null_semantics() -> None:
    print("\n=== SET NULL relationship ===")

    records = [
        {"employee_id": 1, "name": "Ravi", "manager_id": None},
        {"employee_id": 2, "name": "Meera", "manager_id": 1},
        {"employee_id": 3, "name": "Kabir", "manager_id": 1},
    ]

    print("Before manager deletion:", records)

    deleted_manager = 1

    for employee in records:
        if employee["manager_id"] == deleted_manager:
            employee["manager_id"] = None

    records = [
        employee
        for employee in records
        if employee["employee_id"] != deleted_manager
    ]

    print("After SET NULL behavior:", records)
    print(
        "SET NULL preserves child rows but removes the reference. "
        "The foreign-key column must therefore allow NULL."
    )


def demonstrate_transactional_sqlite() -> None:
    print("\n=== Real SQLite foreign-key enforcement ===")

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    connection.executescript(
        """
        CREATE TABLE customer (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE customer_order (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            amount REAL NOT NULL CHECK (amount >= 0),
            FOREIGN KEY (customer_id)
                REFERENCES customer(customer_id)
                ON DELETE RESTRICT
                ON UPDATE CASCADE
        );

        CREATE TABLE order_item (
            item_id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL,
            product TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            FOREIGN KEY (order_id)
                REFERENCES customer_order(order_id)
                ON DELETE CASCADE
        );
        """
    )

    connection.execute(
        "INSERT INTO customer(customer_id, name) VALUES (?, ?)",
        (1, "Database Customer"),
    )

    connection.execute(
        """
        INSERT INTO customer_order(order_id, customer_id, amount)
        VALUES (?, ?, ?)
        """,
        (100, 1, 2500.00),
    )

    connection.execute(
        """
        INSERT INTO order_item(item_id, order_id, product, quantity)
        VALUES (?, ?, ?, ?)
        """,
        (1000, 100, "Storage Device", 2),
    )

    try:
        connection.execute(
            "INSERT INTO customer_order(order_id, customer_id, amount) "
            "VALUES (?, ?, ?)",
            (101, 999, 500.00),
        )
    except sqlite3.IntegrityError as exc:
        print("Database rejected orphan order:", exc)

    try:
        connection.execute("DELETE FROM customer WHERE customer_id = ?", (1,))
    except sqlite3.IntegrityError as exc:
        print("Database enforced RESTRICT:", exc)

    connection.execute("DELETE FROM customer_order WHERE order_id = ?", (100,))

    remaining_items = connection.execute(
        "SELECT COUNT(*) FROM order_item WHERE order_id = 100"
    ).fetchone()[0]

    print("Items remaining after order deletion:", remaining_items)

    connection.close()


def demonstrate_update_actions() -> None:
    print("\n=== ON UPDATE behavior ===")

    store = ReferentialIntegrityStore()
    store.add_customer(30, "Original Customer")
    store.add_order(701, 30, 300.00)

    old_id = 30
    new_id = 31

    customer = store.customers.pop(old_id)
    store.customers[new_id] = Customer(new_id, customer.name)

    for order_id, order in list(store.orders.items()):
        if order.customer_id == old_id:
            store.orders[order_id] = Order(
                order.order_id,
                new_id,
                order.amount,
            )

    print("Updated customer key:", new_id)
    print("Order now references:", store.orders[701].customer_id)
    print("Integrity errors:", store.validate())


def demonstrate_failure_modes() -> None:
    print("\n=== Failure conditions and validation ===")

    store = ReferentialIntegrityStore()

    try:
        store.add_item(1, 999, "Orphan Item", 1)
    except ReferentialIntegrityError as exc:
        print("Orphan prevention:", exc)

    store.add_customer(40, "Validation Customer")

    try:
        store.add_order(801, 40, -50)
    except ValueError as exc:
        print("Domain validation:", exc)

    try:
        store.add_customer(40, "Duplicate Customer")
    except ReferentialIntegrityError as exc:
        print("Duplicate parent prevention:", exc)

    store.add_order(801, 40, 500)
    store.add_item(8011, 801, "Valid Product", 1)

    try:
        store.reassign_order(801, 4040)
    except ReferentialIntegrityError as exc:
        print("Invalid reassignment prevention:", exc)

    print("Integrity validation:", store.validate())


def main() -> None:
    print("REFERENTIAL INTEGRITY: FOREIGN KEYS AND CASCADING ACTIONS")

    demonstrate_basic_foreign_key_relationships()
    demonstrate_restrict_and_cascade()
    demonstrate_transitive_cascade()
    demonstrate_set_null_semantics()
    demonstrate_update_actions()
    demonstrate_failure_modes()
    demonstrate_transactional_sqlite()

    print("\n=== Production considerations ===")
    print(
        "Foreign keys protect database invariants at the storage boundary; "
        "application validation should complement them rather than replace them."
    )
    print(
        "Choose CASCADE only when deleting the parent logically means deleting "
        "the dependent data. Use RESTRICT when child records have independent "
        "business significance."
    )
    print(
        "Use SET NULL only when an orphaned child without its former parent "
        "remains meaningful and the foreign-key column is nullable."
    )
    print(
        "Indexes on foreign-key columns improve joins and make dependent-row "
        "checks and cascading operations more efficient on large tables."
    )


if __name__ == "__main__":
    main()
