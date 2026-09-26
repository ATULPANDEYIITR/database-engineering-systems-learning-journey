"use strict";

/*
 * Running and Moving Calculations
 *
 * This file demonstrates:
 * - Running totals
 * - Cumulative averages
 * - Running minimums and maximums
 * - Moving sums and averages
 * - Weighted moving averages
 * - Exponential moving averages
 * - Rolling statistics
 * - Prefix sums
 * - Streaming calculations
 * - Monotonic-deque optimization
 * - Missing-value handling
 * - Asynchronous data processing
 * - Validation and testing
 *
 * The file uses only standard JavaScript features and can run in Node.js.
 */

// -----------------------------------------------------------------------------
// 1. BASIC RUNNING CALCULATIONS
// -----------------------------------------------------------------------------

function runningTotal(values) {
    const result = [];
    let total = 0;

    for (const value of values) {
        total += value;
        result.push(total);
    }

    return result;
}

function runningCount(values) {
    const result = [];
    let count = 0;

    for (const _ of values) {
        count += 1;
        result.push(count);
    }

    return result;
}

function runningMinimum(values) {
    const result = [];
    let currentMinimum = null;

    for (const value of values) {
        if (currentMinimum === null || value < currentMinimum) {
            currentMinimum = value;
        }

        result.push(currentMinimum);
    }

    return result;
}

function runningMaximum(values) {
    const result = [];
    let currentMaximum = null;

    for (const value of values) {
        if (currentMaximum === null || value > currentMaximum) {
            currentMaximum = value;
        }

        result.push(currentMaximum);
    }

    return result;
}

function runningAverage(values) {
    const result = [];
    let average = 0;
    let count = 0;

    for (const value of values) {
        count += 1;

        // Online mean update:
        // mean_new = mean_old + (x - mean_old) / count
        average += (value - average) / count;

        result.push(average);
    }

    return result;
}

// -----------------------------------------------------------------------------
// 2. MOVING WINDOWS
// -----------------------------------------------------------------------------

function validateWindow(window, valuesLength) {
    if (!Number.isInteger(window) || window <= 0) {
        throw new RangeError("window must be a positive integer");
    }

    if (window > valuesLength) {
        return false;
    }

    return true;
}

function movingSum(values, window) {
    if (!validateWindow(window, values.length)) {
        return [];
    }

    const result = [];
    let currentSum = 0;

    for (let index = 0; index < window; index += 1) {
        currentSum += values[index];
    }

    result.push(currentSum);

    for (let index = window; index < values.length; index += 1) {
        currentSum += values[index];
        currentSum -= values[index - window];
        result.push(currentSum);
    }

    return result;
}

function movingAverage(values, window, minPeriods = window) {
    if (!Number.isInteger(window) || window <= 0) {
        throw new RangeError("window must be a positive integer");
    }

    if (
        !Number.isInteger(minPeriods) ||
        minPeriods <= 0 ||
        minPeriods > window
    ) {
        throw new RangeError(
            "minPeriods must be an integer between 1 and window"
        );
    }

    const result = [];
    const queue = [];
    let currentSum = 0;

    for (const value of values) {
        queue.push(value);
        currentSum += value;

        if (queue.length > window) {
            currentSum -= queue.shift();
        }

        if (queue.length >= minPeriods) {
            result.push(currentSum / queue.length);
        } else {
            result.push(null);
        }
    }

    return result;
}

// -----------------------------------------------------------------------------
// 3. WEIGHTED MOVING AVERAGE
// -----------------------------------------------------------------------------

function weightedMovingAverage(values, weights) {
    if (weights.length === 0) {
        throw new RangeError("weights cannot be empty");
    }

    if (weights.length > values.length) {
        return [];
    }

    if (weights.some((weight) => weight < 0)) {
        throw new RangeError("weights cannot be negative");
    }

    const weightTotal = weights.reduce(
        (total, weight) => total + weight,
        0
    );

    if (weightTotal === 0) {
        throw new RangeError("weights must have a positive total");
    }

    const result = [];
    const window = weights.length;

    for (let index = window - 1; index < values.length; index += 1) {
        let weightedSum = 0;

        for (let offset = 0; offset < window; offset += 1) {
            weightedSum +=
                values[index - window + 1 + offset] * weights[offset];
        }

        result.push(weightedSum / weightTotal);
    }

    return result;
}

// -----------------------------------------------------------------------------
// 4. EXPONENTIALLY WEIGHTED MOVING AVERAGE
// -----------------------------------------------------------------------------

function exponentialMovingAverage(values, alpha) {
    if (!(alpha > 0 && alpha <= 1)) {
        throw new RangeError("alpha must be greater than 0 and at most 1");
    }

    if (values.length === 0) {
        return [];
    }

    const result = [values[0]];

    for (let index = 1; index < values.length; index += 1) {
        const previous = result[result.length - 1];

        result.push(
            alpha * values[index] +
            (1 - alpha) * previous
        );
    }

    return result;
}

