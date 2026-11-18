#!/usr/bin/env python3
"""
Dirty Reads: Causes, Examples, Detection, and Prevention

A self-contained transaction simulator demonstrating:
- Dirty reads under weak isolation.
- Committed and uncommitted transaction data.
- Rollback contamination.
- READ UNCOMMITTED, READ COMMITTED, and REPEATABLE READ.
- Snapshot-based visibility.
- Concurrent transaction scheduling.
- Validation and transaction-state management.
- Automated assertions and security considerations.

Run:
    python dirty_reads.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import logging
import unittest


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)

logger = logging.getLogger("dirty_reads")


class IsolationLevel(Enum):
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"


class TransactionState(Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"


class TransactionError(Exception):
    """Base transaction exception."""


class InvalidTransactionState(TransactionError):
    pass


class MissingRecordError(TransactionError):
    pass


class DirtyReadError(TransactionError):
    pass


@dataclass
class Account:
    account_id: int
    owner: str
    balance: float

    def __post_init__(self) -> None:
        if self.account_id <= 0:
            raise ValueError("Account ID must be positive.")

        if not self.owner.strip():
            raise ValueError("Account owner cannot be empty.")

        if self.balance < 0:
            raise ValueError("Initial balance cannot be negative.")


@dataclass
class Transaction:
    transaction_id: int
    isolation: IsolationLevel
    state: TransactionState = TransactionState.ACTIVE
    writes: dict[int, float] = field(default_factory=dict)
    snapshot: dict[int, float] | None = None
    read_log: list[dict[str, Any]] = field(default_factory=list)


class Database:
    """
    In-memory database with transaction-level write buffers.

    READ UNCOMMITTED:
        Exposes other active transactions' uncommitted writes.

    READ COMMITTED:
        Exposes committed values and the current transaction's writes.

    REPEATABLE READ:
        Uses a transaction-start snapshot plus its own writes.

    This is an educational isolation model, not a complete
    implementation of any specific database engine.
    """

    def __init__(self) -> None:
        self.committed: dict[int, Account] = {}
        self.transactions: dict[int, Transaction] = {}
        self.next_transaction_id = 1
        self.version = 0

    def add_account(self, account: Account) -> None:
        if account.account_id in self.committed:
            raise ValueError("Duplicate account ID.")

        self.committed[account.account_id] = account
        self.version += 1

    def begin(self, isolation: IsolationLevel) -> Transaction:
        transaction = Transaction(
            transaction_id=self.next_transaction_id,
            isolation=isolation
        )

        if isolation == IsolationLevel.REPEATABLE_READ:
            transaction.snapshot = {
                account_id: account.balance
                for account_id, account in self.committed.items()
            }

        self.transactions[transaction.transaction_id] = transaction
        self.next_transaction_id += 1

        logger.info(
            "Transaction %s started with %s",
            transaction.transaction_id,
            isolation.value
        )

        return transaction

    def _validate_active(self, transaction: Transaction) -> None:
        if transaction.state != TransactionState.ACTIVE:
            raise InvalidTransactionState(
                f"Transaction {transaction.transaction_id} is "
                f"{transaction.state.value}."
            )

    def _account_exists(self, account_id: int) -> None:
        if account_id not in self.committed:
            raise MissingRecordError(
                f"Account {account_id} does not exist."
            )

    def write(
        self,
        transaction: Transaction,
        account_id: int,
        new_balance: float
    ) -> None:
        self._validate_active(transaction)
        self._account_exists(account_id)

        if new_balance < 0:
            raise ValueError("Account balance cannot be negative.")

        transaction.writes[account_id] = float(new_balance)

        logger.info(
            "Transaction %s staged balance %.2f for account %s",
            transaction.transaction_id,
            new_balance,
            account_id
        )

    def read(
        self,
        transaction: Transaction,
        account_id: int
    ) -> float:
        self._validate_active(transaction)
        self._account_exists(account_id)

        if account_id in transaction.writes:
            value = transaction.writes[account_id]
            source = "OWN_UNCOMMITTED_WRITE"

        elif transaction.isolation == IsolationLevel.READ_UNCOMMITTED:
            value = self.committed[account_id].balance
            source = "COMMITTED"

            # Inspect other active transactions' write buffers.
            for other in self.transactions.values():
                if (
                    other.transaction_id != transaction.transaction_id
                    and other.state == TransactionState.ACTIVE
                    and account_id in other.writes
                ):
                    value = other.writes[account_id]
                    source = (
                        f"UNCOMMITTED_TRANSACTION_"
                        f"{other.transaction_id}"
                    )
                    break

        elif transaction.isolation == IsolationLevel.READ_COMMITTED:
            value = self.committed[account_id].balance
            source = "COMMITTED"

        else:
            assert transaction.snapshot is not None
            value = transaction.snapshot[account_id]
            source = "TRANSACTION_SNAPSHOT"

        transaction.read_log.append({
            "account_id": account_id,
            "value": value,
            "source": source
        })

        logger.info(
            "Transaction %s read account %s: %.2f (%s)",
            transaction.transaction_id,
            account_id,
            value,
            source
        )

        return value

    def commit(self, transaction: Transaction) -> None:
        self._validate_active(transaction)

        # Validate all changes before publishing any of them.
        for account_id, balance in transaction.writes.items():
            self._account_exists(account_id)

            if balance < 0:
                raise ValueError("Invalid balance at commit.")

        for account_id, balance in transaction.writes.items():
            self.committed[account_id].balance = balance

        self.version += 1
        transaction.state = TransactionState.COMMITTED

        logger.info(
            "Transaction %s committed.",
            transaction.transaction_id
        )

    def rollback(self, transaction: Transaction) -> None:
        self._validate_active(transaction)

        transaction.writes.clear()
        transaction.state = TransactionState.ROLLED_BACK

        logger.info(
            "Transaction %s rolled back.",
            transaction.transaction_id
        )

    def committed_balance(self, account_id: int) -> float:
        self._account_exists(account_id)
        return self.committed[account_id].balance

    def detect_dirty_reads(self) -> list[dict[str, Any]]:
        """
        Identify reads that observed another active transaction's
        uncommitted write and whose writer later rolled back.
        """
        findings = []

        for reader in self.transactions.values():
            for entry in reader.read_log:
                source = entry["source"]

                if not source.startswith("UNCOMMITTED_TRANSACTION_"):
                    continue

                writer_id = int(source.rsplit("_", 1)[1])
                writer = self.transactions[writer_id]

                if writer.state == TransactionState.ROLLED_BACK:
                    findings.append({
                        "reader": reader.transaction_id,
                        "writer": writer_id,
                        "account_id": entry["account_id"],
                        "observed_value": entry["value"],
                        "result": "CONFIRMED_DIRTY_READ"
                    })

        return findings


def demonstrate_dirty_read() -> None:
    print("\n" + "=" * 65)
    print("SCENARIO 1: DIRTY READ AND ROLLBACK")
    print("=" * 65)

    database = Database()
    database.add_account(Account(101, "Alice", 1000.00))

    transaction_a = database.begin(
        IsolationLevel.READ_UNCOMMITTED
    )

    transaction_b = database.begin(
        IsolationLevel.READ_UNCOMMITTED
    )

    print("Initial committed balance:", database.committed_balance(101))

    database.write(transaction_a, 101, 500.00)

    observed = database.read(transaction_b, 101)
    print("Transaction B observes:", observed)

    database.rollback(transaction_a)

    print("Transaction A rolls back.")
    print("Transaction B previously observed:", observed)
    print("Actual committed balance:", database.committed_balance(101))

    print("Detected anomalies:", database.detect_dirty_reads())


def demonstrate_prevention() -> None:
    print("\n" + "=" * 65)
    print("SCENARIO 2: READ COMMITTED PREVENTION")
    print("=" * 65)

    database = Database()
    database.add_account(Account(201, "Bob", 2000.00))

    writer = database.begin(IsolationLevel.READ_UNCOMMITTED)
    reader = database.begin(IsolationLevel.READ_COMMITTED)

    database.write(writer, 201, 800.00)

    observed = database.read(reader, 201)

    print("Uncommitted writer value:", writer.writes[201])
    print("READ COMMITTED reader observes:", observed)

    database.rollback(writer)

    print("Writer rolled back.")
    print("Committed balance:", database.committed_balance(201))

    assert observed == 2000.00


def demonstrate_repeatable_read() -> None:
    print("\n" + "=" * 65)
    print("SCENARIO 3: REPEATABLE READ SNAPSHOT")
    print("=" * 65)

    database = Database()
    database.add_account(Account(301, "Carol", 3000.00))

    reader = database.begin(IsolationLevel.REPEATABLE_READ)
    writer = database.begin(IsolationLevel.READ_COMMITTED)

    first_read = database.read(reader, 301)

    database.write(writer, 301, 2500.00)
    database.commit(writer)

    second_read = database.read(reader, 301)

    print("First reader observation:", first_read)
    print("Writer committed new balance: 2500.00")
    print("Second reader observation:", second_read)
    print("Current committed balance:", database.committed_balance(301))

    assert first_read == second_read == 3000.00


def demonstrate_commit_visibility() -> None:
    print("\n" + "=" * 65)
    print("SCENARIO 4: COMMIT VISIBILITY")
    print("=" * 65)

    database = Database()
    database.add_account(Account(401, "David", 5000.00))

    writer = database.begin(IsolationLevel.READ_COMMITTED)
    reader = database.begin(IsolationLevel.READ_COMMITTED)

    database.write(writer, 401, 4500.00)

    before_commit = database.read(reader, 401)
    database.commit(writer)
    after_commit = database.read(reader, 401)

    print("Before commit:", before_commit)
    print("After commit:", after_commit)

    assert before_commit == 5000.00
    assert after_commit == 4500.00


class DirtyReadTests(unittest.TestCase):

    def setUp(self) -> None:
        self.database = Database()
        self.database.add_account(Account(1, "Test", 100.00))

    def test_dirty_read(self) -> None:
        writer = self.database.begin(
            IsolationLevel.READ_UNCOMMITTED
        )
        reader = self.database.begin(
            IsolationLevel.READ_UNCOMMITTED
        )

        self.database.write(writer, 1, 50.00)

        self.assertEqual(
            self.database.read(reader, 1),
            50.00
        )

        self.database.rollback(writer)

        self.assertEqual(
            self.database.committed_balance(1),
            100.00
        )

        self.assertEqual(
            len(self.database.detect_dirty_reads()),
            1
        )

    def test_read_committed_prevents_dirty_read(self) -> None:
        writer = self.database.begin(
            IsolationLevel.READ_UNCOMMITTED
        )
        reader = self.database.begin(
            IsolationLevel.READ_COMMITTED
        )

        self.database.write(writer, 1, 25.00)

        self.assertEqual(
            self.database.read(reader, 1),
            100.00
        )

        self.database.rollback(writer)

    def test_repeatable_read(self) -> None:
        reader = self.database.begin(
            IsolationLevel.REPEATABLE_READ
        )
        writer = self.database.begin(
            IsolationLevel.READ_COMMITTED
        )

        first = self.database.read(reader, 1)

        self.database.write(writer, 1, 75.00)
        self.database.commit(writer)

        second = self.database.read(reader, 1)

        self.assertEqual(first, second)

    def test_invalid_transaction_state(self) -> None:
        transaction = self.database.begin(
            IsolationLevel.READ_COMMITTED
        )

        self.database.commit(transaction)

        with self.assertRaises(InvalidTransactionState):
            self.database.commit(transaction)

    def test_negative_balance_rejected(self) -> None:
        transaction = self.database.begin(
            IsolationLevel.READ_COMMITTED
        )

        with self.assertRaises(ValueError):
            self.database.write(transaction, 1, -10.00)


def main() -> None:
    demonstrate_dirty_read()
    demonstrate_prevention()
    demonstrate_repeatable_read()
    demonstrate_commit_visibility()

    print("\n" + "=" * 65)
    print("AUTOMATED VALIDATION")
    print("=" * 65)

    unittest.main(argv=["dirty_reads.py"], exit=False)


if __name__ == "__main__":
    main()
