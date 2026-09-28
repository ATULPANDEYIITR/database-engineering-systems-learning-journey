/*
 * Date and Time Analytics
 * ========================
 *
 * Self-contained JavaScript study program covering:
 *
 * - Date objects and timestamps
 * - Epoch time
 * - Duration arithmetic
 * - Date arithmetic
 * - Parsing and formatting
 * - UTC and local time
 * - Fixed-offset parsing
 * - Timezone-aware formatting with Intl
 * - Interval modeling
 * - Interval overlap and merging
 * - Business-day calculations
 * - Event duration analytics
 * - Percentiles and SLA measurements
 * - Recurring schedules
 * - Validation and error handling
 * - Performance considerations
 * - A realistic event-log analytics case study
 *
 * No external npm packages are required.
 *
 * Important JavaScript limitation:
 * The classic Date object represents an instant internally as milliseconds
 * since the Unix epoch. It does not itself retain an IANA timezone such as
 * "Asia/Kolkata". The Intl API can format an instant in a requested timezone.
 *
 * Modern JavaScript environments may also provide Temporal. This file uses
 * Date + Intl so that it remains broadly executable without relying on
 * Temporal availability.
 */

"use strict";

// ============================================================================
// 1. BASIC DATE OBJECTS
// ============================================================================

function fundamentalsDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("1. FUNDAMENTAL DATE AND TIME TYPES");
    console.log("=".repeat(80));

    const now = new Date();

    // Date stores an instant. Its textual display can vary by environment.
    console.log("Current Date object:", now);

    // ISO output is deterministic and suitable for data interchange.
    console.log("ISO representation:", now.toISOString());

    // Date.now() returns Unix epoch milliseconds.
    console.log("Epoch milliseconds:", Date.now());

    // Explicit UTC construction avoids dependence on the machine's local zone.
    const utcDate = new Date(Date.UTC(2026, 8, 28, 6, 26, 0));
    console.log("Explicit UTC instant:", utcDate.toISOString());
}


// ============================================================================
// 2. TIMESTAMPS
// ============================================================================

function timestampDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("2. TIMESTAMPS");
    console.log("=".repeat(80));

    const timestampMilliseconds = Date.UTC(2026, 8, 28, 6, 26, 0);

    const date = new Date(timestampMilliseconds);

    console.log("Timestamp:", timestampMilliseconds);
    console.log("UTC:", date.toISOString());

    const seconds = Math.floor(timestampMilliseconds / 1000);

    console.log("Unix seconds:", seconds);
    console.log("Restored:", new Date(seconds * 1000).toISOString());

    // JavaScript Date uses milliseconds, while many APIs and databases use
    // seconds. Unit confusion is a common source of bugs.
}


// ============================================================================
// 3. DATE COMPONENTS
// ============================================================================

function componentDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("3. DATE COMPONENTS");
    console.log("=".repeat(80));

    const value = new Date(Date.UTC(2026, 8, 28, 6, 26, 30));

    console.log("UTC year:", value.getUTCFullYear());
    console.log("UTC month:", value.getUTCMonth() + 1);
    console.log("UTC day:", value.getUTCDate());
    console.log("UTC hour:", value.getUTCHours());
    console.log("UTC minute:", value.getUTCMinutes());
    console.log("UTC second:", value.getUTCSeconds());
    console.log("UTC weekday:", value.getUTCDay());

    // JavaScript months are zero-based when constructing/accessing Date
    // components through getMonth()/setMonth().
    // January = 0, September = 8.
}


// ============================================================================
// 4. DURATION ARITHMETIC
// ============================================================================

function durationDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("4. DURATION ARITHMETIC");
    console.log("=".repeat(80));

    const start = new Date(Date.UTC(2026, 8, 28, 9, 30, 0));
    const durationMilliseconds =
        (2 * 60 * 60 * 1000) +
        (45 * 60 * 1000) +
        (30 * 1000);

    const end = new Date(start.getTime() + durationMilliseconds);

    console.log("Start:", start.toISOString());
    console.log("End:", end.toISOString());
    console.log(
        "Duration seconds:",
        (end.getTime() - start.getTime()) / 1000
    );

    // Date subtraction produces a numeric millisecond duration.
}


