/*
 * Date and Time Analytics: Industry-Style Event Scheduling and SLA System
 * =========================================================================
 *
 * C++17 case study:
 *
 * A distributed support platform receives events from users in different
 * regions. The system must:
 *
 * 1. Represent timestamps as UTC-based instants.
 * 2. Validate event intervals.
 * 3. Calculate elapsed durations.
 * 4. Detect overlapping maintenance windows.
 * 5. Merge overlapping windows.
 * 6. Calculate service availability coverage.
 * 7. Calculate response-time statistics.
 * 8. Calculate percentile latency.
 * 9. Validate business-day deadlines.
 * 10. Generate an operational report.
 *
 * C++17's standard chrono library provides strong duration and clock
 * abstractions, but portable IANA timezone database support is not available
 * in the same way as Python's zoneinfo or JavaScript's Intl API.
 *
 * This case study therefore models instants using std::chrono::system_clock
 * and handles calendar/business-day logic explicitly.
 *
 * Compile:
 *     g++ -std=c++17 -O2 -Wall -Wextra -pedantic main.cpp -o date_time_analytics
 */

#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

using Clock = std::chrono::system_clock;
using TimePoint = Clock::time_point;
using Milliseconds = std::chrono::milliseconds;
using Seconds = std::chrono::seconds;
using Minutes = std::chrono::minutes;
using Hours = std::chrono::hours;
using Days = std::chrono::duration<int, std::ratio<86400>>;


// ============================================================================
// 1. GENERAL DATE/TIME UTILITIES
// ============================================================================

TimePoint makeTimePoint(
    int year,
    unsigned month,
    unsigned day,
    int hour,
    int minute,
    int second
) {
    /*
     * C++17 does not provide a portable standard-library constructor that
     * directly builds a calendar date from year/month/day.
     *
     * For this self-contained case study, we use a civil-date conversion
     * algorithm based on Howard Hinnant's public-domain-style calendar
     * arithmetic approach.
     *
     * The returned value is treated as a UTC-like system_clock instant.
     */

    if (month < 1 || month > 12) {
        throw std::invalid_argument("Month must be 1..12.");
    }

    if (day < 1 || day > 31) {
        throw std::invalid_argument("Day must be 1..31.");
    }

    if (hour < 0 || hour > 23) {
        throw std::invalid_argument("Hour must be 0..23.");
    }

    if (minute < 0 || minute > 59) {
        throw std::invalid_argument("Minute must be 0..59.");
    }

    if (second < 0 || second > 59) {
        throw std::invalid_argument("Second must be 0..59.");
    }

    int adjustedYear = year - (month <= 2 ? 1 : 0);

    const int era =
        (adjustedYear >= 0 ? adjustedYear : adjustedYear - 399) / 400;

    const unsigned yearOfEra =
        static_cast<unsigned>(adjustedYear - era * 400);

    const unsigned adjustedMonth =
        month + (month > 2 ? -3 : 9);

    const unsigned dayOfYear =
        (153 * adjustedMonth + 2) / 5 + day - 1;

    const unsigned dayOfEra =
        yearOfEra * 365
        + yearOfEra / 4
        - yearOfEra / 100
        + dayOfYear;

    const long long daysSinceEpoch =
        static_cast<long long>(era) * 146097LL
        + static_cast<long long>(dayOfEra)
        - 719468LL;

    const auto dayDuration =
        std::chrono::duration_cast<Clock::duration>(
            Days(static_cast<int>(daysSinceEpoch))
        );

    const auto timeDuration =
        std::chrono::duration_cast<Clock::duration>(
            Hours(hour)
            + Minutes(minute)
            + Seconds(second)
        );

    return TimePoint(dayDuration + timeDuration);
}


// ============================================================================
// 2. FORMAT TIMESTAMP
// ============================================================================

std::string formatTimePoint(const TimePoint& timePoint) {
    /*
     * system_clock::to_time_t converts the instant into time_t.
     * gmtime is used to render it as UTC.
     *
     * gmtime is sufficient for this educational single-threaded report.
     * Production code should use a thread-safe platform/API equivalent when
     * shared mutable C runtime state is a concern.
     */

    std::time_t rawTime = Clock::to_time_t(timePoint);

    std::tm utcTime{};

#ifdef _WIN32
    gmtime_s(&utcTime, &rawTime);
#else
    gmtime_r(&rawTime, &utcTime);
#endif

    std::ostringstream output;

    output << std::put_time(
        &utcTime,
        "%Y-%m-%d %H:%M:%S UTC"
    );

    return output.str();
}


