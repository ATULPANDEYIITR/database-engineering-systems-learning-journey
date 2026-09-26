#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <optional>
#include <queue>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

/*
 * Running and Moving Calculations
 *
 * Complete C++17 case study.
 *
 * Scenario:
 * A technology platform receives daily operational telemetry:
 * traffic, revenue, transactions, response measurements, and customer
 * counts. The system needs cumulative metrics for reporting and moving
 * metrics for detecting trends and anomalies.
 *
 * The program demonstrates:
 * - Running totals
 * - Running averages
 * - Running minimums and maximums
 * - Moving sums
 * - Moving averages
 * - Weighted moving averages
 * - Exponential moving averages
 * - Rolling standard deviation
 * - Prefix sums
 * - O(n) monotonic-deque moving extrema
 * - Streaming calculations
 * - Online variance
 * - Validation
 * - Edge cases
 * - Complexity considerations
 *
 * Compile:
 *     g++ -std=c++17 -O2 main.cpp -o running_metrics
 */

using Number = double;

// -----------------------------------------------------------------------------
// UTILITY FUNCTIONS
// -----------------------------------------------------------------------------

void printSection(const std::string& title) {
    std::cout << "\n"
              << std::string(78, '=')
              << "\n"
              << title
              << "\n"
              << std::string(78, '=')
              << "\n";
}

void printVector(
    const std::string& label,
    const std::vector<Number>& values
) {
    std::cout << label << ": [";

    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i > 0) {
            std::cout << ", ";
        }

        std::cout << std::fixed
                  << std::setprecision(3)
                  << values[i];
    }

    std::cout << "]\n";
}

void validateWindow(
    std::size_t window,
    std::size_t size
) {
    if (window == 0) {
        throw std::invalid_argument(
            "window must be greater than zero"
        );
    }

    if (window > size) {
        throw std::invalid_argument(
            "window cannot exceed the number of observations"
        );
    }
}

// -----------------------------------------------------------------------------
// RUNNING TOTAL
// -----------------------------------------------------------------------------

std::vector<Number> runningTotal(
    const std::vector<Number>& values
) {
    std::vector<Number> result;
    result.reserve(values.size());

    Number total = 0.0;

    for (Number value : values) {
        total += value;
        result.push_back(total);
    }

    return result;
}

// -----------------------------------------------------------------------------
// RUNNING AVERAGE
// -----------------------------------------------------------------------------

std::vector<Number> runningAverage(
    const std::vector<Number>& values
) {
    std::vector<Number> result;
    result.reserve(values.size());

    Number average = 0.0;
    std::size_t count = 0;

    for (Number value : values) {
        ++count;

        // Online mean:
        //
        // mean_new =
        //     mean_old + (value - mean_old) / count
        //
        // This avoids repeatedly summing the entire prefix.
        average += (value - average)
                   / static_cast<Number>(count);

        result.push_back(average);
    }

    return result;
}

// -----------------------------------------------------------------------------
// RUNNING MINIMUM AND MAXIMUM
// -----------------------------------------------------------------------------

std::vector<Number> runningMinimum(
    const std::vector<Number>& values
) {
    std::vector<Number> result;
    result.reserve(values.size());

    if (values.empty()) {
        return result;
    }

    Number current = values.front();

    for (Number value : values) {
        current = std::min(current, value);
        result.push_back(current);
    }

    return result;
}

std::vector<Number> runningMaximum(
    const std::vector<Number>& values
) {
    std::vector<Number> result;
    result.reserve(values.size());

    if (values.empty()) {
        return result;
    }

    Number current = values.front();

    for (Number value : values) {
        current = std::max(current, value);
        result.push_back(current);
    }

    return result;
}

// -----------------------------------------------------------------------------
// MOVING SUM
// -----------------------------------------------------------------------------