// ============================================================================
// 5. CALENDAR-DAY ARITHMETIC
// ============================================================================

function addCalendarDaysUTC(date, days) {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
        throw new TypeError("A valid Date object is required.");
    }

    const result = new Date(date.getTime());
    result.setUTCDate(result.getUTCDate() + days);
    return result;
}

function calendarArithmeticDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("5. CALENDAR-DAY ARITHMETIC");
    console.log("=".repeat(80));

    const original = new Date(Date.UTC(2026, 8, 28));

    console.log("Original:", original.toISOString());
    console.log("+ 7 days:", addCalendarDaysUTC(original, 7).toISOString());
    console.log("- 30 days:", addCalendarDaysUTC(original, -30).toISOString());

    // setUTCDate handles month/year boundaries automatically.
}


// ============================================================================
// 6. MONTH ARITHMETIC
// ============================================================================

function daysInMonthUTC(year, monthZeroBased) {
    // Day zero of the next month is the last day of the requested month.
    return new Date(Date.UTC(year, monthZeroBased + 1, 0)).getUTCDate();
}

function addMonthsUTC(date, months) {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
        throw new TypeError("A valid Date object is required.");
    }

    if (!Number.isInteger(months)) {
        throw new TypeError("months must be an integer.");
    }

    const originalDay = date.getUTCDate();

    const target = new Date(Date.UTC(
        date.getUTCFullYear(),
        date.getUTCMonth() + months,
        1,
        date.getUTCHours(),
        date.getUTCMinutes(),
        date.getUTCSeconds(),
        date.getUTCMilliseconds()
    ));

    const lastDay = daysInMonthUTC(
        target.getUTCFullYear(),
        target.getUTCMonth()
    );

    target.setUTCDate(Math.min(originalDay, lastDay));

    return target;
}

function monthArithmeticDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("6. CALENDAR MONTH ARITHMETIC");
    console.log("=".repeat(80));

    const examples = [
        new Date(Date.UTC(2026, 0, 31)),
        new Date(Date.UTC(2024, 0, 31)),
        new Date(Date.UTC(2026, 11, 31))
    ];

    for (const value of examples) {
        console.log(
            value.toISOString(),
            "->",
            addMonthsUTC(value, 1).toISOString()
        );
    }

    // Calendar-month arithmetic is not the same as adding 30 days.
}


// ============================================================================
// 7. ISO PARSING
// ============================================================================

function parseISODateTime(value) {
    if (typeof value !== "string") {
        throw new TypeError("ISO datetime must be a string.");
    }

    const parsed = new Date(value);

    if (Number.isNaN(parsed.getTime())) {
        throw new RangeError(`Invalid ISO datetime: ${value}`);
    }

    // For an analytics pipeline requiring an exact instant, require an
    // explicit timezone marker or UTC Z suffix.
    if (!/[zZ]|[+-]\d{2}:\d{2}$/.test(value)) {
        throw new RangeError(
            "Timezone-aware ISO datetime required."
        );
    }

    return parsed;
}

function parsingDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("7. ISO PARSING AND VALIDATION");
    console.log("=".repeat(80));

    const examples = [
        "2026-09-28T11:56:00+05:30",
        "2026-09-28T06:26:00Z",
        "invalid-date",
        "2026-09-28T11:56:00"
    ];

    for (const value of examples) {
        try {
            console.log(
                value,
                "->",
                parseISODateTime(value).toISOString()
            );
        } catch (error) {
            console.log(value, "-> REJECTED:", error.message);
        }
    }
}


// ============================================================================
// 8. TIMEZONE FORMATTING WITH INTL
// ============================================================================

function formatInTimeZone(date, timeZone, options = {}) {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
        throw new TypeError("A valid Date object is required.");
    }

    try {
        return new Intl.DateTimeFormat("en-IN", {
            timeZone,
            dateStyle: "medium",
            timeStyle: "long",
            ...options
        }).format(date);
    } catch (error) {
        throw new RangeError(
            `Invalid or unsupported timezone: ${timeZone}`
        );
    }
}

function timezoneDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("8. TIMEZONES");
    console.log("=".repeat(80));

    const instant = new Date("2026-09-28T06:26:00Z");

    const zones = [
        "UTC",
        "Asia/Kolkata",
        "Europe/London",
        "America/New_York",
        "Asia/Tokyo"
    ];

    for (const zone of zones) {
        console.log(
            `${zone}:`,
            formatInTimeZone(instant, zone)
        );
    }

    // The same Date object is formatted differently because each timezone
    // maps the same instant to a different local wall-clock representation.
}


// ============================================================================
// 9. UTC-FIRST APPLICATION DESIGN
// ============================================================================

function utcFirstDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("9. UTC-FIRST APPLICATION DESIGN");
    console.log("=".repeat(80));

    const userInput = "2026-09-28T18:30:00+05:30";
    const instant = parseISODateTime(userInput);

    console.log("Input:", userInput);
    console.log("Normalized UTC:", instant.toISOString());

    console.log(
        "Displayed in India:",
        formatInTimeZone(instant, "Asia/Kolkata")
    );

    console.log(
        "Displayed in New York:",
        formatInTimeZone(instant, "America/New_York")
    );
}


// ============================================================================
// 10. INTERVAL CLASS
// ============================================================================

class TimeInterval {
    /*
     * A half-open interval [start, end):
     * start is included, end is excluded.
     *
     * This makes adjacent intervals naturally non-overlapping.
     */

    constructor(start, end) {
        if (!(start instanceof Date) || Number.isNaN(start.getTime())) {
            throw new TypeError("Invalid interval start.");
        }

        if (!(end instanceof Date) || Number.isNaN(end.getTime())) {
            throw new TypeError("Invalid interval end.");
        }

        if (end.getTime() <= start.getTime()) {
            throw new RangeError(
                "Interval end must be after interval start."
            );
        }

        this.start = new Date(start.getTime());
        this.end = new Date(end.getTime());
    }

    durationMilliseconds() {
        return this.end.getTime() - this.start.getTime();
    }

    durationSeconds() {
        return this.durationMilliseconds() / 1000;
    }

    contains(instant) {
        if (!(instant instanceof Date) || Number.isNaN(instant.getTime())) {
            throw new TypeError("Invalid instant.");
        }

        return (
            instant.getTime() >= this.start.getTime() &&
            instant.getTime() < this.end.getTime()
        );
    }

    overlaps(other) {
        return (
            this.start.getTime() < other.end.getTime() &&
            other.start.getTime() < this.end.getTime()
        );
    }

    intersection(other) {
        if (!this.overlaps(other)) {
            return null;
        }

        const start = new Date(
            Math.max(this.start.getTime(), other.start.getTime())
        );

        const end = new Date(
            Math.min(this.end.getTime(), other.end.getTime())
        );

        return new TimeInterval(start, end);
    }

    toJSON() {
        return {
            start: this.start.toISOString(),
            end: this.end.toISOString(),
            durationMilliseconds: this.durationMilliseconds()
        };
    }
}

function intervalDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("10. INTERVAL ANALYTICS");
    console.log("=".repeat(80));

    const first = new TimeInterval(
        new Date("2026-09-28T09:00:00Z"),
        new Date("2026-09-28T12:00:00Z")
    );

    const second = new TimeInterval(
        new Date("2026-09-28T11:30:00Z"),
        new Date("2026-09-28T14:00:00Z")
    );

    console.log("First:", first.toJSON());
    console.log("Second:", second.toJSON());
    console.log("Overlap:", first.overlaps(second));
    console.log("Intersection:", first.intersection(second)?.toJSON());

    console.log(
        "Contains 10:00 UTC:",
        first.contains(new Date("2026-09-28T10:00:00Z"))
    );

    console.log(
        "Contains endpoint:",
        first.contains(new Date("2026-09-28T12:00:00Z"))
    );
}


