#!/usr/bin/env python3
"""
Database Design Patterns: Audit Tables, Soft Deletes, and Status Models.

A self-contained Python demonstration of database lifecycle design for an
enterprise equipment-maintenance system.

The implementation covers:
- Immutable audit events and actor attribution.
- Soft deletion, restoration, and active-record filtering.
- Explicit status transitions and transition validation.
- Optimistic concurrency control.
- Atomic state changes and audit recording.
- Idempotency, history queries, integrity checks, and JSON export.
- Unit tests for lifecycle and failure conditions.

Run:
    python database_patterns.py

Only the Python standard library is required.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, Callable
from uuid import uuid4


def utc_now() -> datetime:
    """Return an aware UTC timestamp suitable for persisted event times."""
    return datetime.now(timezone.utc)


class DomainError(Exception):
    """Base class for expected domain and persistence failures."""


class NotFoundError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class InvalidTransitionError(DomainError):
    pass


class ConcurrencyError(DomainError):
    pass


class DuplicateOperationError(DomainError):
    pass


class EquipmentStatus(str, Enum):
    """Operational status is independent of deletion state."""

    REQUESTED = "requested"
    APPROVED = "approved"
    IN_SERVICE = "in_service"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


ALLOWED_TRANSITIONS: dict[EquipmentStatus, frozenset[EquipmentStatus]] = {
    EquipmentStatus.REQUESTED: frozenset({EquipmentStatus.APPROVED}),
    EquipmentStatus.APPROVED: frozenset({
        EquipmentStatus.IN_SERVICE,
        EquipmentStatus.RETIRED,
    }),
    EquipmentStatus.IN_SERVICE: frozenset({
        EquipmentStatus.MAINTENANCE,
        EquipmentStatus.RETIRED,
    }),
    EquipmentStatus.MAINTENANCE: frozenset({
        EquipmentStatus.IN_SERVICE,
        EquipmentStatus.RETIRED,
    }),
    EquipmentStatus.RETIRED: frozenset(),
}


@dataclass
class Equipment:
    equipment_id: str
    asset_tag: str
    name: str
    status: EquipmentStatus = EquipmentStatus.REQUESTED
    is_deleted: bool = False
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    created_by: str = "system"
    updated_at: datetime = field(default_factory=utc_now)
    updated_by: str = "system"
    version: int = 1

    def validate(self) -> None:
        if not self.asset_tag.strip():
            raise ValidationError("Asset tag cannot be empty.")
        if not self.name.strip():
            raise ValidationError("Equipment name cannot be empty.")
        if self.version < 1:
            raise ValidationError("Version must be positive.")

        if self.is_deleted:
            if self.deleted_at is None or not self.deleted_by:
                raise ValidationError(
                    "Deleted records require deleted_at and deleted_by."
                )
        elif self.deleted_at is not None or self.deleted_by is not None:
            raise ValidationError(
                "Active records cannot retain deletion metadata."
            )


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    entity_type: str
    entity_id: str
    action: str
    actor: str
    occurred_at: datetime
    old_values: dict[str, Any]
    new_values: dict[str, Any]
    correlation_id: str
    reason: str | None = None


@dataclass(frozen=True)
class OperationResult:
    equipment: Equipment
    event_id: str


class EquipmentRepository:
    """
    In-memory repository illustrating transaction boundaries.

    The lock makes each public mutation atomic within this process.
    Production systems should use database transactions, row-level locking
    or conditional UPDATE statements, and durable audit tables.
    """

    def __init__(self) -> None:
        self._records: dict[str, Equipment] = {}
        self._asset_tags: dict[str, str] = {}
        self._audit: list[AuditEvent] = []
        self._idempotency: dict[str, OperationResult] = {}
        self._lock = RLock()

    @staticmethod
    def _snapshot(record: Equipment) -> dict[str, Any]:
        result = asdict(record)
        result["status"] = record.status.value
        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
        return result

    @staticmethod
    def _require_actor(actor: str) -> None:
        if not actor or not actor.strip():
            raise ValidationError("An authenticated actor is required.")

    @staticmethod
    def _require_reason(reason: str) -> None:
        if not reason or not reason.strip():
            raise ValidationError("A reason is required for this operation.")

    def _record_event(
        self,
        record: Equipment,
        action: str,
        actor: str,
        old_values: dict[str, Any],
        new_values: dict[str, Any],
        correlation_id: str,
        reason: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid4()),
            entity_type="equipment",
            entity_id=record.equipment_id,
            action=action,
            actor=actor,
            occurred_at=utc_now(),
            old_values=old_values,
            new_values=new_values,
            correlation_id=correlation_id,
            reason=reason,
        )
        self._audit.append(event)
        return event

    def create(
        self,
        asset_tag: str,
        name: str,
        actor: str,
        correlation_id: str | None = None,
    ) -> OperationResult:
        self._require_actor(actor)
        asset_tag = asset_tag.strip().upper()
        name = name.strip()

        if not asset_tag or not name:
            raise ValidationError("Asset tag and name are required.")

        with self._lock:
            if asset_tag in self._asset_tags:
                raise ValidationError(f"Asset tag {asset_tag} already exists.")

            record = Equipment(
                equipment_id=str(uuid4()),
                asset_tag=asset_tag,
                name=name,
                created_by=actor,
                updated_by=actor,
            )
            record.validate()
            snapshot = self._snapshot(record)

            # Store the entity and audit event together while holding the lock.
            self._records[record.equipment_id] = record
            self._asset_tags[asset_tag] = record.equipment_id
            event = self._record_event(
                record,
                "created",
                actor,
                {},
                snapshot,
                correlation_id or str(uuid4()),
            )
            return OperationResult(record, event.event_id)

    def get(
        self,
        equipment_id: str,
        include_deleted: bool = False,
    ) -> Equipment:
        with self._lock:
            record = self._records.get(equipment_id)
            if record is None or (record.is_deleted and not include_deleted):
                raise NotFoundError("Equipment was not found.")
            return record

    def list_active(self) -> list[Equipment]:
        with self._lock:
            return sorted(
                (
                    record
                    for record in self._records.values()
                    if not record.is_deleted
                ),
                key=lambda item: item.asset_tag,
            )

    def list_with_deleted(self) -> list[Equipment]:
        with self._lock:
            return sorted(
                self._records.values(),
                key=lambda item: item.asset_tag,
            )

    def _prepare_mutation(
        self,
        equipment_id: str,
        expected_version: int,
        actor: str,
        allow_deleted: bool = False,
    ) -> Equipment:
        self._require_actor(actor)
        record = self._records.get(equipment_id)

        if record is None or (record.is_deleted and not allow_deleted):
            raise NotFoundError("Equipment was not found.")

        if record.version != expected_version:
            raise ConcurrencyError(
                f"Expected version {expected_version}; "
                f"current version is {record.version}."
            )
        return record

    def _finish_mutation(
        self,
        record: Equipment,
        actor: str,
        old_values: dict[str, Any],
        action: str,
        correlation_id: str | None,
        reason: str | None = None,
    ) -> OperationResult:
        record.version += 1
        record.updated_at = utc_now()
        record.updated_by = actor
        record.validate()

        event = self._record_event(
            record,
            action,
            actor,
            old_values,
            self._snapshot(record),
            correlation_id or str(uuid4()),
            reason,
        )
        return OperationResult(record, event.event_id)

    def transition(
        self,
        equipment_id: str,
        target: EquipmentStatus,
        expected_version: int,
        actor: str,
        reason: str,
        correlation_id: str | None = None,
    ) -> OperationResult:
        self._require_reason(reason)

        with self._lock:
            record = self._prepare_mutation(
                equipment_id, expected_version, actor
            )
            if target not in ALLOWED_TRANSITIONS[record.status]:
                raise InvalidTransitionError(
                    f"Cannot transition from {record.status.value} "
                    f"to {target.value}."
                )

            old_values = {"status": record.status.value}
            record.status = target
            return self._finish_mutation(
                record,
                actor,
                old_values,
                "status_changed",
                correlation_id,
                reason,
            )

    def soft_delete(
        self,
        equipment_id: str,
        expected_version: int,
        actor: str,
        reason: str,
        operation_key: str,
    ) -> OperationResult:
        self._require_reason(reason)
        self._require_actor(actor)

        with self._lock:
            existing = self._idempotency.get(operation_key)
            if existing is not None:
                if (
                    existing.equipment.equipment_id != equipment_id
                    or existing.equipment.deleted_by != actor
                ):
                    raise DuplicateOperationError(
                        "Idempotency key was used for another operation."
                    )
                return existing

            record = self._prepare_mutation(
                equipment_id, expected_version, actor
            )
            old_values = {
                "is_deleted": record.is_deleted,
                "deleted_at": None,
                "deleted_by": None,
            }

            record.is_deleted = True
            record.deleted_at = utc_now()
            record.deleted_by = actor
            result = self._finish_mutation(
                record,
                actor,
                old_values,
                "soft_deleted",
                operation_key,
                reason,
            )
            self._idempotency[operation_key] = result
            return result

    def restore(
        self,
        equipment_id: str,
        expected_version: int,
        actor: str,
        reason: str,
        correlation_id: str | None = None,
    ) -> OperationResult:
        self._require_reason(reason)

        with self._lock:
            record = self._prepare_mutation(
                equipment_id,
                expected_version,
                actor,
                allow_deleted=True,
            )
            if not record.is_deleted:
                raise InvalidTransitionError("Equipment is not deleted.")

            old_values = {
                "is_deleted": True,
                "deleted_at": record.deleted_at.isoformat(),
                "deleted_by": record.deleted_by,
            }
            record.is_deleted = False
            record.deleted_at = None
            record.deleted_by = None
            return self._finish_mutation(
                record,
                actor,
                old_values,
                "restored",
                correlation_id,
                reason,
            )

    def rename(
        self,
        equipment_id: str,
        new_name: str,
        expected_version: int,
        actor: str,
        reason: str,
    ) -> OperationResult:
        new_name = new_name.strip()
        if not new_name:
            raise ValidationError("Equipment name cannot be empty.")
        self._require_reason(reason)

        with self._lock:
            record = self._prepare_mutation(
                equipment_id, expected_version, actor
            )
            if record.name == new_name:
                raise ValidationError("New name matches the existing name.")

            old_values = {"name": record.name}
            record.name = new_name
            return self._finish_mutation(
                record, actor, old_values, "renamed", None, reason
            )

    def audit_history(self, equipment_id: str) -> list[AuditEvent]:
        with self._lock:
            if equipment_id not in self._records:
                raise NotFoundError("Equipment was not found.")
            return [
                event
                for event in self._audit
                if event.entity_id == equipment_id
            ]

    def export_audit(self, destination: Path) -> None:
        """Write an audit export without exposing internal mutable objects."""
        with self._lock:
            payload = [
                {
                    **asdict(event),
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in self._audit
            ]
        destination.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )

    def verify_audit_coverage(self) -> list[str]:
        """Find records without creation events or with invalid event order."""
        issues: list[str] = []
        with self._lock:
            events_by_entity: dict[str, list[AuditEvent]] = {}
            for event in self._audit:
                events_by_entity.setdefault(event.entity_id, []).append(event)

            for equipment_id in self._records:
                events = events_by_entity.get(equipment_id, [])
                if not events or events[0].action != "created":
                    issues.append(
                        f"{equipment_id}: missing initial creation event"
                    )
                if any(
                    later.occurred_at < earlier.occurred_at
                    for earlier, later in zip(events, events[1:])
                ):
                    issues.append(
                        f"{equipment_id}: audit timestamps are out of order"
                    )
        return issues


class RepositoryPatternTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = EquipmentRepository()
        self.created = self.repository.create(
            "eq-100",
            "Hydraulic pump",
            "inventory-admin",
        )
        self.equipment = self.created.equipment

    def test_status_transition_records_history(self) -> None:
        result = self.repository.transition(
            self.equipment.equipment_id,
            EquipmentStatus.APPROVED,
            self.equipment.version,
            "maintenance-manager",
            "Purchase specification verified.",
        )
        self.assertEqual(result.equipment.status, EquipmentStatus.APPROVED)
        history = self.repository.audit_history(self.equipment.equipment_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1].action, "status_changed")

    def test_invalid_transition_does_not_change_record(self) -> None:
        with self.assertRaises(InvalidTransitionError):
            self.repository.transition(
                self.equipment.equipment_id,
                EquipmentStatus.RETIRED,
                self.equipment.version,
                "maintenance-manager",
                "Incorrect attempted transition.",
            )
        self.assertEqual(
            self.equipment.status, EquipmentStatus.REQUESTED
        )
        self.assertEqual(len(self.repository.audit_history(
            self.equipment.equipment_id
        )), 1)

    def test_soft_delete_hides_but_preserves_record(self) -> None:
        result = self.repository.soft_delete(
            self.equipment.equipment_id,
            self.equipment.version,
            "inventory-admin",
            "Duplicate asset registration.",
            "delete-eq-100",
        )
        with self.assertRaises(NotFoundError):
            self.repository.get(self.equipment.equipment_id)

        retained = self.repository.get(
            self.equipment.equipment_id, include_deleted=True
        )
        self.assertTrue(retained.is_deleted)
        self.assertEqual(result.equipment.version, 2)

    def test_restore_retains_history(self) -> None:
        deleted = self.repository.soft_delete(
            self.equipment.equipment_id,
            1,
            "inventory-admin",
            "Temporary archival.",
            "delete-1",
        )
        restored = self.repository.restore(
            self.equipment.equipment_id,
            deleted.equipment.version,
            "inventory-admin",
            "Record confirmed as legitimate.",
        )
        self.assertFalse(restored.equipment.is_deleted)
        self.assertEqual(len(self.repository.audit_history(
            self.equipment.equipment_id
        )), 3)

    def test_stale_version_is_rejected(self) -> None:
        self.repository.rename(
            self.equipment.equipment_id,
            "Hydraulic pump model B",
            1,
            "inventory-admin",
            "Corrected equipment description.",
        )
        with self.assertRaises(ConcurrencyError):
            self.repository.rename(
                self.equipment.equipment_id,
                "Hydraulic pump model C",
                1,
                "inventory-admin",
                "Attempt with stale version.",
            )

    def test_duplicate_asset_tag_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.repository.create(
                "EQ-100", "Second pump", "inventory-admin"
            )

    def test_idempotent_delete(self) -> None:
        first = self.repository.soft_delete(
            self.equipment.equipment_id,
            1,
            "inventory-admin",
            "Asset transferred out.",
            "transfer-100",
        )
        second = self.repository.soft_delete(
            self.equipment.equipment_id,
            1,
            "inventory-admin",
            "Asset transferred out.",
            "transfer-100",
        )
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(len(self.repository.audit_history(
            self.equipment.equipment_id
        )), 2)

    def test_audit_export_is_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit.json"
            self.repository.export_audit(output)
            events = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(events[0]["action"], "created")


def run_demonstration() -> None:
    repository = EquipmentRepository()

    print("Equipment lifecycle and database design patterns")
    created = repository.create(
        "pump-204",
        "Cooling water pump",
        "asset-clerk",
    )
    equipment = created.equipment
    print(f"Created {equipment.asset_tag}: {equipment.status.value}")

    approved = repository.transition(
        equipment.equipment_id,
        EquipmentStatus.APPROVED,
        equipment.version,
        "maintenance-supervisor",
        "Technical documentation verified.",
    )
    print(f"Status changed to {approved.equipment.status.value}")

    active_records = repository.list_active()
    print(f"Active records: {len(active_records)}")

    deleted = repository.soft_delete(
        equipment.equipment_id,
        approved.equipment.version,
        "records-officer",
        "Asset was entered against the wrong department.",
        "archive-pump-204",
    )
    print(f"Soft-deleted at {deleted.equipment.deleted_at.isoformat()}")
    print(f"Visible active records: {len(repository.list_active())}")

    restored = repository.restore(
        equipment.equipment_id,
        deleted.equipment.version,
        "records-officer",
        "Department verified the original asset record.",
    )
    print(f"Restored record version: {restored.equipment.version}")

    for event in repository.audit_history(equipment.equipment_id):
        print(
            f"{event.action}: actor={event.actor}, "
            f"reason={event.reason or '-'}, "
            f"event_id={event.event_id}"
        )

    print("Audit integrity issues:", repository.verify_audit_coverage())


if __name__ == "__main__":
    run_demonstration()
    print("\nRunning tests...")
    unittest.main(argv=["database_patterns.py"], exit=False, verbosity=2)
