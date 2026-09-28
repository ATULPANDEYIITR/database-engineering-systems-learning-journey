"""
Date and Time Analytics: Intervals, Timestamps, Time Zones, and Date Arithmetic
===============================================================================

A self-contained study program covering:

1. Dates, times, and datetime values
2. Timestamps and Unix/POSIX time
3. Timedeltas and intervals
4. Date arithmetic
5. Calendar arithmetic
6. Comparisons and ordering
7. Parsing and formatting
8. Time zones and UTC
9. Daylight-saving-time transitions
10. Ambiguous and nonexistent local times
11. Fixed offsets versus geographic time zones
12. Business-day calculations
13. Interval overlap, merging, and containment
14. Recurring schedules
15. Event analytics
16. Duration and latency analytics
17. Validation and error handling
18. Precision and performance considerations
19. Testing and production-oriented design
20. Advanced timezone-aware scheduling examples

The script intentionally uses the Python standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    time,
    timedelta,
    timezone,
)
from decimal import Decimal
from statistics import mean, median
from typing import Iterable, Optional, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import calendar
import math
import time as time_module


# ============================================================================
# 1. FUNDAMENTAL TYPES
# ============================================================================

def fundamentals_demo() -> None:
    print("\n" + "=" * 80)
    print("1. FUNDAMENTAL DATE AND TIME TYPES")
    print("=" * 80)

    calendar_date = date(2026, 9, 28)
    clock_time = time(11, 56, 0)
    naive_datetime = datetime(2026, 9, 28, 11, 56, 0)

    utc_datetime = datetime(
        2026,
        9,
        28,
        6,
        26,
        tzinfo=timezone.utc,
    )

    print("date:", calendar_date)
    print("time:", clock_time)
    print("naive datetime:", naive_datetime)
    print("UTC-aware datetime:", utc_datetime)

    # A naive datetime has no timezone information.
    print("naive tzinfo:", naive_datetime.tzinfo)

    # An aware datetime has a timezone or fixed UTC offset.
    print("aware tzinfo:", utc_datetime.tzinfo)


# ============================================================================
# 2. TIMESTAMPS
# ============================================================================

def timestamp_demo() -> None:
    print("\n" + "=" * 80)
    print("2. TIMESTAMPS")
    print("=" * 80)

    instant = datetime(1970, 1, 1, tzinfo=timezone.utc)
    print("Unix epoch:", instant)

    sample = datetime(2026, 9, 28, 6, 26, tzinfo=timezone.utc)
    timestamp = sample.timestamp()

    print("UTC datetime:", sample)
    print("POSIX timestamp:", timestamp)

    restored = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    print("Restored datetime:", restored)

    # Timestamps represent an instant on the UTC timeline.
    # Local date/time representations depend on timezone rules.
    print("Round-trip preserved:", restored == sample)


# ============================================================================
# 3. TIME DELTAS AND DURATION
# ============================================================================

def timedelta_demo() -> None:
    print("\n" + "=" * 80)
    print("3. TIMEDelta AND DURATION ARITHMETIC")
    print("=" * 80)

    start = datetime(2026, 9, 28, 9, 30)
    duration = timedelta(hours=2, minutes=45, seconds=30)
    end = start + duration

    print("Start:", start)
    print("Duration:", duration)
    print("End:", end)

    print("Difference:", end - start)

    # timedelta stores elapsed duration using days, seconds, and microseconds.
    print("Days:", duration.days)
    print("Seconds:", duration.seconds)
    print("Microseconds:", duration.microseconds)

    # Negative durations are valid.
    reverse = start - end
    print("Negative duration:", reverse)


# ============================================================================
# 4. DATE ARITHMETIC
# ============================================================================

def date_arithmetic_demo() -> None:
    print("\n" + "=" * 80)
    print("4. DATE ARITHMETIC")
    print("=" * 80)

    original = date(2026, 9, 28)

    print("Original:", original)
    print("+ 7 days:", original + timedelta(days=7))
    print("- 30 days:", original - timedelta(days=30))

    next_week = original + timedelta(weeks=1)
    print("+ 1 week:", next_week)

    # Subtracting dates produces a timedelta.
    another = date(2026, 10, 10)
    difference = another - original

    print("Difference:", difference)
    print("Difference in days:", difference.days)


# ============================================================================
# 5. MONTH/YEAR ARITHMETIC
# ============================================================================

def add_months(value: date, months: int) -> date:
    """
    Add calendar months while clamping the day to the destination month.

    Example:
        January 31 + 1 month -> February 28/29
    """
    zero_based_month = value.month - 1 + months
    target_year = value.year + zero_based_month // 12
    target_month = zero_based_month % 12 + 1

    last_day = calendar.monthrange(target_year, target_month)[1]
    target_day = min(value.day, last_day)

    return date(target_year, target_month, target_day)


def month_arithmetic_demo() -> None:
    print("\n" + "=" * 80)
    print("5. CALENDAR MONTH ARITHMETIC")
    print("=" * 80)

    examples = [
        date(2026, 1, 31),
        date(2026, 3, 31),
        date(2026, 12, 31),
    ]

    for value in examples:
        print(
            value,
            "-> +1 month ->",
            add_months(value, 1),
            "-> -1 month ->",
            add_months(value, -1),
        )

    leap_day = date(2024, 2, 29)
    print("Leap day:", leap_day)
    print("+ 12 months:", add_months(leap_day, 12))

    # Important distinction:
    # timedelta(days=30) means exactly 30 elapsed calendar days.
    # add_months(..., 1) means one calendar month with day clamping.


# ============================================================================
# 6. DATE DIFFERENCE AND CALENDAR METRICS
# ============================================================================

def calendar_metrics(value: date) -> dict[str, int]:
    iso_year, iso_week, iso_weekday = value.isocalendar()

    return {
        "year": value.year,
        "month": value.month,
        "day": value.day,
        "day_of_year": value.timetuple().tm_yday,
        "weekday_zero_based": value.weekday(),
        "iso_weekday": iso_weekday,
        "iso_week": iso_week,
        "iso_year": iso_year,
        "days_in_month": calendar.monthrange(value.year, value.month)[1],
    }


def calendar_metrics_demo() -> None:
    print("\n" + "=" * 80)
    print("6. CALENDAR METRICS")
    print("=" * 80)

    value = date(2026, 9, 28)

    for key, metric in calendar_metrics(value).items():
        print(f"{key}: {metric}")


# ============================================================================
# 7. PARSING AND FORMATTING
# ============================================================================

def parsing_and_formatting_demo() -> None:
    print("\n" + "=" * 80)
    print("7. PARSING AND FORMATTING")
    print("=" * 80)

    text_value = "2026-09-28 11:56:30"
    parsed = datetime.strptime(text_value, "%Y-%m-%d %H:%M:%S")

    print("Parsed:", parsed)

    print("ISO:", parsed.isoformat())
    print("Date only:", parsed.strftime("%Y-%m-%d"))
    print("Human format:", parsed.strftime("%d %B %Y, %I:%M %p"))

    # ISO 8601 is particularly useful for machine-readable timestamps.
    iso_text = "2026-09-28T11:56:30+05:30"
    aware = datetime.fromisoformat(iso_text)

    print("ISO input:", iso_text)
    print("Parsed aware value:", aware)
    print("UTC equivalent:", aware.astimezone(timezone.utc))


# ============================================================================
# 8. TIME ZONES
# ============================================================================

def timezone_demo() -> None:
    print("\n" + "=" * 80)
    print("8. TIME ZONES")
    print("=" * 80)

    utc = ZoneInfo("UTC")
    kolkata = ZoneInfo("Asia/Kolkata")
    new_york = ZoneInfo("America/New_York")
    london = ZoneInfo("Europe/London")

    instant = datetime(2026, 9, 28, 12, 0, tzinfo=utc)

    for name, zone in [
        ("UTC", utc),
        ("Asia/Kolkata", kolkata),
        ("America/New_York", new_york),
        ("Europe/London", london),
    ]:
        localized = instant.astimezone(zone)
        print(
            f"{name:20} "
            f"{localized.isoformat()} "
            f"offset={localized.utcoffset()}"
        )

    # All values above represent the same instant.
    print(
        "Same instant:",
        instant.astimezone(kolkata)
        == instant.astimezone(new_york)
    )


# ============================================================================
# 9. UTC-FIRST DESIGN
# ============================================================================

def utc_first_demo() -> None:
    print("\n" + "=" * 80)
    print("9. UTC-FIRST DESIGN")
    print("=" * 80)

    user_zone = ZoneInfo("Asia/Kolkata")

    local_event = datetime(
        2026,
        9,
        28,
        18,
        30,
        tzinfo=user_zone,
    )

    stored_utc = local_event.astimezone(timezone.utc)

    print("User entered:", local_event)
    print("Stored/transmitted UTC:", stored_utc)

    # Convert UTC back to the user's display timezone.
    displayed = stored_utc.astimezone(user_zone)
    print("Displayed again:", displayed)


# ============================================================================
# 10. FIXED OFFSET VERSUS GEOGRAPHIC TIMEZONE
# ============================================================================

def fixed_offset_demo() -> None:
    print("\n" + "=" * 80)
    print("10. FIXED OFFSET VS GEOGRAPHIC TIME ZONE")
    print("=" * 80)

    fixed_india_offset = timezone(timedelta(hours=5, minutes=30))
    geographic_india = ZoneInfo("Asia/Kolkata")

    value = datetime(
        2026,
        9,
        28,
        18,
        0,
    )

    fixed_value = value.replace(tzinfo=fixed_india_offset)
    geographic_value = value.replace(tzinfo=geographic_india)

    print("Fixed offset:", fixed_value)
    print("Geographic timezone:", geographic_value)
    print("Same offset now:", fixed_value.utcoffset() == geographic_value.utcoffset())

    # A geographic zone is backed by historical and future timezone rules.
    # A fixed offset means exactly that offset and nothing else.


# ============================================================================
# 11. DST AND LOCAL TIME TRANSITIONS
# ============================================================================

def dst_demo() -> None:
    print("\n" + "=" * 80)
    print("11. DAYLIGHT-SAVING-TIME TRANSITIONS")
    print("=" * 80)

    zone = ZoneInfo("America/New_York")

    before_fall_back = datetime(
        2026,
        11,
        1,
        1,
        30,
        tzinfo=zone,
        fold=0,
    )

    after_fall_back = datetime(
        2026,
        11,
        1,
        1,
        30,
        tzinfo=zone,
        fold=1,
    )

    print("First 01:30:", before_fall_back)
    print("Second 01:30:", after_fall_back)

    print(
        "First UTC:",
        before_fall_back.astimezone(timezone.utc),
    )
    print(
        "Second UTC:",
        after_fall_back.astimezone(timezone.utc),
    )

    # fold distinguishes repeated wall-clock times.
    print("fold values:", before_fall_back.fold, after_fall_back.fold)


# ============================================================================
# 12. TIMEZONE VALIDATION
# ============================================================================

def validate_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown IANA timezone: {name}") from exc


def timezone_validation_demo() -> None:
    print("\n" + "=" * 80)
    print("12. TIMEZONE VALIDATION")
    print("=" * 80)

    for name in ["Asia/Kolkata", "UTC", "Invalid/Zone"]:
        try:
            zone = validate_timezone(name)
            print(f"{name}: valid -> {zone}")
        except ValueError as exc:
            print(f"{name}: rejected -> {exc}")


# ============================================================================
# 13. INTERVAL DATA MODEL
# ============================================================================

@dataclass(frozen=True)
class Interval:
    """
    Half-open interval [start, end).

    start is included.
    end is excluded.

    This convention makes adjacent intervals easy to reason about:
        [09:00, 10:00) and [10:00, 11:00)
    do not overlap.
    """

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Intervals must use timezone-aware datetimes.")

        if self.end <= self.start:
            raise ValueError("Interval end must be after interval start.")

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def contains(self, instant: datetime) -> bool:
        return self.start <= instant < self.end

    def overlaps(self, other: "Interval") -> bool:
        return self.start < other.end and other.start < self.end

    def intersection(self, other: "Interval") -> Optional["Interval"]:
        if not self.overlaps(other):
            return None

        start = max(self.start, other.start)
        end = min(self.end, other.end)

        return Interval(start, end)

    def gap_to(self, other: "Interval") -> Optional[timedelta]:
        if self.overlaps(other):
            return timedelta(0)

        if self.end <= other.start:
            return other.start - self.end

        return self.start - other.end


def interval_demo() -> None:
    print("\n" + "=" * 80)
    print("13. INTERVAL ANALYTICS")
    print("=" * 80)

    zone = ZoneInfo("Asia/Kolkata")

    first = Interval(
        datetime(2026, 9, 28, 9, 0, tzinfo=zone),
        datetime(2026, 9, 28, 12, 0, tzinfo=zone),
    )

    second = Interval(
        datetime(2026, 9, 28, 11, 30, tzinfo=zone),
        datetime(2026, 9, 28, 14, 0, tzinfo=zone),
    )

    print("First duration:", first.duration)
    print("Second duration:", second.duration)
    print("Overlap:", first.overlaps(second))

    intersection = first.intersection(second)
    print("Intersection:", intersection)

    test_instant = datetime(2026, 9, 28, 10, 0, tzinfo=zone)
    print("Contains 10:00:", first.contains(test_instant))


# ============================================================================
# 14. MERGING INTERVALS
# ============================================================================

def merge_intervals(
    intervals: Sequence[Interval],
    merge_adjacent: bool = True,
) -> list[Interval]:
    """
    Merge overlapping intervals.

    If merge_adjacent is True:
        [09:00, 10:00) + [10:00, 11:00)
        becomes [09:00, 11:00).
    """
    if not intervals:
        return []

    ordered = sorted(intervals, key=lambda item: item.start)
    merged = [ordered[0]]

    for current in ordered[1:]:
        previous = merged[-1]

        touching = current.start == previous.end

        if previous.overlaps(current) or (
            merge_adjacent and touching
        ):
            merged[-1] = Interval(
                previous.start,
                max(previous.end, current.end),
            )
        else:
            merged.append(current)

    return merged


def interval_merge_demo() -> None:
    print("\n" + "=" * 80)
    print("14. MERGING INTERVALS")
    print("=" * 80)

    zone = ZoneInfo("Asia/Kolkata")

    raw = [
        Interval(
            datetime(2026, 9, 28, 9, 0, tzinfo=zone),
            datetime(2026, 9, 28, 10, 0, tzinfo=zone),
        ),
        Interval(
            datetime(2026, 9, 28, 9, 45, tzinfo=zone),
            datetime(2026, 9, 28, 11, 0, tzinfo=zone),
        ),
        Interval(
            datetime(2026, 9, 28, 11, 0, tzinfo=zone),
            datetime(2026, 9, 28, 12, 0, tzinfo=zone),
        ),
        Interval(
            datetime(2026, 9, 28, 14, 0, tzinfo=zone),
            datetime(2026, 9, 28, 15, 0, tzinfo=zone),
        ),
    ]

    print("Original:")
    for item in raw:
        print(" ", item)

    print("Merged:")
    for item in merge_intervals(raw):
        print(" ", item)


# ============================================================================
# 15. BUSINESS DAYS
# ============================================================================

def is_business_day(value: date) -> bool:
    return value.weekday() < 5


def add_business_days(value: date, number_of_days: int) -> date:
    if number_of_days == 0:
        return value

    direction = 1 if number_of_days > 0 else -1
    remaining = abs(number_of_days)
    current = value

    while remaining:
        current += timedelta(days=direction)
        if is_business_day(current):
            remaining -= 1

    return current


def business_day_demo() -> None:
    print("\n" + "=" * 80)
    print("15. BUSINESS-DAY ARITHMETIC")
    print("=" * 80)

    friday = date(2026, 10, 2)

    print("Starting date:", friday)
    print("+ 1 business day:", add_business_days(friday, 1))
    print("+ 3 business days:", add_business_days(friday, 3))
    print("- 1 business day:", add_business_days(friday, -1))

    # Weekends are skipped.
    for offset in range(7):
        current = friday + timedelta(days=offset)
        print(current, "business" if is_business_day(current) else "weekend")


# ============================================================================
# 16. BUSINESS DAYS WITH HOLIDAYS
# ============================================================================

def add_business_days_with_holidays(
    value: date,
    number_of_days: int,
    holidays: set[date],
) -> date:
    if number_of_days == 0:
        return value

    direction = 1 if number_of_days > 0 else -1
    remaining = abs(number_of_days)
    current = value

    while remaining:
        current += timedelta(days=direction)

        if (
            is_business_day(current)
            and current not in holidays
        ):
            remaining -= 1

    return current


def holiday_demo() -> None:
    print("\n" + "=" * 80)
    print("16. BUSINESS DAYS WITH HOLIDAYS")
    print("=" * 80)

    holidays = {
        date(2026, 10, 2),
        date(2026, 10, 5),
    }

    start = date(2026, 10, 1)

    print(
        "Start:",
        start,
        "next business date after two valid business days:",
        add_business_days_with_holidays(start, 2, holidays),
    )


# ============================================================================
# 17. EVENT RECORDS
# ============================================================================

@dataclass(frozen=True)
class Event:
    event_id: str
    name: str
    started_at: datetime
    ended_at: datetime

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware.")

        if self.ended_at.tzinfo is None:
            raise ValueError("ended_at must be timezone-aware.")

        if self.ended_at < self.started_at:
            raise ValueError("ended_at cannot precede started_at.")

    @property
    def duration_seconds(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()


def event_analytics(events: Sequence[Event]) -> dict[str, float]:
    durations = [event.duration_seconds for event in events]

    if not durations:
        return {
            "count": 0,
            "total_seconds": 0.0,
            "mean_seconds": 0.0,
            "median_seconds": 0.0,
            "min_seconds": 0.0,
            "max_seconds": 0.0,
        }

    return {
        "count": float(len(durations)),
        "total_seconds": sum(durations),
        "mean_seconds": mean(durations),
        "median_seconds": median(durations),
        "min_seconds": min(durations),
        "max_seconds": max(durations),
    }


def event_demo() -> None:
    print("\n" + "=" * 80)
    print("17. EVENT DURATION ANALYTICS")
    print("=" * 80)

    zone = ZoneInfo("Asia/Kolkata")

    events = [
        Event(
            "E001",
            "Login",
            datetime(2026, 9, 28, 9, 0, tzinfo=zone),
            datetime(2026, 9, 28, 9, 0, 5, tzinfo=zone),
        ),
        Event(
            "E002",
            "Report generation",
            datetime(2026, 9, 28, 9, 5, tzinfo=zone),
            datetime(2026, 9, 28, 9, 5, 40, tzinfo=zone),
        ),
        Event(
            "E003",
            "Database query",
            datetime(2026, 9, 28, 9, 10, tzinfo=zone),
            datetime(2026, 9, 28, 9, 10, 12, tzinfo=zone),
        ),
    ]

    for event in events:
        print(event.event_id, event.name, event.duration_seconds, "seconds")

    print("Analytics:")
    for key, value in event_analytics(events).items():
        print(f"  {key}: {value}")


# ============================================================================
# 18. SLA ANALYTICS
# ============================================================================

def percentile(values: Sequence[float], percentile_value: float) -> float:
    """
    Linear-interpolation percentile implementation.

    percentile_value must be between 0 and 100.
    """
    if not values:
        raise ValueError("Cannot calculate a percentile of empty data.")

    if not 0 <= percentile_value <= 100:
        raise ValueError("Percentile must be between 0 and 100.")

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * percentile_value / 100
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    fraction = position - lower
    return (
        ordered[lower]
        + (ordered[upper] - ordered[lower]) * fraction
    )


def sla_demo() -> None:
    print("\n" + "=" * 80)
    print("18. LATENCY AND SLA ANALYTICS")
    print("=" * 80)

    latencies = [120, 95, 80, 210, 150, 300, 110, 90, 130, 180]

    print("Latencies:", latencies)
    print("Mean:", mean(latencies))
    print("Median:", median(latencies))
    print("P90:", percentile(latencies, 90))
    print("P95:", percentile(latencies, 95))
    print("P99:", percentile(latencies, 99))

    threshold = 200
    within_sla = sum(value <= threshold for value in latencies)

    print(
        "SLA compliance:",
        within_sla / len(latencies) * 100,
        "%",
    )


# ============================================================================
# 19. SCHEDULE GENERATION
# ============================================================================

def generate_daily_schedule(
    start: datetime,
    occurrences: int,
    interval: timedelta,
) -> list[datetime]:
    if start.tzinfo is None:
        raise ValueError("Schedule start must be timezone-aware.")

    if occurrences < 0:
        raise ValueError("occurrences cannot be negative.")

    if interval <= timedelta(0):
        raise ValueError("interval must be positive.")

    return [
        start + index * interval
        for index in range(occurrences)
    ]


def schedule_demo() -> None:
    print("\n" + "=" * 80)
    print("19. RECURRING SCHEDULES")
    print("=" * 80)

    zone = ZoneInfo("Asia/Kolkata")

    schedule = generate_daily_schedule(
        datetime(2026, 9, 28, 9, 0, tzinfo=zone),
        occurrences=5,
        interval=timedelta(days=1),
    )

    for occurrence in schedule:
        print(occurrence.isoformat())


# ============================================================================
# 20. CALENDAR-DAY SCHEDULE VERSUS ELAPSED-HOUR SCHEDULE
# ============================================================================

def compare_calendar_and_elapsed_time() -> None:
    print("\n" + "=" * 80)
    print("20. CALENDAR DAYS VS ELAPSED HOURS")
    print("=" * 80)

    zone = ZoneInfo("America/New_York")

    start = datetime(
        2026,
        11,
        1,
        0,
        30,
        tzinfo=zone,
    )

    calendar_next = start + timedelta(days=1)

    elapsed_24_hours = (
        start.astimezone(timezone.utc)
        + timedelta(hours=24)
    ).astimezone(zone)

    print("Start:", start)
    print("Calendar arithmetic:", calendar_next)
    print("Elapsed 24 hours:", elapsed_24_hours)

    print(
        "Calendar UTC:",
        calendar_next.astimezone(timezone.utc),
    )
    print(
        "Elapsed UTC:",
        elapsed_24_hours.astimezone(timezone.utc),
    )

    # Around timezone transitions, "one calendar day later" and
    # "exactly 24 elapsed hours later" are conceptually different.


# ============================================================================
# 21. DATE RANGE GENERATION
# ============================================================================

def date_range(
    start: date,
    end: date,
    step_days: int = 1,
) -> Iterable[date]:
    if step_days == 0:
        raise ValueError("step_days cannot be zero.")

    step = timedelta(days=step_days)
    current = start

    if step_days > 0:
        while current <= end:
            yield current
            current += step
    else:
        while current >= end:
            yield current
            current += step


def date_range_demo() -> None:
    print("\n" + "=" * 80)
    print("21. DATE RANGES")
    print("=" * 80)

    print("Forward:")
    for value in date_range(
        date(2026, 9, 28),
        date(2026, 10, 2),
    ):
        print(value)

    print("Backward:")
    for value in date_range(
        date(2026, 10, 2),
        date(2026, 9, 28),
        -1,
    ):
        print(value)


# ============================================================================
# 22. AGE CALCULATION
# ============================================================================

def calculate_age(birth_date: date, reference_date: date) -> int:
    if birth_date > reference_date:
        raise ValueError("Birth date cannot be after reference date.")

    age = reference_date.year - birth_date.year

    birthday_has_occurred = (
        (reference_date.month, reference_date.day)
        >= (birth_date.month, birth_date.day)
    )

    if not birthday_has_occurred:
        age -= 1

    return age


def age_demo() -> None:
    print("\n" + "=" * 80)
    print("22. CALENDAR-BASED AGE")
    print("=" * 80)

    birth = date(1990, 9, 30)
    reference = date(2026, 9, 28)

    print("Birth date:", birth)
    print("Reference:", reference)
    print("Age:", calculate_age(birth, reference))


# ============================================================================
# 23. SAFE ISO PARSING
# ============================================================================

def parse_iso_datetime(value: str) -> datetime:
    """
    Parse ISO-8601 datetime text and require timezone awareness.

    A production system should establish one clear input contract:
    timestamps without offsets are rejected here because their instant
    cannot be determined unambiguously.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO datetime: {value}") from exc

    if parsed.tzinfo is None:
        raise ValueError(
            "Timezone-aware ISO datetime required; "
            "include Z or an explicit UTC offset."
        )

    return parsed


