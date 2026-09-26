# Running and Moving Calculations

## 1. Topic Introduction

Running and moving calculations are fundamental techniques for analyzing sequential numerical data.

They are especially useful when observations arrive over time, such as:

- Daily revenue
- Website traffic
- Sensor readings
- Stock prices
- Transaction volumes
- Customer counts
- CPU utilization
- Network latency
- Production output
- Energy consumption
- Scientific measurements
- Operational telemetry

Two major families of calculations are involved:

1. **Running or cumulative calculations**
2. **Moving or rolling calculations**

A running calculation incorporates every observation from the beginning of the sequence through the current observation.

A moving calculation uses a limited window of recent observations and moves that window forward as new observations arrive.

For example, given:

`10, 20, 30, 40, 50`

the running totals are:

`10, 30, 60, 100, 150`

A three-observation moving sum is:

`60, 90, 120`

because the windows are:

- `10, 20, 30`
- `20, 30, 40`
- `30, 40, 50`

The distinction between cumulative and moving calculations is central to time-series analysis.

---

## 2. Fundamental Terminology

### Observation

An individual measurement in a sequence.

Example:

`25`

may represent the number of transactions recorded during one minute.

### Sequence

An ordered collection of observations.

Example:

`[10, 20, 30, 40]`

### Running Calculation

A calculation that incorporates all observations encountered so far.

For a sequence:

`x1, x2, x3, ..., xn`

a running total at position `n` is:

`Tn = x1 + x2 + ... + xn`

### Cumulative Metric

A metric that grows or evolves as additional observations are incorporated.

Examples include:

- Cumulative revenue
- Cumulative sales
- Cumulative count
- Cumulative distance
- Cumulative energy consumption
- Cumulative number of errors

### Moving Window

A fixed-size subset of the most recent observations.

For a window size of three:

`[10, 20, 30]`

then:

`[20, 30, 40]`

then:

`[30, 40, 50]`

The window advances by one observation at a time.

### Rolling Calculation

"Rolling" and "moving" are commonly used interchangeably.

A rolling average is therefore usually the same concept as a moving average.

### Window Size

The number of observations included in a moving calculation.

A window size of `7` is common for daily data when analyzing weekly behavior.

### Warm-Up Period

The initial portion of a sequence during which a complete moving window does not yet exist.

For example, with a seven-observation window, the first six positions cannot have a complete seven-observation calculation.

---

## 3. Running Total

A running total continuously accumulates values.

Given:

`[10, 20, 15, 30]`

the calculation is:

- Start with `0`
- Add `10` → `10`
- Add `20` → `30`
- Add `15` → `45`
- Add `30` → `75`

The result is:

`[10, 30, 45, 75]`

The Python implementation uses `running_total()`.

The JavaScript implementation uses `runningTotal()`.

The C++ implementation uses `runningTotal()`.

All three implementations use an accumulator instead of repeatedly recalculating the entire prefix.

### Complexity

For `n` observations:

- Time: `O(n)`
- Output space: `O(n)`

If only the latest cumulative value is needed, the calculation can be performed with:

- Time: `O(n)`
- Additional working space: `O(1)`

---

## 4. Running Count

A running count records how many observations have been processed.

For:

`[100, 200, 300, 400]`

the running count is:

`[1, 2, 3, 4]`

This is useful when constructing cumulative rates or averages.

For example:

`running_average = running_total / running_count`

The implementations calculate the average more directly with an online mean update.

---

## 5. Running Minimum

A running minimum records the smallest value observed so far.

For:

`[10, 7, 12, 4, 9]`

the result is:

`[10, 7, 7, 4, 4]`

The important property is that a running minimum can never increase when more observations are added.

This is useful for:

- Lowest recorded temperature
- Lowest account balance
- Minimum response time
- Minimum daily sales
- Lowest observed sensor value

---

## 6. Running Maximum

A running maximum is the opposite concept.

For:

`[10, 7, 12, 4, 15]`

the result is:

`[10, 10, 12, 12, 15]`

The running maximum can never decrease.

It is useful for:

- Peak traffic
- Maximum CPU utilization
- Highest revenue
- Maximum transaction count
- Peak sensor readings

---

## 7. Running Average

A running average represents the average of all observations seen so far.

A direct formula is:

`average = cumulative_total / observation_count`

The implementations use an online update:

`new_average = old_average + (new_value - old_average) / count`

For example:

