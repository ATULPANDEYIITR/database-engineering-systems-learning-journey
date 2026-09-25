/*
 * Analytical Windows: LAG, LEAD, FIRST_VALUE, LAST_VALUE
 * ========================================================
 *
 * C++17 case study:
 *
 * A transaction analytics engine for a retail organization.
 *
 * The program models the analytical semantics commonly implemented in SQL
 * window functions. It progressively develops:
 *
 *   1. Transaction storage
 *   2. Partitioning by customer
 *   3. Deterministic ordering
 *   4. LAG
 *   5. LEAD
 *   6. FIRST_VALUE
 *   7. LAST_VALUE
 *   8. Percentage-change analysis
 *   9. Activity-gap analysis
 *  10. Customer lifecycle analysis
 *  11. Validation
 *  12. Complexity and architectural considerations
 *
 * Build:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic analytical_windows.cpp -o analytical_windows
 *
 * Run:
 *   ./analytical_windows
 */

#include <algorithm>
#include <cassert>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

// -----------------------------------------------------------------------------
// 1. DOMAIN MODEL
// -----------------------------------------------------------------------------

struct Sale {
    int saleId;
    int customerId;
    string region;
    string date;
    string product;
    int quantity;
    double unitPrice;

    double revenue() const {
        return quantity * unitPrice;
    }
};

struct CustomerAnalysis {
    int customerId;
    string date;
    string product;
    double revenue;

    optional<double> previousRevenue;
    optional<double> nextRevenue;

    optional<string> previousProduct;
    optional<string> nextProduct;

    optional<double> firstRevenue;
    optional<double> lastRevenue;

    optional<double> percentageChange;
    optional<int> daysSincePrevious;

    string movement;
};

// -----------------------------------------------------------------------------
// 2. VALIDATION
// -----------------------------------------------------------------------------

void validateSale(const Sale& sale) {
    if (sale.saleId <= 0) {
        throw invalid_argument("saleId must be positive");
    }

    if (sale.customerId <= 0) {
        throw invalid_argument("customerId must be positive");
    }

    if (sale.quantity <= 0) {
        throw invalid_argument("quantity must be positive");
    }

    if (sale.unitPrice < 0) {
        throw invalid_argument("unitPrice cannot be negative");
    }

    if (sale.date.empty()) {
        throw invalid_argument("date cannot be empty");
    }

    if (sale.product.empty()) {
        throw invalid_argument("product cannot be empty");
    }
}

// -----------------------------------------------------------------------------
// 3. DATE UTILITIES
// -----------------------------------------------------------------------------

struct SimpleDate {
    int year;
    int month;
    int day;
};

SimpleDate parseDate(const string& value) {
    if (value.size() != 10 ||
        value[4] != '-' ||
        value[7] != '-') {
        throw invalid_argument("Date must use YYYY-MM-DD format: " + value);
    }

    return {
        stoi(value.substr(0, 4)),
        stoi(value.substr(5, 2)),
        stoi(value.substr(8, 2))
    };
}

bool isLeapYear(int year) {
    return (year % 400 == 0) ||
           (year % 4 == 0 && year % 100 != 0);
}

int daysInMonth(int year, int month) {
    static const int days[] = {
        31, 28, 31, 30, 31, 30,
        31, 31, 30, 31, 30, 31
    };

    if (month == 2 && isLeapYear(year)) {
        return 29;
    }

    return days[month - 1];
}

long long daysFromCivil(int year, unsigned month, unsigned day) {
    year -= month <= 2;

    const long long era =
        (year >= 0 ? year : year - 399) / 400;

    const unsigned yearOfEra =
        static_cast<unsigned>(year - era * 400);

    const unsigned dayOfYear =
        (153 * (month + (month > 2 ? -3 : 9)) + 2) / 5
        + day - 1;

    const unsigned dayOfEra =
        yearOfEra * 365
        + yearOfEra / 4
        - yearOfEra / 100
        + dayOfYear;

    return era * 146097
         + static_cast<long long>(dayOfEra)
         - 719468;
}

int daysBetween(const string& earlier, const string& later) {
    const SimpleDate a = parseDate(earlier);
    const SimpleDate b = parseDate(later);

    const long long first =
        daysFromCivil(a.year, a.month, a.day);

    const long long second =
        daysFromCivil(b.year, b.month, b.day);

    return static_cast<int>(second - first);
}

// -----------------------------------------------------------------------------
// 4. DATASET
// -----------------------------------------------------------------------------