// ============================================================================
// 3. DURATION FORMATTING
// ============================================================================

std::string formatDuration(Milliseconds duration) {
    const auto totalMilliseconds = duration.count();

    const auto hours =
        totalMilliseconds / (60LL * 60LL * 1000LL);

    const auto remainingAfterHours =
        totalMilliseconds % (60LL * 60LL * 1000LL);

    const auto minutes =
        remainingAfterHours / (60LL * 1000LL);

    const auto remainingAfterMinutes =
        remainingAfterHours % (60LL * 1000LL);

    const auto seconds =
        remainingAfterMinutes / 1000LL;

    const auto milliseconds =
        remainingAfterMinutes % 1000LL;

    std::ostringstream output;

    output
        << hours << "h "
        << minutes << "m "
        << seconds << "s "
        << milliseconds << "ms";

    return output.str();
}


// ============================================================================
// 4. INTERVAL CLASS
// ============================================================================

class Interval {
public:
    /*
     * The interval follows the half-open convention [start, end).
     *
     * This means:
     *   start <= instant < end
     *
     * Two intervals [09:00, 10:00) and [10:00, 11:00) are adjacent but do
     * not overlap.
     */

    Interval(TimePoint start, TimePoint end)
        : start_(start), end_(end) {

        if (end_ <= start_) {
            throw std::invalid_argument(
                "Interval end must be after start."
            );
        }
    }

    TimePoint start() const {
        return start_;
    }

    TimePoint end() const {
        return end_;
    }

    Milliseconds duration() const {
        return std::chrono::duration_cast<Milliseconds>(
            end_ - start_
        );
    }

    bool contains(TimePoint instant) const {
        return start_ <= instant && instant < end_;
    }

    bool overlaps(const Interval& other) const {
        return (
            start_ < other.end_
            && other.start_ < end_
        );
    }

    std::optional<Interval> intersection(
        const Interval& other
    ) const {
        if (!overlaps(other)) {
            return std::nullopt;
        }

        const auto intersectionStart =
            std::max(start_, other.start_);

        const auto intersectionEnd =
            std::min(end_, other.end_);

        return Interval(
            intersectionStart,
            intersectionEnd
        );
    }

private:
    TimePoint start_;
    TimePoint end_;
};


// ============================================================================
// 5. INTERVAL MERGING
// ============================================================================

std::vector<Interval> mergeIntervals(
    std::vector<Interval> intervals,
    bool mergeAdjacent = true
) {
    if (intervals.empty()) {
        return {};
    }

    std::sort(
        intervals.begin(),
        intervals.end(),
        [](const Interval& first, const Interval& second) {
            return first.start() < second.start();
        }
    );

    std::vector<Interval> merged;

    merged.push_back(intervals.front());

    for (std::size_t index = 1; index < intervals.size(); ++index) {
        const Interval& current = intervals[index];
        const Interval& previous = merged.back();

        const bool overlaps = previous.overlaps(current);

        const bool adjacent =
            previous.end() == current.start();

        if (overlaps || (mergeAdjacent && adjacent)) {
            const TimePoint newEnd =
                std::max(previous.end(), current.end());

            merged.back() =
                Interval(previous.start(), newEnd);
        } else {
            merged.push_back(current);
        }
    }

    return merged;
}


// ============================================================================
// 6. TOTAL UNION COVERAGE
// ============================================================================

Milliseconds calculateUnionDuration(
    const std::vector<Interval>& intervals
) {
    const auto merged = mergeIntervals(intervals);

    Milliseconds total{0};

    for (const auto& interval : merged) {
        total += interval.duration();
    }

    return total;
}


// ============================================================================
// 7. BUSINESS-DAY UTILITIES
// ============================================================================

int weekdayFromTimePoint(TimePoint timePoint) {
    /*
     * 1970-01-01 was Thursday.
     *
     * Return values:
     *   0 = Sunday
     *   1 = Monday
     *   ...
     *   6 = Saturday
     */

    const auto days =
        std::chrono::duration_cast<Days>(
            timePoint.time_since_epoch()
        ).count();

    long long weekday =
        (days + 4) % 7;

    if (weekday < 0) {
        weekday += 7;
    }

    return static_cast<int>(weekday);
}