def safe_parsing_demo() -> None:
    print("\n" + "=" * 80)
    print("23. SAFE DATETIME PARSING")
    print("=" * 80)

    examples = [
        "2026-09-28T11:56:00+05:30",
        "2026-09-28T06:26:00+00:00",
        "not-a-date",
        "2026-09-28T11:56:00",
    ]

    for example in examples:
        try:
            print(example, "->", parse_iso_datetime(example))
        except ValueError as exc:
            print(example, "-> REJECTED:", exc)


# ============================================================================
# 24. TIMEZONE CONVERSION PIPELINE
# ============================================================================

def convert_between_zones(
    value: datetime,
    target_timezone: str,
) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Input must be timezone-aware.")

    return value.astimezone(validate_timezone(target_timezone))


def conversion_demo() -> None:
    print("\n" + "=" * 80)
    print("24. TIMEZONE CONVERSION PIPELINE")
    print("=" * 80)

    source = parse_iso_datetime("2026-09-28T18:30:00+05:30")

    for zone_name in [
        "UTC",
        "Europe/London",
        "America/New_York",
        "Asia/Tokyo",
    ]:
        print(
            zone_name,
            "->",
            convert_between_zones(source, zone_name),
        )


# ============================================================================
# 25. INTERVAL COVERAGE
# ============================================================================