vector<Sale> createSales() {
    vector<Sale> sales = {
        {1, 101, "North", "2026-01-05", "Laptop", 1, 1200.00},
        {2, 101, "North", "2026-01-20", "Mouse", 2, 25.00},
        {3, 101, "North", "2026-02-03", "Monitor", 1, 350.00},
        {4, 101, "North", "2026-02-20", "Keyboard", 1, 80.00},
        {5, 101, "North", "2026-03-10", "Laptop", 1, 1250.00},

        {6, 102, "South", "2026-01-07", "Phone", 1, 800.00},
        {7, 102, "South", "2026-01-25", "Case", 2, 30.00},
        {8, 102, "South", "2026-02-11", "Phone", 1, 820.00},
        {9, 102, "South", "2026-03-05", "Earbuds", 1, 150.00},

        {10, 103, "North", "2026-01-15", "Tablet", 1, 500.00},
        {11, 103, "North", "2026-02-15", "Tablet", 1, 500.00},
        {12, 103, "North", "2026-03-15", "Stylus", 1, 60.00},

        {13, 104, "West", "2026-01-03", "Camera", 1, 1000.00},
        {14, 104, "West", "2026-01-03", "Tripod", 1, 120.00},
        {15, 104, "West", "2026-02-01", "Lens", 1, 700.00},
        {16, 104, "West", "2026-03-01", "Camera", 1, 1100.00},

        {17, 105, "East", "2026-02-01", "Chair", 1, 250.00},
        {18, 105, "East", "2026-03-01", "Desk", 1, 450.00}
    };

    for (const Sale& sale : sales) {
        validateSale(sale);
    }

    return sales;
}

// -----------------------------------------------------------------------------
// 5. DETERMINISTIC ORDERING
// -----------------------------------------------------------------------------

bool saleOrder(const Sale& a, const Sale& b) {
    if (a.customerId != b.customerId) {
        return a.customerId < b.customerId;
    }

    if (a.date != b.date) {
        return a.date < b.date;
    }

    // saleId makes ordering deterministic when dates are equal.
    return a.saleId < b.saleId;
}

// -----------------------------------------------------------------------------
// 6. PARTITIONING
// -----------------------------------------------------------------------------

map<int, vector<Sale>> partitionByCustomer(
    const vector<Sale>& sales
) {
    map<int, vector<Sale>> partitions;

    for (const Sale& sale : sales) {
        partitions[sale.customerId].push_back(sale);
    }

    for (auto& [customerId, rows] : partitions) {
        sort(
            rows.begin(),
            rows.end(),
            [](const Sale& a, const Sale& b) {
                if (a.date != b.date) {
                    return a.date < b.date;
                }

                return a.saleId < b.saleId;
            }
        );
    }

    return partitions;
}

// -----------------------------------------------------------------------------
// 7. GENERIC LAG
// -----------------------------------------------------------------------------

template <typename T>
optional<T> lag(
    const vector<T>& values,
    size_t index,
    size_t offset = 1
) {
    if (offset > index) {
        return nullopt;
    }

    return values[index - offset];
}

// -----------------------------------------------------------------------------
// 8. GENERIC LEAD
// -----------------------------------------------------------------------------

template <typename T>
optional<T> lead(
    const vector<T>& values,
    size_t index,
    size_t offset = 1
) {
    if (index + offset >= values.size()) {
        return nullopt;
    }

    return values[index + offset];
}

// -----------------------------------------------------------------------------
// 9. FIRST_VALUE
// -----------------------------------------------------------------------------

template <typename T>
optional<T> firstValue(const vector<T>& values) {
    if (values.empty()) {
        return nullopt;
    }

    return values.front();
}

// -----------------------------------------------------------------------------
// 10. LAST_VALUE
// -----------------------------------------------------------------------------

template <typename T>
optional<T> lastValue(const vector<T>& values) {
    if (values.empty()) {
        return nullopt;
    }

    return values.back();
}

// -----------------------------------------------------------------------------
// 11. MOVEMENT CLASSIFICATION
// -----------------------------------------------------------------------------

string classifyMovement(
    double current,
    const optional<double>& previous
) {
    if (!previous.has_value()) {
        return "FIRST SALE";
    }

    if (current > previous.value()) {
        return "INCREASE";
    }

    if (current < previous.value()) {
        return "DECREASE";
    }

    return "UNCHANGED";
}

// -----------------------------------------------------------------------------
// 12. PERCENTAGE CHANGE
// -----------------------------------------------------------------------------

optional<double> percentageChange(
    double current,
    const optional<double>& previous
) {
    if (!previous.has_value()) {
        return nullopt;
    }

    if (previous.value() == 0.0) {
        // Division by zero is not analytically meaningful here.
        return nullopt;
    }

    return ((current - previous.value()) / previous.value()) * 100.0;
}

