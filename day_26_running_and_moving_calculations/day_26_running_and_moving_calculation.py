"""
Running and Moving Calculations
================================

A comprehensive standalone study file covering:

1. Running totals and cumulative sums
2. Running counts and cumulative counts
3. Running minimums and maximums
4. Running averages
5. Weighted cumulative metrics
6. Moving windows
7. Simple moving averages
8. Moving sums, counts, minimums, and maximums
9. Weighted moving averages
10. Exponentially weighted moving averages
11. Rolling statistics
12. Expanding statistics
13. Time-series calculations
14. Warm-up periods and insufficient-window behavior
15. Missing values
16. Validation and numerical edge cases
17. Streaming and memory-efficient calculations
18. Prefix sums and range queries
19. Online algorithms
20. Performance comparisons
21. Financial, operational, scientific, and telemetry applications
22. Testing and production-oriented design

The examples use only the Python standard library.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import sqrt
from statistics import mean
from typing import Iterable, Iterator, Optional, Sequence


# ---------------------------------------------------------------------------
# 1. FUNDAMENTAL CONCEPTS
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def running_total(values: Iterable[float]) -> list[float]:
    """
    Return the cumulative sum.

    Example:
        [10, 20, 30] -> [10, 30, 60]

    Time: O(n)
    Space: O(n) for the returned result.
    """
    totals: list[float] = []
    total = 0.0

    for value in values:
        total += value
        totals.append(total)

    return totals


def running_count(values: Iterable[object]) -> list[int]:
    """Return the number of observations seen at each position."""
    counts: list[int] = []
    count = 0

    for _ in values:
        count += 1
        counts.append(count)

    return counts


def running_minimum(values: Iterable[float]) -> list[float]:
    """Return the minimum value observed so far."""
    result: list[float] = []
    current_min: Optional[float] = None

    for value in values:
        if current_min is None or value < current_min:
            current_min = value
        result.append(current_min)

    return result


def running_maximum(values: Iterable[float]) -> list[float]:
    """Return the maximum value observed so far."""
    result: list[float] = []
    current_max: Optional[float] = None

    for value in values:
        if current_max is None or value > current_max:
            current_max = value
        result.append(current_max)

    return result


def running_average(values: Iterable[float]) -> list[float]:
    """
    Calculate an online cumulative average.

    The formula is:

        average_n = average_(n-1) + (x_n - average_(n-1)) / n

    This avoids repeatedly summing the entire prefix.
    """
    result: list[float] = []
    average = 0.0
    count = 0

    for value in values:
        count += 1
        average += (value - average) / count
        result.append(average)

    return result


# ---------------------------------------------------------------------------
# 2. BASIC RUNNING CALCULATIONS
# ---------------------------------------------------------------------------

def demonstrate_basic_running_calculations() -> None:
    section("1. BASIC RUNNING CALCULATIONS")

    values = [10, 20, 15, 30, 25]

    print("Input:", values)
    print("Running total:", running_total(values))
    print("Running count:", running_count(values))
    print("Running minimum:", running_minimum(values))
    print("Running maximum:", running_maximum(values))
    print("Running average:", running_average(values))

    # A running calculation is cumulative: every result depends on all
    # observations from the beginning through the current observation.

    # The running total at position i is:
    #     total[i] = values[0] + ... + values[i]

    # The running average at position i is:
    #     average[i] = total[i] / (i + 1)


# ---------------------------------------------------------------------------
# 3. CUMULATIVE METRICS WITH REALISTIC DATA
# ---------------------------------------------------------------------------

def cumulative_percentage(values: Sequence[float]) -> list[float]:
    """Return each cumulative total as a percentage of the final total."""
    if not values:
        return []

    total = sum(values)

    if total == 0:
        return [0.0 for _ in values]

    cumulative = running_total(values)
    return [value / total * 100 for value in cumulative]


def cumulative_growth_rates(values: Sequence[float]) -> list[Optional[float]]:
    """
    Return percentage change from the first value to each later value.

    None is used for the first observation because there is no earlier
    reference point.
    """
    if not values:
        return []

    first = values[0]
    result: list[Optional[float]] = [None]

    for value in values[1:]:
        if first == 0:
            result.append(None)
        else:
            result.append((value - first) / first * 100)

    return result


def demonstrate_cumulative_metrics() -> None:
    section("2. CUMULATIVE METRICS")

    daily_sales = [1200, 950, 1400, 1100, 1800, 1550]

    totals = running_total(daily_sales)
    percentages = cumulative_percentage(daily_sales)
    growth = cumulative_growth_rates(daily_sales)

    print("Daily sales:", daily_sales)
    print("Cumulative sales:", totals)
    print("Share of final total (%):", [round(x, 2) for x in percentages])
    print("Growth from first day (%):", growth)


# ---------------------------------------------------------------------------
# 4. GENERIC RUNNING METRICS
# ---------------------------------------------------------------------------

@dataclass
class RunningStatistics:
    """Stateful online statistics for a stream of numeric observations."""

    count: int = 0
    total: float = 0.0
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    average: float = 0.0

    def update(self, value: float) -> None:
        """Consume one new observation."""
        if self.count == 0:
            self.minimum = value
            self.maximum = value
        else:
            self.minimum = min(self.minimum, value)
            self.maximum = max(self.maximum, value)

        self.count += 1
        self.total += value

        # Numerically stable online mean update.
        self.average += (value - self.average) / self.count

    def snapshot(self) -> dict[str, Optional[float]]:
        return {
            "count": self.count,
            "total": self.total,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "average": self.average if self.count else None,
        }


def demonstrate_running_statistics() -> None:
    section("3. STATEFUL RUNNING STATISTICS")

    statistics = RunningStatistics()

    for value in [8, 12, 7, 20, 15]:
        statistics.update(value)
        print(f"After {value:>2}: {statistics.snapshot()}")


# ---------------------------------------------------------------------------
# 5. MOVING WINDOWS
# ---------------------------------------------------------------------------

def moving_sum(values: Sequence[float], window: int) -> list[float]:
    """
    Return sums of complete fixed-size windows.

    Example:
        values = [1, 2, 3, 4, 5], window = 3
        -> [6, 9, 12]

    A moving window differs from a running calculation because old
    observations leave the calculation when the window advances.
    """
    if window <= 0:
        raise ValueError("window must be positive")

    if window > len(values):
        return []

    result: list[float] = []
    current_sum = sum(values[:window])
    result.append(current_sum)

    for index in range(window, len(values)):
        current_sum += values[index]
        current_sum -= values[index - window]
        result.append(current_sum)

    return result


def moving_average(
    values: Sequence[float],
    window: int,
    min_periods: Optional[int] = None,
) -> list[Optional[float]]:
    """
    Calculate a simple moving average.

    If min_periods is omitted, a full window is required.

    If min_periods is smaller than the window, warm-up observations can
    produce partial-window averages.
    """
    if window <= 0:
        raise ValueError("window must be positive")

    if min_periods is None:
        min_periods = window

    if min_periods <= 0 or min_periods > window:
        raise ValueError("min_periods must be between 1 and window")

    result: list[Optional[float]] = []
    current_sum = 0.0
    values_queue: deque[float] = deque()

    for value in values:
        values_queue.append(value)
        current_sum += value

        if len(values_queue) > window:
            current_sum -= values_queue.popleft()

        if len(values_queue) >= min_periods:
            result.append(current_sum / len(values_queue))
        else:
            result.append(None)

    return result


def moving_minimum(values: Sequence[float], window: int) -> list[float]:
    """
    Naive moving minimum.

    This is intentionally simple and has O(n * window) worst-case time.
    A monotonic deque can reduce this to O(n), demonstrated later.
    """
    if window <= 0:
        raise ValueError("window must be positive")

    if window > len(values):
        return []

    return [
        min(values[index - window + 1:index + 1])
        for index in range(window - 1, len(values))
    ]


def moving_maximum(values: Sequence[float], window: int) -> list[float]:
    """Naive moving maximum with O(n * window) worst-case time."""
    if window <= 0:
        raise ValueError("window must be positive")

    if window > len(values):
        return []

    return [
        max(values[index - window + 1:index + 1])
        for index in range(window - 1, len(values))
    ]


def demonstrate_moving_windows() -> None:
    section("4. MOVING WINDOWS")

    values = [10, 20, 30, 40, 50, 60]

    print("Values:", values)
    print("Window size:", 3)
    print("Moving sums:", moving_sum(values, 3))
    print("Moving averages:", moving_average(values, 3))
    print("Moving minimums:", moving_minimum(values, 3))
    print("Moving maximums:", moving_maximum(values, 3))

    print(
        "Partial-window averages:",
        moving_average(values, 3, min_periods=1),
    )


# ---------------------------------------------------------------------------
# 6. WEIGHTED MOVING AVERAGE
# ---------------------------------------------------------------------------

def weighted_moving_average(
    values: Sequence[float],
    weights: Sequence[float],
) -> list[float]:
    """
    Calculate a weighted moving average.

    The most recent observation can receive the largest weight.

    For weights [1, 2, 3] and values [10, 20, 30]:

        (10*1 + 20*2 + 30*3) / (1+2+3)
    """
    if not weights:
        raise ValueError("weights cannot be empty")

    if len(weights) > len(values):
        return []

    if any(weight < 0 for weight in weights):
        raise ValueError("weights cannot be negative")

    weight_total = sum(weights)

    if weight_total == 0:
        raise ValueError("weights must have a positive total")

    window = len(weights)
    result: list[float] = []

    for index in range(window - 1, len(values)):
        data_window = values[index - window + 1:index + 1]
        weighted_sum = sum(
            value * weight
            for value, weight in zip(data_window, weights)
        )
        result.append(weighted_sum / weight_total)

    return result


# ---------------------------------------------------------------------------
# 7. EXPONENTIALLY WEIGHTED MOVING AVERAGE
# ---------------------------------------------------------------------------

def exponential_moving_average(
    values: Sequence[float],
    alpha: float,
) -> list[float]:
    """
    Calculate an exponentially weighted moving average.

    Formula:

        EMA_t = alpha * x_t + (1 - alpha) * EMA_(t-1)

    alpha close to 1 reacts quickly.
    alpha close to 0 produces more smoothing.
    """
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be greater than 0 and at most 1")

    if not values:
        return []

    result = [float(values[0])]

    for value in values[1:]:
        previous = result[-1]
        result.append(alpha * value + (1 - alpha) * previous)

    return result


def demonstrate_weighted_methods() -> None:
    section("5. WEIGHTED AND EXPONENTIAL MOVING AVERAGES")

    values = [100, 105, 103, 110, 108, 115, 112]

    print("Values:", values)
    print(
        "Weighted moving average:",
        [round(x, 3) for x in weighted_moving_average(values, [1, 2, 3])],
    )
    print(
        "EMA alpha=0.2:",
        [round(x, 3) for x in exponential_moving_average(values, 0.2)],
    )
    print(
        "EMA alpha=0.7:",
        [round(x, 3) for x in exponential_moving_average(values, 0.7)],
    )


# ---------------------------------------------------------------------------
# 8. ROLLING VARIANCE AND STANDARD DEVIATION
# ---------------------------------------------------------------------------

def moving_standard_deviation(
    values: Sequence[float],
    window: int,
    sample: bool = False,
) -> list[float]:
    """
    Calculate rolling standard deviation.

    This direct implementation is designed for clarity.

    Population variance:
        sum((x - mean)^2) / n

    Sample variance:
        sum((x - mean)^2) / (n - 1)
    """
    if window <= 0:
        raise ValueError("window must be positive")

    if window > len(values):
        return []

    if sample and window < 2:
        raise ValueError("sample standard deviation requires window >= 2")

    result: list[float] = []

    for index in range(window - 1, len(values)):
        window_values = values[index - window + 1:index + 1]
        average = mean(window_values)
        squared_deviations = [
            (value - average) ** 2
            for value in window_values
        ]

        denominator = window - 1 if sample else window
        variance = sum(squared_deviations) / denominator
        result.append(sqrt(variance))

    return result


# ---------------------------------------------------------------------------
# 9. PREFIX SUMS AND RANGE QUERIES
# ---------------------------------------------------------------------------

def prefix_sums(values: Sequence[float]) -> list[float]:
    """
    Build prefix sums with a leading zero.

    prefix[i] represents the sum of values before index i.

    Then:
        sum(values[left:right]) = prefix[right] - prefix[left]

    Range queries become O(1) after O(n) preprocessing.
    """
    prefix = [0.0]

    for value in values:
        prefix.append(prefix[-1] + value)

    return prefix


def range_sum(prefix: Sequence[float], left: int, right: int) -> float:
    """Return the half-open range sum [left, right)."""
    if left < 0 or right < left or right >= len(prefix):
        raise IndexError("invalid range")

    return prefix[right] - prefix[left]


def demonstrate_prefix_sums() -> None:
    section("6. PREFIX SUMS AND FAST RANGE QUERIES")

    values = [5, 8, 2, 10, 7, 4]
    prefix = prefix_sums(values)

    print("Values:", values)
    print("Prefix sums:", prefix)

    print("Sum of values[1:5]:", range_sum(prefix, 1, 5))
    print("Sum of values[2:4]:", range_sum(prefix, 2, 4))


# ---------------------------------------------------------------------------
# 10. MONOTONIC DEQUE FOR O(n) MOVING MIN/MAX
# ---------------------------------------------------------------------------

def optimized_moving_maximum(
    values: Sequence[float],
    window: int,
) -> list[float]:
    """
    O(n) moving maximum using a monotonic decreasing deque.

    The deque stores indices, not values.

    The front is always the index of the largest value in the current
    window.
    """
    if window <= 0:
        raise ValueError("window must be positive")

    if window > len(values):
        return []

    indices: deque[int] = deque()
    result: list[float] = []

    for index, value in enumerate(values):
        while indices and indices[0] <= index - window:
            indices.popleft()

        while indices and values[indices[-1]] <= value:
            indices.pop()

        indices.append(index)

        if index >= window - 1:
            result.append(values[indices[0]])

    return result


def optimized_moving_minimum(
    values: Sequence[float],
    window: int,
) -> list[float]:
    """O(n) moving minimum using a monotonic increasing deque."""
    if window <= 0:
        raise ValueError("window must be positive")

    if window > len(values):
        return []

    indices: deque[int] = deque()
    result: list[float] = []

    for index, value in enumerate(values):
        while indices and indices[0] <= index - window:
            indices.popleft()

        while indices and values[indices[-1]] >= value:
            indices.pop()

        indices.append(index)

        if index >= window - 1:
            result.append(values[indices[0]])

    return result


# ---------------------------------------------------------------------------
# 11. STREAMING MOVING AVERAGE
# ---------------------------------------------------------------------------

class StreamingMovingAverage:
    """
    Fixed-size streaming moving average.

    Only the current window is stored, so memory usage is O(window).
    """

    def __init__(self, window: int):
        if window <= 0:
            raise ValueError("window must be positive")

        self.window = window
        self.values: deque[float] = deque()
        self.total = 0.0

    def update(self, value: float) -> Optional[float]:
        """Add one value and return the current average when available."""
        self.values.append(value)
        self.total += value

        if len(self.values) > self.window:
            self.total -= self.values.popleft()

        if len(self.values) < self.window:
            return None

        return self.total / self.window


def demonstrate_streaming() -> None:
    section("7. STREAMING MOVING AVERAGE")

    calculator = StreamingMovingAverage(window=3)

    for value in [10, 20, 30, 40, 50]:
        average = calculator.update(value)
        print(f"Added {value:>2}; moving average = {average}")


# ---------------------------------------------------------------------------
# 12. SALES AND BUSINESS METRICS
# ---------------------------------------------------------------------------

def sales_dashboard_metrics(daily_sales: Sequence[float]) -> list[dict]:
    """
    Produce common daily business metrics.

    Each record contains:
    - day
    - sales
    - cumulative sales
    - seven-day moving average where available
    - cumulative average
    """
    cumulative = running_total(daily_sales)
    cumulative_avg = running_average(daily_sales)
    seven_day = moving_average(daily_sales, 7, min_periods=1)

    records = []

    for index, sales in enumerate(daily_sales, start=1):
        records.append(
            {
                "day": index,
                "sales": sales,
                "cumulative_sales": cumulative[index - 1],
                "cumulative_average": cumulative_avg[index - 1],
                "seven_day_average": seven_day[index - 1],
            }
        )

    return records


# ---------------------------------------------------------------------------
# 13. TIME-SERIES DATA WITH TIMESTAMPS
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Observation:
    timestamp: str
    value: float


def moving_average_observations(
    observations: Sequence[Observation],
    window: int,
) -> list[tuple[str, Optional[float]]]:
    """Attach a moving average to timestamped observations."""
    values = [observation.value for observation in observations]
    averages = moving_average(values, window)

    return [
        (observation.timestamp, average)
        for observation, average in zip(observations, averages)
    ]


# ---------------------------------------------------------------------------
# 14. MISSING VALUES
# ---------------------------------------------------------------------------

def running_average_ignore_missing(
    values: Sequence[Optional[float]],
) -> list[Optional[float]]:
    """
    Calculate cumulative averages while ignoring missing observations.

    None does not increase the valid observation count.
    """
    result: list[Optional[float]] = []
    total = 0.0
    count = 0

    for value in values:
        if value is not None:
            total += value
            count += 1

        result.append(total / count if count else None)

    return result


def moving_average_ignore_missing(
    values: Sequence[Optional[float]],
    window: int,
    min_periods: int = 1,
) -> list[Optional[float]]:
    """
    Moving average that ignores None values.

    The window is based on observations by position, while the average
    uses only valid numeric values.
    """
    if window <= 0:
        raise ValueError("window must be positive")

    if min_periods <= 0 or min_periods > window:
        raise ValueError("invalid min_periods")

    queue: deque[Optional[float]] = deque()
    total = 0.0
    valid_count = 0
    result: list[Optional[float]] = []

    for value in values:
        queue.append(value)

        if value is not None:
            total += value
            valid_count += 1

        if len(queue) > window:
            old = queue.popleft()

            if old is not None:
                total -= old
                valid_count -= 1

        if valid_count >= min_periods:
            result.append(total / valid_count)
        else:
            result.append(None)

    return result


# ---------------------------------------------------------------------------
# 15. EDGE CASES
# ---------------------------------------------------------------------------

def demonstrate_edge_cases() -> None:
    section("8. EDGE CASES")

    cases = {
        "empty input": [],
        "single value": [42],
        "negative values": [-5, -2, -8, 4],
        "zeros": [0, 0, 0],
        "mixed signs": [-10, 20, -5, 30],
        "repeated values": [7, 7, 7, 7],
    }

    for name, values in cases.items():
        print(f"\n{name}: {values}")
        print("  running total:", running_total(values))
        print("  running average:", running_average(values))

        if values:
            print("  moving average:", moving_average(values, min(2, len(values))))

    print("\nWindow larger than input:")
    print(moving_average([1, 2], 5))

    print("\nInvalid window demonstration:")
    try:
        moving_average([1, 2, 3], 0)
    except ValueError as error:
        print("Caught:", error)


# ---------------------------------------------------------------------------
# 16. PERFORMANCE COMPARISON
# ---------------------------------------------------------------------------

def naive_running_total(values: Sequence[float]) -> list[float]:
    """
    Educationally naive cumulative sum.

    It repeatedly sums the prefix, resulting in O(n^2) work.
    """
    return [
        sum(values[:index + 1])
        for index in range(len(values))
    ]


def optimized_running_total(values: Sequence[float]) -> list[float]:
    """O(n) cumulative sum."""
    return running_total(values)


# ---------------------------------------------------------------------------
# 17. ONLINE VARIANCE USING WELFORD'S ALGORITHM
# ---------------------------------------------------------------------------

@dataclass
class OnlineVariance:
    """
    Numerically stable online variance calculator using Welford's method.

    State:
        count = number of observations
        mean = current mean
        m2 = sum of squared deviations from the current mean

    Population variance = m2 / count
    Sample variance     = m2 / (count - 1)
    """

    count: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def update(self, value: float) -> None:
        self.count += 1

        delta = value - self.mean
        self.mean += delta / self.count
        delta_after_mean = value - self.mean
        self.m2 += delta * delta_after_mean

    @property
    def population_variance(self) -> Optional[float]:
        if self.count == 0:
            return None

        return self.m2 / self.count

    @property
    def sample_variance(self) -> Optional[float]:
        if self.count < 2:
            return None

        return self.m2 / (self.count - 1)

    @property
    def population_standard_deviation(self) -> Optional[float]:
        variance = self.population_variance
        return sqrt(variance) if variance is not None else None


def demonstrate_online_variance() -> None:
    section("9. ONLINE VARIANCE")

    calculator = OnlineVariance()

    for value in [10, 12, 9, 14, 13, 20]:
        calculator.update(value)

        print(
            f"value={value:>2}, "
            f"mean={calculator.mean:.4f}, "
            f"population_variance={calculator.population_variance:.4f}"
        )


# ---------------------------------------------------------------------------
# 18. ANOMALY DETECTION WITH MOVING STATISTICS
# ---------------------------------------------------------------------------

def moving_z_scores(
    values: Sequence[float],
    window: int,
) -> list[Optional[float]]:
    """
    Calculate a z-score using the preceding window.

    The current value is compared with the historical window immediately
    before it. The current value is deliberately excluded from the baseline.

    This is useful for streaming anomaly detection.
    """
    if window <= 1:
        raise ValueError("window must be greater than 1")

    result: list[Optional[float]] = []

    for index, current in enumerate(values):
        if index < window:
            result.append(None)
            continue

        history = values[index - window:index]
        average = mean(history)

        variance = sum(
            (value - average) ** 2
            for value in history
        ) / window

        standard_deviation = sqrt(variance)

        if standard_deviation == 0:
            result.append(0.0 if current == average else float("inf"))
        else:
            result.append((current - average) / standard_deviation)

    return result


# ---------------------------------------------------------------------------
# 19. BUSINESS KPI PIPELINE
# ---------------------------------------------------------------------------

def calculate_kpis(
    revenue: Sequence[float],
    customers: Sequence[int],
) -> list[dict]:
    """
    Calculate cumulative and moving business KPIs.

    Revenue per customer is calculated for each period.
    """
    if len(revenue) != len(customers):
        raise ValueError("revenue and customers must have equal lengths")

    cumulative_revenue = running_total(revenue)
    cumulative_customers = running_total(customers)
    average_revenue = running_average(revenue)
    moving_revenue = moving_average(revenue, 3, min_periods=1)

    output = []

    for index in range(len(revenue)):
        customer_count = customers[index]
        revenue_per_customer = (
            revenue[index] / customer_count
            if customer_count
            else None
        )

        output.append(
            {
                "period": index + 1,
                "revenue": revenue[index],
                "customers": customer_count,
                "cumulative_revenue": cumulative_revenue[index],
                "cumulative_customers": cumulative_customers[index],
                "average_revenue": average_revenue[index],
                "moving_3_period_revenue": moving_revenue[index],
                "revenue_per_customer": revenue_per_customer,
            }
        )

    return output


# ---------------------------------------------------------------------------
# 20. TESTS
# ---------------------------------------------------------------------------

def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(
            f"{message}\nExpected: {expected}\nActual: {actual}"
        )


def assert_close(
    actual: Sequence[float],
    expected: Sequence[float],
    message: str,
    tolerance: float = 1e-9,
) -> None:
    if len(actual) != len(expected):
        raise AssertionError(
            f"{message}: different lengths: {len(actual)} != {len(expected)}"
        )

    for index, (left, right) in enumerate(zip(actual, expected)):
        if abs(left - right) > tolerance:
            raise AssertionError(
                f"{message} at index {index}: {left} != {right}"
            )


def run_tests() -> None:
    section("10. AUTOMATED TESTS")

    assert_equal(
        running_total([1, 2, 3, 4]),
        [1.0, 3.0, 6.0, 10.0],
        "running_total failed",
    )

    assert_close(
        running_average([2, 4, 6]),
        [2.0, 3.0, 4.0],
        "running_average failed",
    )

    assert_close(
        moving_sum([1, 2, 3, 4, 5], 3),
        [6.0, 9.0, 12.0],
        "moving_sum failed",
    )

    assert_close(
        moving_average([1, 2, 3, 4, 5], 3),
        [2.0, 3.0, 4.0],
        "moving_average failed",
    )

    assert_close(
        moving_average([1, 2, 3], 3, min_periods=1),
        [1.0, 1.5, 2.0],
        "partial moving_average failed",
    )

    assert_equal(
        optimized_moving_maximum([1, 5, 2, 4, 3], 3),
        [5, 5, 4],
        "optimized maximum failed",
    )

    assert_equal(
        optimized_moving_minimum([1, 5, 2, 4, 3], 3),
        [1, 2, 2],
        "optimized minimum failed",
    )

    assert_close(
        weighted_moving_average([10, 20, 30], [1, 2, 3]),
        [23.333333333333332],
        "weighted moving average failed",
    )

    assert_close(
        exponential_moving_average([10, 20, 30], 0.5),
        [10.0, 15.0, 22.5],
        "EMA failed",
    )

    prefix = prefix_sums([5, 8, 2, 10])
    assert_close(
        [range_sum(prefix, 1, 4)],
        [20.0],
        "range_sum failed",
    )

    print("All tests passed.")


# ---------------------------------------------------------------------------
# 21. COMPLETE CASE STUDY
# ---------------------------------------------------------------------------

def run_case_study() -> None:
    section("11. COMPLETE TIME-SERIES CASE STUDY")

    daily_traffic = [
        1200, 1350, 1280, 1420, 1500,
        1620, 1580, 1750, 1690, 1810,
        1950, 1880, 2020, 2150, 2090,
    ]

    cumulative = running_total(daily_traffic)
    cumulative_average = running_average(daily_traffic)
    seven_day_average = moving_average(
        daily_traffic,
        window=7,
        min_periods=1,
    )
    seven_day_minimum = moving_minimum(
        daily_traffic,
        window=7,
    )
    seven_day_maximum = moving_maximum(
        daily_traffic,
        window=7,
    )
    ema = exponential_moving_average(
        daily_traffic,
        alpha=0.3,
    )
    z_scores = moving_z_scores(
        daily_traffic,
        window=7,
    )

    print(
        "Day | Traffic | Cumulative | CumAvg | 7DayAvg | EMA | ZScore"
    )
    print("-" * 78)

    for index, value in enumerate(daily_traffic):
        avg = seven_day_average[index]
        z = z_scores[index]

        print(
            f"{index + 1:>3} | "
            f"{value:>7.0f} | "
            f"{cumulative[index]:>10.0f} | "
            f"{cumulative_average[index]:>6.2f} | "
            f"{avg:>7.2f} | "
            f"{ema[index]:>7.2f} | "
            f"{'N/A' if z is None else f'{z:.2f}':>6}"
        )

    print("\nComplete-window 7-day minimums:", seven_day_minimum)
    print("Complete-window 7-day maximums:", seven_day_maximum)


# ---------------------------------------------------------------------------
# 22. MAIN PROGRAM
# ---------------------------------------------------------------------------

def main() -> None:
    section("RUNNING AND MOVING CALCULATIONS")

    demonstrate_basic_running_calculations()
    demonstrate_cumulative_metrics()
    demonstrate_running_statistics()
    demonstrate_moving_windows()
    demonstrate_weighted_methods()
    demonstrate_prefix_sums()
    demonstrate_streaming()
    demonstrate_edge_cases()
    demonstrate_online_variance()
    run_case_study()

    print("\nKPI example:")
    kpis = calculate_kpis(
        revenue=[1000, 1200, 900, 1500],
        customers=[50, 60, 45, 75],
    )

    for record in kpis:
        print(record)

    run_tests()


if __name__ == "__main__":
    main()