def calculate_union_duration(
    intervals: Sequence[Interval],
) -> timedelta:
    merged = merge_intervals(intervals)

    return sum(
        (item.duration for item in merged),
        timedelta(0),
    )


def interval_coverage_demo() -> None:
    print("\n" + "=" * 80)
    print("25. UNION DURATION / COVERAGE")
    print("=" * 80)

    zone = ZoneInfo("UTC")

    intervals = [
        Interval(
            datetime(2026, 9, 28, 9, 0, tzinfo=zone),
            datetime(2026, 9, 28, 10, 0, tzinfo=zone),
        ),
        Interval(
            datetime(2026, 9, 28, 9, 30, tzinfo=zone),
            datetime(2026, 9, 28, 11, 0, tzinfo=zone),
        ),
        Interval(
            datetime(2026, 9, 28, 13, 0, tzinfo=zone),
            datetime(2026, 9, 28, 14, 0, tzinfo=zone),
        ),
    ]

    print("Raw duration:", sum(
        (item.duration for item in intervals),
        timedelta(0),
    ))

    print("Union duration:", calculate_union_duration(intervals))


# ============================================================================
# 26. APPOINTMENT CONFLICT DETECTION
# ============================================================================

def find_conflicts(
    intervals: Sequence[Interval],
) -> list[tuple[Interval, Interval]]:
    ordered = sorted(intervals, key=lambda item: item.start)
    conflicts = []

    for index in range(len(ordered)):
        for other_index in range(index + 1, len(ordered)):
            first = ordered[index]
            second = ordered[other_index]

            if first.overlaps(second):
                conflicts.append((first, second))

    return conflicts


