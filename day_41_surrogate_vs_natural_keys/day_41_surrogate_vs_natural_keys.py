#!/usr/bin/env python3
"""
Surrogate Keys vs Natural Keys: executable database design laboratory.

Demonstrates:
- Natural-key identity and business uniqueness.
- Surrogate identifiers using integers and UUIDs.
- Composite natural keys.
- Mutable business attributes and stable references.
- Foreign-key relationships and referential integrity.
- Key migration, collision detection, and duplicate prevention.
- Deterministic identifier generation versus random UUID generation.
- Integer allocation, UUID storage costs, and key-width trade-offs.
- A dependency-free SQLite implementation of a realistic order system.

Run with:
    python keys_design_lab.py
"""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Optional


class DesignError(ValueError):
    """Raised when an identifier violates a domain rule."""


def normalize_email(email: str) -> str:
    """Normalize an email for application-level identity matching."""
    if not isinstance(email, str):
        raise DesignError("Email must be a string.")
    normalized = email.strip().casefold()
    if not normalized or "@" not in normalized:
        raise DesignError("A non-empty, valid-looking email is required.")
    local, separator, domain = normalized.partition("@")
    if not local or not separator or "." not in domain:
        raise DesignError("Email must contain a local part and a domain.")
    return normalized


def deterministic_external_id(namespace: str, external_id: str) -> str:
    """
    Create a stable namespaced identifier for a known external record.
    This is not a substitute for a unique database constraint.
    """
    if not namespace.strip() or not external_id.strip():
        raise DesignError("Namespace and external ID cannot be empty.")
    canonical = f"{namespace.strip().casefold()}:{external_id.strip()}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Customer:
    customer_id: int
    email: str
    display_name: str


@dataclass(frozen=True)
class Order:
    order_id: str
    customer_id: int
    external_reference: str
    amount_minor_units: int


class CustomerRegistry:
    """An in-memory example of surrogate identity plus natural uniqueness."""

    def __init__(self) -> None:
        self._customers: dict[int, Customer] = {}
        self._customer_id_by_email: dict[str, int] = {}
        self._next_id = 1

    def register(self, email: str, display_name: str) -> Customer:
        normalized_email = normalize_email(email)
        if not display_name.strip():
            raise DesignError("Display name cannot be empty.")

        if normalized_email in self._customer_id_by_email:
            existing_id = self._customer_id_by_email[normalized_email]
            existing = self._customers[existing_id]
            raise DesignError(
                f"Email already belongs to customer {existing.customer_id}."
            )

        customer = Customer(
            customer_id=self._next_id,
            email=normalized_email,
            display_name=display_name.strip(),
        )
        self._customers[customer.customer_id] = customer
        self._customer_id_by_email[normalized_email] = customer.customer_id
        self._next_id += 1
        return customer

    def find_by_email(self, email: str) -> Optional[Customer]:
        customer_id = self._customer_id_by_email.get(normalize_email(email))
        return self._customers.get(customer_id) if customer_id is not None else None

    def change_email(self, customer_id: int, new_email: str) -> Customer:
        """
        Changing a natural attribute does not change surrogate identity.
        The uniqueness index is updated as one logical operation.
        """
        if customer_id not in self._customers:
            raise DesignError(f"Unknown customer ID: {customer_id}")

        normalized_email = normalize_email(new_email)
        owner = self._customer_id_by_email.get(normalized_email)
        if owner is not None and owner != customer_id:
            raise DesignError("The new email belongs to another customer.")

        old_customer = self._customers[customer_id]
        self._customer_id_by_email.pop(old_customer.email)
        updated = Customer(
            customer_id=customer_id,
            email=normalized_email,
            display_name=old_customer.display_name,
        )
        self._customers[customer_id] = updated
        self._customer_id_by_email[normalized_email] = customer_id
        return updated