bool isBusinessDay(TimePoint timePoint) {
    const int weekday = weekdayFromTimePoint(timePoint);

    return weekday >= 1 && weekday <= 5;
}

TimePoint addBusinessDays(
    TimePoint startingPoint,
    int numberOfDays,
    const std::vector<TimePoint>& holidays
) {
    if (numberOfDays == 0) {
        return startingPoint;
    }

    const int direction =
        numberOfDays > 0 ? 1 : -1;

    int remaining =
        std::abs(numberOfDays);

    TimePoint current = startingPoint;

    auto isHoliday = [&](TimePoint value) {
        /*
         * Holiday comparison is based on the represented day boundary in this
         * simplified UTC case study.
         */
        return std::any_of(
            holidays.begin(),
            holidays.end(),
            [&](TimePoint holiday) {
                return (
                    std::chrono::duration_cast<Days>(
                        current.time_since_epoch()
                    ).count()
                    ==
                    std::chrono::duration_cast<Days>(
                        holiday.time_since_epoch()
                    ).count()
                );
            }
        );
    };

    while (remaining > 0) {
        current += Days(direction);

        if (isBusinessDay(current) && !isHoliday(current)) {
            --remaining;
        }
    }

    return current;
}


// ============================================================================
// 8. EVENT RECORD
// ============================================================================

struct EventRecord {
    std::string id;
    std::string name;
    std::string region;
    TimePoint startedAt;
    TimePoint completedAt;

    Milliseconds latency() const {
        if (completedAt < startedAt) {
            throw std::logic_error(
                "Event completed before it started."
            );
        }

        return std::chrono::duration_cast<Milliseconds>(
            completedAt - startedAt
        );
    }
};


// ============================================================================
// 9. PERCENTILE
// ============================================================================

double percentile(
    std::vector<double> values,
    double percentileValue
) {
    if (values.empty()) {
        throw std::invalid_argument(
            "Cannot calculate percentile of empty data."
        );
    }

    if (
        percentileValue < 0.0
        || percentileValue > 100.0
    ) {
        throw std::invalid_argument(
            "Percentile must be between 0 and 100."
        );
    }

    std::sort(values.begin(), values.end());

    if (values.size() == 1) {
        return values.front();
    }

    const double position =
        (static_cast<double>(values.size()) - 1.0)
        * percentileValue
        / 100.0;

    const std::size_t lower =
        static_cast<std::size_t>(
            std::floor(position)
        );

    const std::size_t upper =
        static_cast<std::size_t>(
            std::ceil(position)
        );

    if (lower == upper) {
        return values[lower];
    }

    const double fraction =
        position - static_cast<double>(lower);

    return (
        values[lower]
        + (values[upper] - values[lower]) * fraction
    );
}


// ============================================================================
// 10. MEDIAN
// ============================================================================

double median(std::vector<double> values) {
    if (values.empty()) {
        throw std::invalid_argument(
            "Cannot calculate median of empty data."
        );
    }

    std::sort(values.begin(), values.end());

    const std::size_t middle =
        values.size() / 2;

    if (values.size() % 2 == 0) {
        return (
            values[middle - 1]
            + values[middle]
        ) / 2.0;
    }

    return values[middle];
}


// ============================================================================
// 11. ANALYTICS REPORT
// ============================================================================

struct AnalyticsReport {
    std::size_t recordCount{};
    double meanMilliseconds{};
    double medianMilliseconds{};
    double p95Milliseconds{};
    double maximumMilliseconds{};
};

AnalyticsReport analyzeEvents(
    const std::vector<EventRecord>& events
) {
    if (events.empty()) {
        return {};
    }

    std::vector<double> latencies;

    latencies.reserve(events.size());

    for (const auto& event : events) {
        const auto duration = event.latency();

        if (duration.count() < 0) {
            throw std::logic_error(
                "Negative latency detected."
            );
        }

        latencies.push_back(
            static_cast<double>(duration.count())
        );
    }

    const double total =
        std::accumulate(
            latencies.begin(),
            latencies.end(),
            0.0
        );

    return AnalyticsReport{
        events.size(),
        total / static_cast<double>(events.size()),
        median(latencies),
        percentile(latencies, 95.0),
        *std::max_element(
            latencies.begin(),
            latencies.end()
        )
    };
}


// ============================================================================
// 12. REGION ANALYTICS
// ============================================================================

struct RegionalReport {
    std::string region;
    std::size_t count{};
    double meanMilliseconds{};
    double p95Milliseconds{};
};