std::vector<Number> movingSum(
    const std::vector<Number>& values,
    std::size_t window
) {
    validateWindow(window, values.size());

    std::vector<Number> result;
    result.reserve(values.size() - window + 1);

    Number currentSum = std::accumulate(
        values.begin(),
        values.begin() + static_cast<std::ptrdiff_t>(window),
        0.0
    );

    result.push_back(currentSum);

    for (std::size_t index = window;
         index < values.size();
         ++index) {

        currentSum += values[index];
        currentSum -= values[index - window];

        result.push_back(currentSum);
    }

    return result;
}

// -----------------------------------------------------------------------------
// MOVING AVERAGE
// -----------------------------------------------------------------------------

std::vector<std::optional<Number>> movingAverage(
    const std::vector<Number>& values,
    std::size_t window,
    std::size_t minPeriods
) {
    if (window == 0) {
        throw std::invalid_argument(
            "window must be greater than zero"
        );
    }

    if (minPeriods == 0 || minPeriods > window) {
        throw std::invalid_argument(
            "minPeriods must be between 1 and window"
        );
    }

    std::vector<std::optional<Number>> result;
    result.reserve(values.size());

    Number currentSum = 0.0;
    std::queue<Number> queue;

    for (Number value : values) {
        queue.push(value);
        currentSum += value;

        if (queue.size() > window) {
            currentSum -= queue.front();
            queue.pop();
        }

        if (queue.size() >= minPeriods) {
            result.push_back(
                currentSum /
                static_cast<Number>(queue.size())
            );
        } else {
            result.push_back(std::nullopt);
        }
    }

    return result;
}

// -----------------------------------------------------------------------------
// WEIGHTED MOVING AVERAGE
// -----------------------------------------------------------------------------

std::vector<Number> weightedMovingAverage(
    const std::vector<Number>& values,
    const std::vector<Number>& weights
) {
    if (weights.empty()) {
        throw std::invalid_argument(
            "weights cannot be empty"
        );
    }

    if (weights.size() > values.size()) {
        return {};
    }

    Number weightTotal = 0.0;

    for (Number weight : weights) {
        if (weight < 0.0) {
            throw std::invalid_argument(
                "weights cannot be negative"
            );
        }

        weightTotal += weight;
    }

    if (weightTotal == 0.0) {
        throw std::invalid_argument(
            "weight total must be positive"
        );
    }

    std::vector<Number> result;

    const std::size_t window = weights.size();

    for (std::size_t index = window - 1;
         index < values.size();
         ++index) {

        Number weightedSum = 0.0;

        for (std::size_t offset = 0;
             offset < window;
             ++offset) {

            weightedSum +=
                values[index - window + 1 + offset]
                * weights[offset];
        }

        result.push_back(weightedSum / weightTotal);
    }

    return result;
}

// -----------------------------------------------------------------------------
// EXPONENTIAL MOVING AVERAGE
// -----------------------------------------------------------------------------

std::vector<Number> exponentialMovingAverage(
    const std::vector<Number>& values,
    Number alpha
) {
    if (!(alpha > 0.0 && alpha <= 1.0)) {
        throw std::invalid_argument(
            "alpha must be greater than 0 and at most 1"
        );
    }

    if (values.empty()) {
        return {};
    }

    std::vector<Number> result;
    result.reserve(values.size());

    Number current = values.front();
    result.push_back(current);

    for (std::size_t index = 1;
         index < values.size();
         ++index) {

        current =
            alpha * values[index]
            + (1.0 - alpha) * current;

        result.push_back(current);
    }

    return result;
}

// -----------------------------------------------------------------------------
// ROLLING STANDARD DEVIATION
// -----------------------------------------------------------------------------