def demonstrate_integer_surrogate_keys() -> None:
    print("\n=== Integer surrogate keys ===")
    registry = CustomerRegistry()

    alice = registry.register("Alice@example.com", "Alice")
    bob = registry.register("bob@example.com", "Bob")
    print(f"Registered: {alice}")
    print(f"Registered: {bob}")

    updated = registry.change_email(alice.customer_id, "alice.new@example.com")
    print(f"Email changed; identity retained: {updated.customer_id}")
    print(f"Lookup: {registry.find_by_email('ALICE.NEW@example.com')}")

    try:
        registry.register(" alice.new@example.com ", "Duplicate Alice")
    except DesignError as error:
        print(f"Duplicate rejected: {error}")

    try:
        registry.change_email(bob.customer_id, "alice.new@example.com")
    except DesignError as error:
        print(f"Conflicting update rejected: {error}")


def demonstrate_uuid_keys() -> None:
    print("\n=== UUID surrogate keys ===")
    first = uuid.uuid4()
    second = uuid.uuid4()

    print(f"UUID v4: {first}")
    print(f"UUID v4: {second}")
    print(f"Different generated identifiers: {first != second}")
    print(f"Text representation: {len(str(first))} characters")
    print(f"Binary representation: {len(first.bytes)} bytes")

    namespace = "billing-system"
    external_id = "invoice-2048"
    stable_a = deterministic_external_id(namespace, external_id)
    stable_b = deterministic_external_id(namespace, external_id)
    stable_c = deterministic_external_id(namespace, "invoice-2049")

    print(f"Stable namespaced digest: {stable_a}")
    print(f"Repeated input is deterministic: {stable_a == stable_b}")
    print(f"Different input produces a different digest: {stable_a != stable_c}")
    print("A digest is not automatically collision-free; retain source uniqueness.")


def demonstrate_natural_and_composite_keys() -> None:
    print("\n=== Natural and composite keys ===")

    # A country code plus tax identifier models a jurisdiction-specific
    # business identity. The composite key is valid only if the domain
    # guarantees this pair is unique and stable.
    tax_records: dict[tuple[str, str], str] = {
        ("IN", "GSTIN-29ABCDE1234F1Z5"): "Example Supplies India",
        ("US", "EIN-12-3456789"): "Example Supplies USA",
    }

    key = ("IN", "GSTIN-29ABCDE1234F1Z5")
    print(f"Composite natural key {key}: {tax_records[key]}")

    # A natural key can be changed by legal restructuring or correction.
    old_key = ("IN", "GSTIN-29ABCDE1234F1Z5")
    new_key = ("IN", "GSTIN-29ABCDE1234F1Z6")
    entity = tax_records.pop(old_key)
    tax_records[new_key] = entity
    print(f"Natural-key update requires changing the dictionary key: {new_key}")

    # A natural key must be backed by an authoritative domain rule.
    # A person's name, address, or phone number is not generally unique.
    person_names = ["Ravi Kumar", "Ravi Kumar"]
    print(f"Repeated display names are valid: {len(person_names) == 2}")