`10, 20, 30`

produces:

- After `10`: `10`
- After `20`: `15`
- After `30`: `20`

The online formulation is efficient because the entire prefix does not need to be summed again for every observation.

### Complexity

- Time: `O(n)`
- Additional working state: `O(1)`
- Output storage: `O(n)` if all intermediate averages are retained

---

## 8. Cumulative Percentage

A cumulative percentage measures how much of a final total has accumulated.

Suppose daily sales are:

`[100, 200, 300]`

The cumulative sales are:

`[100, 300, 600]`

Relative to the final total:

- `100 / 600 = 16.67%`
- `300 / 600 = 50%`
- `600 / 600 = 100%`

This type of metric is useful for:

- Project completion
- Budget consumption
- Sales accumulation
- Production output
- Research progress
- Resource consumption

A zero final total requires special handling because division by zero is undefined.

---

## 9. Running Growth

A cumulative growth calculation compares the current observation with a reference observation.

A common formula is:

`growth_percentage = ((current - reference) / reference) × 100`

The reference may be:

- First observation
- Previous observation
- Beginning-of-period value
- Baseline value

The implementation demonstrates comparison with the first observation.

A zero baseline requires special handling because the percentage formula becomes undefined.

---

## 10. Moving Windows

A moving calculation differs fundamentally from a running calculation.

Consider:

`[10, 20, 30, 40, 50]`

with a window size of `3`.

The windows are:

`[10, 20, 30]`

`[20, 30, 40]`

`[30, 40, 50]`

The first value leaves the calculation when the fourth value arrives.

This means a moving metric reflects recent behavior rather than the entire historical sequence.

---

## 11. Moving Sum

For:

`[10, 20, 30, 40, 50]`

with window `3`:

- `10 + 20 + 30 = 60`
- `20 + 30 + 40 = 90`
- `30 + 40 + 50 = 120`

Result:

`[60, 90, 120]`

A naive implementation recalculates each window from scratch.

An optimized implementation maintains the previous sum:

`new_sum = old_sum + entering_value - leaving_value`

This changes the per-window update from potentially `O(window)` to `O(1)`.

The Python, JavaScript, and C++ implementations demonstrate this optimization.

---

## 12. Simple Moving Average

A simple moving average, or SMA, is:

`SMA = window_sum / window_size`

For:

`[10, 20, 30, 40, 50]`

with window `3`:

- `(10 + 20 + 30) / 3 = 20`
- `(20 + 30 + 40) / 3 = 30`
- `(30 + 40 + 50) / 3 = 40`

Result:

`[20, 30, 40]`

Moving averages are commonly used to reduce short-term noise.

They are useful in:

- Operational dashboards
- Demand forecasting
- Sensor processing
- Financial analysis
- Website analytics
- Manufacturing
- Network monitoring

A moving average does not predict the future by itself. It transforms historical observations into a smoothed series.

---

## 13. Partial Windows and `min_periods`

A system has to decide what to do before a complete window exists.

With:

`[10, 20, 30, 40]`

and window `3`, a strict moving average produces:

`[20, 30]`

because only two complete windows exist.

A partial-window implementation can instead produce:

`[10, 15, 20, 30]`

when at least one observation is accepted.

This distinction matters in dashboards because showing a value immediately may be useful, but it must be clear that early values are based on fewer observations.

The Python and JavaScript implementations expose this behavior through `min_periods` and `minPeriods`.

The C++ implementation uses `minPeriods`.

---

## 14. Weighted Moving Average

A weighted moving average gives different observations different importance.

Suppose:

`values = [10, 20, 30]`

and:

`weights = [1, 2, 3]`

The calculation is:

`(10×1 + 20×2 + 30×3) / (1+2+3)`

which gives approximately:

`23.3333`

The largest weight belongs to the newest observation in this example.

Weights may represent:

- Recency
- Confidence
- Measurement quality
- Business importance
- Sampling reliability

Weights must normally be non-negative, and the total weight must not be zero.

---

## 15. Exponential Moving Average

An exponential moving average, or EMA, applies exponentially decreasing influence to older observations.

The recursive formula is:

`EMA_t = alpha × x_t + (1 - alpha) × EMA_(t-1)`

where `alpha` is between `0` and `1`.

A high `alpha` responds quickly to new observations.

A low `alpha` produces more smoothing.

For:

`[10, 20, 30]`

and:

`alpha = 0.5`

