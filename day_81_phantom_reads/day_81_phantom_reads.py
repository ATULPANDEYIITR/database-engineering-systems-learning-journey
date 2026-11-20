#!/usr/bin/env python3
"""
Phantom Reads: Range Queries and Transaction Isolation

Demonstrates:
- Read Committed phantom reads
- Repeatable Read snapshot behavior
- Serializable predicate-range validation
- Transaction-local writes
- Concurrent transaction interleaving
- Write conflict detection
- Atomic commit and rollback
- Range boundaries and validation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import copy
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("phantom_reads")


class IsolationLevel(Enum):
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


class TransactionState(Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class TransactionError(Exception):
    pass


class SerializationFailure(TransactionError):
    pass


class WriteConflict(TransactionError):
    pass


class InvalidTransaction(TransactionError):
    pass


@dataclass(frozen=True)
class RangePredicate:
    minimum: float
    maximum: float
    include_minimum: bool = True
    include_maximum: bool = False

    def __post_init__(self):
        if self.minimum > self.maximum:
            raise ValueError("Minimum cannot exceed maximum")

    def contains(self, value: float) -> bool:
        lower = (
            value >= self.minimum
            if self.include_minimum
            else value > self.minimum
        )
        upper = (
            value <= self.maximum
            if self.include_maximum
            else value < self.maximum
        )
        return lower and upper


@dataclass
class Product:
    product_id: int
    name: str
    price: float
    category: str

    def validate(self):
        if self.product_id <= 0:
            raise ValueError("Product ID must be positive")
        if not self.name.strip():
            raise ValueError("Product name cannot be empty")
        if self.price < 0:
            raise ValueError("Price cannot be negative")
        if not self.category.strip():
            raise ValueError("Category cannot be empty")


@dataclass
class VersionedProduct:
    product: Product
    version: int


@dataclass
class Transaction:
    transaction_id: int
    isolation: IsolationLevel
    snapshot: dict[int, VersionedProduct]
    start_version: int
    state: TransactionState = TransactionState.ACTIVE
    writes: dict[int, Optional[Product]] = field(default_factory=dict)
    read_ranges: list[RangePredicate] = field(default_factory=list)


class Database:
    def __init__(self):
        self._rows: dict[int, VersionedProduct] = {}
        self._version = 0
        self._next_transaction_id = 1
        self._commit_history: list[tuple[int, Product]] = []

    def seed(self, products: list[Product]):
        for product in products:
            product.validate()
            if product.product_id in self._rows:
                raise ValueError("Duplicate product ID")

            self._version += 1
            self._rows[product.product_id] = VersionedProduct(
                copy.deepcopy(product),
                self._version
            )

    def begin(
        self,
        isolation: IsolationLevel = IsolationLevel.READ_COMMITTED
    ) -> Transaction:
        snapshot = copy.deepcopy(self._rows)

        transaction = Transaction(
            transaction_id=self._next_transaction_id,
            isolation=isolation,
            snapshot=snapshot,
            start_version=self._version
        )

        self._next_transaction_id += 1

        logger.info(
            "Transaction %s started using %s",
            transaction.transaction_id,
            isolation.value
        )

        return transaction

    def _ensure_active(self, transaction: Transaction):
        if transaction.state != TransactionState.ACTIVE:
            raise InvalidTransaction(
                f"Transaction {transaction.transaction_id} "
                f"is {transaction.state.value}"
            )

    def _visible_rows(
        self,
        transaction: Transaction
    ) -> dict[int, Product]:

        self._ensure_active(transaction)

        source = (
            self._rows
            if transaction.isolation == IsolationLevel.READ_COMMITTED
            else transaction.snapshot
        )

        visible = {
            product_id: copy.deepcopy(versioned.product)
            for product_id, versioned in source.items()
        }

        for product_id, product in transaction.writes.items():
            if product is None:
                visible.pop(product_id, None)
            else:
                visible[product_id] = copy.deepcopy(product)

        return visible

    def query_price_range(
        self,
        transaction: Transaction,
        predicate: RangePredicate
    ) -> list[Product]:

        self._ensure_active(transaction)

        if transaction.isolation == IsolationLevel.SERIALIZABLE:
            transaction.read_ranges.append(predicate)

        results = [
            product
            for product in self._visible_rows(transaction).values()
            if predicate.contains(product.price)
        ]

        return sorted(results, key=lambda p: p.product_id)

    def insert(
        self,
        transaction: Transaction,
        product: Product
    ):
        self._ensure_active(transaction)
        product.validate()

        if product.product_id in self._visible_rows(transaction):
            raise WriteConflict(
                f"Product {product.product_id} already exists"
            )

        transaction.writes[product.product_id] = copy.deepcopy(product)

        logger.info(
            "Transaction %s staged insertion of product %s",
            transaction.transaction_id,
            product.product_id
        )

    def update(
        self,
        transaction: Transaction,
        product: Product
    ):
        self._ensure_active(transaction)
        product.validate()

        if product.product_id not in self._visible_rows(transaction):
            raise TransactionError("Product does not exist")

        transaction.writes[product.product_id] = copy.deepcopy(product)

    def delete(
        self,
        transaction: Transaction,
        product_id: int
    ):
        self._ensure_active(transaction)

        if product_id not in self._visible_rows(transaction):
            raise TransactionError("Product does not exist")

        transaction.writes[product_id] = None

    def _check_write_conflicts(self, transaction: Transaction):
        for product_id in transaction.writes:
            current = self._rows.get(product_id)
            original = transaction.snapshot.get(product_id)

            if transaction.isolation != IsolationLevel.READ_COMMITTED:
                if current != original:
                    raise WriteConflict(
                        f"Concurrent modification of product {product_id}"
                    )

            elif original is None and current is not None:
                raise WriteConflict(
                    f"Concurrent insertion of product {product_id}"
                )

    def _check_serializable(self, transaction: Transaction):
        """
        Detect committed inserts or updates that changed a previously
        evaluated predicate range after the transaction began.
        """

        for commit_version, product in self._commit_history:
            if commit_version <= transaction.start_version:
                continue

            if any(
                predicate.contains(product.price)
                for predicate in transaction.read_ranges
            ):
                raise SerializationFailure(
                    "A concurrent transaction modified a previously "
                    "read price range"
                )

    def commit(self, transaction: Transaction):
        self._ensure_active(transaction)

        try:
            self._check_write_conflicts(transaction)

            if transaction.isolation == IsolationLevel.SERIALIZABLE:
                self._check_serializable(transaction)

            # Validate the complete write set before applying any changes.
            for product in transaction.writes.values():
                if product is not None:
                    product.validate()

            for product_id, product in transaction.writes.items():
                self._version += 1

                if product is None:
                    self._rows.pop(product_id, None)
                else:
                    saved = copy.deepcopy(product)
                    self._rows[product_id] = VersionedProduct(
                        saved,
                        self._version
                    )
                    self._commit_history.append(
                        (self._version, copy.deepcopy(saved))
                    )

            transaction.state = TransactionState.COMMITTED

            logger.info(
                "Transaction %s committed",
                transaction.transaction_id
            )

        except TransactionError:
            transaction.state = TransactionState.ABORTED
            logger.exception(
                "Transaction %s aborted",
                transaction.transaction_id
            )
            raise

    def rollback(self, transaction: Transaction):
        self._ensure_active(transaction)
        transaction.writes.clear()
        transaction.state = TransactionState.ABORTED
        logger.info(
            "Transaction %s rolled back",
            transaction.transaction_id
        )

    def current_products(self) -> list[Product]:
        return sorted(
            [
                copy.deepcopy(row.product)
                for row in self._rows.values()
            ],
            key=lambda product: product.product_id
        )


def display(title: str, products: list[Product]):
    print(f"\n{title}")
    print("-" * 65)

    if not products:
        print("No matching products")
        return

    for product in products:
        print(
            f"ID={product.product_id:<3} "
            f"Name={product.name:<20} "
            f"Price={product.price:>8.2f}"
        )

    print(f"Rows returned: {len(products)}")


def create_database() -> Database:
    database = Database()

    database.seed([
        Product(1, "Keyboard", 1200, "Electronics"),
        Product(2, "Mouse", 800, "Electronics"),
        Product(3, "Monitor", 8500, "Electronics"),
        Product(4, "Desk", 6000, "Furniture"),
        Product(5, "Notebook", 150, "Stationery")
    ])

    return database


def demonstrate_read_committed():
    print("\n=== READ COMMITTED: PHANTOM READ ===")

    database = create_database()
    predicate = RangePredicate(500, 5000)

    transaction_a = database.begin(
        IsolationLevel.READ_COMMITTED
    )

    first = database.query_price_range(
        transaction_a,
        predicate
    )
    display("Transaction A: First range query", first)

    transaction_b = database.begin(
        IsolationLevel.READ_COMMITTED
    )

    database.insert(
        transaction_b,
        Product(6, "Webcam", 2500, "Electronics")
    )
    database.commit(transaction_b)

    second = database.query_price_range(
        transaction_a,
        predicate
    )
    display("Transaction A: Second range query", second)

    assert len(first) == 3
    assert len(second) == 4

    database.commit(transaction_a)


def demonstrate_repeatable_read():
    print("\n=== REPEATABLE READ: STABLE SNAPSHOT ===")

    database = create_database()
    predicate = RangePredicate(500, 5000)

    transaction_a = database.begin(
        IsolationLevel.REPEATABLE_READ
    )

    first = database.query_price_range(
        transaction_a,
        predicate
    )

    transaction_b = database.begin(
        IsolationLevel.READ_COMMITTED
    )

    database.insert(
        transaction_b,
        Product(6, "Webcam", 2500, "Electronics")
    )
    database.commit(transaction_b)

    second = database.query_price_range(
        transaction_a,
        predicate
    )

    display("First range query", first)
    display("Second range query", second)

    assert len(first) == len(second) == 3

    transaction_a.commit if False else None
    database.commit(transaction_a)

    later = database.begin(IsolationLevel.REPEATABLE_READ)
    current = database.query_price_range(later, predicate)

    display("New transaction sees committed insertion", current)
    assert len(current) == 4

    database.commit(later)


def demonstrate_serializable():
    print("\n=== SERIALIZABLE: PREDICATE VALIDATION ===")

    database = create_database()
    predicate = RangePredicate(500, 5000)

    transaction_a = database.begin(
        IsolationLevel.SERIALIZABLE
    )

    first = database.query_price_range(
        transaction_a,
        predicate
    )

    transaction_b = database.begin(
        IsolationLevel.READ_COMMITTED
    )

    database.insert(
        transaction_b,
        Product(6, "Webcam", 2500, "Electronics")
    )
    database.commit(transaction_b)

    display("Transaction A initial query", first)

    try:
        database.commit(transaction_a)
    except SerializationFailure as error:
        print("Expected serialization failure:", error)

    assert transaction_a.state == TransactionState.ABORTED


def demonstrate_range_boundaries():
    print("\n=== RANGE BOUNDARY VALIDATION ===")

    database = create_database()

    transaction = database.begin(
        IsolationLevel.REPEATABLE_READ
    )

    predicate = RangePredicate(
        minimum=800,
        maximum=6000,
        include_minimum=True,
        include_maximum=False
    )

    results = database.query_price_range(
        transaction,
        predicate
    )

    display("Range [800, 6000)", results)

    assert all(800 <= product.price < 6000 for product in results)

    database.commit(transaction)


def demonstrate_rollback():
    print("\n=== ROLLBACK ===")

    database = create_database()
    transaction = database.begin()

    database.insert(
        transaction,
        Product(10, "Temporary Product", 900, "Testing")
    )

    database.rollback(transaction)

    assert all(
        product.product_id != 10
        for product in database.current_products()
    )

    print("Uncommitted insertion was discarded.")


def main():
    demonstrate_read_committed()
    demonstrate_repeatable_read()
    demonstrate_serializable()
    demonstrate_range_boundaries()
    demonstrate_rollback()

    print("\n=== FINAL DATABASE STATE ===")

    database = create_database()

    for product in database.current_products():
        print(product)

    print("\nAll transaction demonstrations completed.")


if __name__ == "__main__":
    main()