// -----------------------------------------------------------------------------
// 5. ROLLING STANDARD DEVIATION
// -----------------------------------------------------------------------------

function movingStandardDeviation(values, window, sample = false) {
    if (!validateWindow(window, values.length)) {
        return [];
    }

    if (sample && window < 2) {
        throw new RangeError(
            "sample standard deviation requires window >= 2"
        );
    }

    const result = [];

    for (let index = window - 1; index < values.length; index += 1) {
        const currentWindow = values.slice(
            index - window + 1,
            index + 1
        );

        const average =
            currentWindow.reduce((sum, value) => sum + value, 0) /
            currentWindow.length;

        const squaredDeviation =
            currentWindow.reduce(
                (sum, value) => sum + (value - average) ** 2,
                0
            );

        const denominator = sample ? window - 1 : window;

        result.push(
            Math.sqrt(squaredDeviation / denominator)
        );
    }

    return result;
}

// -----------------------------------------------------------------------------
// 6. PREFIX SUMS
// -----------------------------------------------------------------------------

function prefixSums(values) {
    const prefix = [0];

    for (const value of values) {
        prefix.push(prefix[prefix.length - 1] + value);
    }

    return prefix;
}

function rangeSum(prefix, left, right) {
    if (
        left < 0 ||
        right < left ||
        right >= prefix.length
    ) {
        throw new RangeError("invalid range");
    }

    return prefix[right] - prefix[left];
}

// -----------------------------------------------------------------------------
// 7. OPTIMIZED MOVING MAXIMUM
// -----------------------------------------------------------------------------

function movingMaximumOptimized(values, window) {
    if (!validateWindow(window, values.length)) {
        return [];
    }

    /*
     * The deque stores indexes whose values are decreasing.
     *
     * The front therefore identifies the largest value in the
     * current window. Each index enters and leaves the deque once,
     * giving O(n) time.
     */
    const deque = [];
    let front = 0;
    const result = [];

    for (let index = 0; index < values.length; index += 1) {
        while (
            front < deque.length &&
            deque[front] <= index - window
        ) {
            front += 1;
        }

        while (
            deque.length > front &&
            values[deque[deque.length - 1]] <= values[index]
        ) {
            deque.pop();
        }

        deque.push(index);

        if (index >= window - 1) {
            result.push(values[deque[front]]);
        }
    }

    return result;
}

function movingMinimumOptimized(values, window) {
    if (!validateWindow(window, values.length)) {
        return [];
    }

    const deque = [];
    let front = 0;
    const result = [];

    for (let index = 0; index < values.length; index += 1) {
        while (
            front < deque.length &&
            deque[front] <= index - window
        ) {
            front += 1;
        }

        while (
            deque.length > front &&
            values[deque[deque.length - 1]] >= values[index]
        ) {
            deque.pop();
        }

        deque.push(index);

        if (index >= window - 1) {
            result.push(values[deque[front]]);
        }
    }

    return result;
}

// -----------------------------------------------------------------------------
// 8. STREAMING CALCULATOR
// -----------------------------------------------------------------------------

class StreamingMovingAverage {
    constructor(window) {
        if (!Number.isInteger(window) || window <= 0) {
            throw new RangeError("window must be a positive integer");
        }

        this.window = window;
        this.queue = [];
        this.total = 0;
    }

    update(value) {
        this.queue.push(value);
        this.total += value;

        if (this.queue.length > this.window) {
            this.total -= this.queue.shift();
        }

        if (this.queue.length < this.window) {
            return null;
        }

        return this.total / this.window;
    }
}

// -----------------------------------------------------------------------------
// 9. ONLINE VARIANCE
// -----------------------------------------------------------------------------

class OnlineVariance {
    constructor() {
        this.count = 0;
        this.mean = 0;
        this.m2 = 0;
    }

    update(value) {
        this.count += 1;

        const delta = value - this.mean;
        this.mean += delta / this.count;

        const deltaAfterMean = value - this.mean;
        this.m2 += delta * deltaAfterMean;
    }

    populationVariance() {
        if (this.count === 0) {
            return null;
        }

        return this.m2 / this.count;
    }

    sampleVariance() {
        if (this.count < 2) {
            return null;
        }

        return this.m2 / (this.count - 1);
    }
}

// -----------------------------------------------------------------------------
// 10. MISSING VALUES
// -----------------------------------------------------------------------------

function runningAverageIgnoreMissing(values) {
    let total = 0;
    let count = 0;

    return values.map((value) => {
        if (value !== null && value !== undefined) {
            total += value;
            count += 1;
        }

        return count === 0 ? null : total / count;
    });
}