std::vector<Number> movingStandardDeviation(
    const std::vector<Number>& values,
    std::size_t window,
    bool sample
) {
    validateWindow(window, values.size());

    if (sample && window < 2) {
        throw std::invalid_argument(
            "sample standard deviation requires window >= 2"
        );
    }

    std::vector<Number> result;

    for (std::size_t index = window - 1;
         index < values.size();
         ++index) {

        Number total = 0.0;

        for (std::size_t offset = 0;
             offset < window;
             ++offset) {

            total += values[index - window + 1 + offset];
        }

        const Number average =
            total / static_cast<Number>(window);

        Number squaredDeviation = 0.0;

        for (std::size_t offset = 0;
             offset < window;
             ++offset) {

            const Number difference =
                values[index - window + 1 + offset]
                - average;

            squaredDeviation += difference * difference;
        }

        const Number denominator =
            static_cast<Number>(
                sample ? window - 1 : window
            );

        result.push_back(
            std::sqrt(squaredDeviation / denominator)
        );
    }

    return result;
}

// -----------------------------------------------------------------------------
// PREFIX SUMS
// -----------------------------------------------------------------------------

std::vector<Number> prefixSums(
    const std::vector<Number>& values
) {
    std::vector<Number> prefix;
    prefix.reserve(values.size() + 1);

    // The leading zero makes half-open range queries convenient.
    prefix.push_back(0.0);

    for (Number value : values) {
        prefix.push_back(prefix.back() + value);
    }

    return prefix;
}

Number rangeSum(
    const std::vector<Number>& prefix,
    std::size_t left,
    std::size_t right
) {
    if (left > right || right >= prefix.size()) {
        throw std::out_of_range(
            "invalid prefix-sum range"
        );
    }

    return prefix[right] - prefix[left];
}

// -----------------------------------------------------------------------------
// O(n) MOVING MAXIMUM USING A MONOTONIC DEQUE
// -----------------------------------------------------------------------------

std::vector<Number> movingMaximumOptimized(
    const std::vector<Number>& values,
    std::size_t window
) {
    validateWindow(window, values.size());

    std::deque<std::size_t> indices;
    std::vector<Number> result;

    for (std::size_t index = 0;
         index < values.size();
         ++index) {

        // Remove indexes outside the current window.
        while (
            !indices.empty() &&
            indices.front() <= index - window
        ) {
            indices.pop_front();
        }

        // Maintain decreasing values in the deque.
        while (
            !indices.empty() &&
            values[indices.back()] <= values[index]
        ) {
            indices.pop_back();
        }

        indices.push_back(index);

        if (index + 1 >= window) {
            result.push_back(values[indices.front()]);
        }
    }

    return result;
}

// -----------------------------------------------------------------------------
// O(n) MOVING MINIMUM USING A MONOTONIC DEQUE
// -----------------------------------------------------------------------------

std::vector<Number> movingMinimumOptimized(
    const std::vector<Number>& values,
    std::size_t window
) {
    validateWindow(window, values.size());

    std::deque<std::size_t> indices;
    std::vector<Number> result;

    for (std::size_t index = 0;
         index < values.size();
         ++index) {

        while (
            !indices.empty() &&
            indices.front() <= index - window
        ) {
            indices.pop_front();
        }

        while (
            !indices.empty() &&
            values[indices.back()] >= values[index]
        ) {
            indices.pop_back();
        }

        indices.push_back(index);

        if (index + 1 >= window) {
            result.push_back(values[indices.front()]);
        }
    }

    return result;
}

// -----------------------------------------------------------------------------
// STREAMING MOVING AVERAGE
// -----------------------------------------------------------------------------

class StreamingMovingAverage {
private:
    std::size_t window_;
    std::queue<Number> values_;
    Number total_;

public:
    explicit StreamingMovingAverage(std::size_t window)
        : window_(window), total_(0.0) {

        if (window == 0) {
            throw std::invalid_argument(
                "window must be greater than zero"
            );
        }
    }

    std::optional<Number> update(Number value) {
        values_.push(value);
        total_ += value;

        if (values_.size() > window_) {
            total_ -= values_.front();
            values_.pop();
        }

        if (values_.size() < window_) {
            return std::nullopt;
        }

        return total_ /
               static_cast<Number>(window_);
    }
};

