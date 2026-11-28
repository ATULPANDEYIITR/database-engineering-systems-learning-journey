#!/usr/bin/env python3
"""
Distributed Transactions: Two-Phase Commit (2PC) and Coordination.

Simulates:
- Distributed transaction coordination.
- Participant registration and resource preparation.
- Phase 1: Prepare and voting.
- Phase 2: Commit or abort.
- Durable coordinator decision logging.
- Idempotent message processing.
- Participant failures and timeouts.
- Coordinator recovery.
- Transaction state validation.
- The blocking limitation of classical 2PC.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Optional


class TransactionState(str, Enum):
    ACTIVE = "ACTIVE"
    PREPARING = "PREPARING"
    PREPARED = "PREPARED"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"
    ABORTING = "ABORTING"
    ABORTED = "ABORTED"
    IN_DOUBT = "IN_DOUBT"


class ParticipantState(str, Enum):
    ACTIVE = "ACTIVE"
    PREPARED = "PREPARED"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


class Vote(str, Enum):
    YES = "YES"
    NO = "NO"


class Decision(str, Enum):
    COMMIT = "COMMIT"
    ABORT = "ABORT"


class TransactionError(Exception):
    """Base exception for transaction failures."""


class InvalidTransition(TransactionError):
    pass


class ParticipantUnavailable(TransactionError):
    pass


class LogFailure(TransactionError):
    pass


@dataclass
class Transaction:
    transaction_id: str
    description: str
    state: TransactionState = TransactionState.ACTIVE
    participants: list[str] = field(default_factory=list)
    votes: dict[str, str] = field(default_factory=dict)
    decision: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class DurableLog:
    """Append-only JSONL decision log with flush and fsync."""

    def __init__(self, path: str = "transaction_log.jsonl"):
        self.path = Path(path)
        self.lock = RLock()

    def append(self, event: dict) -> None:
        with self.lock:
            try:
                with self.path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(event, sort_keys=True) + "\n")
                    file.flush()
                    import os
                    os.fsync(file.fileno())
            except OSError as exc:
                raise LogFailure(f"Unable to persist event: {exc}") from exc

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []

        events = []
        with self.lock:
            with self.path.open("r", encoding="utf-8") as file:
                for line_number, line in enumerate(file, 1):
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        raise LogFailure(
                            f"Corrupt log entry at line {line_number}"
                        ) from exc
        return events


class Participant:
    """Represents an independent transactional resource manager."""

    def __init__(
        self,
        name: str,
        initial_balance: int = 10000,
        can_prepare: bool = True
    ):
        if not name.strip():
            raise ValueError("Participant name cannot be empty")
        if initial_balance < 0:
            raise ValueError("Balance cannot be negative")

        self.name = name
        self.balance = initial_balance
        self.can_prepare = can_prepare
        self.available = True
        self.state_by_transaction: dict[str, ParticipantState] = {}
        self.pending: dict[str, tuple[int, int]] = {}
        self.lock = RLock()

    def prepare(
        self,
        transaction_id: str,
        debit: int,
        credit: int
    ) -> Vote:
        with self.lock:
            if not self.available:
                raise ParticipantUnavailable(
                    f"{self.name} is unavailable"
                )

            previous = self.state_by_transaction.get(transaction_id)

            if previous in (
                ParticipantState.PREPARED,
                ParticipantState.COMMITTED
            ):
                return Vote.YES

            if previous == ParticipantState.ABORTED:
                return Vote.NO

            if not self.can_prepare:
                self.state_by_transaction[transaction_id] = (
                    ParticipantState.FAILED
                )
                return Vote.NO

            if debit < 0 or credit < 0:
                return Vote.NO

            if self.balance < debit:
                self.state_by_transaction[transaction_id] = (
                    ParticipantState.FAILED
                )
                return Vote.NO

            # The resource is reserved logically, not yet permanently changed.
            self.pending[transaction_id] = (debit, credit)
            self.state_by_transaction[transaction_id] = (
                ParticipantState.PREPARED
            )
            return Vote.YES

    def commit(self, transaction_id: str) -> None:
        with self.lock:
            if not self.available:
                raise ParticipantUnavailable(
                    f"{self.name} cannot receive COMMIT"
                )

            state = self.state_by_transaction.get(transaction_id)

            if state == ParticipantState.COMMITTED:
                return

            if state != ParticipantState.PREPARED:
                raise InvalidTransition(
                    f"{self.name} cannot commit from {state}"
                )

            debit, credit = self.pending.pop(transaction_id)
            self.balance = self.balance - debit + credit
            self.state_by_transaction[transaction_id] = (
                ParticipantState.COMMITTED
            )

    def abort(self, transaction_id: str) -> None:
        with self.lock:
            if not self.available:
                raise ParticipantUnavailable(
                    f"{self.name} cannot receive ABORT"
                )

            state = self.state_by_transaction.get(transaction_id)

            if state == ParticipantState.ABORTED:
                return

            if state == ParticipantState.COMMITTED:
                raise InvalidTransition(
                    "A committed participant cannot be rolled back by 2PC"
                )

            self.pending.pop(transaction_id, None)
            self.state_by_transaction[transaction_id] = (
                ParticipantState.ABORTED
            )


class Coordinator:
    """Coordinates transaction voting and final decisions."""

    def __init__(self, durable_log: DurableLog):
        self.log = durable_log
        self.participants: dict[str, Participant] = {}
        self.transactions: dict[str, Transaction] = {}
        self.lock = RLock()

    def register(self, participant: Participant) -> None:
        with self.lock:
            if participant.name in self.participants:
                raise ValueError("Participant already registered")
            self.participants[participant.name] = participant

    def begin(self, description: str) -> Transaction:
        with self.lock:
            transaction = Transaction(
                transaction_id=str(uuid.uuid4()),
                description=description
            )
            self.log.append({
                "event": "BEGIN",
                "transaction_id": transaction.transaction_id,
                "description": description
            })
            self.transactions[transaction.transaction_id] = transaction
            return transaction

    def enlist(
        self,
        transaction_id: str,
        participant_name: str
    ) -> None:
        with self.lock:
            transaction = self._get_transaction(transaction_id)

            if transaction.state != TransactionState.ACTIVE:
                raise InvalidTransition("Cannot enlist after preparation")

            if participant_name not in self.participants:
                raise ValueError("Unknown participant")

            if participant_name in transaction.participants:
                raise ValueError("Participant already enlisted")

            transaction.participants.append(participant_name)
            transaction.updated_at = time.time()

    def _get_transaction(self, transaction_id: str) -> Transaction:
        try:
            return self.transactions[transaction_id]
        except KeyError as exc:
            raise ValueError("Unknown transaction") from exc

    def prepare(
        self,
        transaction_id: str,
        operations: dict[str, tuple[int, int]]
    ) -> bool:
        """
        Phase 1:
        Ask every participant to prepare and vote.

        A YES vote means the participant promises to retain its
        prepared state until it learns the final decision.
        """
        with self.lock:
            transaction = self._get_transaction(transaction_id)

            if transaction.state == TransactionState.PREPARED:
                return True

            if transaction.state != TransactionState.ACTIVE:
                raise InvalidTransition("Transaction cannot enter prepare")

            if not transaction.participants:
                raise TransactionError(
                    "A transaction requires at least one participant"
                )

            if set(operations) != set(transaction.participants):
                raise ValueError(
                    "Exactly one operation is required per participant"
                )

            transaction.state = TransactionState.PREPARING

            self.log.append({
                "event": "PREPARE_REQUESTED",
                "transaction_id": transaction_id,
                "participants": transaction.participants
            })

            all_yes = True

            for name in transaction.participants:
                participant = self.participants[name]
                debit, credit = operations[name]

                try:
                    vote = participant.prepare(
                        transaction_id, debit, credit
                    )
                except ParticipantUnavailable:
                    vote = Vote.NO

                transaction.votes[name] = vote.value

                self.log.append({
                    "event": "VOTE",
                    "transaction_id": transaction_id,
                    "participant": name,
                    "vote": vote.value
                })

                if vote != Vote.YES:
                    all_yes = False

            if all_yes:
                transaction.state = TransactionState.PREPARED
                transaction.updated_at = time.time()
                return True

            self._record_decision(transaction, Decision.ABORT)
            self._deliver_decision(transaction)
            return False

    def _record_decision(
        self,
        transaction: Transaction,
        decision: Decision
    ) -> None:
        """
        Persist the global decision before sending phase-2 messages.

        A production implementation must use a genuinely durable,
        replicated log and fencing against concurrent coordinators.
        """
        if transaction.decision is not None:
            if transaction.decision != decision.value:
                raise InvalidTransition("Conflicting global decision")
            return

        self.log.append({
            "event": "GLOBAL_DECISION",
            "transaction_id": transaction.transaction_id,
            "decision": decision.value
        })

        transaction.decision = decision.value
        transaction.state = (
            TransactionState.COMMITTING
            if decision == Decision.COMMIT
            else TransactionState.ABORTING
        )
        transaction.updated_at = time.time()

    def commit(self, transaction_id: str) -> None:
        """Phase 2: Commit every prepared participant."""
        with self.lock:
            transaction = self._get_transaction(transaction_id)

            if transaction.state == TransactionState.COMMITTED:
                return

            if transaction.state != TransactionState.PREPARED:
                raise InvalidTransition("Transaction is not prepared")

            self._record_decision(transaction, Decision.COMMIT)
            self._deliver_decision(transaction)

    def abort(self, transaction_id: str) -> None:
        """Record and distribute an irreversible global abort decision."""
        with self.lock:
            transaction = self._get_transaction(transaction_id)

            if transaction.state == TransactionState.ABORTED:
                return

            if transaction.decision == Decision.COMMIT.value:
                raise InvalidTransition("Commit decision already recorded")

            if transaction.state in (
                TransactionState.COMMITTED,
                TransactionState.COMMITTING
            ):
                raise InvalidTransition("Cannot abort after commit decision")

            self._record_decision(transaction, Decision.ABORT)
            self._deliver_decision(transaction)

    def _deliver_decision(self, transaction: Transaction) -> None:
        """Retry delivery independently; never reverse a global decision."""
        decision = transaction.decision
        failures = []

        for name in transaction.participants:
            participant = self.participants[name]

            try:
                if decision == Decision.COMMIT.value:
                    participant.commit(transaction.transaction_id)
                elif decision == Decision.ABORT.value:
                    participant.abort(transaction.transaction_id)
            except (ParticipantUnavailable, InvalidTransition) as exc:
                failures.append(f"{name}: {exc}")

        if failures:
            transaction.state = TransactionState.IN_DOUBT
            self.log.append({
                "event": "DELIVERY_INCOMPLETE",
                "transaction_id": transaction.transaction_id,
                "failures": failures
            })
            return

        transaction.state = (
            TransactionState.COMMITTED
            if decision == Decision.COMMIT.value
            else TransactionState.ABORTED
        )
        transaction.updated_at = time.time()

        self.log.append({
            "event": "COMPLETED",
            "transaction_id": transaction.transaction_id,
            "state": transaction.state.value
        })

    def recover(self, transaction_id: str) -> None:
        """
        Recover using the durable global decision.

        A transaction without a recorded decision must not be
        unilaterally committed. It requires coordinator recovery
        and participant-state reconciliation.
        """
        with self.lock:
            transaction = self._get_transaction(transaction_id)

            if transaction.decision is None:
                transaction.state = TransactionState.IN_DOUBT
                raise TransactionError(
                    "No durable global decision exists; "
                    "automatic commit is unsafe"
                )

            self._deliver_decision(transaction)

    def report(self, transaction_id: str) -> dict:
        transaction = self._get_transaction(transaction_id)

        return {
            "transaction_id": transaction.transaction_id,
            "description": transaction.description,
            "state": transaction.state.value,
            "participants": transaction.participants,
            "votes": transaction.votes,
            "decision": transaction.decision,
            "balances": {
                name: self.participants[name].balance
                for name in transaction.participants
            }
        }


def demonstration() -> None:
    log_path = "2pc_demo_log.jsonl"

    # Remove the previous demonstration log for reproducible execution.
    path = Path(log_path)
    if path.exists():
        path.unlink()

    coordinator = Coordinator(DurableLog(log_path))

    accounts = [
        Participant("BANK_A", 10000),
        Participant("BANK_B", 5000),
        Participant("BANK_C", 7000)
    ]

    for account in accounts:
        coordinator.register(account)

    print("\nCASE 1: Successful distributed transfer")

    tx1 = coordinator.begin("Transfer between distributed accounts")

    for name in ("BANK_A", "BANK_B"):
        coordinator.enlist(tx1.transaction_id, name)

    operations = {
        "BANK_A": (1000, 0),
        "BANK_B": (0, 1000)
    }

    if coordinator.prepare(tx1.transaction_id, operations):
        coordinator.commit(tx1.transaction_id)

    print(json.dumps(
        coordinator.report(tx1.transaction_id),
        indent=2
    ))

    assert tx1.state == TransactionState.COMMITTED
    assert accounts[0].balance == 9000
    assert accounts[1].balance == 6000

    print("\nCASE 2: Participant votes NO")

    tx2 = coordinator.begin("Transfer exceeding available funds")
    coordinator.enlist(tx2.transaction_id, "BANK_A")
    coordinator.enlist(tx2.transaction_id, "BANK_C")

    operations = {
        "BANK_A": (500, 0),
        "BANK_C": (100000, 0)
    }

    result = coordinator.prepare(tx2.transaction_id, operations)

    assert result is False
    assert tx2.state == TransactionState.ABORTED

    print(json.dumps(
        coordinator.report(tx2.transaction_id),
        indent=2
    ))

    print("\nCASE 3: Participant unavailable during phase 2")

    tx3 = coordinator.begin("Commit with delayed participant")
    coordinator.enlist(tx3.transaction_id, "BANK_A")
    coordinator.enlist(tx3.transaction_id, "BANK_B")

    operations = {
        "BANK_A": (200, 0),
        "BANK_B": (0, 200)
    }

    assert coordinator.prepare(tx3.transaction_id, operations)

    accounts[1].available = False
    coordinator.commit(tx3.transaction_id)

    assert tx3.state == TransactionState.IN_DOUBT
    assert tx3.decision == Decision.COMMIT.value

    print(json.dumps(
        coordinator.report(tx3.transaction_id),
        indent=2
    ))

    # Restore connectivity and recover the recorded COMMIT decision.
    accounts[1].available = True
    coordinator.recover(tx3.transaction_id)

    assert tx3.state == TransactionState.COMMITTED
    assert accounts[0].balance == 8800
    assert accounts[1].balance == 6200

    print("\nCASE 4: Idempotent recovery")

    coordinator.recover(tx3.transaction_id)
    assert tx3.state == TransactionState.COMMITTED

    print("Repeated recovery did not apply the transfer twice.")

    print("\nCASE 5: Durable event inspection")

    events = coordinator.log.read_all()
    print(f"Persisted events: {len(events)}")

    for event in events:
        if event["event"] == "GLOBAL_DECISION":
            print(
                event["transaction_id"],
                event["decision"]
            )

    print("\nAll assertions passed.")


if __name__ == "__main__":
    try:
        demonstration()
    except (TransactionError, ValueError, OSError) as error:
        print(f"Transaction system error: {error}")
        raise