the calculation is:

- EMA1 = `10`
- EMA2 = `0.5×20 + 0.5×10 = 15`
- EMA3 = `0.5×30 + 0.5×15 = 22.5`

EMA is useful when recent observations should matter more without maintaining a fixed-size window.

Unlike a simple moving average, an EMA has an effectively long memory.

---

## 16. Simple Moving Average Versus EMA

| Property | Simple Moving Average | Exponential Moving Average |
|---|---|---|
| Window | Fixed | Effectively decaying history |
| Older observations | Removed completely | Influence decreases gradually |
| Parameter | Window size | Alpha |
| Memory | Window-dependent | Constant state |
| Response | Depends on window | Depends on alpha |
| Implementation | Usually queue-based | Recursive |
| Typical use | Fixed recent period | Smoothing with recency weighting |

Neither approach is universally correct.

The appropriate method depends on the meaning of the data and the desired response to new observations.

---

## 17. Moving Minimum and Maximum

Moving minimum and maximum calculations find extrema inside each recent window.

For:

`[1, 5, 2, 4, 3]`

with window `3`:

Windows:

- `[1, 5, 2]`
- `[5, 2, 4]`
- `[2, 4, 3]`

Moving minimum:

`[1, 2, 2]`

Moving maximum:

`[5, 5, 4]`

A straightforward implementation scans every window.

That requires approximately:

`O(n × window)`

time.

---

## 18. Monotonic Deque Optimization

The C++, Python, and JavaScript implementations contain optimized moving minimum and maximum algorithms.

The key data structure is a deque of indexes.

For a moving maximum, the deque maintains values in decreasing order.

For a moving minimum, the deque maintains values in increasing order.

When a new observation arrives:

1. Remove indexes that are outside the window.
2. Remove indexes that cannot become the answer because the new value dominates them.
3. Add the new index.
4. Read the answer from the front.

Each index enters and leaves the deque at most once.

Therefore:

- Time: `O(n)`
- Auxiliary deque space: `O(window)`

This is substantially more efficient than rescanning every window when the window is large.

---

## 19. Rolling Standard Deviation

A moving standard deviation measures local variability.

For a window with values:

`x1, x2, ..., xn`

the population variance is:

`variance = Σ(xi - mean)² / n`

and:

`standard_deviation = sqrt(variance)`

The sample variance uses:

`n - 1`

instead of `n`.

The implementations explicitly distinguish population and sample standard deviation.

This distinction matters because they answer different statistical questions.

---

## 20. Prefix Sums

A prefix sum is a cumulative sum designed to make later range queries efficient.

For:

`[5, 8, 2, 10]`

the prefix array is:

`[0, 5, 13, 15, 25]`

The sum of the half-open range `[left, right)` is:

`prefix[right] - prefix[left]`

For example:

`sum([8, 2, 10])`

corresponds to:

`prefix[4] - prefix[1]`

which is:

`25 - 5 = 20`

### Complexity

Building the prefix array:

`O(n)`

Each later range query:

`O(1)`

This technique is useful when many range-sum queries are performed over unchanged data.

---

## 21. Running Versus Prefix-Sum Calculations

These concepts are related but serve different purposes.

A running total directly produces the cumulative value for every position.

A prefix-sum array additionally supports efficient arbitrary range queries.

For example:

`running_total([10, 20, 30, 40])`

produces:

`[10, 30, 60, 100]`

The equivalent prefix representation with a leading zero is:

`[0, 10, 30, 60, 100]`

The leading zero is useful because it makes range subtraction straightforward.

---

## 22. Streaming Calculations

A batch calculation assumes the complete dataset is already available.

A streaming calculation processes observations one at a time.

For example:

`stream.update(100)`

then:

`stream.update(120)`

then:

`stream.update(110)`

A streaming moving average only needs the active window and its current sum.

This is useful for:

- Live dashboards
- IoT sensors
- Network monitoring
- Market feeds
- Application logs
- Manufacturing systems
- Real-time analytics

### Memory

If the window has size `k`, a fixed-window streaming average requires approximately:

`O(k)`

working memory.

The full dataset does not need to be retained.

---

## 23. Online Statistics

An online statistic updates its state when a new observation arrives.

The Python `RunningStatistics` class tracks:

- Count
- Total
- Minimum
- Maximum
- Average

The JavaScript `OnlineVariance` class and C++ `OnlineVariance` class also demonstrate incremental statistical state.

