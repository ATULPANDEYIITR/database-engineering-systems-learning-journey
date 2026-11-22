# locks.py
# Shared Locks, Exclusive Locks, and Lock Compatibility
# Python 3.10+
#
# Demonstrates transaction-level locking, compatibility, lock conversion,
# FIFO scheduling, timeouts, reentrancy, and deadlock-aware upgrade handling.

from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Dict, Optional


class LockMode(Enum):
    SHARED = "S"
    EXCLUSIVE = "X"


class LockError(Exception):
    pass


class LockTimeout(LockError):
    pass


class LockUpgradeConflict(LockError):
    pass


class LockNotHeld(LockError):
    pass


# A shared lock is compatible with another shared lock.
# An exclusive lock conflicts with both shared and exclusive locks.
COMPATIBILITY = {
    LockMode.SHARED: {
        LockMode.SHARED: True,
        LockMode.EXCLUSIVE: False,
    },
    LockMode.EXCLUSIVE: {
        LockMode.SHARED: False,
        LockMode.EXCLUSIVE: False,
    },
}


@dataclass
class LockRequest:
    transaction_id: str
    resource: str
    mode: LockMode
    requested_at: float = field(default_factory=time.monotonic)


@dataclass
class LockState:
    holders: Dict[str, LockMode] = field(default_factory=dict)
    counts: Dict[str, int] = field(default_factory=dict)
    queue: Deque[LockRequest] = field(default_factory=deque)


class LockManager:
    """Thread-safe in-memory lock manager with FIFO request scheduling."""

    def __init__(self):
        self._condition = threading.Condition(threading.RLock())
        self._resources: Dict[str, LockState] = defaultdict(LockState)

    @staticmethod
    def _compatible_with_holders(
        state: LockState,
        transaction_id: str,
        requested_mode: LockMode,
    ) -> bool:
        for holder_id, held_mode in state.holders.items():
            if holder_id == transaction_id:
                continue

            if not COMPATIBILITY[requested_mode][held_mode]:
                return False

        return True

    def _can_grant(
        self,
        state: LockState,
        request: LockRequest,
    ) -> bool:
        if not self._compatible_with_holders(
            state,
            request.transaction_id,
            request.mode,
        ):
            return False

        # Do not bypass earlier incompatible requests.
        for earlier in state.queue:
            if earlier is request:
                break

            if not (
                earlier.mode == LockMode.SHARED
                and request.mode == LockMode.SHARED
            ):
                return False

        return True

    def acquire(
        self,
        transaction_id: str,
        resource: str,
        mode: LockMode,
        timeout: Optional[float] = 5.0,
    ) -> None:
        if not transaction_id or not resource:
            raise ValueError("Transaction ID and resource are required.")

        if timeout is not None and timeout < 0:
            raise ValueError("Timeout cannot be negative.")

        deadline = (
            None if timeout is None else time.monotonic() + timeout
        )

        with self._condition:
            state = self._resources[resource]

            current_mode = state.holders.get(transaction_id)

            # Reentrant acquisition of an already-held lock.
            if current_mode == LockMode.EXCLUSIVE:
                state.counts[transaction_id] += 1
                return

            if current_mode == LockMode.SHARED:
                if mode == LockMode.SHARED:
                    state.counts[transaction_id] += 1
                    return

                # Shared-to-exclusive conversion can deadlock when
                # multiple transactions simultaneously request upgrades.
                other_holders = [
                    holder
                    for holder in state.holders
                    if holder != transaction_id
                ]

                if other_holders:
                    raise LockUpgradeConflict(
                        f"{transaction_id} cannot upgrade {resource}: "
                        f"other transactions hold shared locks."
                    )

            request = LockRequest(transaction_id, resource, mode)
            state.queue.append(request)

            while True:
                if self._can_grant(state, request):
                    state.queue.remove(request)

                    if current_mode == LockMode.SHARED:
                        # Replace the existing shared lock.
                        state.holders[transaction_id] = mode
                        state.counts[transaction_id] = 1
                    else:
                        state.holders[transaction_id] = mode
                        state.counts[transaction_id] = 1

                    self._condition.notify_all()
                    return

                remaining = (
                    None if deadline is None
                    else deadline - time.monotonic()
                )

                if remaining is not None and remaining <= 0:
                    state.queue.remove(request)
                    self._condition.notify_all()

                    raise LockTimeout(
                        f"Transaction {transaction_id} timed out "
                        f"waiting for {mode.value} on {resource}."
                    )

                self._condition.wait(remaining)

    def release(
        self,
        transaction_id: str,
        resource: str,
    ) -> None:
        with self._condition:
            state = self._resources.get(resource)

            if state is None or transaction_id not in state.holders:
                raise LockNotHeld(
                    f"{transaction_id} does not hold {resource}."
                )

            state.counts[transaction_id] -= 1

            if state.counts[transaction_id] == 0:
                del state.counts[transaction_id]
                del state.holders[transaction_id]

            self._condition.notify_all()

    def release_all(self, transaction_id: str) -> None:
        """Release every lock owned by a transaction."""
        with self._condition:
            for state in self._resources.values():
                state.holders.pop(transaction_id, None)
                state.counts.pop(transaction_id, None)

            self._condition.notify_all()

    def snapshot(self) -> dict:
        with self._condition:
            return {
                resource: {
                    "holders": {
                        transaction: {
                            "mode": mode.value,
                            "count": state.counts[transaction],
                        }
                        for transaction, mode in state.holders.items()
                    },
                    "waiting": [
                        {
                            "transaction": request.transaction_id,
                            "mode": request.mode.value,
                        }
                        for request in state.queue
                    ],
                }
                for resource, state in self._resources.items()
            }

    @contextmanager
    def transaction(self, transaction_id: Optional[str] = None):
        """Provide transaction-style automatic lock cleanup."""
        transaction_id = transaction_id or str(uuid.uuid4())

        try:
            yield Transaction(self, transaction_id)
        finally:
            self.release_all(transaction_id)


