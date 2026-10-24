#!/usr/bin/env python3

"""
PostgreSQL transaction concepts modeled in Python.

This executable simulation demonstrates:
- BEGIN / COMMIT / ROLLBACK semantics
- Savepoints
- Nested units of work using savepoints
- Atomic state changes
- Constraint-style validation
- Transaction-local state
- Failure recovery
- Concurrent-style conflict detection using versions
- Transaction audit information

The implementation is intentionally in-memory so it runs with only the
Python standard library. The transaction boundaries mirror the behavior
that an application would manage around PostgreSQL transactions.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional


class TransactionState(Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"


class TransactionError(Exception):
    """Base exception for transaction-related failures."""


class ConstraintViolation(TransactionError):
    """Raised when a database-like constraint is violated."""


class TransactionStateError(TransactionError):
    """Raised when a transaction operation is invalid for its state."""


class SerializationConflict(TransactionError):
    """Raised when the committed state changed after a transaction began."""


@dataclass
class Account:
    account_id: int
    owner: str
    balance: Decimal
    version: int = 0

    def copy(self) -> "Account":
        return Account(
            account_id=self.account_id,
            owner=self.owner,
            balance=self.balance,
            version=self.version,
        )


@dataclass
class AuditEvent:
    transaction_id: int
    action: str
    details: str


@dataclass
class Database:
    accounts: Dict[int, Account] = field(default_factory=dict)
    audit_log: List[AuditEvent] = field(default_factory=list)
    version: int = 0

    def add_account(self, account_id: int, owner: str, balance: Decimal) -> None:
        if account_id in self.accounts:
            raise ConstraintViolation("account_id must be unique")
        if balance < Decimal("0"):
            raise ConstraintViolation("balance cannot be negative")

        self.accounts[account_id] = Account(
            account_id=account_id,
            owner=owner,
            balance=balance,
        )
        self.version += 1


@dataclass
class Savepoint:
    name: str
    accounts: Dict[int, Account]
    audit_log: List[AuditEvent]


class Transaction:
    """
    Represents one database transaction.

    The transaction keeps a private working copy. COMMIT publishes that
    state only after checking that the database version has not changed.
    SAVEPOINT stores a rollback point inside the active transaction.
    """

    def __init__(self, database: Database, transaction_id: int):
        self.database = database
        self.transaction_id = transaction_id
        self.state = TransactionState.ACTIVE

        self.accounts = {
            account_id: account.copy()
            for account_id, account in database.accounts.items()
        }
        self.audit_log = list(database.audit_log)
        self.initial_database_version = database.version
        self.savepoints: Dict[str, Savepoint] = {}

    def _require_active(self) -> None:
        if self.state is not TransactionState.ACTIVE:
            raise TransactionStateError(
                f"transaction is {self.state.value.lower()}"
            )

    def _validate_account(self, account_id: int) -> Account:
        self._require_active()

        if account_id not in self.accounts:
            raise ConstraintViolation(
                f"account {account_id} does not exist"
            )

        return self.accounts[account_id]

    def _audit(self, action: str, details: str) -> None:
        self.audit_log.append(
            AuditEvent(
                transaction_id=self.transaction_id,
                action=action,
                details=details,
            )
        )

    def begin_savepoint(self, name: str) -> None:
        self._require_active()

        if not name:
            raise ValueError("savepoint name cannot be empty")

        self.savepoints[name] = Savepoint(
            name=name,
            accounts=deepcopy(self.accounts),
            audit_log=list(self.audit_log),
        )

    def rollback_to_savepoint(self, name: str) -> None:
        self._require_active()

        if name not in self.savepoints:
            raise TransactionStateError(
                f"savepoint {name!r} does not exist"
            )

        savepoint = self.savepoints[name]
        self.accounts = deepcopy(savepoint.accounts)
        self.audit_log = list(savepoint.audit_log)

        # Savepoints created after the target no longer describe the
        # current transaction state.
        names = list(self.savepoints)
        target_index = names.index(name)

        for obsolete_name in names[target_index + 1 :]:
            del self.savepoints[obsolete_name]

    def release_savepoint(self, name: str) -> None:
        self._require_active()

        if name not in self.savepoints:
            raise TransactionStateError(
                f"savepoint {name!r} does not exist"
            )

        del self.savepoints[name]

    def deposit(self, account_id: int, amount: Decimal) -> None:
        account = self._validate_account(account_id)

        if amount <= Decimal("0"):
            raise ConstraintViolation("deposit amount must be positive")

        account.balance += amount
        self._audit(
            "DEPOSIT",
            f"account={account_id}, amount={amount}",
        )

    def withdraw(self, account_id: int, amount: Decimal) -> None:
        account = self._validate_account(account_id)

        if amount <= Decimal("0"):
            raise ConstraintViolation("withdrawal amount must be positive")

        if account.balance < amount:
            raise ConstraintViolation(
                f"insufficient funds for account {account_id}"
            )

        account.balance -= amount
        self._audit(
            "WITHDRAW",
            f"account={account_id}, amount={amount}",
        )

    def transfer(
        self,
        source_id: int,
        target_id: int,
        amount: Decimal,
    ) -> None:
        self._require_active()

        if source_id == target_id:
            raise ConstraintViolation("source and target must differ")

        # Both operations happen in the same transaction. If the second
        # operation fails, the caller can roll the transaction back.
        self.withdraw(source_id, amount)
        self.deposit(target_id, amount)

        self._audit(
            "TRANSFER",
            f"source={source_id}, target={target_id}, amount={amount}",
        )

    def commit(self) -> None:
        self._require_active()

        if self.database.version != self.initial_database_version:
            self.state = TransactionState.ROLLED_BACK
            raise SerializationConflict(
                "database changed while this transaction was active"
            )

        # Increment versions of changed accounts.
        for account_id, account in self.accounts.items():
            original = self.database.accounts.get(account_id)

            if original is None:
                continue

            if account.balance != original.balance:
                account.version = original.version + 1

        self.database.accounts = {
            account_id: account.copy()
            for account_id, account in self.accounts.items()
        }
        self.database.audit_log = list(self.audit_log)
        self.database.version += 1

        self.state = TransactionState.COMMITTED

    def rollback(self) -> None:
        self._require_active()

        self.accounts = {
            account_id: account.copy()
            for account_id, account in self.database.accounts.items()
        }
        self.audit_log = list(self.database.audit_log)
        self.savepoints.clear()
        self.state = TransactionState.ROLLED_BACK


class TransactionManager:
    def __init__(self, database: Database):
        self.database = database
        self.next_transaction_id = 1

    def begin(self) -> Transaction:
        transaction = Transaction(
            self.database,
            self.next_transaction_id,
        )
        self.next_transaction_id += 1
        return transaction


def print_accounts(database: Database, title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))

    for account in database.accounts.values():
        print(
            f"{account.account_id}: "
            f"{account.owner:<12} "
            f"balance={account.balance:>8} "
            f"version={account.version}"
        )


def demonstrate_commit(manager: TransactionManager) -> None:
    transaction = manager.begin()

    transaction.deposit(1, Decimal("250.00"))
    transaction.commit()

    print_accounts(
        manager.database,
        "After successful COMMIT",
    )


def demonstrate_rollback(manager: TransactionManager) -> None:
    transaction = manager.begin()

    try:
        transaction.withdraw(2, Decimal("9000.00"))
        transaction.commit()
    except TransactionError as exc:
        print(f"\nROLLBACK example: {exc}")
        transaction.rollback()

    print_accounts(
        manager.database,
        "After failed transaction and ROLLBACK",
    )


def demonstrate_savepoint(manager: TransactionManager) -> None:
    transaction = manager.begin()

    transaction.deposit(1, Decimal("100.00"))

    transaction.begin_savepoint("before_risky_operation")

    try:
        transaction.withdraw(2, Decimal("100000.00"))
    except ConstraintViolation as exc:
        print(f"\nSAVEPOINT example: {exc}")
        transaction.rollback_to_savepoint("before_risky_operation")

    # The valid operation before the savepoint remains part of the
    # transaction and can still be committed.
    transaction.deposit(2, Decimal("50.00"))
    transaction.release_savepoint("before_risky_operation")
    transaction.commit()

    print_accounts(
        manager.database,
        "After partial recovery with SAVEPOINT",
    )


def demonstrate_atomic_transfer(manager: TransactionManager) -> None:
    transaction = manager.begin()

    try:
        transaction.transfer(
            source_id=1,
            target_id=2,
            amount=Decimal("125.00"),
        )
        transaction.commit()
    except TransactionError as exc:
        transaction.rollback()
        print(f"Transfer failed: {exc}")

    print_accounts(
        manager.database,
        "After atomic transfer",
    )


def demonstrate_concurrency_conflict(
    manager: TransactionManager,
) -> None:
    first = manager.begin()
    second = manager.begin()

    first.deposit(1, Decimal("10.00"))
    first.commit()

    try:
        second.deposit(2, Decimal("10.00"))
        second.commit()
    except SerializationConflict as exc:
        print(f"\nConcurrent transaction conflict: {exc}")

    print_accounts(
        manager.database,
        "After optimistic conflict detection",
    )


def main() -> None:
    database = Database()

    database.add_account(
        1,
        "Alice",
        Decimal("1500.00"),
    )
    database.add_account(
        2,
        "Bob",
        Decimal("900.00"),
    )
    database.add_account(
        3,
        "Carol",
        Decimal("300.00"),
    )

    manager = TransactionManager(database)

    print_accounts(database, "Initial database state")

    demonstrate_commit(manager)
    demonstrate_rollback(manager)
    demonstrate_savepoint(manager)
    demonstrate_atomic_transfer(manager)
    demonstrate_concurrency_conflict(manager)

    print("\nAudit log")
    print("---------")
    for event in database.audit_log:
        print(
            f"tx={event.transaction_id:<2} "
            f"{event.action:<10} "
            f"{event.details}"
        )

    # Basic executable assertions.
    assert database.accounts[1].balance == Decimal("1745.00")
    assert database.accounts[2].balance == Decimal("950.00")
    assert database.accounts[3].balance == Decimal("300.00")


if __name__ == "__main__":
    main()