Online algorithms are important when:

- Data is too large to fit comfortably in memory
- Data arrives continuously
- Results are needed immediately
- Reprocessing the entire history would be expensive

---

## 24. Welford's Online Variance Algorithm

A naive variance implementation can suffer from numerical problems when values are large and differences are small.

Welford's algorithm maintains:

- Count
- Mean
- `M2`

For each new value:

`delta = value - mean`

Then:

`mean = mean + delta / count`

and:

`M2 = M2 + delta × (value - new_mean)`

At the end:

`population_variance = M2 / count`

and:

`sample_variance = M2 / (count - 1)`

This approach is suitable for streaming variance calculations and generally has better numerical behavior than directly subtracting large squared quantities.

---

## 25. Missing Values

Real-world data is often incomplete.

Examples include:

`[10, null, 20, null, 30]`

A missing value should not automatically be treated as zero.

Treating missing data as zero changes the meaning of the dataset.

The provided implementations include functions that ignore missing observations when calculating averages.

Possible policies include:

1. Ignore missing values.
2. Return a missing result.
3. Interpolate.
4. Forward-fill.
5. Back-fill.
6. Treat missing as zero when domain semantics explicitly justify it.

The correct policy depends on the data-generating process.

---

## 26. Missing Data and Window Semantics

Consider:

`[10, null, 20]`

with a window of `3`.

There are two separate questions:

1. Does `null` occupy a position in the window?
2. Should `null` count as an observation in the average?

The implementation demonstrates a policy where the position remains inside the window, but the missing value is excluded from the arithmetic.

This distinction is important in time-series systems.

A missing reading at 10:05 should not necessarily cause the 10:05 timestamp itself to disappear.

---

## 27. Edge Cases

Important edge cases include:

### Empty sequence

There may be no result.

Functions should define this behavior explicitly.

### Single observation

A running calculation is still valid.

A moving calculation with a larger window may not yet be valid.

### Window larger than the dataset

A complete-window calculation cannot produce a result.

### Window of zero

A zero-sized window has no meaningful average or sum.

It should normally be rejected.

### Negative values

Running and moving sums and averages naturally support negative values.

### Repeated values

Repeated values are valid and should not cause special behavior.

### All zeros

A total may be zero, creating division-by-zero problems for percentage metrics.

### Zero denominator

Metrics such as revenue per customer require explicit handling when the denominator is zero.

### Invalid alpha

EMA requires an alpha in a valid range.

---

## 28. Cumulative Metrics Versus Moving Metrics

| Characteristic | Cumulative | Moving |
|---|---|---|
| Historical scope | Entire history | Recent window |
| Memory of old data | Permanent | Limited |
| Typical purpose | Progress and totals | Trend and smoothing |
| Example | Year-to-date revenue | Seven-day revenue average |
| Response to old values | Never removed | Eventually removed |
| Window required | No | Usually yes |

A cumulative total answers:

"How much has happened since the beginning?"

A moving average answers:

"What has the recent behavior looked like?"

These are different analytical questions.

---

## 29. Cumulative Metrics in Business

A sales system might maintain:

- Daily sales
- Cumulative sales
- Daily customer count
- Cumulative customer count
- Cumulative average revenue
- Revenue per customer
- Moving revenue average

For example:

`revenue = [1000, 1200, 900, 1500]`

The cumulative revenue is:

`[1000, 2200, 3100, 4600]`

A three-period moving revenue average can reveal recent changes without discarding the cumulative historical record.

The Python, JavaScript, and C++ implementations all contain a business KPI pipeline.

---

## 30. Telemetry Case Study

The C++ program models a technology platform receiving daily traffic measurements.

Example values include:

`1200, 1350, 1280, 1420, 1500, ...`

The system calculates:

- Daily traffic
- Cumulative traffic
- Cumulative average
- Seven-period moving average
- EMA

This mirrors an operational analytics system.

The cumulative metric answers how much total traffic has been processed.

The moving average shows recent traffic behavior.

The EMA responds more strongly to recent changes.

These measurements can support operational monitoring, capacity planning, and anomaly analysis.

---

## 31. Anomaly Detection

A moving z-score can compare a current value against a historical moving baseline.

The general formula is:

`z = (current - historical_mean) / historical_standard_deviation`

The implementation deliberately calculates the baseline from observations before the current value.

This avoids allowing the value being tested to influence its own baseline.

