#!/usr/bin/env python3
"""
Serializable Systems: Serializable Execution and Practical Costs

Implements:
1. Conflict-serializability analysis using precedence graphs.
2. Topological ordering of transactions.
3. Optimistic concurrency control (OCC).
4. Transaction read/write-set validation.
5. Commit and abort behavior.
6. Serializable execution simulation.
7. Performance and contention measurements.

Python standard library only.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations
from typing import Optional
import time


class OperationType(Enum):
    READ = "READ"
    WRITE = "WRITE"


class TransactionState(Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


@dataclass(frozen=True)
class Operation:
    transaction_id: str
    operation_type: OperationType
    resource: str

    def __post_init__(self):
        if not self.transaction_id.strip():
            raise ValueError("Transaction ID cannot be empty")
        if not self.resource.strip():
            raise ValueError("Resource cannot be empty")


@dataclass
class Transaction:
    transaction_id: str
    start_timestamp: int
    read_set: set[str] = field(default_factory=set)
    write_set: set[str] = field(default_factory=set)
    state: TransactionState = TransactionState.ACTIVE
    commit_timestamp: Optional[int] = None

    def read(self, resource: str):
        self._ensure_active()
        self.read_set.add(resource)

    def write(self, resource: str):
        self._ensure_active()
        self.write_set.add(resource)

    def _ensure_active(self):
        if self.state != TransactionState.ACTIVE:
            raise RuntimeError(
                f"Transaction {self.transaction_id} is not active"
            )


@dataclass
class AnalysisResult:
    serializable: bool
    execution_order: list[str]
    dependencies: dict[str, set[str]]
    cycle: list[str]


class ConflictSerializabilityAnalyzer:
    """
    Constructs a precedence graph.

    An edge Ti -> Tj exists when an operation of Ti conflicts
    with an earlier operation of Tj on the same resource.
    """

    @staticmethod
    def analyze(
        operations: list[Operation]
    ) -> AnalysisResult:

        transaction_ids = list(
            dict.fromkeys(op.transaction_id for op in operations)
        )

        graph = {
            transaction_id: set()
            for transaction_id in transaction_ids
        }

        for index, first in enumerate(operations):
            for second in operations[index + 1:]:

                if first.transaction_id == second.transaction_id:
                    continue

                if first.resource != second.resource:
                    continue

                if (
                    first.operation_type == OperationType.READ
                    and second.operation_type == OperationType.READ
                ):
                    continue

                graph[first.transaction_id].add(
                    second.transaction_id
                )

        indegree = {
            transaction_id: 0
            for transaction_id in transaction_ids
        }

        for neighbors in graph.values():
            for neighbor in neighbors:
                indegree[neighbor] += 1

        queue = deque(
            transaction_id
            for transaction_id in transaction_ids
            if indegree[transaction_id] == 0
        )

        order = []

        while queue:
            current = queue.popleft()
            order.append(current)

            for neighbor in sorted(graph[current]):
                indegree[neighbor] -= 1

                if indegree[neighbor] == 0:
                    queue.append(neighbor)

        serializable = len(order) == len(transaction_ids)

        cycle = []

        if not serializable:
            cycle = [
                transaction_id
                for transaction_id in transaction_ids
                if indegree[transaction_id] > 0
            ]

        return AnalysisResult(
            serializable=serializable,
            execution_order=order,
            dependencies=graph,
            cycle=cycle,
        )


class OptimisticTransactionManager:
    """
    Simplified optimistic concurrency control.

    Validation checks whether another committed transaction
    modified an object read by the current transaction after
    its start timestamp.

    This is an educational OCC model. It uses whole-transaction
    write publication and conservative validation.
    """

    def __init__(self, initial_data: dict[str, int]):
        self.data = dict(initial_data)
        self.version = {
            key: 0 for key in initial_data
        }

        self.clock = 0
        self.transactions: dict[str, Transaction] = {}
        self.commit_history = []
        self.abort_count = 0

    def begin(self, transaction_id: str) -> Transaction:

        if transaction_id in self.transactions:
            raise ValueError("Transaction ID already exists")

        self.clock += 1

        transaction = Transaction(
            transaction_id=transaction_id,
            start_timestamp=self.clock,
        )

        self.transactions[transaction_id] = transaction
        return transaction

    def read(self, transaction: Transaction, resource: str) -> int:

        transaction._ensure_active()

        if resource not in self.data:
            raise KeyError(f"Unknown resource: {resource}")

        transaction.read(resource)
        return self.data[resource]

    def write(
        self,
        transaction: Transaction,
        resource: str,
        value: int,
    ):

        transaction._ensure_active()

        if resource not in self.data:
            raise KeyError(f"Unknown resource: {resource}")

        if not isinstance(value, int):
            raise TypeError("This example accepts integer values")

        transaction.write(resource)

        # Private workspace: changes are not visible before commit.
        if not hasattr(transaction, "_workspace"):
            transaction._workspace = {}

        transaction._workspace[resource] = value

    def validate(self, transaction: Transaction) -> bool:

        transaction._ensure_active()

        for committed in self.commit_history:

            if committed["timestamp"] <= transaction.start_timestamp:
                continue

            changed_resources = committed["write_set"]

            # A transaction must not commit using stale reads.
            if transaction.read_set.intersection(changed_resources):
                return False

        return True

    def commit(self, transaction: Transaction) -> bool:

        transaction._ensure_active()

        if not self.validate(transaction):
            self.abort(transaction)
            return False

        self.clock += 1

        workspace = getattr(
            transaction,
            "_workspace",
            {},
        )

        # Publish all writes together after successful validation.
        for resource, value in workspace.items():
            self.data[resource] = value
            self.version[resource] = self.clock

        transaction.state = TransactionState.COMMITTED
        transaction.commit_timestamp = self.clock

        self.commit_history.append({
            "transaction_id": transaction.transaction_id,
            "timestamp": self.clock,
            "read_set": set(transaction.read_set),
            "write_set": set(transaction.write_set),
        })

        return True

    def abort(self, transaction: Transaction):

        transaction._ensure_active()

        transaction.state = TransactionState.ABORTED
        transaction.write_set.clear()

        if hasattr(transaction, "_workspace"):
            transaction._workspace.clear()

        self.abort_count += 1

    def snapshot(self):
        return dict(self.data)


class PerformanceMetrics:

    @staticmethod
    def estimate(
        transaction_count: int,
        conflict_count: int,
        validation_cost: float,
        retry_cost: float,
    ) -> dict:

        if transaction_count < 0 or conflict_count < 0:
            raise ValueError("Counts cannot be negative")

        if validation_cost < 0 or retry_cost < 0:
            raise ValueError("Costs cannot be negative")

        return {
            "transactions": transaction_count,
            "conflicts": conflict_count,
            "validation_cost": validation_cost,
            "retry_cost": retry_cost,
            "estimated_total_cost": (
                transaction_count * validation_cost
                + conflict_count * retry_cost
            ),
        }


def demonstrate_conflict_serializability():

    print("\n=== Conflict Serializability ===")

    schedule = [
        Operation("T1", OperationType.READ, "Account_A"),
        Operation("T2", OperationType.READ, "Account_B"),
        Operation("T1", OperationType.WRITE, "Account_B"),
        Operation("T2", OperationType.WRITE, "Account_A"),
    ]

    result = ConflictSerializabilityAnalyzer.analyze(schedule)

    print("Serializable:", result.serializable)
    print("Dependencies:", result.dependencies)
    print("Execution order:", result.execution_order)
    print("Cycle:", result.cycle)

    assert result.serializable is False


def demonstrate_serial_schedule():

    print("\n=== Serializable Schedule ===")

    schedule = [
        Operation("T1", OperationType.READ, "A"),
        Operation("T1", OperationType.WRITE, "A"),
        Operation("T2", OperationType.READ, "A"),
        Operation("T2", OperationType.WRITE, "A"),
        Operation("T1", OperationType.READ, "B"),
        Operation("T2", OperationType.READ, "B"),
    ]

    result = ConflictSerializabilityAnalyzer.analyze(schedule)

    print("Serializable:", result.serializable)
    print("Equivalent order:", result.execution_order)

    assert result.serializable


def demonstrate_optimistic_execution():

    print("\n=== Optimistic Concurrency Control ===")

    manager = OptimisticTransactionManager({
        "Account_A": 1000,
        "Account_B": 500,
    })

    transaction_1 = manager.begin("T1")
    transaction_2 = manager.begin("T2")

    # Both transactions read the same initial balance.
    balance_1 = manager.read(transaction_1, "Account_A")
    balance_2 = manager.read(transaction_2, "Account_A")

    manager.write(
        transaction_1,
        "Account_A",
        balance_1 - 100,
    )

    manager.write(
        transaction_2,
        "Account_A",
        balance_2 - 200,
    )

    print("T1 commit:", manager.commit(transaction_1))

    # T2 must abort because its read is stale.
    print("T2 commit:", manager.commit(transaction_2))

    print("Final balances:", manager.snapshot())
    print("Aborted transactions:", manager.abort_count)

    assert manager.snapshot()["Account_A"] == 900
    assert transaction_2.state == TransactionState.ABORTED


def demonstrate_nonconflicting_transactions():

    print("\n=== Independent Transactions ===")

    manager = OptimisticTransactionManager({
        "Account_A": 1000,
        "Account_B": 500,
    })

    first = manager.begin("T1")
    second = manager.begin("T2")

    manager.write(first, "Account_A", 900)
    manager.write(second, "Account_B", 400)

    assert manager.commit(first)
    assert manager.commit(second)

    print("Final balances:", manager.snapshot())


def demonstrate_performance():

    print("\n=== Practical Cost Model ===")

    metrics = PerformanceMetrics.estimate(
        transaction_count=1000,
        conflict_count=120,
        validation_cost=0.15,
        retry_cost=2.5,
    )

    for key, value in metrics.items():
        print(f"{key}: {value}")


def main():

    start = time.perf_counter()

    demonstrate_conflict_serializability()
    demonstrate_serial_schedule()
    demonstrate_optimistic_execution()
    demonstrate_nonconflicting_transactions()
    demonstrate_performance()

    elapsed = time.perf_counter() - start

    print("\nExecution completed.")
    print(f"Elapsed time: {elapsed:.6f} seconds")


if __name__ == "__main__":
    main()
