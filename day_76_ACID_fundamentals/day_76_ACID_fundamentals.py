#!/usr/bin/env python3
"""
ACID Fundamentals: Atomicity, Consistency, Isolation, Durability

Executable transaction-management laboratory using Python and SQLite.

Demonstrates:
- Atomicity: all operations commit or roll back.
- Consistency: database constraints preserve valid states.
- Isolation: concurrent transactions and SQLite locking.
- Durability: committed transactions survive connection closure.
- Savepoints, nested transaction scopes, optimistic concurrency.
- Transaction failures, retries, audit records and integrity checks.

Requires Python 3.10+.
Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import tempfile
import threading
import time
import uuid

from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("acid")


class TransactionError(Exception):
    """Base exception for transaction failures."""


class InsufficientFunds(TransactionError):
    pass


class AccountNotFound(TransactionError):
    pass


class ConcurrentModification(TransactionError):
    pass


class InvalidTransaction(TransactionError):
    pass


@dataclass(frozen=True)
class TransferResult:
    transaction_id: str
    source_account: int
    destination_account: int
    amount: Decimal
    source_balance: Decimal
    destination_balance: Decimal
    status: str


@dataclass(frozen=True)
class Account:
    account_id: int
    owner: str
    balance: Decimal
    version: int


class Database:
    """Owns database initialization and connection configuration."""

    def __init__(self, path: str | Path):
        self.path = str(path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=10,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")

            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id INTEGER PRIMARY KEY,
                    owner TEXT NOT NULL UNIQUE,
                    balance_cents INTEGER NOT NULL DEFAULT 0
                        CHECK (balance_cents >= 0),
                    version INTEGER NOT NULL DEFAULT 0
                        CHECK (version >= 0),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS transfers (
                    transaction_id TEXT PRIMARY KEY,
                    source_account INTEGER NOT NULL,
                    destination_account INTEGER NOT NULL,
                    amount_cents INTEGER NOT NULL
                        CHECK (amount_cents > 0),
                    status TEXT NOT NULL
                        CHECK (status IN ('COMMITTED')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK (source_account <> destination_account),
                    FOREIGN KEY (source_account)
                        REFERENCES accounts(account_id),
                    FOREIGN KEY (destination_account)
                        REFERENCES accounts(account_id)
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_transfers_source
                    ON transfers(source_account);

                CREATE INDEX IF NOT EXISTS idx_transfers_destination
                    ON transfers(destination_account);
                """
            )


