#!/usr/bin/env python3
"""
Transaction Lifecycle Simulator
Demonstrates transaction states, commit, rollback, savepoints,
isolation concepts, validation, atomicity, and failure recovery.

Run:
    python transaction_lifecycle.py
"""

from __future__ import annotations

import copy
import json
import logging
import uuid

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("transaction")


class TransactionState(Enum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


class TransactionError(Exception):
    """Base transaction exception."""


class InvalidStateError(TransactionError):
    pass


class ValidationError(TransactionError):
    pass


class InsufficientFundsError(TransactionError):
    pass


class ConcurrencyError(TransactionError):
    pass


@dataclass
class Account:
    account_id: str
    owner: str
    balance: Decimal
    version: int = 0

    def __post_init__(self):
        if self.balance < Decimal("0"):
            raise ValidationError("Account balance cannot be negative.")

        if not self.account_id or not self.owner:
            raise ValidationError("Account ID and owner are required.")


@dataclass
class TransactionEvent:
    timestamp: str
    transaction_id: str
    previous_state: str
    current_state: str
    description: str


@dataclass
class Transaction:
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: TransactionState = TransactionState.NEW
    operations: list[dict[str, Any]] = field(default_factory=list)
    events: list[TransactionEvent] = field(default_factory=list)
    savepoints: dict[str, dict[str, Account]] = field(default_factory=dict)
    error: str | None = None

    def transition(self, new_state: TransactionState, description: str):
        allowed = {
            TransactionState.NEW: {TransactionState.ACTIVE},
            TransactionState.ACTIVE: {
                TransactionState.COMMITTING,
                TransactionState.ROLLING_BACK,
                TransactionState.FAILED,
            },
            TransactionState.COMMITTING: {
                TransactionState.COMMITTED,
                TransactionState.FAILED,
            },
            TransactionState.ROLLING_BACK: {
                TransactionState.ROLLED_BACK,
                TransactionState.FAILED,
            },
            TransactionState.FAILED: {
                TransactionState.ROLLING_BACK,
            },
            TransactionState.COMMITTED: set(),
            TransactionState.ROLLED_BACK: set(),
        }

        if new_state not in allowed[self.state]:
            raise InvalidStateError(
                f"Invalid transition: {self.state.value} -> {new_state.value}"
            )

        previous = self.state
        self.state = new_state

        self.events.append(
            TransactionEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                transaction_id=self.transaction_id,
                previous_state=previous.value,
                current_state=new_state.value,
                description=description,
            )
        )

        logger.info(
            "%s: %s -> %s",
            self.transaction_id[:8],
            previous.value,
            new_state.value,
        )


class BankDatabase:
    """
    In-memory transactional database.

    Each transaction works on a private snapshot.
    Commit checks account versions before publishing changes.
    """

    def __init__(self):
        self.accounts: dict[str, Account] = {}
        self.lock = RLock()

    def add_account(self, account: Account):
        with self.lock:
            if account.account_id in self.accounts:
                raise ValidationError("Duplicate account ID.")

            self.accounts[account.account_id] = copy.deepcopy(account)

    def get_account(self, account_id: str) -> Account:
        with self.lock:
            if account_id not in self.accounts:
                raise ValidationError(f"Unknown account: {account_id}")

            return copy.deepcopy(self.accounts[account_id])

    def snapshot(self) -> dict[str, Account]:
        with self.lock:
            return copy.deepcopy(self.accounts)