A high absolute z-score may indicate unusual behavior.

A zero historical standard deviation is a special case.

If every historical observation is identical:

- A matching current value is not unusual.
- A different current value cannot be normalized by zero standard deviation.

The implementation represents the latter case with infinity.

In production systems, anomaly thresholds should be chosen according to the domain and false-positive requirements.

---

## 32. JavaScript-Specific Considerations

JavaScript is useful for running calculations in:

- Browser dashboards
- Web applications
- Node.js services
- Event-driven systems
- Streaming interfaces

The JavaScript implementation demonstrates an asynchronous generator.

An asynchronous data stream can produce values over time.

The `for await...of` syntax consumes asynchronous observations without requiring the entire dataset to be available beforehand.

This is particularly relevant to real-time applications.

---

## 33. Python-Specific Considerations

Python is useful for:

- Data analysis
- Scientific computing
- Prototyping
- ETL pipelines
- Statistical analysis
- Automation

The Python implementation emphasizes readability and educational decomposition.

The `deque` structure is used for fixed-size windows.

Dataclasses are used to represent stateful calculators.

Type annotations make interfaces more explicit without requiring third-party packages.

---

## 34. C++-Specific Considerations

C++ is particularly useful when:

- Low latency matters
- Memory efficiency matters
- High throughput is required
- Embedded processing is involved
- Large data streams must be processed efficiently

The C++ implementation demonstrates:

- `std::vector`
- `std::deque`
- `std::queue`
- `std::optional`
- Classes
- Exceptions
- Algorithms
- Explicit memory management decisions
- Compile-time type checking

The C++ program also provides a realistic system-style case study rather than only isolated language examples.

---

## 35. Performance Considerations

### Repeated prefix summation

A naive running-total implementation may repeatedly calculate:

`sum(values[:i])`

This can require `O(n²)` work.

The optimized approach maintains one accumulator and requires:

`O(n)`

time.

### Moving sum

Recalculating every window:

`O(n × k)`

Incremental update:

`O(n)`

where `k` is the window size.

### Moving minimum or maximum

Naive scanning:

`O(n × k)`

Monotonic deque:

`O(n)`

### Prefix sums

Preprocessing:

`O(n)`

Each range sum:

`O(1)`

### EMA

Each observation requires constant work:

`O(n)` total time.

EMA also requires only constant working state.

---

## 36. Numerical Precision

Running calculations can accumulate floating-point rounding errors.

For example, binary floating-point cannot represent every decimal fraction exactly.

Repeated addition can therefore produce values such as:

`0.9999999999999999`

instead of exactly:

`1.0`

For ordinary analytics this may be acceptable.

For financial systems, the representation strategy must be chosen carefully.

Possible approaches include:

- Integer minor units such as cents
- Decimal arithmetic
- Carefully controlled floating-point calculations

The C++ case study uses `double` for general numerical demonstrations, not as a statement that binary floating point is appropriate for every financial production system.

---

## 37. Overflow Considerations

Cumulative totals can become much larger than individual observations.

For example:

`1,000,000,000`

repeated millions of times can exceed the capacity of a narrow integer type.

Production implementations should select numeric types based on realistic maximum values.

Possible strategies include:

- Wider integer types
- Floating-point types
- Decimal representations
- Arbitrary-precision libraries where necessary
- Explicit overflow checks

C++ makes integer-width choices particularly important because integer overflow behavior differs depending on signedness and type.

---

## 38. Security Considerations

Running and moving calculations are mathematical operations, but production systems still require input validation.

Important validation includes:

- Rejecting invalid window sizes
- Rejecting invalid weighting parameters
- Validating numeric input
- Checking denominators
- Handling missing values explicitly
- Limiting resource consumption
- Avoiding unbounded queues
- Avoiding memory growth in long-running processes

A streaming system should not accidentally store every observation indefinitely when only the latest window is required.

Input validation also prevents malformed external data from silently corrupting metrics.

---

## 39. Production Design Considerations

A production metric pipeline should define:

### Data contract

Specify:

- Data type
- Units
- Timestamp meaning
- Missing-value representation
- Valid ranges

### Window semantics

Specify:

- Number of observations
- Time duration
- Whether incomplete windows are allowed
- Minimum valid observations

### Time semantics

A seven-observation window is not necessarily the same as a seven-day window.

If data is missing, seven observations could span ten calendar days.