function movingAverageIgnoreMissing(
    values,
    window,
    minPeriods = 1
) {
    if (!Number.isInteger(window) || window <= 0) {
        throw new RangeError("window must be positive");
    }

    if (
        !Number.isInteger(minPeriods) ||
        minPeriods <= 0 ||
        minPeriods > window
    ) {
        throw new RangeError("invalid minPeriods");
    }

    const queue = [];
    let total = 0;
    let validCount = 0;
    const result = [];

    for (const value of values) {
        queue.push(value);

        if (value !== null && value !== undefined) {
            total += value;
            validCount += 1;
        }

        if (queue.length > window) {
            const removed = queue.shift();

            if (removed !== null && removed !== undefined) {
                total -= removed;
                validCount -= 1;
            }
        }

        result.push(
            validCount >= minPeriods
                ? total / validCount
                : null
        );
    }

    return result;
}

// -----------------------------------------------------------------------------
// 11. ANOMALY DETECTION
// -----------------------------------------------------------------------------

function movingZScores(values, window) {
    if (!Number.isInteger(window) || window <= 1) {
        throw new RangeError("window must be greater than 1");
    }

    const result = [];

    for (let index = 0; index < values.length; index += 1) {
        if (index < window) {
            result.push(null);
            continue;
        }

        const history = values.slice(
            index - window,
            index
        );

        const average =
            history.reduce((sum, value) => sum + value, 0) /
            history.length;

        const variance =
            history.reduce(
                (sum, value) =>
                    sum + (value - average) ** 2,
                0
            ) / history.length;

        const standardDeviation = Math.sqrt(variance);

        if (standardDeviation === 0) {
            result.push(
                values[index] === average
                    ? 0
                    : Infinity
            );
        } else {
            result.push(
                (values[index] - average) /
                standardDeviation
            );
        }
    }

    return result;
}

// -----------------------------------------------------------------------------
// 12. ASYNCHRONOUS STREAM SIMULATION
// -----------------------------------------------------------------------------

async function* simulatedDataStream(values, delayMilliseconds = 10) {
    for (const value of values) {
        await new Promise((resolve) =>
            setTimeout(resolve, delayMilliseconds)
        );

        yield value;
    }
}

async function processStream(values) {
    const calculator = new StreamingMovingAverage(3);
    const records = [];

    for await (const value of simulatedDataStream(values)) {
        records.push({
            value,
            movingAverage: calculator.update(value)
        });
    }

    return records;
}

// -----------------------------------------------------------------------------
// 13. BUSINESS KPI PIPELINE
// -----------------------------------------------------------------------------

function calculateKpis(revenue, customers) {
    if (revenue.length !== customers.length) {
        throw new RangeError(
            "revenue and customers must have equal lengths"
        );
    }

    const cumulativeRevenue = runningTotal(revenue);
    const cumulativeCustomers = runningTotal(customers);
    const cumulativeAverage = runningAverage(revenue);
    const movingRevenue = movingAverage(
        revenue,
        3,
        1
    );

    return revenue.map((value, index) => ({
        period: index + 1,
        revenue: value,
        customers: customers[index],
        cumulativeRevenue: cumulativeRevenue[index],
        cumulativeCustomers: cumulativeCustomers[index],
        cumulativeAverage: cumulativeAverage[index],
        movingThreePeriodRevenue: movingRevenue[index],
        revenuePerCustomer:
            customers[index] === 0
                ? null
                : value / customers[index]
    }));
}

// -----------------------------------------------------------------------------
// 14. ASSERTIONS AND TESTS
// -----------------------------------------------------------------------------

function assertDeepEqual(actual, expected, message) {
    const actualText = JSON.stringify(actual);
    const expectedText = JSON.stringify(expected);

    if (actualText !== expectedText) {
        throw new Error(
            `${message}\nExpected: ${expectedText}\nActual: ${actualText}`
        );
    }
}

function assertClose(actual, expected, message, tolerance = 1e-9) {
    if (actual.length !== expected.length) {
        throw new Error(`${message}: different lengths`);
    }

    for (let index = 0; index < actual.length; index += 1) {
        if (Math.abs(actual[index] - expected[index]) > tolerance) {
            throw new Error(
                `${message} at index ${index}: ` +
                `${actual[index]} != ${expected[index]}`
            );
        }
    }
}