def create_database() -> sqlite3.Connection:
    """Create a runnable relational model with explicit key constraints."""
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    connection.executescript(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            email TEXT NOT NULL COLLATE NOCASE UNIQUE,
            display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0)
        );

        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            external_reference TEXT NOT NULL UNIQUE,
            amount_minor_units INTEGER NOT NULL
                CHECK (amount_minor_units >= 0),
            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id)
                ON UPDATE RESTRICT
                ON DELETE RESTRICT
        );

        CREATE INDEX idx_orders_customer_id
            ON orders(customer_id);
        """
    )
    return connection


def demonstrate_relational_integrity() -> None:
    print("\n=== Relational key design ===")
    connection = create_database()

    try:
        with connection:
            connection.execute(
                """
                INSERT INTO customers (customer_id, email, display_name)
                VALUES (?, ?, ?)
                """,
                (101, "alice@example.com", "Alice"),
            )
            connection.execute(
                """
                INSERT INTO customers (customer_id, email, display_name)
                VALUES (?, ?, ?)
                """,
                (102, "bob@example.com", "Bob"),
            )
            connection.execute(
                """
                INSERT INTO orders
                    (order_id, customer_id, external_reference, amount_minor_units)
                VALUES (?, ?, ?, ?)
                """,
                ("ord_8f42", 101, "WEB-2026-0001", 129900),
            )
            connection.execute(
                """
                INSERT INTO orders
                    (order_id, customer_id, external_reference, amount_minor_units)
                VALUES (?, ?, ?, ?)
                """,
                ("ord_9c17", 101, "WEB-2026-0002", 4500),
            )

        rows = connection.execute(
            """
            SELECT c.customer_id, c.email, o.order_id,
                   o.external_reference, o.amount_minor_units
            FROM customers AS c
            JOIN orders AS o ON o.customer_id = c.customer_id
            ORDER BY o.external_reference
            """
        ).fetchall()

        for row in rows:
            print(row)

        invalid_operations = [
            (
                "duplicate natural key",
                """
                INSERT INTO customers (customer_id, email, display_name)
                VALUES (103, 'ALICE@example.com', 'Duplicate')
                """,
            ),
            (
                "missing referenced customer",
                """
                INSERT INTO orders
                    (order_id, customer_id, external_reference, amount_minor_units)
                VALUES ('ord_bad', 999, 'WEB-2026-0003', 100)
                """,
            ),
            (
                "negative amount",
                """
                INSERT INTO orders
                    (order_id, customer_id, external_reference, amount_minor_units)
                VALUES ('ord_bad2', 101, 'WEB-2026-0004', -10)
                """,
            ),
            (
                "duplicate external reference",
                """
                INSERT INTO orders
                    (order_id, customer_id, external_reference, amount_minor_units)
                VALUES ('ord_bad3', 101, 'WEB-2026-0001', 100)
                """,
            ),
        ]

        for label, statement in invalid_operations:
            try:
                with connection:
                    connection.execute(statement)
            except sqlite3.IntegrityError as error:
                print(f"Database rejected {label}: {error}")

        # Natural attributes can change without rewriting dependent rows.
        with connection:
            connection.execute(
                "UPDATE customers SET email = ? WHERE customer_id = ?",
                ("alice.updated@example.com", 101),
            )

        order_count = connection.execute(
            "SELECT COUNT(*) FROM orders WHERE customer_id = 101"
        ).fetchone()[0]
        print(f"Orders remain linked after email change: {order_count}")

        try:
            with connection:
                connection.execute("DELETE FROM customers WHERE customer_id = 101")
        except sqlite3.IntegrityError as error:
            print(f"Referenced customer deletion rejected: {error}")

    finally:
        connection.close()


def compare_design_tradeoffs() -> None:
    print("\n=== Identifier design trade-offs ===")

    designs = [
        {
            "strategy": "32-bit integer",
            "payload_bytes": 4,
            "generation": "Central sequence or coordinated allocator",
            "benefit": "Compact indexes and efficient joins",
            "risk": "Coordination and possible identifier enumeration",
        },
        {
            "strategy": "64-bit integer",
            "payload_bytes": 8,
            "generation": "Database identity or sequence",
            "benefit": "Large capacity and compact joins",
            "risk": "Coordination; public IDs can expose approximate volume",
        },
        {
            "strategy": "UUID",
            "payload_bytes": 16,
            "generation": "Distributed UUID generation",
            "benefit": "Independent generation across services",
            "risk": "Larger indexes and less sequential insertion for random UUIDs",
        },
        {
            "strategy": "Natural string",
            "payload_bytes": "variable",
            "generation": "Authoritative business identifier",
            "benefit": "Carries domain meaning and can support external matching",
            "risk": "Mutability, normalization, collation, and wider indexes",
        },
    ]

    for design in designs:
        print(
            f"{design['strategy']}: storage={design['payload_bytes']}, "
            f"generation={design['generation']}; "
            f"benefit={design['benefit']}; risk={design['risk']}"
        )

    print(
        "Storage estimates exclude row headers, index overhead, alignment, "
        "and secondary-index entries."
    )


def main() -> None:
    demonstrate_integer_surrogate_keys()
    demonstrate_uuid_keys()
    demonstrate_natural_and_composite_keys()
    demonstrate_relational_integrity()
    compare_design_tradeoffs()


if __name__ == "__main__":
    main()