// ============================================================================
// 11. INTERVAL MERGING
// ============================================================================

function mergeIntervals(intervals, mergeAdjacent = true) {
    if (!Array.isArray(intervals)) {
        throw new TypeError("intervals must be an array.");
    }

    if (intervals.length === 0) {
        return [];
    }

    const ordered = [...intervals].sort(
        (a, b) => a.start.getTime() - b.start.getTime()
    );

    const merged = [ordered[0]];

    for (let index = 1; index < ordered.length; index += 1) {
        const current = ordered[index];
        const previous = merged[merged.length - 1];

        const overlap = previous.overlaps(current);
        const adjacent =
            previous.end.getTime() === current.start.getTime();

        if (overlap || (mergeAdjacent && adjacent)) {
            const end = new Date(
                Math.max(
                    previous.end.getTime(),
                    current.end.getTime()
                )
            );

            merged[merged.length - 1] =
                new TimeInterval(previous.start, end);
        } else {
            merged.push(current);
        }
    }

    return merged;
}

function intervalMergeDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("11. INTERVAL MERGING");
    console.log("=".repeat(80));

    const intervals = [
        new TimeInterval(
            new Date("2026-09-28T09:00:00Z"),
            new Date("2026-09-28T10:00:00Z")
        ),
        new TimeInterval(
            new Date("2026-09-28T09:45:00Z"),
            new Date("2026-09-28T11:00:00Z")
        ),
        new TimeInterval(
            new Date("2026-09-28T11:00:00Z"),
            new Date("2026-09-28T12:00:00Z")
        ),
        new TimeInterval(
            new Date("2026-09-28T14:00:00Z"),
            new Date("2026-09-28T15:00:00Z")
        )
    ];

    const merged = mergeIntervals(intervals);

    for (const interval of merged) {
        console.log(interval.toJSON());
    }
}


// ============================================================================
// 12. BUSINESS DAYS
// ============================================================================

function isBusinessDayUTC(date) {
    const day = date.getUTCDay();
    return day >= 1 && day <= 5;
}

function addBusinessDaysUTC(date, numberOfDays, holidays = new Set()) {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
        throw new TypeError("A valid Date object is required.");
    }

    if (!Number.isInteger(numberOfDays)) {
        throw new TypeError("numberOfDays must be an integer.");
    }

    if (numberOfDays === 0) {
        return new Date(date.getTime());
    }

    const direction = numberOfDays > 0 ? 1 : -1;
    let remaining = Math.abs(numberOfDays);
    let current = new Date(date.getTime());

    while (remaining > 0) {
        current = addCalendarDaysUTC(current, direction);

        const dayKey = current.toISOString().slice(0, 10);

        if (isBusinessDayUTC(current) && !holidays.has(dayKey)) {
            remaining -= 1;
        }
    }

    return current;
}

function businessDayDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("12. BUSINESS-DAY ANALYTICS");
    console.log("=".repeat(80));

    const holidays = new Set([
        "2026-10-02",
        "2026-10-05"
    ]);

    const start = new Date("2026-10-01T00:00:00Z");

    console.log(
        "Start:",
        start.toISOString()
    );

    console.log(
        "Two valid business days later:",
        addBusinessDaysUTC(start, 2, holidays).toISOString()
    );
}


// ============================================================================
// 13. EVENT ANALYTICS
// ============================================================================

class EventRecord {
    constructor(id, name, startedAt, endedAt) {
        if (!(startedAt instanceof Date) || Number.isNaN(startedAt.getTime())) {
            throw new TypeError("Invalid startedAt.");
        }

        if (!(endedAt instanceof Date) || Number.isNaN(endedAt.getTime())) {
            throw new TypeError("Invalid endedAt.");
        }

        if (endedAt.getTime() < startedAt.getTime()) {
            throw new RangeError(
                "endedAt cannot precede startedAt."
            );
        }

        this.id = id;
        this.name = name;
        this.startedAt = new Date(startedAt.getTime());
        this.endedAt = new Date(endedAt.getTime());
    }

