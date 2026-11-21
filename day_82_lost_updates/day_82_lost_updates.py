from __future__ import annotations

import copy
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class ConcurrencyError(Exception):
    """Raised when a concurrent modification invalidates a write."""


class ValidationError(Exception):
    """Raised when an invalid account operation is requested."""


class WriteStrategy(Enum):
    UNSAFE = "unsafe"
    PESSIMISTIC = "pessimistic"
    OPTIMISTIC = "optimistic"


@dataclass
class Account:
    account_id: int
    owner: str
    balance: float
    version: int = 0

    def validate(self) -> None:
        if self.account_id <= 0:
            raise ValidationError("Account ID must be positive.")
        if not self.owner.strip():
            raise ValidationError("Account owner is required.")
        if self.balance < 0:
            raise ValidationError("Balance cannot be negative.")


@dataclass
class WriteEvent:
    transaction_id: str
    account_id: int
    operation: str
    old_balance: float
    new_balance: float
    old_version: int
    new_version: int
    strategy: str
    timestamp: float = field(default_factory=time.time)


class AccountStore:
    """
    In-memory account store demonstrating three write strategies.

    Unsafe writes reproduce lost updates.
    Pessimistic writes serialize modifications with a lock.
    Optimistic writes reject stale versions.
    """

    def __init__(self):
        self._accounts: dict[int, Account] = {}
        self._locks: dict[int, threading.RLock] = {}
        self._metadata_lock = threading.RLock()
        self._events: list[WriteEvent] = []

    def add_account(self, account: Account) -> None:
        account.validate()
        with self._metadata_lock:
            if account.account_id in self._accounts:
                raise ValidationError("Account already exists.")
            self._accounts[account.account_id] = copy.deepcopy(account)
            self._locks[account.account_id] = threading.RLock()

    def snapshot(self, account_id: int) -> Account:
        with self._metadata_lock:
            account = self._accounts.get(account_id)
            if account is None:
                raise ValidationError("Account not found.")
            return copy.deepcopy(account)

    def events(self) -> list[WriteEvent]:
        with self._metadata_lock:
            return copy.deepcopy(self._events)

    def _record(
        self,
        account_id: int,
        old_balance: float,
        new_balance: float,
        old_version: int,
        new_version: int,
        strategy: WriteStrategy,
        operation: str,
    ) -> None:
        self._events.append(
            WriteEvent(
                transaction_id=str(uuid.uuid4()),
                account_id=account_id,
                operation=operation,
                old_balance=old_balance,
                new_balance=new_balance,
                old_version=old_version,
                new_version=new_version,
                strategy=strategy.value,
            )
        )

    def unsafe_write(
        self,
        account_id: int,
        previously_read_balance: float,
        amount: float,
        operation: str,
    ) -> float:
        """
        Simulates an application performing read-modify-write
        without a lock or version check.

        The caller supplies a previously read value. Another
        transaction may have changed the account in between.
        """
        if amount <= 0:
            raise ValidationError("Amount must be positive.")

        with self._metadata_lock:
            account = self._accounts.get(account_id)
            if account is None:
                raise ValidationError("Account not found.")

            old_balance = account.balance
            old_version = account.version

            if operation == "deposit":
                new_balance = previously_read_balance + amount
            elif operation == "withdraw":
                new_balance = previously_read_balance - amount
                if new_balance < 0:
                    raise ValidationError("Insufficient funds.")
            else:
                raise ValidationError("Unsupported operation.")

            # Deliberately incorrect: stale data overwrites newer data.
            account.balance = new_balance
            account.version += 1

            self._record(
                account_id, old_balance, new_balance,
                old_version, account.version,
                WriteStrategy.UNSAFE, operation
            )
            return new_balance

    def pessimistic_write(
        self,
        account_id: int,
        amount: float,
        operation: str,
    ) -> float:
        """
        Acquires an account-specific lock before reading and writing.
        Other transactions modifying the same account must wait.
        """
        if amount <= 0:
            raise ValidationError("Amount must be positive.")

        lock = self._locks.get(account_id)
        if lock is None:
            raise ValidationError("Account not found.")

        with lock:
            with self._metadata_lock:
                account = self._accounts[account_id]
                old_balance = account.balance
                old_version = account.version

                if operation == "deposit":
                    new_balance = old_balance + amount
                elif operation == "withdraw":
                    new_balance = old_balance - amount
                    if new_balance < 0:
                        raise ValidationError("Insufficient funds.")
                else:
                    raise ValidationError("Unsupported operation.")

                account.balance = new_balance
                account.version += 1

                self._record(
                    account_id, old_balance, new_balance,
                    old_version, account.version,
                    WriteStrategy.PESSIMISTIC, operation
                )
                return new_balance

    def optimistic_write(
        self,
        account_id: int,
        expected_version: int,
        amount: float,
        operation: str,
    ) -> float:
        """
        Performs a conditional write using a version number.

        The write succeeds only if the current version matches
        the version observed by the transaction.
        """
        if amount <= 0:
            raise ValidationError("Amount must be positive.")

        with self._metadata_lock:
            account = self._accounts.get(account_id)
            if account is None:
                raise ValidationError("Account not found.")

            if account.version != expected_version:
                raise ConcurrencyError(
                    f"Stale version: expected {expected_version}, "
                    f"current {account.version}."
                )

            old_balance = account.balance
            old_version = account.version

            if operation == "deposit":
                new_balance = old_balance + amount
            elif operation == "withdraw":
                new_balance = old_balance - amount
                if new_balance < 0:
                    raise ValidationError("Insufficient funds.")
            else:
                raise ValidationError("Unsupported operation.")

            account.balance = new_balance
            account.version += 1

            self._record(
                account_id, old_balance, new_balance,
                old_version, account.version,
                WriteStrategy.OPTIMISTIC, operation
            )
            return new_balance

    def retry_optimistic(
        self,
        account_id: int,
        amount: float,
        operation: str,
        max_attempts: int = 3,
    ) -> float:
        """
        Retries transient concurrency conflicts by obtaining
        a fresh snapshot and recalculating the operation.
        """
        if max_attempts < 1:
            raise ValidationError("At least one attempt is required.")

        for attempt in range(max_attempts):
            snapshot = self.snapshot(account_id)
            try:
                return self.optimistic_write(
                    account_id,
                    snapshot.version,
                    amount,
                    operation,
                )
            except ConcurrencyError:
                if attempt == max_attempts - 1:
                    raise
                time.sleep(0.01 * (2 ** attempt))

        raise ConcurrencyError("Maximum retry attempts exceeded.")