std::vector<RegionalReport> analyzeByRegion(
    const std::vector<EventRecord>& events
) {
    std::map<std::string, std::vector<double>> groups;

    for (const auto& event : events) {
        groups[event.region].push_back(
            static_cast<double>(
                event.latency().count()
            )
        );
    }

    std::vector<RegionalReport> result;

    for (const auto& [region, values] : groups) {
        const double total =
            std::accumulate(
                values.begin(),
                values.end(),
                0.0
            );

        result.push_back(
            RegionalReport{
                region,
                values.size(),
                total / static_cast<double>(values.size()),
                percentile(values, 95.0)
            }
        );
    }

    return result;
}


// ============================================================================
// 13. SLA COMPLIANCE
// ============================================================================

double slaCompliance(
    const std::vector<EventRecord>& events,
    Milliseconds threshold
) {
    if (events.empty()) {
        return 0.0;
    }

    std::size_t successful = 0;

    for (const auto& event : events) {
        if (event.latency() <= threshold) {
            ++successful;
        }
    }

    return (
        static_cast<double>(successful)
        / static_cast<double>(events.size())
    ) * 100.0;
}


// ============================================================================
// 14. MAINTENANCE WINDOWS
// ============================================================================

struct MaintenanceWindow {
    std::string system;
    Interval interval;
    std::string reason;
};

void printMaintenanceReport(
    const std::vector<MaintenanceWindow>& windows
) {
    std::cout << "\nMaintenance windows:\n";

    for (const auto& window : windows) {
        std::cout
            << "  System: " << window.system << "\n"
            << "  Reason: " << window.reason << "\n"
            << "  Start: "
            << formatTimePoint(window.interval.start())
            << "\n"
            << "  End: "
            << formatTimePoint(window.interval.end())
            << "\n"
            << "  Duration: "
            << formatDuration(window.interval.duration())
            << "\n\n";
    }
}


// ============================================================================
// 15. CONFLICT DETECTION
// ============================================================================

std::vector<std::pair<MaintenanceWindow, MaintenanceWindow>>
findMaintenanceConflicts(
    const std::vector<MaintenanceWindow>& windows
) {
    std::vector<
        std::pair<MaintenanceWindow, MaintenanceWindow>
    > conflicts;

    for (std::size_t i = 0; i < windows.size(); ++i) {
        for (std::size_t j = i + 1; j < windows.size(); ++j) {
            if (
                windows[i].system == windows[j].system
                && windows[i].interval.overlaps(
                    windows[j].interval
                )
            ) {
                conflicts.emplace_back(
                    windows[i],
                    windows[j]
                );
            }
        }
    }

    return conflicts;
}


// ============================================================================
// 16. TEST FUNCTIONS
// ============================================================================

void expect(
    bool condition,
    const std::string& message
) {
    if (!condition) {
        throw std::runtime_error(
            "TEST FAILED: " + message
        );
    }
}

void runTests() {
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "RUNNING TESTS\n";
    std::cout << std::string(80, '=') << "\n";

    const auto start =
        makeTimePoint(
            2026,
            9,
            28,
            9,
            0,
            0
        );

    const auto end =
        start + Hours(1);

    Interval interval(start, end);

    expect(
        interval.duration() == Milliseconds(3600000),
        "One-hour interval duration is incorrect."
    );

    expect(
        interval.contains(start),
        "Interval should contain its start."
    );

    expect(
        !interval.contains(end),
        "Half-open interval should exclude its end."
    );

    const auto overlapping =
        Interval(
            start + Minutes(30),
            end + Minutes(30)
        );

    expect(
        interval.overlaps(overlapping),
        "Intervals should overlap."
    );

    const auto intersection =
        interval.intersection(overlapping);

    expect(
        intersection.has_value(),
        "Intersection should exist."
    );

    expect(
        intersection->duration()
        == Milliseconds(1800000),
        "Intersection should last 30 minutes."
    );

    const auto firstMonth =
        makeTimePoint(
            2026,
            1,
            31,
            0,
            0,
            0
        );

    /*
     * This case study intentionally does not implement month arithmetic as
     * simple duration arithmetic. A month has variable length, which is one
     * reason calendar arithmetic needs its own model.
     */
    expect(
        firstMonth != TimePoint{},
        "Calendar conversion produced an invalid epoch result."
    );

    const std::vector<double> sample{
        10.0, 20.0, 30.0, 40.0, 50.0
    };

    expect(
        percentile(sample, 50.0) == 30.0,
        "P50 calculation failed."
    );

    expect(
        median(sample) == 30.0,
        "Median calculation failed."
    );

    std::cout << "All tests passed.\n";
}