    durationMilliseconds() {
        return this.endedAt.getTime() - this.startedAt.getTime();
    }

    durationSeconds() {
        return this.durationMilliseconds() / 1000;
    }
}

function mean(values) {
    if (values.length === 0) {
        throw new RangeError("Cannot calculate mean of empty data.");
    }

    return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function median(values) {
    if (values.length === 0) {
        throw new RangeError("Cannot calculate median of empty data.");
    }

    const sorted = [...values].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);

    if (sorted.length % 2 === 0) {
        return (sorted[middle - 1] + sorted[middle]) / 2;
    }

    return sorted[middle];
}

function percentile(values, percentileValue) {
    if (values.length === 0) {
        throw new RangeError("Cannot calculate percentile of empty data.");
    }

    if (
        !Number.isFinite(percentileValue) ||
        percentileValue < 0 ||
        percentileValue > 100
    ) {
        throw new RangeError(
            "Percentile must be between 0 and 100."
        );
    }

    const sorted = [...values].sort((a, b) => a - b);

    if (sorted.length === 1) {
        return sorted[0];
    }

    const position =
        (sorted.length - 1) * percentileValue / 100;

    const lower = Math.floor(position);
    const upper = Math.ceil(position);

    if (lower === upper) {
        return sorted[lower];
    }

    const fraction = position - lower;

    return (
        sorted[lower] +
        (sorted[upper] - sorted[lower]) * fraction
    );
}

function eventAnalytics(events) {
    const durations = events.map(
        event => event.durationMilliseconds()
    );

    if (durations.length === 0) {
        return {
            count: 0,
            totalMilliseconds: 0,
            meanMilliseconds: 0,
            medianMilliseconds: 0,
            p95Milliseconds: 0,
            maxMilliseconds: 0
        };
    }

    return {
        count: durations.length,
        totalMilliseconds: durations.reduce(
            (sum, value) => sum + value,
            0
        ),
        meanMilliseconds: mean(durations),
        medianMilliseconds: median(durations),
        p95Milliseconds: percentile(durations, 95),
        maxMilliseconds: Math.max(...durations)
    };
}

function eventDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("13. EVENT DURATION ANALYTICS");
    console.log("=".repeat(80));

    const events = [
        new EventRecord(
            "E001",
            "Login",
            new Date("2026-09-28T09:00:00Z"),
            new Date("2026-09-28T09:00:05Z")
        ),
        new EventRecord(
            "E002",
            "Report generation",
            new Date("2026-09-28T09:05:00Z"),
            new Date("2026-09-28T09:05:40Z")
        ),
        new EventRecord(
            "E003",
            "Database query",
            new Date("2026-09-28T09:10:00Z"),
            new Date("2026-09-28T09:10:12Z")
        )
    ];

    for (const event of events) {
        console.log(
            event.id,
            event.name,
            event.durationMilliseconds(),
            "ms"
        );
    }

    console.log("Analytics:", eventAnalytics(events));
}


// ============================================================================
// 14. RECURRING SCHEDULES
// ============================================================================

function generateRecurringSchedule(
    start,
    occurrences,
    intervalMilliseconds
) {
    if (!(start instanceof Date) || Number.isNaN(start.getTime())) {
        throw new TypeError("Invalid schedule start.");
    }

    if (!Number.isInteger(occurrences) || occurrences < 0) {
        throw new RangeError(
            "occurrences must be a non-negative integer."
        );
    }

    if (
        !Number.isFinite(intervalMilliseconds) ||
        intervalMilliseconds <= 0
    ) {
        throw new RangeError(
            "intervalMilliseconds must be positive."
        );
    }

    return Array.from(
        { length: occurrences },
        (_, index) =>
            new Date(
                start.getTime() +
                index * intervalMilliseconds
            )
    );
}

function scheduleDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("14. RECURRING SCHEDULES");
    console.log("=".repeat(80));

    const schedule = generateRecurringSchedule(
        new Date("2026-09-28T09:00:00Z"),
        5,
        24 * 60 * 60 * 1000
    );

    for (const value of schedule) {
        console.log(value.toISOString());
    }
}