class AccountService:
    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def to_cents(amount: Decimal) -> int:
        if not amount.is_finite() or amount <= 0:
            raise InvalidTransaction("Amount must be positive and finite.")

        cents = amount * 100

        if cents != cents.to_integral_value():
            raise InvalidTransaction(
                "Currency amounts must have at most two decimal places."
            )

        return int(cents)

    @staticmethod
    def from_cents(cents: int) -> Decimal:
        return Decimal(cents) / Decimal(100)

    def create_account(
        self,
        owner: str,
        initial_balance: Decimal = Decimal("0.00"),
    ) -> int:
        owner = owner.strip()

        if not owner or len(owner) > 100:
            raise ValueError("Owner must contain 1 to 100 characters.")

        if not initial_balance.is_finite() or initial_balance < 0:
            raise ValueError("Initial balance cannot be negative.")

        cents = int(initial_balance * 100)

        if Decimal(cents) / 100 != initial_balance:
            raise ValueError("Initial balance has excessive precision.")

        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO accounts(owner, balance_cents)
                    VALUES (?, ?)
                    """,
                    (owner, cents),
                )
                account_id = cursor.lastrowid
                connection.commit()
                return int(account_id)
            except Exception:
                connection.rollback()
                raise

    def get_account(self, account_id: int) -> Account:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT account_id, owner, balance_cents, version
                FROM accounts
                WHERE account_id = ?
                """,
                (account_id,),
            ).fetchone()

        if row is None:
            raise AccountNotFound(f"Account {account_id} does not exist.")

        return Account(
            account_id=row["account_id"],
            owner=row["owner"],
            balance=self.from_cents(row["balance_cents"]),
            version=row["version"],
        )

    def transfer(
        self,
        source_id: int,
        destination_id: int,
        amount: Decimal,
        fail_after_debit: bool = False,
    ) -> TransferResult:
        """Transfer funds using one atomic database transaction."""

        if source_id == destination_id:
            raise InvalidTransaction("Source and destination must differ.")

        cents = self.to_cents(amount)
        transaction_id = str(uuid.uuid4())

        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")

            try:
                source = connection.execute(
                    """
                    SELECT balance_cents
                    FROM accounts
                    WHERE account_id = ?
                    """,
                    (source_id,),
                ).fetchone()

                destination = connection.execute(
                    """
                    SELECT balance_cents
                    FROM accounts
                    WHERE account_id = ?
                    """,
                    (destination_id,),
                ).fetchone()

                if source is None:
                    raise AccountNotFound(
                        f"Source account {source_id} does not exist."
                    )

                if destination is None:
                    raise AccountNotFound(
                        f"Destination account {destination_id} does not exist."
                    )

                if source["balance_cents"] < cents:
                    raise InsufficientFunds("Insufficient account balance.")

                # Debit and credit are part of the same transaction.
                connection.execute(
                    """
                    UPDATE accounts
                    SET balance_cents = balance_cents - ?,
                        version = version + 1
                    WHERE account_id = ?
                    """,
                    (cents, source_id),
                )

                if fail_after_debit:
                    raise RuntimeError("Simulated failure after debit.")

                connection.execute(
                    """
                    UPDATE accounts
                    SET balance_cents = balance_cents + ?,
                        version = version + 1
                    WHERE account_id = ?
                    """,
                    (cents, destination_id),
                )

                connection.execute(
                    """
                    INSERT INTO transfers(
                        transaction_id,
                        source_account,
                        destination_account,
                        amount_cents,
                        status
                    )
                    VALUES (?, ?, ?, ?, 'COMMITTED')
                    """,
                    (
                        transaction_id,
                        source_id,
                        destination_id,
                        cents,
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO audit_log(
                        transaction_id,
                        event_type,
                        details
                    )
                    VALUES (?, 'TRANSFER', ?)
                    """,
                    (
                        transaction_id,
                        f"Transfer of {amount} from {source_id} to {destination_id}",
                    ),
                )

                source_balance = connection.execute(
                    "SELECT balance_cents FROM accounts WHERE account_id = ?",
                    (source_id,),
                ).fetchone()["balance_cents"]

                destination_balance = connection.execute(
                    "SELECT balance_cents FROM accounts WHERE account_id = ?",
                    (destination_id,),
                ).fetchone()["balance_cents"]

                connection.commit()

                return TransferResult(
                    transaction_id=transaction_id,
                    source_account=source_id,
                    destination_account=destination_id,
                    amount=amount,
                    source_balance=self.from_cents(source_balance),
                    destination_balance=self.from_cents(destination_balance),
                    status="COMMITTED",
                )

            except Exception:
                connection.rollback()
                logger.exception("Transaction %s rolled back", transaction_id)
                raise

    def update_balance_optimistically(
        self,
        account_id: int,
        expected_version: int,
        new_balance: Decimal,
    ) -> None:
        """Prevent lost updates using a version column."""

        if not new_balance.is_finite() or new_balance < 0:
            raise ValueError("Balance must be non-negative and finite.")

        cents = int(new_balance * 100)

        if Decimal(cents) / 100 != new_balance:
            raise ValueError("Balance has excessive precision.")

        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")

            try:
                cursor = connection.execute(
                    """
                    UPDATE accounts
                    SET balance_cents = ?,
                        version = version + 1
                    WHERE account_id = ?
                      AND version = ?
                    """,
                    (cents, account_id, expected_version),
                )

                if cursor.rowcount != 1:
                    raise ConcurrentModification(
                        "Account changed since it was read."
                    )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

    def total_balance(self) -> Decimal:
        with self.database.connect() as connection:
            result = connection.execute(
                "SELECT COALESCE(SUM(balance_cents), 0) AS total FROM accounts"
            ).fetchone()

        return self.from_cents(result["total"])

    def integrity_check(self) -> list[str]:
        with self.database.connect() as connection:
            result = connection.execute(
                "PRAGMA integrity_check"
            ).fetchall()

            foreign_key_errors = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

        messages = [row[0] for row in result]

        if foreign_key_errors:
            messages.append(
                f"Foreign key violations: {len(foreign_key_errors)}"
            )

        return messages


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Reusable transaction context manager."""

    connection.execute("BEGIN")

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def demonstrate_savepoints(database: Database) -> None:
    """A savepoint rolls back part of a transaction."""

    with database.connect() as connection:
        connection.execute("BEGIN")

        try:
            connection.execute(
                "INSERT INTO audit_log(transaction_id, event_type, details) "
                "VALUES ('SAVEPOINT-DEMO', 'START', 'Outer transaction')"
            )

            connection.execute("SAVEPOINT optional_operation")

            connection.execute(
                "INSERT INTO audit_log(transaction_id, event_type, details) "
                "VALUES ('SAVEPOINT-DEMO', 'OPTIONAL', 'Temporary operation')"
            )

            connection.execute("ROLLBACK TO SAVEPOINT optional_operation")
            connection.execute("RELEASE SAVEPOINT optional_operation")

            connection.execute(
                "INSERT INTO audit_log(transaction_id, event_type, details) "
                "VALUES ('SAVEPOINT-DEMO', 'END', 'Outer transaction committed')"
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise


def demonstrate_concurrency(service: AccountService, first: int, second: int):
    """Concurrent transfers are serialized by SQLite write transactions."""

    errors: list[str] = []

    def worker() -> None:
        try:
            service.transfer(first, second, Decimal("1.00"))
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=worker) for _ in range(4)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    logger.info("Concurrent transfer errors: %s", errors)


def run_demo(path: str | Path) -> None:
    database = Database(path)
    database.initialize()

    service = AccountService(database)

    # Create accounts only when the database is initially empty.
    with database.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM accounts"
        ).fetchone()[0]

    if count == 0:
        source_id = service.create_account(
            "Operations Account", Decimal("1000.00")
        )
        destination_id = service.create_account(
            "Research Account", Decimal("250.00")
        )
    else:
        with database.connect() as connection:
            rows = connection.execute(
                "SELECT account_id FROM accounts ORDER BY account_id LIMIT 2"
            ).fetchall()

        if len(rows) < 2:
            raise RuntimeError("The demonstration requires two accounts.")

        source_id, destination_id = [row[0] for row in rows]

    initial_total = service.total_balance()
    print("\nINITIAL STATE")
    print(service.get_account(source_id))
    print(service.get_account(destination_id))
    print("Total:", initial_total)

    print("\nATOMICITY: SIMULATED FAILURE")

    try:
        service.transfer(
            source_id,
            destination_id,
            Decimal("50.00"),
            fail_after_debit=True,
        )
    except RuntimeError as exc:
        print("Expected rollback:", exc)

    assert service.total_balance() == initial_total

    print("\nSUCCESSFUL TRANSFER")

    result = service.transfer(
        source_id,
        destination_id,
        Decimal("100.00"),
    )

    print(result)

    assert service.total_balance() == initial_total

    print("\nCONSISTENCY: INVALID TRANSFER")

    try:
        service.transfer(
            source_id,
            destination_id,
            Decimal("999999.00"),
        )
    except InsufficientFunds as exc:
        print("Rejected:", exc)

    print("\nSAVEPOINT DEMONSTRATION")
    demonstrate_savepoints(database)

    print("\nOPTIMISTIC CONCURRENCY")

    account = service.get_account(source_id)

    try:
        service.update_balance_optimistically(
            source_id,
            account.version - 1,
            account.balance,
        )
    except ConcurrentModification as exc:
        print("Stale version rejected:", exc)

    print("\nCONCURRENT OPERATIONS")
    demonstrate_concurrency(service, source_id, destination_id)

    print("\nFINAL STATE")

    print(service.get_account(source_id))
    print(service.get_account(destination_id))
    print("Total:", service.total_balance())

    print("\nDATABASE INTEGRITY")
    print(service.integrity_check())

    assert service.total_balance() == initial_total
    assert service.integrity_check() == ["ok"]

    print("\nACID demonstration completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ACID transaction fundamentals using SQLite."
    )

    parser.add_argument(
        "--database",
        default="acid_fundamentals.db",
        help="SQLite database file path.",
    )

    parser.add_argument(
        "--temporary",
        action="store_true",
        help="Run using a temporary database.",
    )

    args = parser.parse_args()

    if args.temporary:
        with tempfile.TemporaryDirectory() as directory:
            run_demo(Path(directory) / "acid_demo.db")
    else:
        run_demo(args.database)


if __name__ == "__main__":
    main()