// -----------------------------------------------------------------------------
// 13. CUSTOMER ANALYTICS ENGINE
// -----------------------------------------------------------------------------

class CustomerAnalyticsEngine {
private:
    vector<Sale> sales;

public:
    explicit CustomerAnalyticsEngine(vector<Sale> input)
        : sales(std::move(input)) {}

    vector<CustomerAnalysis> analyze() const {
        const auto partitions = partitionByCustomer(sales);

        vector<CustomerAnalysis> result;

        for (const auto& [customerId, rows] : partitions) {
            vector<double> revenues;
            vector<string> products;
            vector<string> dates;

            revenues.reserve(rows.size());
            products.reserve(rows.size());
            dates.reserve(rows.size());

            for (const Sale& sale : rows) {
                revenues.push_back(sale.revenue());
                products.push_back(sale.product);
                dates.push_back(sale.date);
            }

            const optional<double> firstRevenue =
                firstValue(revenues);

            const optional<double> lastRevenue =
                lastValue(revenues);

            for (size_t index = 0; index < rows.size(); ++index) {
                CustomerAnalysis analysis;

                analysis.customerId = customerId;
                analysis.date = rows[index].date;
                analysis.product = rows[index].product;
                analysis.revenue = rows[index].revenue();

                analysis.previousRevenue =
                    lag(revenues, index);

                analysis.nextRevenue =
                    lead(revenues, index);

                analysis.previousProduct =
                    lag(products, index);

                analysis.nextProduct =
                    lead(products, index);

                analysis.firstRevenue = firstRevenue;
                analysis.lastRevenue = lastRevenue;

                analysis.percentageChange =
                    percentageChange(
                        analysis.revenue,
                        analysis.previousRevenue
                    );

                if (index > 0) {
                    analysis.daysSincePrevious =
                        daysBetween(
                            dates[index - 1],
                            dates[index]
                        );
                }

                analysis.movement =
                    classifyMovement(
                        analysis.revenue,
                        analysis.previousRevenue
                    );

                result.push_back(std::move(analysis));
            }
        }

        return result;
    }
};

// -----------------------------------------------------------------------------
// 14. REPORTING
// -----------------------------------------------------------------------------

string optionalNumber(const optional<double>& value) {
    if (!value.has_value()) {
        return "-";
    }

    ostringstream stream;
    stream << fixed << setprecision(2) << value.value();
    return stream.str();
}

string optionalInteger(const optional<int>& value) {
    if (!value.has_value()) {
        return "-";
    }

    return to_string(value.value());
}

string optionalText(const optional<string>& value) {
    if (!value.has_value()) {
        return "-";
    }

    return value.value();
}

void printAnalysis(
    const vector<CustomerAnalysis>& analysis
) {
    cout << "\n"
         << left
         << setw(10) << "Customer"
         << setw(13) << "Date"
         << setw(14) << "Product"
         << setw(12) << "Revenue"
         << setw(13) << "Previous"
         << setw(13) << "Next"
         << setw(13) << "First"
         << setw(13) << "Last"
         << setw(12) << "Change%"
         << setw(10) << "GapDays"
         << setw(14) << "Movement"
         << "\n";

    cout << string(147, '-') << "\n";

    for (const auto& row : analysis) {
        cout << left
             << setw(10) << row.customerId
             << setw(13) << row.date
             << setw(14) << row.product
             << setw(12) << fixed << setprecision(2) << row.revenue
             << setw(13) << optionalNumber(row.previousRevenue)
             << setw(13) << optionalNumber(row.nextRevenue)
             << setw(13) << optionalNumber(row.firstRevenue)
             << setw(13) << optionalNumber(row.lastRevenue)
             << setw(12) << optionalNumber(row.percentageChange)
             << setw(10) << optionalInteger(row.daysSincePrevious)
             << setw(14) << row.movement
             << "\n";
    }
}

// -----------------------------------------------------------------------------
// 15. CUSTOMER LIFECYCLE REPORT
// -----------------------------------------------------------------------------