For irregularly sampled data, time-based windows may be more appropriate than observation-count windows.

### Late data

Real systems may receive old events after newer events.

The metric system must define whether late events trigger:

- Recalculation
- Correction
- Ignoring
- Backfilling

### Ordering

Running and moving calculations depend on order.

Unsorted observations can produce incorrect time-series results.

---

## 40. Observation Windows Versus Time Windows

A window size of `7` can mean:

"the last seven observations"

or:

"the last seven days"

These are not always equivalent.

Suppose sensor readings arrive irregularly:

- Monday
- Tuesday
- Friday
- Saturday
- Sunday

A five-observation window covers five measurements, not necessarily five days.

For time-series systems, timestamps should be considered explicitly when business meaning depends on elapsed time.

---

## 41. Common Mistakes

### Mistake 1: Confusing cumulative and moving metrics

A cumulative total never removes old observations.

A moving total eventually removes old observations.

### Mistake 2: Recalculating every window from scratch

This can unnecessarily increase computational cost.

### Mistake 3: Ignoring warm-up behavior

The first positions may not have enough observations for a complete window.

### Mistake 4: Treating missing data as zero

This changes the mathematical meaning of the dataset.

### Mistake 5: Dividing by zero

Percentages and ratios require explicit denominator validation.

### Mistake 6: Using the current observation in its own anomaly baseline

This can make anomalies less visible.

### Mistake 7: Choosing an arbitrary window

The window should correspond to the analytical question.

### Mistake 8: Ignoring timestamp semantics

Observation-count windows and time-duration windows are different.

### Mistake 9: Keeping unlimited historical data for a fixed-window calculation

A fixed-window streaming algorithm generally needs only the active window.

### Mistake 10: Assuming smoothing removes information

A moving average transforms the data. It does not recover the underlying signal perfectly.

---

## 42. Best Practices

1. Define the metric mathematically before implementing it.
2. Define the window semantics explicitly.
3. Validate window sizes.
4. Decide how warm-up periods are represented.
5. Define missing-value behavior.
6. Avoid unnecessary repeated calculations.
7. Use incremental updates for streaming data.
8. Use prefix sums when many static range queries are required.
9. Use monotonic deques for efficient moving extrema.
10. Test empty, single-value, zero, negative, and missing-value inputs.
11. Consider numerical precision.
12. Measure performance with realistic data sizes.
13. Preserve timestamps when working with time-series data.
14. Document whether standard deviation is population or sample based.
15. Ensure denominator values are validated before calculating ratios.

---

## 43. Python Implementation

The Python file is structured from basic functions to more advanced streaming algorithms.

Important functions include:

- `running_total()`
- `running_count()`
- `running_minimum()`
- `running_maximum()`
- `running_average()`
- `moving_sum()`
- `moving_average()`
- `weighted_moving_average()`
- `exponential_moving_average()`
- `moving_standard_deviation()`
- `prefix_sums()`
- `range_sum()`
- `optimized_moving_maximum()`
- `optimized_moving_minimum()`
- `moving_z_scores()`

The `StreamingMovingAverage` class demonstrates stateful fixed-window processing.

The `RunningStatistics` dataclass demonstrates multiple cumulative metrics in a single state object.

The `OnlineVariance` dataclass implements Welford's algorithm.

The Python program also contains automated assertions and a complete telemetry case study.

---

## 44. JavaScript Implementation

The JavaScript implementation emphasizes application and event-driven use cases.

It demonstrates:

- Functions
- Classes
- Arrays
- Queues
- Online statistics
- Moving windows
- Monotonic deques
- Prefix sums
- Missing-value handling
- Asynchronous generators
- `for await...of`
- Error handling
- Automated tests

The asynchronous stream simulation is particularly relevant to JavaScript because JavaScript applications frequently process event-driven and asynchronous data.

The `StreamingMovingAverage` class maintains only the active window and its total.

The `processStream()` function shows how asynchronous observations can be transformed into rolling metrics as they arrive.

---

## 45. C++ Case Study

The C++ program models an operational telemetry and business analytics system.

### Problem

A technology platform receives sequential observations such as:

- Traffic
- Revenue
- Customers
- Measurements

The platform needs both historical cumulative metrics and recent rolling metrics.

### Design

The system contains independent functions for:

- Running totals
- Running averages
- Running extrema
- Moving sums
- Moving averages
- Weighted moving averages
- EMA
- Rolling standard deviation
- Prefix sums
- Optimized extrema