def conflict_demo() -> None:
    print("\n" + "=" * 80)
    print("26. APPOINTMENT CONFLICT DETECTION")
    print("=" * 80)

    zone = ZoneInfo("Asia/Kolkata")

    meetings = [
        Interval(
            datetime(2026, 9, 28, 10, 0, tzinfo=zone),
            datetime(2026, 9, 28, 11, 0, tzinfo=zone),
        ),
        Interval(
            datetime(2026, 9, 28, 10, 30, tzinfo=zone),
            datetime(2026, 9, 28, 11, 30, tzinfo=zone),
        ),
        Interval(
            datetime(2026, 9, 28, 12, 0, tzinfo=zone),
            datetime(2026, 9, 28, 13, 0, tzinfo=zone),
        ),
    ]

    conflicts = find_conflicts(meetings)

    print("Conflict count:", len(conflicts))

    for first, second in conflicts:
        print("Conflict:")
        print(" ", first)
        print(" ", second)


# ============================================================================
# 27. TESTS
# ============================================================================

def run_assertions() -> None:
    print("\n" + "=" * 80)
    print("27. BUILT-IN VALIDATION TESTS")
    print("=" * 80)

    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)

    assert calculate_age(
        date(2000, 9, 28),
        date(2026, 9, 28),
    ) == 26

    zone = ZoneInfo("UTC")

    interval = Interval(
        datetime(2026, 9, 28, 9, 0, tzinfo=zone),
        datetime(2026, 9, 28, 10, 0, tzinfo=zone),
    )

    assert interval.contains(
        datetime(2026, 9, 28, 9, 30, tzinfo=zone)
    )

    assert not interval.contains(
        datetime(2026, 9, 28, 10, 0, tzinfo=zone)
    )

    assert interval.duration == timedelta(hours=1)

    assert percentile([10, 20, 30, 40, 50], 50) == 30

    try:
        Interval(
            datetime(2026, 9, 28, 10, 0, tzinfo=zone),
            datetime(2026, 9, 28, 9, 0, tzinfo=zone),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid interval was accepted.")

    try:
        parse_iso_datetime("2026-09-28T11:00:00")
    except ValueError:
        pass
    else:
        raise AssertionError("Naive datetime was accepted.")

    print("All assertions passed.")


# ============================================================================
# 28. PERFORMANCE CONSIDERATIONS
# ============================================================================

def performance_demo() -> None:
    print("\n" + "=" * 80)
    print("28. PERFORMANCE CONSIDERATIONS")
    print("=" * 80)

    values = [
        datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index)
        for index in range(10_000)
    ]

    start = time_module.perf_counter()

    timestamps = [
        value.timestamp()
        for value in values
    ]

    elapsed = time_module.perf_counter() - start

    print("Converted values:", len(timestamps))
    print("Elapsed seconds:", elapsed)

    # Practical performance principles:
    # - Convert and normalize data in batches where possible.
    # - Avoid repeated parsing of the same timestamp.
    # - Prefer indexed database timestamp columns for filtering.
    # - Use appropriate interval algorithms instead of comparing every pair
    #   when the dataset becomes large.
    # - Preserve enough precision for the business requirement.