class TransactionManager:

    def __init__(self, database: BankDatabase):
        self.database = database

    def begin(self) -> Transaction:
        transaction = Transaction()
        transaction.working_data = self.database.snapshot()
        transaction.original_versions = {
            key: account.version
            for key, account in transaction.working_data.items()
        }
        transaction.transition(
            TransactionState.ACTIVE,
            "Transaction started and snapshot created.",
        )
        return transaction

    @staticmethod
    def _require_active(transaction: Transaction):
        if transaction.state != TransactionState.ACTIVE:
            raise InvalidStateError("Transaction is not active.")

    def transfer(
        self,
        transaction: Transaction,
        source_id: str,
        destination_id: str,
        amount: Decimal,
    ):
        self._require_active(transaction)

        if source_id == destination_id:
            raise ValidationError("Source and destination must differ.")

        if not amount.is_finite() or amount <= Decimal("0"):
            raise ValidationError("Transfer amount must be positive and finite.")

        accounts = transaction.working_data

        if source_id not in accounts or destination_id not in accounts:
            raise ValidationError("Source or destination account does not exist.")

        source = accounts[source_id]
        destination = accounts[destination_id]

        if source.balance < amount:
            raise InsufficientFundsError("Insufficient account balance.")

        source.balance -= amount
        destination.balance += amount

        transaction.operations.append({
            "operation": "TRANSFER",
            "source": source_id,
            "destination": destination_id,
            "amount": str(amount),
        })

        logger.info(
            "Transfer staged: %s -> %s (%s)",
            source_id,
            destination_id,
            amount,
        )

    def deposit(
        self,
        transaction: Transaction,
        account_id: str,
        amount: Decimal,
    ):
        self._require_active(transaction)

        if not amount.is_finite() or amount <= Decimal("0"):
            raise ValidationError("Deposit must be positive and finite.")

        if account_id not in transaction.working_data:
            raise ValidationError("Account does not exist.")

        transaction.working_data[account_id].balance += amount

        transaction.operations.append({
            "operation": "DEPOSIT",
            "account": account_id,
            "amount": str(amount),
        })

    def withdraw(
        self,
        transaction: Transaction,
        account_id: str,
        amount: Decimal,
    ):
        self._require_active(transaction)

        if not amount.is_finite() or amount <= Decimal("0"):
            raise ValidationError("Withdrawal must be positive and finite.")

        if account_id not in transaction.working_data:
            raise ValidationError("Account does not exist.")

        account = transaction.working_data[account_id]

        if account.balance < amount:
            raise InsufficientFundsError("Insufficient funds.")

        account.balance -= amount

        transaction.operations.append({
            "operation": "WITHDRAW",
            "account": account_id,
            "amount": str(amount),
        })

    def create_savepoint(self, transaction: Transaction, name: str):
        self._require_active(transaction)

        if not name or name in transaction.savepoints:
            raise ValidationError("Savepoint name must be unique and non-empty.")

        transaction.savepoints[name] = copy.deepcopy(
            transaction.working_data
        )

        logger.info("Savepoint created: %s", name)

    def rollback_to_savepoint(
        self,
        transaction: Transaction,
        name: str,
    ):
        self._require_active(transaction)

        if name not in transaction.savepoints:
            raise ValidationError("Savepoint does not exist.")

        transaction.working_data = copy.deepcopy(
            transaction.savepoints[name]
        )

        transaction.operations.append({
            "operation": "ROLLBACK_TO_SAVEPOINT",
            "savepoint": name,
        })

        # Savepoints created after the target are discarded.
        names = list(transaction.savepoints)
        target_index = names.index(name)

        for later_name in names[target_index + 1:]:
            del transaction.savepoints[later_name]

        logger.info("Rolled back to savepoint: %s", name)

    def commit(self, transaction: Transaction):
        self._require_active(transaction)

        transaction.transition(
            TransactionState.COMMITTING,
            "Commit validation started.",
        )

        try:
            with self.database.lock:
                # Optimistic concurrency control prevents lost updates.
                for account_id, original_version in (
                    transaction.original_versions.items()
                ):
                    current = self.database.accounts[account_id]

                    if current.version != original_version:
                        raise ConcurrencyError(
                            f"Concurrent modification detected: {account_id}"
                        )

                for account in transaction.working_data.values():
                    if not account.balance.is_finite() or account.balance < 0:
                        raise ValidationError(
                            f"Invalid balance: {account.account_id}"
                        )

                changed_ids = [
                    account_id
                    for account_id, account in transaction.working_data.items()
                    if (
                        account.balance
                        != self.database.accounts[account_id].balance
                    )
                ]

                # Publish all changes while holding the same lock.
                for account_id in changed_ids:
                    updated = copy.deepcopy(
                        transaction.working_data[account_id]
                    )
                    updated.version = (
                        self.database.accounts[account_id].version + 1
                    )
                    self.database.accounts[account_id] = updated

            transaction.transition(
                TransactionState.COMMITTED,
                "All changes committed atomically.",
            )

        except Exception as exc:
            transaction.error = str(exc)
            transaction.transition(
                TransactionState.FAILED,
                f"Commit failed: {exc}",
            )
            raise

    def rollback(self, transaction: Transaction):
        if transaction.state not in {
            TransactionState.ACTIVE,
            TransactionState.FAILED,
        }:
            raise InvalidStateError("Transaction cannot be rolled back.")

        transaction.transition(
            TransactionState.ROLLING_BACK,
            "Discarding uncommitted changes.",
        )

        transaction.working_data = self.database.snapshot()
        transaction.operations.clear()
        transaction.savepoints.clear()

        transaction.transition(
            TransactionState.ROLLED_BACK,
            "Rollback completed.",
        )


