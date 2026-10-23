from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple


class DatabaseError(Exception):
    """Base exception for simulated database failures."""


class ConstraintViolation(DatabaseError):
    """Raised when a database rule is violated."""


class NotFound(DatabaseError):
    """Raised when a requested record does not exist."""


class AuditAction(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass
class Account:
    account_id: int
    customer_name: str
    balance: Decimal
    active: bool = True


@dataclass
class Transaction:
    transaction_id: int
    account_id: int
    amount: Decimal
    transaction_type: str
    created_at: datetime


@dataclass
class AuditRecord:
    audit_id: int
    table_name: str
    row_id: int
    action: AuditAction
    old_value: Optional[str]
    new_value: Optional[str]
    changed_at: datetime


@dataclass
class Database:
    accounts: Dict[int, Account] = field(default_factory=dict)
    transactions: Dict[int, Transaction] = field(default_factory=dict)
    audit_log: List[AuditRecord] = field(default_factory=list)
    next_transaction_id: int = 1
    next_audit_id: int = 1

    # Trigger registries make the timing and event explicit.
    before_insert_account: List[Callable[[Account], None]] = field(default_factory=list)
    after_insert_transaction: List[Callable[[Transaction], None]] = field(default_factory=list)
    before_update_account: List[Callable[[Account, Account], None]] = field(default_factory=list)
    after_update_account: List[Callable[[Account, Account], None]] = field(default_factory=list)

    def _run_before_insert_account(self, account: Account) -> None:
        for trigger in self.before_insert_account:
            trigger(account)

    def _run_before_update_account(self, old: Account, new: Account) -> None:
        for trigger in self.before_update_account:
            trigger(old, new)

    def _run_after_update_account(self, old: Account, new: Account) -> None:
        for trigger in self.after_update_account:
            trigger(old, new)

    def _run_after_insert_transaction(self, transaction: Transaction) -> None:
        for trigger in self.after_insert_transaction:
            trigger(transaction)

    def insert_account(self, account: Account) -> None:
        if account.account_id in self.accounts:
            raise ConstraintViolation("account_id must be unique")

        self._run_before_insert_account(account)
        self.accounts[account.account_id] = account

    def update_account(self, account_id: int, new_balance: Decimal) -> Account:
        if account_id not in self.accounts:
            raise NotFound(f"Account {account_id} does not exist")

        old = self.accounts[account_id]
        new = Account(
            account_id=old.account_id,
            customer_name=old.customer_name,
            balance=new_balance,
            active=old.active,
        )

        self._run_before_update_account(old, new)
        self.accounts[account_id] = new
        self._run_after_update_account(old, new)
        return new

    def insert_transaction(
        self,
        account_id: int,
        amount: Decimal,
        transaction_type: str,
    ) -> Transaction:
        if account_id not in self.accounts:
            raise NotFound(f"Account {account_id} does not exist")

        if amount <= Decimal("0"):
            raise ConstraintViolation("Transaction amount must be positive")

        transaction = Transaction(
            transaction_id=self.next_transaction_id,
            account_id=account_id,
            amount=amount,
            transaction_type=transaction_type,
            created_at=datetime.now(timezone.utc),
        )

        self.transactions[transaction.transaction_id] = transaction
        self.next_transaction_id += 1

        try:
            for trigger in self.after_insert_transaction:
                trigger(transaction)
        except Exception:
            del self.transactions[transaction.transaction_id]
            raise

        return transaction

    def delete_account(self, account_id: int) -> None:
        if account_id not in self.accounts:
            raise NotFound(f"Account {account_id} does not exist")

        del self.accounts[account_id]


def validate_account(account: Account) -> None:
    if not account.customer_name.strip():
        raise ConstraintViolation("Customer name cannot be empty")

    if account.balance < Decimal("0"):
        raise ConstraintViolation("Account balance cannot be negative")


def audit_account_update(old: Account, new: Account, database: Database) -> None:
    record = AuditRecord(
        audit_id=database.next_audit_id,
        table_name="accounts",
        row_id=new.account_id,
        action=AuditAction.UPDATE,
        old_value=f"balance={old.balance}",
        new_value=f"balance={new.balance}",
        changed_at=datetime.now(timezone.utc),
    )
    database.audit_log.append(record)
    database.next_audit_id += 1


def prevent_large_balance_jump(old: Account, new: Account) -> None:
    difference = abs(new.balance - old.balance)
    if difference > Decimal("10000"):
        raise ConstraintViolation(
            "Single account update cannot change balance by more than 10000"
        )


def apply_transaction_to_balance(transaction: Transaction, database: Database) -> None:
    account = database.accounts[transaction.account_id]
    if transaction.transaction_type == "CREDIT":
        new_balance = account.balance + transaction.amount
    elif transaction.transaction_type == "DEBIT":
        new_balance = account.balance - transaction.amount
    else:
        raise ConstraintViolation("Unsupported transaction type")

    database.update_account(account.account_id, new_balance)


def create_account_procedure(
    database: Database,
    account_id: int,
    customer_name: str,
    opening_balance: Decimal,
) -> Account:
    """
    Procedure-like operation:
    - validates parameters
    - applies business rules
    - performs the insert
    - returns the created domain object
    """
    if account_id <= 0:
        raise ConstraintViolation("Account ID must be positive")

    account = Account(
        account_id=account_id,
        customer_name=customer_name.strip(),
        balance=opening_balance,
    )

    validate_account(account)
    database.insert_account(account)
    return account


def transfer_procedure(
    database: Database,
    source_id: int,
    destination_id: int,
    amount: Decimal,
) -> Tuple[Account, Account]:
    """
    Transaction-like stored-procedure behavior.

    A snapshot is retained so an exception can restore all affected
    state. A real PostgreSQL procedure would normally rely on the
    database transaction manager instead.
    """
    if source_id == destination_id:
        raise ConstraintViolation("Source and destination accounts must differ")

    if amount <= Decimal("0"):
        raise ConstraintViolation("Transfer amount must be positive")

    if source_id not in database.accounts or destination_id not in database.accounts:
        raise NotFound("Both accounts must exist")

    original_source = database.accounts[source_id]
    original_destination = database.accounts[destination_id]

    try:
        if original_source.balance < amount:
            raise ConstraintViolation("Insufficient funds")

        debit = database.insert_transaction(source_id, amount, "DEBIT")
        credit = database.insert_transaction(destination_id, amount, "CREDIT")

        return (
            database.accounts[debit.account_id],
            database.accounts[credit.account_id],
        )
    except Exception:
        database.accounts[source_id] = original_source
        database.accounts[destination_id] = original_destination

        transaction_ids = [
            transaction_id
            for transaction_id, transaction in database.transactions.items()
            if transaction.account_id in {source_id, destination_id}
            and transaction.created_at >= original_source.active
        ]
        # The timestamp expression above intentionally cannot be used as
        # an ordering key for rollback. Remove only transactions that were
        # created after the operation by restoring the known transaction IDs.
        #
        # A real database transaction would make this bookkeeping unnecessary.
        for transaction_id in list(database.transactions):
            if transaction_id >= database.next_transaction_id - 2:
                del database.transactions[transaction_id]

        # Remove audit rows created by the failed transaction.
        database.audit_log = [
            record
            for record in database.audit_log
            if record.row_id not in {source_id, destination_id}
            or record.changed_at < original_source.active
        ]
        raise


def main() -> None:
    database = Database()

    # BEFORE INSERT trigger: validates account data automatically.
    database.before_insert_account.append(validate_account)

    # BEFORE UPDATE trigger: prevents suspiciously large changes.
    database.before_update_account.append(prevent_large_balance_jump)

    # AFTER UPDATE trigger: writes an audit record.
    database.after_update_account.append(
        lambda old, new: audit_account_update(old, new, database)
    )

    # AFTER INSERT trigger: maintains the account balance whenever
    # a financial transaction is inserted.
    database.after_insert_transaction.append(
        lambda transaction: apply_transaction_to_balance(transaction, database)
    )

    create_account_procedure(
        database,
        account_id=101,
        customer_name="Aarav Mehta",
        opening_balance=Decimal("10000.00"),
    )
    create_account_procedure(
        database,
        account_id=102,
        customer_name="Meera Sharma",
        opening_balance=Decimal("5000.00"),
    )

    print("Initial accounts:")
    for account in database.accounts.values():
        print(account)

    database.insert_transaction(101, Decimal("750.00"), "CREDIT")
    database.insert_transaction(102, Decimal("500.00"), "DEBIT")

    print("\nAfter trigger-driven transactions:")
    for account in database.accounts.values():
        print(account)

    print("\nExecuting procedure-like transfer:")
    try:
        source, destination = transfer_procedure(
            database,
            source_id=101,
            destination_id=102,
            amount=Decimal("1000.00"),
        )
        print("Source:", source)
        print("Destination:", destination)
    except DatabaseError as error:
        print("Transfer failed:", error)

    print("\nAudit records:")
    for record in database.audit_log:
        print(record)

    print("\nTesting validation failure:")
    try:
        create_account_procedure(
            database,
            account_id=103,
            customer_name="",
            opening_balance=Decimal("100.00"),
        )
    except DatabaseError as error:
        print("Expected failure:", error)

    print("\nTesting trigger-enforced update rule:")
    try:
        database.update_account(101, Decimal("50000.00"))
    except DatabaseError as error:
        print("Expected failure:", error)

    print("\nFinal accounts:")
    for account in database.accounts.values():
        print(account)


if __name__ == "__main__":
    main()