# ============================================================================
# 29. PRECISION
# ============================================================================

def precision_demo() -> None:
    print("\n" + "=" * 80)
    print("29. PRECISION")
    print("=" * 80)

    exact_duration = timedelta(
        seconds=1,
        microseconds=123456,
    )

    print("Exact timedelta:", exact_duration)
    print("Microseconds:", exact_duration.total_seconds())

    decimal_seconds = Decimal("1.123456")
    print("Decimal seconds:", decimal_seconds)

    # datetime supports microsecond precision.
    # If nanosecond precision is required, a separate representation may be
    # needed, depending on the database, operating system, and application.


# ============================================================================
# 30. COMMON FAILURE MODES
# ============================================================================

def common_failure_demo() -> None:
    print("\n" + "=" * 80)
    print("30. COMMON FAILURE MODES")
    print("=" * 80)

    aware = datetime(
        2026,
        9,
        28,
        tzinfo=timezone.utc,
    )

    naive = datetime(
        2026,
        9,
        28,
    )

    try:
        print(aware > naive)
    except TypeError as exc:
        print("Naive/aware comparison rejected:", exc)

    # Production rule:
    # establish whether a field represents:
    #   1. an instant,
    #   2. a local wall-clock time,
    #   3. a calendar date,
    #   4. an elapsed duration,
    #   5. a recurring calendar schedule.
    #
    # These concepts should not be treated as interchangeable.