// ============================================================================
// 17. MAIN CASE STUDY
// ============================================================================

int main() {
    try {
        std::cout
            << "DATE AND TIME ANALYTICS\n"
            << "C++17 Distributed Event and SLA Case Study\n";

        // --------------------------------------------------------------------
        // Basic timestamp construction
        // --------------------------------------------------------------------

        const auto serviceStart =
            makeTimePoint(
                2026,
                9,
                28,
                9,
                0,
                0
            );

        const auto serviceEnd =
            serviceStart + Hours(8);

        std::cout
            << "\nService window:\n"
            << "  Start: "
            << formatTimePoint(serviceStart)
            << "\n"
            << "  End: "
            << formatTimePoint(serviceEnd)
            << "\n"
            << "  Duration: "
            << formatDuration(
                std::chrono::duration_cast<Milliseconds>(
                    serviceEnd - serviceStart
                )
            )
            << "\n";

        // --------------------------------------------------------------------
        // Maintenance windows
        // --------------------------------------------------------------------

        const std::vector<MaintenanceWindow> maintenanceWindows{
            {
                "API",
                Interval(
                    makeTimePoint(
                        2026, 9, 28, 10, 0, 0
                    ),
                    makeTimePoint(
                        2026, 9, 28, 11, 30, 0
                    )
                ),
                "API deployment"
            },
            {
                "API",
                Interval(
                    makeTimePoint(
                        2026, 9, 28, 11, 0, 0
                    ),
                    makeTimePoint(
                        2026, 9, 28, 12, 0, 0
                    )
                ),
                "Database migration"
            },
            {
                "WEB",
                Interval(
                    makeTimePoint(
                        2026, 9, 28, 13, 0, 0
                    ),
                    makeTimePoint(
                        2026, 9, 28, 14, 0, 0
                    )
                ),
                "Frontend deployment"
            },
            {
                "WEB",
                Interval(
                    makeTimePoint(
                        2026, 9, 28, 15, 0, 0
                    ),
                    makeTimePoint(
                        2026, 9, 28, 16, 0, 0
                    )
                ),
                "Cache maintenance"
            }
        };

        printMaintenanceReport(maintenanceWindows);

        const auto conflicts =
            findMaintenanceConflicts(
                maintenanceWindows
            );

        std::cout
            << "Maintenance conflicts: "
            << conflicts.size()
            << "\n";

        for (const auto& [first, second] : conflicts) {
            std::cout
                << "  Conflict on system "
                << first.system
                << ":\n"
                << "    "
                << formatTimePoint(
                    first.interval.start()
                )
                << " - "
                << formatTimePoint(
                    first.interval.end()
                )
                << "\n"
                << "    "
                << formatTimePoint(
                    second.interval.start()
                )
                << " - "
                << formatTimePoint(
                    second.interval.end()
                )
                << "\n";
        }

        // --------------------------------------------------------------------
        // Merge windows for API availability calculations
        // --------------------------------------------------------------------

        std::vector<Interval> apiIntervals;

        for (const auto& window : maintenanceWindows) {
            if (window.system == "API") {
                apiIntervals.push_back(window.interval);
            }
        }

        const auto mergedApi =
            mergeIntervals(apiIntervals);

        std::cout
            << "\nMerged API maintenance windows:\n";

        for (const auto& interval : mergedApi) {
            std::cout
                << "  "
                << formatTimePoint(interval.start())
                << " -> "
                << formatTimePoint(interval.end())
                << " ("
                << formatDuration(interval.duration())
                << ")\n";
        }

        const auto totalApiDowntime =
            calculateUnionDuration(apiIntervals);

        std::cout
            << "Total API maintenance coverage: "
            << formatDuration(totalApiDowntime)
            << "\n";

        // --------------------------------------------------------------------
        // Event stream
        // --------------------------------------------------------------------

        const std::vector<EventRecord> events{
            {
                "REQ-001",
                "Authentication",
                "IN",
                makeTimePoint(
                    2026, 9, 28, 6, 0, 0
                ),
                makeTimePoint(
                    2026, 9, 28, 6, 0, 0
                ) + Milliseconds(200)
            },
            {
                "REQ-002",
                "Report",
                "US",
                makeTimePoint(
                    2026, 9, 28, 6, 1, 0
                ),
                makeTimePoint(
                    2026, 9, 28, 6, 1, 0
                ) + Milliseconds(500)
            },
            {
                "REQ-003",
                "Database",
                "IN",
                makeTimePoint(
                    2026, 9, 28, 6, 2, 0
                ),
                makeTimePoint(
                    2026, 9, 28, 6, 2, 1
                )
            },
            {
                "REQ-004",
                "Search",
                "EU",
                makeTimePoint(
                    2026, 9, 28, 6, 3, 0
                ),
                makeTimePoint(
                    2026, 9, 28, 6, 3, 0
                ) + Milliseconds(120)
            },
            {
                "REQ-005",
                "Export",
                "IN",
                makeTimePoint(
                    2026, 9, 28, 6, 4, 0
                ),
                makeTimePoint(
                    2026, 9, 28, 6, 4, 2
                )
            }
        };

        for (const auto& event : events) {
            std::cout
                << "\nEvent "
                << event.id
                << " [" << event.region << "] "
                << event.name
                << "\n  Start: "
                << formatTimePoint(event.startedAt)
                << "\n  End: "
                << formatTimePoint(event.completedAt)
                << "\n  Latency: "
                << formatDuration(event.latency())
                << "\n";
        }

        // --------------------------------------------------------------------
        // Global analytics
        // --------------------------------------------------------------------

        const auto report =
            analyzeEvents(events);

        std::cout
            << "\nGlobal analytics:\n"
            << "  Records: "
            << report.recordCount
            << "\n"
            << "  Mean latency: "
            << report.meanMilliseconds
            << " ms\n"
            << "  Median latency: "
            << report.medianMilliseconds
            << " ms\n"
            << "  P95 latency: "
            << report.p95Milliseconds
            << " ms\n"
            << "  Maximum latency: "
            << report.maximumMilliseconds
            << " ms\n";

        // --------------------------------------------------------------------
        // Regional analytics
        // --------------------------------------------------------------------

        const auto regionalReports =
            analyzeByRegion(events);

        std::cout
            << "\nRegional analytics:\n";

        for (const auto& regional : regionalReports) {
            std::cout
                << "  Region: "
                << regional.region
                << "\n"
                << "    Count: "
                << regional.count
                << "\n"
                << "    Mean: "
                << regional.meanMilliseconds
                << " ms\n"
                << "    P95: "
                << regional.p95Milliseconds
                << " ms\n";
        }

        // --------------------------------------------------------------------
        // SLA
        // --------------------------------------------------------------------

        const Milliseconds slaThreshold(1000);

        std::cout
            << "\nSLA threshold: "
            << slaThreshold.count()
            << " ms\n"
            << "SLA compliance: "
            << slaCompliance(
                events,
                slaThreshold
            )
            << "%\n";

        // --------------------------------------------------------------------
        // Business deadline example
        // --------------------------------------------------------------------

        const auto deadlineStart =
            makeTimePoint(
                2026, 9, 28, 9, 0, 0
            );

        const std::vector<TimePoint> holidays{
            makeTimePoint(
                2026, 10, 2, 0, 0, 0
            )
        };

        const auto deadline =
            addBusinessDays(
                deadlineStart,
                5,
                holidays
            );

        std::cout
            << "\nBusiness deadline:\n"
            << "  Start: "
            << formatTimePoint(deadlineStart)
            << "\n"
            << "  Five business days later: "
            << formatTimePoint(deadline)
            << "\n";

        // --------------------------------------------------------------------
        // Tests
        // --------------------------------------------------------------------

        runTests();

        // --------------------------------------------------------------------
        // Architectural observations
        // --------------------------------------------------------------------

        std::cout
            << "\nDesign observations:\n"
            << "  * Instants are represented using system_clock::time_point.\n"
            << "  * Durations use chrono duration types.\n"
            << "  * Intervals use a half-open [start, end) model.\n"
            << "  * Sorting enables efficient interval merging.\n"
            << "  * Percentiles require ordered latency data.\n"
            << "  * Calendar operations are distinct from elapsed-duration operations.\n"
            << "  * Timezone database handling requires a dedicated timezone-aware\n"
            << "    facility when full IANA timezone behavior is required.\n";

        return 0;
    }
    catch (const std::exception& error) {
        std::cerr
            << "\nFatal error: "
            << error.what()
            << "\n";

        return 1;
    }
}