Stateful classes provide:

- Streaming moving averages
- Online variance

The business layer builds structured KPI records.

### Data Structures

`std::vector` is used for stored numerical sequences.

`std::queue` is used for simple fixed-window streaming calculations.

`std::deque` is used for monotonic moving minimum and maximum algorithms.

`std::optional` represents values that may not yet exist during a warm-up period.

### Validation

Invalid values such as:

- Zero windows
- Invalid alpha
- Invalid ranges
- Invalid weights

are rejected with exceptions.

### Performance

The implementation deliberately demonstrates both straightforward and optimized approaches.

Moving sums use incremental updates.

Moving extrema use monotonic deques.

Running averages use online updates.

Prefix sums support constant-time range queries after linear preprocessing.

---

## 46. Conceptual Comparison of the Three Implementations

| Aspect | Python | JavaScript | C++ |
|---|---|---|---|
| Primary emphasis | Analytics and clarity | Application and asynchronous processing | Performance and systems design |
| Running metrics | Yes | Yes | Yes |
| Moving metrics | Yes | Yes | Yes |
| Streaming | Yes | Yes | Yes |
| Async stream | No | Yes | Not modeled as async |
| Monotonic deque | Yes | Yes | Yes |
| Online variance | Yes | Yes | Yes |
| Prefix sums | Yes | Yes | Yes |
| Testing | Assertions | Assertions | Explicit test function |
| Type model | Type hints | Dynamic runtime types | Static types |
| Memory control | `deque` | Array-based queue | STL containers |

The mathematical concepts remain the same, but each language highlights different implementation concerns.

---

## 47. Practical Applications

### Financial analysis

- Moving prices
- Cumulative returns
- Rolling volatility
- Transaction volume
- Portfolio metrics

### Business analytics

- Cumulative revenue
- Moving sales average
- Customer acquisition
- Revenue per customer
- Order volume

### Web analytics

- Rolling traffic
- Cumulative page views
- Moving conversion rates
- Error-rate monitoring

### Infrastructure

- CPU utilization
- Memory usage
- Request latency
- Network throughput
- Error counts

### Manufacturing

- Rolling production rate
- Cumulative output
- Moving defect rate
- Sensor smoothing

### Scientific computing

- Experimental measurements
- Sensor streams
- Rolling variability
- Cumulative measurements

### Logistics

- Cumulative distance
- Moving delivery time
- Rolling shipment volume
- Recent demand

---

## 48. Important Distinctions

### Running average versus moving average

A running average uses every observation since the beginning.

A moving average uses only observations inside the current window.

### Weighted moving average versus EMA

A weighted moving average normally has a fixed explicit set of weights.

An EMA recursively assigns decreasing influence to older observations.

### Moving average versus moving median

A moving average is sensitive to extreme values.

A moving median is generally more resistant to isolated outliers.

### Cumulative total versus prefix sum

A cumulative total describes sequential accumulation.

A prefix-sum structure also enables fast arbitrary range queries.

### Observation window versus time window

An observation window counts records.

A time window measures elapsed time.

---

## 49. Limitations

Running and moving calculations are transformations of data rather than complete analytical models.

A moving average can hide short-lived events.

A long window can respond slowly to structural changes.

A short window can be noisy.

An EMA depends strongly on its alpha parameter.

A cumulative metric can become dominated by old observations and may be unsuitable for detecting recent changes.

Rolling statistics can be misleading when the underlying process is non-stationary.

Missing or irregular observations can alter the meaning of observation-based windows.

Therefore, the calculation should always be interpreted according to the data collection process and business meaning.

---

## 50. Implementation Checklist

For a new running or moving metric, establish:

- What is the input?
- What does each observation represent?
- What is the unit?
- Is the calculation cumulative or windowed?
- What is the window size?
- Is the window observation-based or time-based?
- Are partial windows allowed?
- What is the minimum number of valid observations?
- How are missing values treated?
- What happens with zero denominators?
- What numerical type is appropriate?
- Does the metric need to work in streaming mode?
- Is `O(n × window)` performance acceptable?
- Would incremental updates improve performance?
- Would a prefix structure help?
- Would a monotonic deque help?
- How are late or out-of-order observations handled?
- How is the metric tested?
- What monitoring is required in production?

These questions determine the appropriate implementation rather than selecting an algorithm solely because it is familiar.