# ============================================================================
# 31. REALISTIC ANALYTICS PIPELINE
# ============================================================================

@dataclass(frozen=True)
class LogRecord:
    request_id: str
    received_at: datetime
    completed_at: datetime
    region: str

    @property
    def latency_ms(self) -> float:
        return (
            self.completed_at - self.received_at
        ).total_seconds() * 1000


def analyze_logs(records: Sequence[LogRecord]) -> dict[str, object]:
    if not records:
        return {
            "records": 0,
            "mean_latency_ms": 0,
            "p95_latency_ms": 0,
            "max_latency_ms": 0,
            "by_region": {},
        }

    latencies = [record.latency_ms for record in records]

    regional: dict[str, list[float]] = {}

    for record in records:
        regional.setdefault(record.region, []).append(
            record.latency_ms
        )

    regional_metrics = {}

    for region, region_latencies in regional.items():
        regional_metrics[region] = {
            "count": len(region_latencies),
            "mean_ms": mean(region_latencies),
            "p95_ms": percentile(region_latencies, 95),
            "max_ms": max(region_latencies),
        }

    return {
        "records": len(records),
        "mean_latency_ms": mean(latencies),
        "p95_latency_ms": percentile(latencies, 95),
        "max_latency_ms": max(latencies),
        "by_region": regional_metrics,
    }


