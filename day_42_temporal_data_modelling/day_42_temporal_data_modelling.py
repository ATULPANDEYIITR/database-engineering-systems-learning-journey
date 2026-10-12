#!/usr/bin/env python3
"""Temporal data modeling: historical records, effective dates, and event time.

Uses only the Python standard library. Run with Python 3.10 or later.
"""

from __future__ import annotations

import json
import sqlite3
import unittest
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import uuid4


UTC = timezone.utc


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp and reject timestamps without a timezone."""
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("A timestamp must include an explicit timezone.")
    return parsed.astimezone(UTC)


def iso_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Cannot serialize a naive datetime.")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class SalaryVersion:
    employee_id: str
    salary: int
    valid_from: datetime
    valid_to: datetime | None
    recorded_at: datetime
    version_id: str

    def __post_init__(self) -> None:
        if not self.employee_id.strip():
            raise ValueError("Employee identifier cannot be empty.")
        if self.salary <= 0:
            raise ValueError("Salary must be positive.")
        for timestamp in (self.valid_from, self.recorded_at):
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("Temporal fields must be timezone-aware.")
        if self.valid_to is not None:
            if self.valid_to.tzinfo is None or self.valid_to.utcoffset() is None:
                raise ValueError("valid_to must be timezone-aware.")
            if self.valid_to <= self.valid_from:
                raise ValueError("valid_to must be later than valid_from.")

    def is_effective_at(self, instant: datetime) -> bool:
        instant = instant.astimezone(UTC)
        return (
            self.valid_from.astimezone(UTC) <= instant
            and (
                self.valid_to is None
                or instant < self.valid_to.astimezone(UTC)
            )
        )


class TemporalSalaryLedger:
    """Retains immutable versions and distinguishes business time from record time.

    Valid time answers when a salary applies in the business domain.
    Record time answers when the ledger learned or recorded that version.
    """

    def __init__(self) -> None:
        self._versions: list[SalaryVersion] = []

    @property
    def versions(self) -> tuple[SalaryVersion, ...]:
        return tuple(self._versions)

    def add(
        self,
        employee_id: str,
        salary: int,
        valid_from: datetime,
        recorded_at: datetime,
        valid_to: datetime | None = None,
    ) -> SalaryVersion:
        candidate = SalaryVersion(
            employee_id=employee_id,
            salary=salary,
            valid_from=valid_from,
            valid_to=valid_to,
            recorded_at=recorded_at,
            version_id=str(uuid4()),
        )
        for existing in self._versions:
            if existing.employee_id != employee_id:
                continue
            # Half-open intervals [start, end) allow one salary to end
            # exactly when its replacement begins.
            existing_end = existing.valid_to or datetime.max.replace(tzinfo=UTC)
            candidate_end = candidate.valid_to or datetime.max.replace(tzinfo=UTC)
            overlaps = (
                existing.valid_from < candidate_end
                and candidate.valid_from < existing_end
            )
            if overlaps:
                raise ValueError(
                    f"Overlapping effective periods for employee {employee_id}."
                )
        self._versions.append(candidate)
        self._versions.sort(
            key=lambda item: (item.employee_id, item.valid_from, item.recorded_at)
        )
        return candidate

    def salary_at(
        self, employee_id: str, business_time: datetime
    ) -> SalaryVersion | None:
        matches = [
            version
            for version in self._versions
            if version.employee_id == employee_id
            and version.is_effective_at(business_time)
        ]
        if len(matches) > 1:
            raise RuntimeError("Ledger integrity violation: overlapping versions.")
        return matches[0] if matches else None

    def history(self, employee_id: str) -> list[SalaryVersion]:
        return [
            version for version in self._versions
            if version.employee_id == employee_id
        ]

    def payroll_as_known_at(
        self,
        employee_id: str,
        business_time: datetime,
        knowledge_time: datetime,
    ) -> SalaryVersion | None:
        """Return the version effective at business_time and known by knowledge_time."""
        knowledge_time = knowledge_time.astimezone(UTC)
        candidates = [
            version
            for version in self.history(employee_id)
            if version.is_effective_at(business_time)
            and version.recorded_at.astimezone(UTC) <= knowledge_time
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda version: version.recorded_at)


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    entity_id: str
    event_time: datetime
    received_at: datetime
    payload: dict[str, object]

    @classmethod
    def create(
        cls,
        event_type: str,
        entity_id: str,
        event_time: datetime,
        received_at: datetime,
        payload: dict[str, object],
    ) -> Event:
        if not event_type.strip() or not entity_id.strip():
            raise ValueError("Event type and entity identifier are required.")
        if event_time.tzinfo is None or received_at.tzinfo is None:
            raise ValueError("Event timestamps must be timezone-aware.")
        return cls(
            event_id=str(uuid4()),
            event_type=event_type,
            entity_id=entity_id,
            event_time=event_time.astimezone(UTC),
            received_at=received_at.astimezone(UTC),
            payload=dict(payload),
        )


class EventTimeWindow:
    """Processes events by event time while exposing late arrivals."""

    def __init__(self, allowed_lateness: timedelta) -> None:
        if allowed_lateness < timedelta(0):
            raise ValueError("Allowed lateness cannot be negative.")
        self.allowed_lateness = allowed_lateness
        self._events: dict[str, Event] = {}
        self._max_event_time: datetime | None = None

    def ingest(self, event: Event) -> str:
        if event.event_id in self._events:
            return "duplicate"

        is_late = (
            self._max_event_time is not None
            and event.event_time < self._max_event_time - self.allowed_lateness
        )
        self._events[event.event_id] = event
        if (
            self._max_event_time is None
            or event.event_time > self._max_event_time
        ):
            self._max_event_time = event.event_time
        return "late" if is_late else "accepted"

    def events_in_window(
        self, start: datetime, end: datetime
    ) -> list[Event]:
        if end <= start:
            raise ValueError("Window end must be later than its start.")
        return sorted(
            (
                event for event in self._events.values()
                if start.astimezone(UTC) <= event.event_time < end.astimezone(UTC)
            ),
            key=lambda event: (event.event_time, event.event_id),
        )

    def aggregate_counts(
        self, start: datetime, end: datetime
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in self.events_in_window(start, end):
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return counts


def demonstrate_temporal_ledger() -> None:
    print("\n=== Effective-dated salary history ===")
    ledger = TemporalSalaryLedger()

    january = parse_timestamp("2026-01-01T00:00:00Z")
    april = parse_timestamp("2026-04-01T00:00:00Z")
    july = parse_timestamp("2026-07-01T00:00:00Z")
    august_recording = parse_timestamp("2026-08-10T09:00:00Z")

    ledger.add(
        "EMP-104", 72000, january, january,
        valid_to=april,
    )
    ledger.add(
        "EMP-104", 78000, april, april,
        valid_to=july,
    )
    ledger.add(
        "EMP-104", 84000, july, august_recording,
    )

    for month in ("2026-02-15T12:00:00Z", "2026-05-15T12:00:00Z",
                  "2026-09-15T12:00:00Z"):
        instant = parse_timestamp(month)
        version = ledger.salary_at("EMP-104", instant)
        print(
            iso_timestamp(instant),
            version.salary if version else "no effective salary",
        )

    try:
        ledger.add(
            "EMP-104",
            90000,
            parse_timestamp("2026-06-01T00:00:00Z"),
            parse_timestamp("2026-09-01T00:00:00Z"),
        )
    except ValueError as error:
        print("Overlap rejected:", error)

    historical_business_time = parse_timestamp("2026-08-01T00:00:00Z")
    before_correction_was_recorded = parse_timestamp("2026-08-01T00:00:00Z")
    version = ledger.payroll_as_known_at(
        "EMP-104",
        historical_business_time,
        before_correction_was_recorded,
    )
    print(
        "Salary known on August 1:",
        version.salary if version else "unknown",
    )


def demonstrate_event_time() -> None:
    print("\n=== Event-time processing ===")
    processor = EventTimeWindow(allowed_lateness=timedelta(minutes=5))

    received = parse_timestamp("2026-10-12T10:15:00Z")
    events = [
        Event.create(
            "order.created", "ORD-201",
            parse_timestamp("2026-10-12T10:10:00Z"), received,
            {"amount": 1250},
        ),
        Event.create(
            "order.created", "ORD-202",
            parse_timestamp("2026-10-12T10:12:00Z"),
            parse_timestamp("2026-10-12T10:15:03Z"),
            {"amount": 2800},
        ),
        Event.create(
            "order.cancelled", "ORD-201",
            parse_timestamp("2026-10-12T10:02:00Z"),
            parse_timestamp("2026-10-12T10:15:05Z"),
            {"reason": "payment_timeout"},
        ),
    ]

    for event in events:
        print(event.event_type, iso_timestamp(event.event_time),
              processor.ingest(event))

    start = parse_timestamp("2026-10-12T10:00:00Z")
    end = parse_timestamp("2026-10-12T10:15:00Z")
    print("Counts by event time:", processor.aggregate_counts(start, end))

    serialized = json.dumps(
        [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "entity_id": event.entity_id,
                "event_time": iso_timestamp(event.event_time),
                "received_at": iso_timestamp(event.received_at),
                "payload": event.payload,
            }
            for event in processor.events_in_window(start, end)
        ],
        indent=2,
    )
    print(serialized)


def demonstrate_sqlite_history() -> None:
    print("\n=== Relational temporal history ===")
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE employee (
                employee_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL
            );

            CREATE TABLE salary_history (
                version_id INTEGER PRIMARY KEY,
                employee_id TEXT NOT NULL REFERENCES employee(employee_id),
                salary INTEGER NOT NULL CHECK (salary > 0),
                valid_from TEXT NOT NULL,
                valid_to TEXT,
                recorded_at TEXT NOT NULL,
                CHECK (valid_to IS NULL OR valid_to > valid_from),
                UNIQUE (employee_id, valid_from)
            );

            CREATE INDEX salary_history_lookup
                ON salary_history(employee_id, valid_from, valid_to);

            CREATE TRIGGER reject_overlapping_salary
            BEFORE INSERT ON salary_history
            BEGIN
                SELECT CASE WHEN EXISTS (
                    SELECT 1
                    FROM salary_history AS old
                    WHERE old.employee_id = NEW.employee_id
                      AND (old.valid_to IS NULL OR old.valid_to > NEW.valid_from)
                      AND (NEW.valid_to IS NULL OR NEW.valid_to > old.valid_from)
                )
                THEN RAISE(ABORT, 'overlapping effective salary period')
                END;
            END;
            """
        )
        with connection:
            connection.execute(
                "INSERT INTO employee VALUES (?, ?)",
                ("EMP-104", "Riya Sharma"),
            )
            connection.executemany(
                """
                INSERT INTO salary_history
                    (employee_id, salary, valid_from, valid_to, recorded_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        "EMP-104", 72000,
                        "2026-01-01T00:00:00Z",
                        "2026-04-01T00:00:00Z",
                        "2026-01-01T00:00:00Z",
                    ),
                    (
                        "EMP-104", 78000,
                        "2026-04-01T00:00:00Z",
                        None,
                        "2026-04-01T00:00:00Z",
                    ),
                ],
            )

        business_time = "2026-05-15T12:00:00Z"
        row = connection.execute(
            """
            SELECT salary, valid_from, valid_to, recorded_at
            FROM salary_history
            WHERE employee_id = ?
              AND valid_from <= ?
              AND (valid_to IS NULL OR ? < valid_to)
            """,
            ("EMP-104", business_time, business_time),
        ).fetchone()
        print("SQL as-of query:", dict(row) if row else None)

        try:
            with connection:
                connection.execute(
                    """
                    INSERT INTO salary_history
                        (employee_id, salary, valid_from, valid_to, recorded_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "EMP-104", 85000,
                        "2026-03-01T00:00:00Z",
                        "2026-05-01T00:00:00Z",
                        "2026-05-10T00:00:00Z",
                    ),
                )
        except sqlite3.IntegrityError as error:
            print("Database rejected overlap:", error)
    finally:
        connection.close()


class TemporalModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = TemporalSalaryLedger()
        self.start = parse_timestamp("2026-01-01T00:00:00Z")
        self.middle = parse_timestamp("2026-04-01T00:00:00Z")
        self.recorded = parse_timestamp("2026-04-03T00:00:00Z")
        self.ledger.add(
            "EMP-1", 50000, self.start, self.start, self.middle
        )
        self.ledger.add(
            "EMP-1", 60000, self.middle, self.recorded
        )

    def test_half_open_effective_boundary(self) -> None:
        result = self.ledger.salary_at("EMP-1", self.middle)
        self.assertIsNotNone(result)
        self.assertEqual(result.salary, 60000)

    def test_no_salary_before_first_effective_date(self) -> None:
        before = self.start - timedelta(seconds=1)
        self.assertIsNone(self.ledger.salary_at("EMP-1", before))

    def test_overlap_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.ledger.add(
                "EMP-1",
                70000,
                self.middle - timedelta(days=1),
                self.recorded,
            )

    def test_naive_timestamp_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_timestamp("2026-01-01T00:00:00")

    def test_late_event_is_retained(self) -> None:
        processor = EventTimeWindow(timedelta(minutes=2))
        first = Event.create(
            "payment.received", "PAY-1",
            parse_timestamp("2026-10-12T10:10:00Z"),
            parse_timestamp("2026-10-12T10:11:00Z"), {},
        )
        late = Event.create(
            "payment.received", "PAY-2",
            parse_timestamp("2026-10-12T10:01:00Z"),
            parse_timestamp("2026-10-12T10:12:00Z"), {},
        )
        self.assertEqual(processor.ingest(first), "accepted")
        self.assertEqual(processor.ingest(late), "late")
        self.assertEqual(len(processor.events_in_window(
            parse_timestamp("2026-10-12T10:00:00Z"),
            parse_timestamp("2026-10-12T10:15:00Z"),
        )), 2)


def main() -> None:
    demonstrate_temporal_ledger()
    demonstrate_event_time()
    demonstrate_sqlite_history()
    print("\n=== Automated temporal-model tests ===")
    unittest.main(argv=["temporal_model.py"], exit=False, verbosity=2)


if __name__ == "__main__":
    main()