class Transaction:
    def __init__(self, manager: LockManager, transaction_id: str):
        self.manager = manager
        self.transaction_id = transaction_id

    def shared_lock(self, resource: str, timeout=5.0):
        self.manager.acquire(
            self.transaction_id, resource, LockMode.SHARED, timeout
        )

    def exclusive_lock(self, resource: str, timeout=5.0):
        self.manager.acquire(
            self.transaction_id, resource, LockMode.EXCLUSIVE, timeout
        )

    def release(self, resource: str):
        self.manager.release(self.transaction_id, resource)


def demonstrate_compatibility():
    print("\n1. Lock compatibility")

    manager = LockManager()

    manager.acquire("T1", "accounts:101", LockMode.SHARED)
    manager.acquire("T2", "accounts:101", LockMode.SHARED)

    print("T1 shared:", manager.snapshot()["accounts:101"]["holders"])

    try:
        manager.acquire(
            "T3", "accounts:101", LockMode.EXCLUSIVE, timeout=0.1
        )
    except LockTimeout as error:
        print("Expected conflict:", error)

    manager.release_all("T1")
    manager.release_all("T2")

    manager.acquire("T3", "accounts:101", LockMode.EXCLUSIVE)
    print("Exclusive granted:", manager.snapshot()["accounts:101"])

    manager.release_all("T3")


def demonstrate_upgrade_conflict():
    print("\n2. Lock upgrade conflict")

    manager = LockManager()

    manager.acquire("T1", "inventory:500", LockMode.SHARED)
    manager.acquire("T2", "inventory:500", LockMode.SHARED)

    try:
        manager.acquire("T1", "inventory:500", LockMode.EXCLUSIVE)
    except LockUpgradeConflict as error:
        print("Upgrade rejected:", error)

    manager.release_all("T1")
    manager.release_all("T2")


def demonstrate_concurrency():
    print("\n3. Concurrent exclusive access")

    manager = LockManager()
    execution_order = []

    def worker(transaction_id: str, delay: float):
        try:
            manager.acquire(
                transaction_id,
                "orders:9001",
                LockMode.EXCLUSIVE,
                timeout=3.0,
            )

            execution_order.append(f"{transaction_id}: acquired")
            time.sleep(delay)
            execution_order.append(f"{transaction_id}: completed")

        except LockError as error:
            execution_order.append(f"{transaction_id}: {error}")

        finally:
            manager.release_all(transaction_id)

    first = threading.Thread(target=worker, args=("T10", 0.2))
    second = threading.Thread(target=worker, args=("T11", 0.1))

    first.start()
    time.sleep(0.03)
    second.start()

    first.join()
    second.join()

    for event in execution_order:
        print(event)


def demonstrate_reentrancy():
    print("\n4. Reentrant locking")

    manager = LockManager()

    manager.acquire("T20", "products:10", LockMode.SHARED)
    manager.acquire("T20", "products:10", LockMode.SHARED)

    print("Acquisition count:",
          manager.snapshot()["products:10"]["holders"]["T20"]["count"])

    manager.release("T20", "products:10")
    print("After one release:",
          manager.snapshot()["products:10"]["holders"]["T20"]["count"])

    manager.release_all("T20")


def demonstrate_transaction_context():
    print("\n5. Automatic transaction cleanup")

    manager = LockManager()

    with manager.transaction("T30") as transaction:
        transaction.exclusive_lock("payments:700")
        print("Inside transaction:", manager.snapshot())

    print("After transaction:", manager.snapshot())


def run_tests():
    manager = LockManager()

    manager.acquire("A", "R", LockMode.SHARED)
    manager.acquire("B", "R", LockMode.SHARED)

    assert len(manager.snapshot()["R"]["holders"]) == 2

    try:
        manager.acquire("C", "R", LockMode.EXCLUSIVE, timeout=0.01)
        raise AssertionError("Exclusive lock should have timed out.")
    except LockTimeout:
        pass

    manager.release_all("A")
    manager.release_all("B")

    manager.acquire("C", "R", LockMode.EXCLUSIVE)

    assert manager.snapshot()["R"]["holders"]["C"]["mode"] == "X"

    manager.release_all("C")

    print("\nAll assertions passed.")


if __name__ == "__main__":
    demonstrate_compatibility()
    demonstrate_upgrade_conflict()
    demonstrate_concurrency()
    demonstrate_reentrancy()
    demonstrate_transaction_context()
    run_tests()