void printLifecycleReport(
    const vector<CustomerAnalysis>& analysis
) {
    cout << "\nCustomer lifecycle analysis\n";
    cout << string(76, '-') << "\n";

    map<int, CustomerAnalysis> firstRows;

    for (const auto& row : analysis) {
        if (!firstRows.contains(row.customerId)) {
            firstRows[row.customerId] = row;
        }
    }

    cout << left
         << setw(12) << "Customer"
         << setw(16) << "First Revenue"
         << setw(16) << "Last Revenue"
         << setw(16) << "Difference"
         << setw(16) << "Status"
         << "\n";

    cout << string(76, '-') << "\n";

    for (const auto& [customerId, row] : firstRows) {
        const double first = row.firstRevenue.value();
        const double last = row.lastRevenue.value();
        const double difference = last - first;

        string status;

        if (difference > 0) {
            status = "Higher";
        } else if (difference < 0) {
            status = "Lower";
        } else {
            status = "Unchanged";
        }

        cout << left
             << setw(12) << customerId
             << setw(16) << fixed << setprecision(2) << first
             << setw(16) << last
             << setw(16) << difference
             << setw(16) << status
             << "\n";
    }
}

// -----------------------------------------------------------------------------
// 16. EDGE CASE TESTS
// -----------------------------------------------------------------------------

void runWindowFunctionTests() {
    cout << "\nRunning analytical-window tests...\n";

    vector<int> values = {10, 20, 30};

    assert(!lag(values, 0).has_value());
    assert(lag(values, 1).value() == 10);

    assert(lag(values, 0, 2).value() == 10);
    assert(lag(values, 1, 2).value() == 20);

    assert(!lead(values, 2).has_value());
    assert(lead(values, 0).value() == 20);
    assert(lead(values, 1).value() == 30);

    assert(firstValue(values).value() == 10);
    assert(lastValue(values).value() == 30);

    vector<int> empty;
    assert(!firstValue(empty).has_value());
    assert(!lastValue(empty).has_value());

    assert(
        percentageChange(
            120.0,
            optional<double>(100.0)
        ).value() == 20.0
    );

    assert(
        !percentageChange(
            100.0,
            optional<double>(0.0)
        ).has_value()
    );

    assert(
        daysBetween(
            "2026-01-01",
            "2026-01-31"
        ) == 30
    );

    cout << "All tests passed.\n";
}

// -----------------------------------------------------------------------------
// 17. PERFORMANCE ANALYSIS
// -----------------------------------------------------------------------------

void printPerformanceAnalysis() {
    cout << R"(
Performance model
-----------------
Let n be the number of input rows.

1. Partition construction is O(n).
2. Sorting all partitions is O(n log n) in the general case.
3. LAG and LEAD access are O(1) per row after sorting.
4. FIRST_VALUE and LAST_VALUE are O(1) per row once the partition is ordered.
5. The overall analytical pipeline is therefore generally O(n log n).
6. Memory consumption is O(n) when partitions and analytical results are
   materialized.
7. A database engine can optimize partition/order processing with indexes,
   sort operators, memory grants, parallel execution, and query planning.
8. Reusing the same partition/order definition can avoid unnecessary work.
9. A deterministic tie-breaker prevents unstable relative-row results.
10. Large analytical workloads should consider partition cardinality,
    data distribution, sorting cost, and intermediate-result size.
)";
}

// -----------------------------------------------------------------------------
// 18. DESIGN TRADE-OFFS
// -----------------------------------------------------------------------------

void printDesignTradeoffs() {
    cout << R"(
Design considerations
---------------------
LAG and LEAD:
    Best when the business question concerns relative rows.

FIRST_VALUE:
    Useful for establishing the initial state of an entity or group.

LAST_VALUE:
    Useful for final state analysis, but requires careful frame semantics
    in SQL. In this C++ model, lastValue() explicitly means the final
    element of the ordered partition.

PARTITION BY:
    Separates independent analytical histories.

ORDER BY:
    Defines the meaning of "previous", "next", "first", and "last".

Tie handling:
    Ordering only by date can be ambiguous when multiple transactions
    share the same date. saleId is therefore used as a deterministic
    secondary key.

NULL/missing values:
    The C++ optional type represents the absence of a previous or next row.
)";
}

// -----------------------------------------------------------------------------
// 19. MAIN CASE STUDY
// -----------------------------------------------------------------------------

int main() {
    try {
        cout << "Analytical Window Case Study\n";
        cout << "Retail customer transaction analytics\n";

        const vector<Sale> sales = createSales();

        CustomerAnalyticsEngine engine(sales);

        const vector<CustomerAnalysis> analysis =
            engine.analyze();

        printAnalysis(analysis);
        printLifecycleReport(analysis);
        runWindowFunctionTests();
        printPerformanceAnalysis();
        printDesignTradeoffs();

        cout << "\nCase study completed successfully.\n";
        return 0;
    }
    catch (const exception& error) {
        cerr << "Application error: "
             << error.what()
             << "\n";
        return 1;
    }
}