def display_accounts(database: BankDatabase):
    print("\nACCOUNT BALANCES")
    print("-" * 48)

    for account in database.snapshot().values():
        print(
            f"{account.account_id:12} "
            f"{account.owner:15} "
            f"{account.balance:>12} "
            f"Version={account.version}"
        )


def display_transaction(transaction: Transaction):
    print(f"\nTransaction ID: {transaction.transaction_id}")
    print(f"Final state: {transaction.state.value}")

    print("\nTransaction operations:")
    print(json.dumps(transaction.operations, indent=2))

    print("\nState history:")
    for event in transaction.events:
        print(
            f"{event.previous_state:12} -> "
            f"{event.current_state:12} | {event.description}"
        )


def run_demonstration():
    database = BankDatabase()

    database.add_account(
        Account("ACC-1001", "Alice", Decimal("10000.00"))
    )
    database.add_account(
        Account("ACC-1002", "Bob", Decimal("5000.00"))
    )
    database.add_account(
        Account("ACC-1003", "Charlie", Decimal("2500.00"))
    )

    manager = TransactionManager(database)

    print("\nSCENARIO 1: SUCCESSFUL COMMIT")

    transaction = manager.begin()

    manager.transfer(
        transaction,
        "ACC-1001",
        "ACC-1002",
        Decimal("1500.00"),
    )

    manager.deposit(
        transaction,
        "ACC-1003",
        Decimal("500.00"),
    )

    manager.commit(transaction)

    display_accounts(database)
    display_transaction(transaction)

    print("\nSCENARIO 2: ROLLBACK")

    transaction = manager.begin()

    manager.withdraw(
        transaction,
        "ACC-1002",
        Decimal("1000.00"),
    )

    manager.rollback(transaction)

    display_accounts(database)
    display_transaction(transaction)

    print("\nSCENARIO 3: SAVEPOINT")

    transaction = manager.begin()

    manager.deposit(
        transaction,
        "ACC-1001",
        Decimal("250.00"),
    )

    manager.create_savepoint(transaction, "before_withdrawal")

    manager.withdraw(
        transaction,
        "ACC-1002",
        Decimal("500.00"),
    )

    manager.rollback_to_savepoint(
        transaction,
        "before_withdrawal",
    )

    manager.commit(transaction)

    display_accounts(database)

    print("\nSCENARIO 4: VALIDATION FAILURE")

    transaction = manager.begin()

    try:
        manager.withdraw(
            transaction,
            "ACC-1002",
            Decimal("999999.00"),
        )
    except TransactionError as exc:
        print("Expected failure:", exc)
        manager.rollback(transaction)

    display_accounts(database)

    print("\nSCENARIO 5: CONCURRENT MODIFICATION")

    first = manager.begin()
    second = manager.begin()

    manager.deposit(first, "ACC-1001", Decimal("100.00"))
    manager.deposit(second, "ACC-1001", Decimal("200.00"))

    manager.commit(first)

    try:
        manager.commit(second)
    except ConcurrencyError as exc:
        print("Concurrency conflict:", exc)
        manager.rollback(second)

    display_accounts(database)

    print("\nALL SCENARIOS COMPLETED")


if __name__ == "__main__":
    run_demonstration()