// -----------------------------------------------------------------------------
// ONLINE VARIANCE: WELFORD'S ALGORITHM
// -----------------------------------------------------------------------------

class OnlineVariance {
private:
    std::size_t count_;
    Number mean_;
    Number m2_;

public:
    OnlineVariance()
        : count_(0), mean_(0.0), m2_(0.0) {}

    void update(Number value) {
        ++count_;

        const Number delta =
            value - mean_;

        mean_ +=
            delta /
            static_cast<Number>(count_);

        const Number deltaAfterMean =
            value - mean_;

        m2_ +=
            delta * deltaAfterMean;
    }

    std::size_t count() const {
        return count_;
    }

    Number mean() const {
        return mean_;
    }

    std::optional<Number> populationVariance() const {
        if (count_ == 0) {
            return std::nullopt;
        }

        return m2_ /
               static_cast<Number>(count_);
    }

    std::optional<Number> sampleVariance() const {
        if (count_ < 2) {
            return std::nullopt;
        }

        return m2_ /
               static_cast<Number>(count_ - 1);
    }
};

// -----------------------------------------------------------------------------
// BUSINESS KPI MODEL
// -----------------------------------------------------------------------------

struct KpiRecord {
    std::size_t period;
    Number revenue;
    Number customers;
    Number cumulativeRevenue;
    Number cumulativeCustomers;
    Number cumulativeAverage;
    std::optional<Number> movingRevenue;
    std::optional<Number> revenuePerCustomer;
};

std::vector<KpiRecord> calculateKpis(
    const std::vector<Number>& revenue,
    const std::vector<Number>& customers
) {
    if (revenue.size() != customers.size()) {
        throw std::invalid_argument(
            "revenue and customers must have equal lengths"
        );
    }

    const auto cumulativeRevenue =
        runningTotal(revenue);

    const auto cumulativeCustomers =
        runningTotal(customers);

    const auto cumulativeAverage =
        runningAverage(revenue);

    const auto movingRevenue =
        movingAverage(revenue, 3, 1);

    std::vector<KpiRecord> result;
    result.reserve(revenue.size());

    for (std::size_t index = 0;
         index < revenue.size();
         ++index) {

        std::optional<Number> revenuePerCustomer;

        if (customers[index] != 0.0) {
            revenuePerCustomer =
                revenue[index] /
                customers[index];
        }

        result.push_back(
            KpiRecord{
                index + 1,
                revenue[index],
                customers[index],
                cumulativeRevenue[index],
                cumulativeCustomers[index],
                cumulativeAverage[index],
                movingRevenue[index],
                revenuePerCustomer
            }
        );
    }

    return result;
}

// -----------------------------------------------------------------------------
// TESTING
// -----------------------------------------------------------------------------

void assertNear(
    Number actual,
    Number expected,
    const std::string& message,
    Number tolerance = 1e-9
) {
    if (std::abs(actual - expected) > tolerance) {
        throw std::runtime_error(
            message +
            ": expected " +
            std::to_string(expected) +
            ", got " +
            std::to_string(actual)
        );
    }
}