function runTests() {
    assertDeepEqual(
        runningTotal([1, 2, 3]),
        [1, 3, 6],
        "runningTotal failed"
    );

    assertClose(
        runningAverage([2, 4, 6]),
        [2, 3, 4],
        "runningAverage failed"
    );

    assertDeepEqual(
        movingSum([1, 2, 3, 4, 5], 3),
        [6, 9, 12],
        "movingSum failed"
    );

    assertClose(
        movingAverage([1, 2, 3, 4, 5], 3),
        [2, 3, 4],
        "movingAverage failed"
    );

    assertClose(
        movingAverage([1, 2, 3], 3, 1),
        [1, 1.5, 2],
        "partial movingAverage failed"
    );

    assertDeepEqual(
        movingMaximumOptimized([1, 5, 2, 4, 3], 3),
        [5, 5, 4],
        "movingMaximumOptimized failed"
    );

    assertDeepEqual(
        movingMinimumOptimized([1, 5, 2, 4, 3], 3),
        [1, 2, 2],
        "movingMinimumOptimized failed"
    );

    assertClose(
        weightedMovingAverage([10, 20, 30], [1, 2, 3]),
        [23.333333333333332],
        "weightedMovingAverage failed"
    );

    assertClose(
        exponentialMovingAverage([10, 20, 30], 0.5),
        [10, 15, 22.5],
        "exponentialMovingAverage failed"
    );

    const prefix = prefixSums([5, 8, 2, 10]);

    assertClose(
        [rangeSum(prefix, 1, 4)],
        [20],
        "rangeSum failed"
    );

    console.log("All JavaScript tests passed.");
}

// -----------------------------------------------------------------------------
// 15. DEMONSTRATIONS
// -----------------------------------------------------------------------------

async function main() {
    console.log("=".repeat(78));
    console.log("RUNNING AND MOVING CALCULATIONS");
    console.log("=".repeat(78));

    const values = [10, 20, 15, 30, 25];

    console.log("\nBasic running metrics");
    console.log("Values:", values);
    console.log("Running total:", runningTotal(values));
    console.log("Running count:", runningCount(values));
    console.log("Running minimum:", runningMinimum(values));
    console.log("Running maximum:", runningMaximum(values));
    console.log("Running average:", runningAverage(values));

    console.log("\nMoving calculations");
    console.log("Moving sum:", movingSum(values, 3));
    console.log("Moving average:", movingAverage(values, 3));
    console.log(
        "Partial moving average:",
        movingAverage(values, 3, 1)
    );

    console.log("\nWeighted calculations");
    console.log(
        "Weighted moving average:",
        weightedMovingAverage(values, [1, 2, 3])
    );
    console.log(
        "EMA:",
        exponentialMovingAverage(values, 0.3)
    );

    console.log("\nRolling statistics");
    console.log(
        "Moving standard deviation:",
        movingStandardDeviation(values, 3)
    );
    console.log(
        "Optimized moving maximum:",
        movingMaximumOptimized(values, 3)
    );
    console.log(
        "Optimized moving minimum:",
        movingMinimumOptimized(values, 3)
    );

    console.log("\nPrefix sums");
    const prefix = prefixSums(values);
    console.log("Prefix:", prefix);
    console.log("Range [1, 4):", rangeSum(prefix, 1, 4));

    console.log("\nMissing values");
    const incomplete = [10, null, 20, null, 30];
    console.log(
        "Input:",
        incomplete
    );
    console.log(
        "Running average ignoring missing:",
        runningAverageIgnoreMissing(incomplete)
    );
    console.log(
        "Moving average ignoring missing:",
        movingAverageIgnoreMissing(incomplete, 3, 1)
    );

    console.log("\nOnline variance");
    const variance = new OnlineVariance();

    for (const value of [10, 12, 9, 14, 13]) {
        variance.update(value);
        console.log(
            `Value=${value}, mean=${variance.mean.toFixed(3)}, ` +
            `variance=${variance.populationVariance()?.toFixed(3)}`
        );
    }

    console.log("\nStreaming asynchronous processing");

    const streamRecords = await processStream([
        100,
        110,
        105,
        120,
        130
    ]);

    console.table(streamRecords);

    console.log("\nBusiness KPI pipeline");

    console.table(
        calculateKpis(
            [1000, 1200, 900, 1500],
            [50, 60, 45, 75]
        )
    );

    console.log("\nMoving anomaly scores");

    const traffic = [
        1200, 1350, 1280, 1420, 1500,
        1620, 1580, 1750, 1690, 1810,
        1950, 1880, 2020, 2150, 2090
    ];

    console.table(
        traffic.map((value, index) => ({
            day: index + 1,
            traffic: value,
            cumulative: runningTotal(traffic)[index],
            movingAverage: movingAverage(
                traffic,
                7,
                1
            )[index],
            zScore: movingZScores(
                traffic,
                7
            )[index]
        }))
    );

    runTests();

    console.log("\nCompleted.");
}

main().catch((error) => {
    console.error("Execution failed:", error.message);
    process.exitCode = 1;
});