// ============================================================================
// 15. CALENDAR RANGE
// ============================================================================

function dateRangeUTC(start, end, stepDays = 1) {
    if (!(start instanceof Date) || Number.isNaN(start.getTime())) {
        throw new TypeError("Invalid start date.");
    }

    if (!(end instanceof Date) || Number.isNaN(end.getTime())) {
        throw new TypeError("Invalid end date.");
    }

    if (!Number.isInteger(stepDays) || stepDays === 0) {
        throw new RangeError(
            "stepDays must be a non-zero integer."
        );
    }

    const results = [];
    let current = new Date(start.getTime());

    if (stepDays > 0) {
        while (current.getTime() <= end.getTime()) {
            results.push(new Date(current.getTime()));
            current = addCalendarDaysUTC(current, stepDays);
        }
    } else {
        while (current.getTime() >= end.getTime()) {
            results.push(new Date(current.getTime()));
            current = addCalendarDaysUTC(current, stepDays);
        }
    }

    return results;
}

function rangeDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("15. DATE RANGES");
    console.log("=".repeat(80));

    const values = dateRangeUTC(
        new Date("2026-09-28T00:00:00Z"),
        new Date("2026-10-02T00:00:00Z")
    );

    for (const value of values) {
        console.log(value.toISOString().slice(0, 10));
    }
}


// ============================================================================
// 16. REALISTIC LOG ANALYTICS
// ============================================================================

function analyzeLogs(records) {
    if (!Array.isArray(records)) {
        throw new TypeError("records must be an array.");
    }

    const latencyValues = records.map(record => {
        if (
            !(record.receivedAt instanceof Date) ||
            !(record.completedAt instanceof Date)
        ) {
            throw new TypeError(
                "Log timestamps must be Date objects."
            );
        }

        const latency =
            record.completedAt.getTime() -
            record.receivedAt.getTime();

        if (latency < 0) {
            throw new RangeError(
                `Negative latency for request ${record.requestId}.`
            );
        }

        return latency;
    });

    if (latencyValues.length === 0) {
        return {
            records: 0,
            meanMs: 0,
            medianMs: 0,
            p95Ms: 0,
            maxMs: 0,
            byRegion: {}
        };
    }

    const byRegion = new Map();

    records.forEach((record, index) => {
        if (!byRegion.has(record.region)) {
            byRegion.set(record.region, []);
        }

        byRegion.get(record.region).push(
            latencyValues[index]
        );
    });

    const regional = {};

    for (const [region, values] of byRegion.entries()) {
        regional[region] = {
            count: values.length,
            meanMs: mean(values),
            p95Ms: percentile(values, 95),
            maxMs: Math.max(...values)
        };
    }

    return {
        records: records.length,
        meanMs: mean(latencyValues),
        medianMs: median(latencyValues),
        p95Ms: percentile(latencyValues, 95),
        maxMs: Math.max(...latencyValues),
        byRegion: regional
    };
}

function logAnalyticsDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("16. REALISTIC LOG ANALYTICS");
    console.log("=".repeat(80));

    const records = [
        {
            requestId: "R001",
            receivedAt: new Date("2026-09-28T06:00:00.000Z"),
            completedAt: new Date("2026-09-28T06:00:00.200Z"),
            region: "IN"
        },
        {
            requestId: "R002",
            receivedAt: new Date("2026-09-28T06:01:00.000Z"),
            completedAt: new Date("2026-09-28T06:01:00.500Z"),
            region: "US"
        },
        {
            requestId: "R003",
            receivedAt: new Date("2026-09-28T06:02:00.000Z"),
            completedAt: new Date("2026-09-28T06:02:01.000Z"),
            region: "IN"
        }
    ];

    console.log(analyzeLogs(records));
}


// ============================================================================
// 17. PERFORMANCE MEASUREMENT
// ============================================================================

function performanceDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("17. PERFORMANCE CONSIDERATIONS");
    console.log("=".repeat(80));

    const values = Array.from(
        { length: 100000 },
        (_, index) =>
            new Date(
                Date.UTC(2026, 0, 1) +
                index * 60 * 1000
            )
    );

    const start = performance.now();

    const timestamps = values.map(
        value => value.getTime()
    );

    const elapsed = performance.now() - start;

    console.log("Processed:", timestamps.length);
    console.log("Elapsed milliseconds:", elapsed);

    // For large datasets:
    // - Store timestamps in compact numeric/database representations.
    // - Avoid repeatedly parsing identical strings.
    // - Sort once when interval processing permits it.
    // - Use indexed timestamp columns in databases.
    // - Be explicit about seconds versus milliseconds.
}


// ============================================================================
// 18. ERROR HANDLING
// ============================================================================

function errorHandlingDemo() {
    console.log("\n" + "=".repeat(80));
    console.log("18. ERROR HANDLING AND EDGE CASES");
    console.log("=".repeat(80));

    const invalidInputs = [
        "not-a-date",
        "2026-09-28T11:00:00",
        "2026-13-50T99:99:99Z"
    ];

    for (const input of invalidInputs) {
        try {
            const parsed = parseISODateTime(input);
            console.log(input, "->", parsed.toISOString());
        } catch (error) {
            console.log(
                input,
                "-> rejected:",
                error.name,
                error.message
            );
        }
    }

    try {
        new TimeInterval(
            new Date("2026-09-28T10:00:00Z"),
            new Date("2026-09-28T09:00:00Z")
        );
    } catch (error) {
        console.log(
            "Invalid interval rejected:",
            error.message
        );
    }
}


// ============================================================================
// 19. ASSERTIONS
// ============================================================================

function assert(condition, message) {
    if (!condition) {
        throw new Error(`Assertion failed: ${message}`);
    }
}

function runAssertions() {
    console.log("\n" + "=".repeat(80));
    console.log("19. BUILT-IN TESTS");
    console.log("=".repeat(80));

    const january31 = new Date("2026-01-31T00:00:00Z");
    const february = addMonthsUTC(january31, 1);

    assert(
        february.toISOString().startsWith("2026-02-28"),
        "January 31 + one month should clamp to February 28."
    );

    const interval = new TimeInterval(
        new Date("2026-09-28T09:00:00Z"),
        new Date("2026-09-28T10:00:00Z")
    );

    assert(
        interval.contains(new Date("2026-09-28T09:30:00Z")),
        "Interval should contain 09:30."
    );

    assert(
        !interval.contains(new Date("2026-09-28T10:00:00Z")),
        "Half-open interval should exclude its endpoint."
    );

    assert(
        median([10, 20, 30]) === 20,
        "Median calculation failed."
    );

    assert(
        percentile([10, 20, 30, 40, 50], 50) === 30,
        "P50 calculation failed."
    );

    try {
        new TimeInterval(
            new Date("2026-09-28T10:00:00Z"),
            new Date("2026-09-28T09:00:00Z")
        );

        throw new Error(
            "Invalid interval should have thrown."
        );
    } catch (error) {
        if (error.message === "Invalid interval should have thrown.") {
            throw error;
        }
    }

    console.log("All assertions passed.");
}


// ============================================================================
// 20. MAIN
// ============================================================================

function main() {
    console.log("DATE AND TIME ANALYTICS STUDY PROGRAM");
    console.log("JavaScript Date + Intl implementation");

    fundamentalsDemo();
    timestampDemo();
    componentDemo();
    durationDemo();
    calendarArithmeticDemo();
    monthArithmeticDemo();
    parsingDemo();
    timezoneDemo();
    utcFirstDemo();
    intervalDemo();
    intervalMergeDemo();
    businessDayDemo();
    eventDemo();
    scheduleDemo();
    rangeDemo();
    logAnalyticsDemo();
    performanceDemo();
    errorHandlingDemo();
    runAssertions();

    console.log("\n" + "=".repeat(80));
    console.log("END OF DATE AND TIME ANALYTICS PROGRAM");
    console.log("=".repeat(80));
}

main();