void runTests() {
    printSection("AUTOMATED TESTS");

    {
        const auto result =
            runningTotal({1, 2, 3});

        assertNear(result[0], 1.0, "runningTotal[0]");
        assertNear(result[1], 3.0, "runningTotal[1]");
        assertNear(result[2], 6.0, "runningTotal[2]");
    }

    {
        const auto result =
            runningAverage({2, 4, 6});

        assertNear(result[0], 2.0, "runningAverage[0]");
        assertNear(result[1], 3.0, "runningAverage[1]");
        assertNear(result[2], 4.0, "runningAverage[2]");
    }

    {
        const auto result =
            movingSum({1, 2, 3, 4, 5}, 3);

        assertNear(result[0], 6.0, "movingSum[0]");
        assertNear(result[1], 9.0, "movingSum[1]");
        assertNear(result[2], 12.0, "movingSum[2]");
    }

    {
        const auto result =
            movingAverage({1, 2, 3, 4, 5}, 3, 3);

        assertNear(
            *result[0],
            2.0,
            "movingAverage[0]"
        );

        assertNear(
            *result[1],
            3.0,
            "movingAverage[1]"
        );

        assertNear(
            *result[2],
            4.0,
            "movingAverage[2]"
        );
    }

    {
        const auto result =
            weightedMovingAverage(
                {10, 20, 30},
                {1, 2, 3}
            );

        assertNear(
            result[0],
            23.333333333333332,
            "weightedMovingAverage"
        );
    }

    {
        const auto result =
            exponentialMovingAverage(
                {10, 20, 30},
                0.5
            );

        assertNear(result[0], 10.0, "EMA[0]");
        assertNear(result[1], 15.0, "EMA[1]");
        assertNear(result[2], 22.5, "EMA[2]");
    }

    {
        const auto result =
            movingMaximumOptimized(
                {1, 5, 2, 4, 3},
                3
            );

        assertNear(result[0], 5.0, "maximum[0]");
        assertNear(result[1], 5.0, "maximum[1]");
        assertNear(result[2], 4.0, "maximum[2]");
    }

    {
        const auto result =
            movingMinimumOptimized(
                {1, 5, 2, 4, 3},
                3
            );

        assertNear(result[0], 1.0, "minimum[0]");
        assertNear(result[1], 2.0, "minimum[1]");
        assertNear(result[2], 2.0, "minimum[2]");
    }

    {
        const auto prefix =
            prefixSums({5, 8, 2, 10});

        assertNear(
            rangeSum(prefix, 1, 4),
            20.0,
            "rangeSum"
        );
    }

    {
        OnlineVariance variance;

        for (Number value : {10, 12, 9, 14, 13}) {
            variance.update(value);
        }

        if (!variance.populationVariance().has_value()) {
            throw std::runtime_error(
                "variance should exist"
            );
        }
    }

    std::cout << "All C++ tests passed.\n";
}

// -----------------------------------------------------------------------------
// CASE STUDY OUTPUT
// -----------------------------------------------------------------------------

void printCaseStudy(
    const std::vector<Number>& traffic
) {
    printSection("INDUSTRY-STYLE TELEMETRY CASE STUDY");

    const auto cumulative =
        runningTotal(traffic);

    const auto cumulativeAverage =
        runningAverage(traffic);

    const auto moving =
        movingAverage(traffic, 7, 1);

    const auto ema =
        exponentialMovingAverage(traffic, 0.3);

    std::cout
        << std::setw(5) << "Day"
        << std::setw(12) << "Traffic"
        << std::setw(15) << "Cumulative"
        << std::setw(14) << "CumAvg"
        << std::setw(14) << "7-Day Avg"
        << std::setw(14) << "EMA"
        << "\n";

    std::cout << std::string(74, '-') << "\n";

    for (std::size_t index = 0;
         index < traffic.size();
         ++index) {

        std::cout
            << std::setw(5) << index + 1
            << std::setw(12)
            << std::fixed
            << std::setprecision(0)
            << traffic[index]
            << std::setw(15)
            << cumulative[index]
            << std::setw(14)
            << std::setprecision(2)
            << cumulativeAverage[index]
            << std::setw(14);

        if (moving[index].has_value()) {
            std::cout
                << moving[index].value();
        } else {
            std::cout << "N/A";
        }

        std::cout
            << std::setw(14)
            << ema[index]
            << "\n";
    }
}

// -----------------------------------------------------------------------------
// MAIN
// -----------------------------------------------------------------------------