def demonstrate_lost_update() -> None:
    print("\n1. Demonstrating a lost update")

    store = AccountStore()
    store.add_account(Account(1, "Customer A", 1000.0))

    # Both transactions read the same initial balance.
    transaction_a_balance = store.snapshot(1).balance
    transaction_b_balance = store.snapshot(1).balance

    # Transaction A deposits 200.
    store.unsafe_write(1, transaction_a_balance, 200, "deposit")

    # Transaction B withdraws 100 using its stale balance.
    store.unsafe_write(1, transaction_b_balance, 100, "withdraw")

    final_balance = store.snapshot(1).balance

    print("Initial balance: 1000")
    print("Transaction A: +200")
    print("Transaction B: -100")
    print(f"Expected balance: 1100")
    print(f"Actual balance: {final_balance}")

    assert final_balance == 900.0
    print("Lost update confirmed: the deposit was overwritten.")


def demonstrate_optimistic_locking() -> None:
    print("\n2. Demonstrating optimistic concurrency control")

    store = AccountStore()
    store.add_account(Account(2, "Customer B", 1000.0))

    snapshot_a = store.snapshot(2)
    snapshot_b = store.snapshot(2)

    store.optimistic_write(
        2, snapshot_a.version, 200, "deposit"
    )

    try:
        store.optimistic_write(
            2, snapshot_b.version, 100, "withdraw"
        )
    except ConcurrencyError as error:
        print(f"Transaction B rejected: {error}")

    # A fresh transaction can safely retry.
    store.retry_optimistic(2, 100, "withdraw")

    final = store.snapshot(2)
    print(f"Final balance: {final.balance}")
    print(f"Final version: {final.version}")

    assert final.balance == 1100.0


def demonstrate_pessimistic_locking() -> None:
    print("\n3. Demonstrating pessimistic locking")

    store = AccountStore()
    store.add_account(Account(3, "Customer C", 1000.0))

    def deposit() -> None:
        for _ in range(100):
            store.pessimistic_write(3, 10, "deposit")

    threads = [
        threading.Thread(target=deposit)
        for _ in range(5)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    final = store.snapshot(3)
    print(f"Expected balance: 6000")
    print(f"Actual balance: {final.balance}")

    assert final.balance == 6000.0


def demonstrate_validation() -> None:
    print("\n4. Demonstrating validation")

    store = AccountStore()
    store.add_account(Account(4, "Customer D", 100.0))

    for amount, operation in [
        (-10, "deposit"),
        (200, "withdraw"),
    ]:
        try:
            store.pessimistic_write(4, amount, operation)
        except ValidationError as error:
            print(f"Rejected operation: {error}")


def analyze_events(store: AccountStore) -> None:
    print("\n5. Transaction audit events")

    for event in store.events():
        print(
            f"{event.strategy}: {event.operation}, "
            f"{event.old_balance} -> {event.new_balance}, "
            f"version {event.old_version} -> {event.new_version}"
        )


def write_audit_report(store: AccountStore, filename: str) -> None:
    """
    Writes an audit report atomically to avoid exposing
    a partially written report.
    """
    target = Path(filename)
    temporary = target.with_suffix(target.suffix + ".tmp")

    try:
        with temporary.open("w", encoding="utf-8") as file:
            file.write("TRANSACTION AUDIT REPORT\n")
            file.write("========================\n")

            for event in store.events():
                file.write(
                    f"{event.transaction_id},"
                    f"{event.account_id},"
                    f"{event.strategy},"
                    f"{event.operation},"
                    f"{event.old_balance},"
                    f"{event.new_balance},"
                    f"{event.old_version},"
                    f"{event.new_version}\n"
                )

        temporary.replace(target)

    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    demonstrate_lost_update()
    demonstrate_optimistic_locking()
    demonstrate_pessimistic_locking()
    demonstrate_validation()

    audit_store = AccountStore()
    audit_store.add_account(Account(5, "Audit Customer", 500))
    audit_store.retry_optimistic(5, 50, "deposit")
    analyze_events(audit_store)

    try:
        write_audit_report(audit_store, "lost_update_audit.csv")
        print("\nAudit report written successfully.")
    except OSError as error:
        print(f"Audit report could not be written: {error}")


if __name__ == "__main__":
    main()