def log_analytics_demo() -> None:
    print("\n" + "=" * 80)
    print("31. REALISTIC LOG ANALYTICS")
    print("=" * 80)

    utc = timezone.utc

    records = [
        LogRecord(
            "R001",
            datetime(2026, 9, 28, 6, 0, 0, tzinfo=utc),
            datetime(2026, 9, 28, 6, 0, 0, 200000, tzinfo=utc),
            "IN",
        ),
        LogRecord(
            "R002",
            datetime(2026, 9, 28, 6, 1, 0, tzinfo=utc),
            datetime(2026, 9, 28, 6, 1, 0, 500000, tzinfo=utc),
            "US",
        ),
        LogRecord(
            "R003",
            datetime(2026, 9, 28, 6, 2, 0, tzinfo=utc),
            datetime(2026, 9, 28, 6, 2, 1, tzinfo=utc),
            "IN",
        ),
    ]

    analytics = analyze_logs(records)

    for key, value in analytics.items():
        print(key, ":", value)


# ============================================================================
# 32. MAIN PROGRAM
# ============================================================================

def main() -> None:
    print("DATE AND TIME ANALYTICS STUDY PROGRAM")
    print("Python standard-library implementation")

    fundamentals_demo()
    timestamp_demo()
    timedelta_demo()
    date_arithmetic_demo()
    month_arithmetic_demo()
    calendar_metrics_demo()
    parsing_and_formatting_demo()
    timezone_demo()
    utc_first_demo()
    fixed_offset_demo()
    dst_demo()
    timezone_validation_demo()
    interval_demo()
    interval_merge_demo()
    business_day_demo()
    holiday_demo()
    event_demo()
    sla_demo()
    schedule_demo()
    compare_calendar_and_elapsed_time()
    date_range_demo()
    age_demo()
    safe_parsing_demo()
    conversion_demo()
    interval_coverage_demo()
    conflict_demo()
    run_assertions()
    performance_demo()
    precision_demo()
    common_failure_demo()
    log_analytics_demo()

    print("\n" + "=" * 80)
    print("END OF DATE AND TIME ANALYTICS PROGRAM")
    print("=" * 80)


if __name__ == "__main__":
    main()