int main() {
    try {
        printSection("RUNNING AND MOVING CALCULATIONS");

        const std::vector<Number> values = {
            10, 20, 15, 30, 25, 40
        };

        printVector(
            "Values",
            values
        );

        printVector(
            "Running total",
            runningTotal(values)
        );

        printVector(
            "Running average",
            runningAverage(values)
        );

        printVector(
            "Running minimum",
            runningMinimum(values)
        );

        printVector(
            "Running maximum",
            runningMaximum(values)
        );

        printVector(
            "Moving sum",
            movingSum(values, 3)
        );

        const auto averages =
            movingAverage(values, 3, 1);

        std::cout << "Moving average: [";

        for (std::size_t index = 0;
             index < averages.size();
             ++index) {

            if (index > 0) {
                std::cout << ", ";
            }

            if (averages[index].has_value()) {
                std::cout << averages[index].value();
            } else {
                std::cout << "N/A";
            }
        }

        std::cout << "]\n";

        printVector(
            "Weighted moving average",
            weightedMovingAverage(
                values,
                {1, 2, 3}
            )
        );

        printVector(
            "EMA",
            exponentialMovingAverage(
                values,
                0.3
            )
        );

        printVector(
            "Moving standard deviation",
            movingStandardDeviation(
                values,
                3,
                false
            )
        );

        printVector(
            "Optimized moving maximum",
            movingMaximumOptimized(
                values,
                3
            )
        );

        printVector(
            "Optimized moving minimum",
            movingMinimumOptimized(
                values,
                3
            )
        );

        const auto prefix =
            prefixSums(values);

        printVector(
            "Prefix sums",
            prefix
        );

        std::cout
            << "Range sum [1, 5): "
            << rangeSum(prefix, 1, 5)
            << "\n";

        printSection("STREAMING CALCULATION");

        StreamingMovingAverage stream(3);

        for (Number value : values) {
            const auto result =
                stream.update(value);

            std::cout
                << "Input "
                << value
                << " -> ";

            if (result.has_value()) {
                std::cout << result.value();
            } else {
                std::cout << "warming up";
            }

            std::cout << "\n";
        }

        printSection("ONLINE VARIANCE");

        OnlineVariance variance;

        for (Number value : values) {
            variance.update(value);

            std::cout
                << "Value="
                << value
                << ", Mean="
                << variance.mean()
                << ", Population variance=";

            if (variance.populationVariance().has_value()) {
                std::cout
                    << variance.populationVariance().value();
            } else {
                std::cout << "N/A";
            }

            std::cout << "\n";
        }

        printSection("BUSINESS KPI CASE STUDY");

        const auto kpis =
            calculateKpis(
                {1000, 1200, 900, 1500, 1800},
                {50, 60, 45, 75, 90}
            );

        for (const auto& record : kpis) {
            std::cout
                << "Period "
                << record.period
                << ": revenue="
                << record.revenue
                << ", cumulativeRevenue="
                << record.cumulativeRevenue
                << ", cumulativeCustomers="
                << record.cumulativeCustomers
                << ", revenuePerCustomer=";

            if (record.revenuePerCustomer.has_value()) {
                std::cout
                    << record.revenuePerCustomer.value();
            } else {
                std::cout << "N/A";
            }

            std::cout << "\n";
        }

        printCaseStudy({
            1200, 1350, 1280, 1420, 1500,
            1620, 1580, 1750, 1690, 1810,
            1950, 1880, 2020, 2150, 2090
        });

        runTests();

        printSection("EDGE CASE VALIDATION");

        try {
            movingAverage(
                {1, 2, 3},
                0,
                1
            );
        } catch (const std::exception& error) {
            std::cout
                << "Correctly rejected invalid window: "
                << error.what()
                << "\n";
        }

        try {
            exponentialMovingAverage(
                {1, 2, 3},
                1.5
            );
        } catch (const std::exception& error) {
            std::cout
                << "Correctly rejected invalid alpha: "
                << error.what()
                << "\n";
        }

        std::cout << "\nProgram completed successfully.\n";

        return 0;
    }
    catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << "\n";

        return 1;
    }
}
