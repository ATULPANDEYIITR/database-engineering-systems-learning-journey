#!/usr/bin/env python3
"""
Deadlock Management System
Detection, Prevention, and Recovery

Implements:
- Single-instance resource allocation
- Wait-for graph construction
- DFS-based deadlock detection
- Resource-ordering prevention
- Deadlock recovery through victim selection
- Transaction rollback and resource release
- Validation, event logging, and executable tests

Python 3.10+
Standard library only.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TransactionState(Enum):
    ACTIVE = "ACTIVE"
    WAITING = "WAITING"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class DeadlockError(Exception):
    pass


class ResourceOrderViolation(Exception):
    pass


class TransactionError(Exception):
    pass


@dataclass
class Transaction:
    transaction_id: str
    start_order: int
    state: TransactionState = TransactionState.ACTIVE
    held_resources: set[str] = field(default_factory=set)
    waiting_for: Optional[str] = None
    rollback_count: int = 0


@dataclass
class Resource:
    name: str
    order: int
    owner: Optional[str] = None
    wait_queue: deque[str] = field(default_factory=deque)


@dataclass
class DeadlockReport:
    cycle: list[str]
    victim: str
    explanation: str


class DeadlockManager:
    """
    Single-instance resource manager.

    Detection:
        Constructs a wait-for graph and searches for directed cycles.

    Prevention:
        Enforces a global resource acquisition order.

    Recovery:
        Aborts the youngest transaction in a detected cycle.
        Releases its resources and wakes eligible waiting transactions.
    """

    def __init__(self, prevention_enabled: bool = False):
        self.transactions: dict[str, Transaction] = {}
        self.resources: dict[str, Resource] = {}
        self.prevention_enabled = prevention_enabled
        self.clock = 0
        self.events: list[str] = []

    def log(self, message: str) -> None:
        self.events.append(message)
        print(f"[EVENT] {message}")

    def add_resource(self, name: str, order: int) -> None:
        if not name or name in self.resources:
            raise ValueError(f"Invalid or duplicate resource: {name}")

        if order < 0:
            raise ValueError("Resource order cannot be negative.")

        if any(r.order == order for r in self.resources.values()):
            raise ValueError("Resource ordering values must be unique.")

        self.resources[name] = Resource(name, order)
        self.log(f"Resource {name} registered with order {order}.")

    def begin_transaction(self, transaction_id: str) -> None:
        if not transaction_id:
            raise ValueError("Transaction ID cannot be empty.")

        if transaction_id in self.transactions:
            raise TransactionError("Transaction ID already exists.")

        self.clock += 1

        self.transactions[transaction_id] = Transaction(
            transaction_id=transaction_id,
            start_order=self.clock,
        )

        self.log(f"Transaction {transaction_id} started.")

    def _get_active_transaction(self, transaction_id: str) -> Transaction:
        transaction = self.transactions.get(transaction_id)

        if transaction is None:
            raise TransactionError("Unknown transaction.")

        if transaction.state not in {
            TransactionState.ACTIVE,
            TransactionState.WAITING,
        }:
            raise TransactionError(
                f"Transaction is {transaction.state.value}."
            )

        return transaction

    def acquire(self, transaction_id: str, resource_name: str) -> bool:
        """
        Returns True when acquired immediately.
        Returns False when the transaction must wait.
        """

        transaction = self._get_active_transaction(transaction_id)
        resource = self.resources.get(resource_name)

        if resource is None:
            raise ValueError(f"Unknown resource: {resource_name}")

        if resource_name in transaction.held_resources:
            return True

        if self.prevention_enabled and transaction.held_resources:
            highest_order = max(
                self.resources[name].order
                for name in transaction.held_resources
            )

            if resource.order < highest_order:
                raise ResourceOrderViolation(
                    f"{transaction_id} requested {resource_name} "
                    "out of global resource order."
                )

        if resource.owner is None:
            resource.owner = transaction_id
            transaction.held_resources.add(resource_name)
            transaction.waiting_for = None
            transaction.state = TransactionState.ACTIVE

            self.log(
                f"{transaction_id} acquired {resource_name}."
            )

            return True

        if resource.owner == transaction_id:
            return True

        if transaction_id not in resource.wait_queue:
            resource.wait_queue.append(transaction_id)

        transaction.waiting_for = resource_name
        transaction.state = TransactionState.WAITING

        self.log(
            f"{transaction_id} waits for {resource_name}, "
            f"owned by {resource.owner}."
        )

        return False

    def build_wait_for_graph(self) -> dict[str, set[str]]:
        """
        An edge T1 -> T2 means T1 waits for a resource held by T2.
        """

        graph = defaultdict(set)

        for transaction in self.transactions.values():
            if transaction.state == TransactionState.WAITING:
                resource = self.resources[transaction.waiting_for]

                if resource.owner is not None:
                    graph[transaction.transaction_id].add(
                        resource.owner
                    )

        return dict(graph)

    def detect_deadlocks(self) -> list[list[str]]:
        """
        DFS cycle detection using three-color traversal.

        WHITE: unvisited
        GRAY: currently on recursion stack
        BLACK: fully processed
        """

        graph = self.build_wait_for_graph()

        white = 0
        gray = 1
        black = 2

        color = {name: white for name in self.transactions}
        stack: list[str] = []
        cycles: list[list[str]] = []
        seen: set[tuple[str, ...]] = set()

        def canonicalize(cycle: list[str]) -> tuple[str, ...]:
            rotations = [
                tuple(cycle[i:] + cycle[:i])
                for i in range(len(cycle))
            ]
            return min(rotations)

        def dfs(node: str) -> None:
            color[node] = gray
            stack.append(node)

            for neighbor in graph.get(node, set()):
                if color[neighbor] == white:
                    dfs(neighbor)

                elif color[neighbor] == gray:
                    index = stack.index(neighbor)
                    cycle = stack[index:].copy()
                    key = canonicalize(cycle)

                    if key not in seen:
                        seen.add(key)
                        cycles.append(cycle)

            stack.pop()
            color[node] = black

        for transaction_id in graph:
            if color[transaction_id] == white:
                dfs(transaction_id)

        return cycles

    def select_victim(self, cycle: list[str]) -> str:
        """
        Select the youngest transaction.

        The transaction with the greatest start_order is the victim.
        """

        return max(
            cycle,
            key=lambda transaction_id:
                self.transactions[transaction_id].start_order
        )

    def _remove_from_queues(self, transaction_id: str) -> None:
        for resource in self.resources.values():
            resource.wait_queue = deque(
                transaction
                for transaction in resource.wait_queue
                if transaction != transaction_id
            )

    def _wake_waiters(self, resource: Resource) -> None:
        """
        FIFO scheduling for released single-instance resources.
        """

        while resource.owner is None and resource.wait_queue:
            transaction_id = resource.wait_queue.popleft()
            transaction = self.transactions[transaction_id]

            if transaction.state != TransactionState.WAITING:
                continue

            resource.owner = transaction_id
            transaction.held_resources.add(resource.name)
            transaction.waiting_for = None
            transaction.state = TransactionState.ACTIVE

            self.log(
                f"{transaction_id} resumed and acquired "
                f"{resource.name}."
            )

    def release(self, transaction_id: str, resource_name: str) -> None:
        transaction = self._get_active_transaction(transaction_id)
        resource = self.resources.get(resource_name)

        if resource is None:
            raise ValueError("Unknown resource.")

        if resource.owner != transaction_id:
            raise TransactionError(
                f"{transaction_id} does not own {resource_name}."
            )

        resource.owner = None
        transaction.held_resources.remove(resource_name)

        self.log(
            f"{transaction_id} released {resource_name}."
        )

        self._wake_waiters(resource)

    def recover(self, cycle: list[str]) -> DeadlockReport:
        if not cycle:
            raise ValueError("A deadlock cycle is required.")

        victim = self.select_victim(cycle)
        transaction = self.transactions[victim]

        self.log(f"Recovery initiated for cycle: {cycle}.")
        self.log(f"Selected victim: {victim}.")

        self._remove_from_queues(victim)

        held = list(transaction.held_resources)

        transaction.held_resources.clear()
        transaction.waiting_for = None
        transaction.state = TransactionState.ABORTED
        transaction.rollback_count += 1

        # Release all resources before waking waiting transactions.
        for resource_name in held:
            resource = self.resources[resource_name]
            resource.owner = None

        self.log(
            f"{victim} aborted. {len(held)} resources released."
        )

        for resource_name in held:
            self._wake_waiters(self.resources[resource_name])

        return DeadlockReport(
            cycle=cycle,
            victim=victim,
            explanation=(
                f"Transaction {victim} was aborted to break "
                "the circular wait."
            ),
        )

    def commit(self, transaction_id: str) -> None:
        transaction = self._get_active_transaction(transaction_id)

        if transaction.state == TransactionState.WAITING:
            raise TransactionError(
                "A waiting transaction cannot commit."
            )

        if any(
            transaction_id in resource.wait_queue
            for resource in self.resources.values()
        ):
            raise TransactionError(
                "Transaction has unresolved resource requests."
            )

        held = list(transaction.held_resources)

        transaction.held_resources.clear()
        transaction.state = TransactionState.COMMITTED

        for resource_name in held:
            resource = self.resources[resource_name]
            resource.owner = None

        self.log(f"{transaction_id} committed.")

        for resource_name in held:
            self._wake_waiters(self.resources[resource_name])

    def detect_and_recover(self) -> list[DeadlockReport]:
        reports = []

        while True:
            cycles = self.detect_deadlocks()

            if not cycles:
                break

            for cycle in cycles:
                if self.detect_deadlocks():
                    reports.append(self.recover(cycle))

        return reports

    def display_state(self) -> None:
        print("\nTRANSACTION TABLE")

        for transaction in self.transactions.values():
            print(
                f"{transaction.transaction_id}: "
                f"state={transaction.state.value}, "
                f"held={sorted(transaction.held_resources)}, "
                f"waiting_for={transaction.waiting_for}"
            )

        print("\nRESOURCE TABLE")

        for resource in self.resources.values():
            print(
                f"{resource.name}: "
                f"owner={resource.owner}, "
                f"queue={list(resource.wait_queue)}"
            )

        print("\nWAIT-FOR GRAPH")

        for transaction, owners in self.build_wait_for_graph().items():
            print(f"{transaction} -> {sorted(owners)}")


def demonstrate_deadlock_detection() -> None:
    print("\n" + "=" * 65)
    print("SCENARIO 1: DEADLOCK DETECTION AND RECOVERY")
    print("=" * 65)

    manager = DeadlockManager()

    manager.add_resource("DATABASE", 1)
    manager.add_resource("FILE_SYSTEM", 2)

    manager.begin_transaction("T1")
    manager.begin_transaction("T2")

    manager.acquire("T1", "DATABASE")
    manager.acquire("T2", "FILE_SYSTEM")

    manager.acquire("T1", "FILE_SYSTEM")
    manager.acquire("T2", "DATABASE")

    manager.display_state()

    cycles = manager.detect_deadlocks()

    print("\nDEADLOCK DETECTION RESULTS")

    for cycle in cycles:
        print("Detected cycle:", " -> ".join(cycle + [cycle[0]]))

    reports = manager.detect_and_recover()

    print("\nRECOVERY RESULTS")

    for report in reports:
        print(report.explanation)

    manager.display_state()

    for transaction in manager.transactions.values():
        if transaction.state == TransactionState.ACTIVE:
            manager.commit(transaction.transaction_id)

    manager.display_state()


def demonstrate_deadlock_prevention() -> None:
    print("\n" + "=" * 65)
    print("SCENARIO 2: RESOURCE ORDERING PREVENTION")
    print("=" * 65)

    manager = DeadlockManager(prevention_enabled=True)

    manager.add_resource("ACCOUNT", 1)
    manager.add_resource("LEDGER", 2)
    manager.add_resource("AUDIT_LOG", 3)

    manager.begin_transaction("T3")

    manager.acquire("T3", "ACCOUNT")
    manager.acquire("T3", "LEDGER")

    try:
        manager.acquire("T3", "ACCOUNT")
    except ResourceOrderViolation as error:
        print("[PREVENTION]", error)

    manager.commit("T3")
    manager.display_state()


def demonstrate_error_handling() -> None:
    print("\n" + "=" * 65)
    print("SCENARIO 3: VALIDATION AND FAILURE HANDLING")
    print("=" * 65)

    manager = DeadlockManager()
    manager.add_resource("CACHE", 1)
    manager.begin_transaction("T4")

    try:
        manager.acquire("T4", "UNKNOWN")
    except ValueError as error:
        print("[VALIDATION]", error)

    try:
        manager.release("T4", "CACHE")
    except TransactionError as error:
        print("[VALIDATION]", error)

    manager.commit("T4")


def run_assertions() -> None:
    """Small automated checks for the main invariants."""

    manager = DeadlockManager()

    manager.add_resource("R1", 1)
    manager.add_resource("R2", 2)

    manager.begin_transaction("A")
    manager.begin_transaction("B")

    assert manager.acquire("A", "R1")
    assert manager.acquire("B", "R2")

    assert not manager.acquire("A", "R2")
    assert not manager.acquire("B", "R1")

    cycles = manager.detect_deadlocks()

    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B"}

    reports = manager.detect_and_recover()

    assert len(reports) == 1

    victim = reports[0].victim

    assert manager.transactions[victim].state == (
        TransactionState.ABORTED
    )

    assert not manager.detect_deadlocks()

    ordered = DeadlockManager(prevention_enabled=True)

    ordered.add_resource("LOW", 1)
    ordered.add_resource("HIGH", 2)
    ordered.begin_transaction("C")

    assert ordered.acquire("C", "LOW")
    assert ordered.acquire("C", "HIGH")

    try:
        ordered.acquire("C", "LOW")
        raise AssertionError("Expected ordering violation.")
    except ResourceOrderViolation:
        pass

    ordered.commit("C")

    print("\n[TEST] All assertions passed.")


def main() -> None:
    demonstrate_deadlock_detection()
    demonstrate_deadlock_prevention()
    demonstrate_error_handling()
    run_assertions()


if __name__ == "__main__":
    main()
