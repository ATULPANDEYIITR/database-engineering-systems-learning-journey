/*
 * Window Functions I | OVER, PARTITION BY, ORDER BY
 *
 * C++17 case study:
 * Regional sales analytics engine
 *
 * The program models the same analytical concepts provided by SQL window
 * functions, but implements them explicitly using C++ standard-library
 * containers and algorithms.
 *
 * It demonstrates:
 *   - partitioning;
 *   - ordering;
 *   - ROW_NUMBER;
 *   - RANK;
 *   - DENSE_RANK;
 *   - LAG;
 *   - LEAD;
 *   - running totals;
 *   - moving averages;
 *   - percentage of partition total;
 *   - top-N per partition;
 *   - deterministic tie-breaking;
 *   - validation;
 *   - complexity considerations;
 *   - production-style reporting.
 *
 * Compile:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic window_functions.cpp -o window_functions
 *
 * Run:
 *   ./window_functions
 */

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using namespace std;


// -----------------------------------------------------------------------------
// 1. DATA MODEL
// -----------------------------------------------------------------------------

struct Sale {
    int id;
    int employeeId;
    string date;
    string region;
    string product;
    double revenue;
};

struct Employee {
    int id;
    string name;
    string department;
    double salary;
};

struct SaleAnalytics {
    Sale sale;

    double regionTotal = 0.0;
    double runningRegionTotal = 0.0;

    optional<double> previousRevenue;
    optional<double> nextRevenue;
    optional<double> revenueChange;

    int rowNumber = 0;
    int rank = 0;
    int denseRank = 0;

    double percentOfRegion = 0.0;
    double movingAverage = 0.0;
};


// -----------------------------------------------------------------------------
// 2. SAMPLE DATA
// -----------------------------------------------------------------------------

vector<Employee> createEmployees() {
    return {
        {101, "Aarav", "Engineering", 95000},
        {102, "Diya", "Engineering", 110000},
        {103, "Kabir", "Engineering", 110000},
        {104, "Meera", "Engineering", 82000},

        {105, "Rohan", "Sales", 90000},
        {106, "Anaya", "Sales", 105000},
        {107, "Vihaan", "Sales", 105000},
        {108, "Ishita", "Sales", 76000},

        {109, "Arjun", "Finance", 120000},
        {110, "Sara", "Finance", 98000},
        {111, "Neil", "Finance", 98000},

        {112, "Tara", "Operations", 88000}
    };
}

vector<Sale> createSales() {
    return {
        {1, 105, "2026-01-02", "North", "Laptop", 1800},
        {2, 106, "2026-01-03", "North", "Phone", 2500},
        {3, 107, "2026-01-03", "North", "Laptop", 900},
        {4, 105, "2026-01-05", "North", "Monitor", 900},
        {5, 106, "2026-01-08", "North", "Laptop", 1800},
        {6, 107, "2026-01-10", "North", "Phone", 2000},
        {7, 108, "2026-01-11", "North", "Monitor", 600},
        {8, 105, "2026-01-15", "North", "Phone", 1500},

        {9, 109, "2026-01-02", "West", "Laptop", 900},
        {10, 110, "2026-01-04", "West", "Phone", 2000},
        {11, 111, "2026-01-04", "West", "Monitor", 1500},
        {12, 109, "2026-01-07", "West", "Laptop", 1800},
        {13, 110, "2026-01-12", "West", "Phone", 1000},
        {14, 111, "2026-01-14", "West", "Laptop", 2700},

        {15, 112, "2026-01-03", "South", "Monitor", 1200},
        {16, 112, "2026-01-09", "South", "Laptop", 1800}
    };
}


// -----------------------------------------------------------------------------
// 3. VALIDATION
// -----------------------------------------------------------------------------

void validateEmployee(const Employee& employee) {
    if (employee.id <= 0) {
        throw invalid_argument("Employee id must be positive.");
    }

    if (employee.name.empty()) {
        throw invalid_argument("Employee name cannot be empty.");
    }

    if (employee.salary < 0.0) {
        throw invalid_argument("Employee salary cannot be negative.");
    }
}

void validateSale(const Sale& sale) {
    if (sale.id <= 0) {
        throw invalid_argument("Sale id must be positive.");
    }

    if (sale.employeeId <= 0) {
        throw invalid_argument("Employee id must be positive.");
    }

    if (sale.date.empty()) {
        throw invalid_argument("Sale date cannot be empty.");
    }

    if (sale.region.empty()) {
        throw invalid_argument("Region cannot be empty.");
    }

    if (!isfinite(sale.revenue) || sale.revenue < 0.0) {
        throw invalid_argument("Revenue must be finite and non-negative.");
    }
}

void validateData(
    const vector<Employee>& employees,
    const vector<Sale>& sales
) {
    for (const auto& employee : employees) {
        validateEmployee(employee);
    }

    for (const auto& sale : sales) {
        validateSale(sale);
    }
}


// -----------------------------------------------------------------------------
// 4. OUTPUT HELPERS
// -----------------------------------------------------------------------------

void printTitle(const string& title) {
    cout << "\n" << string(80, '=') << "\n";
    cout << title << "\n";
    cout << string(80, '=') << "\n";
}

string optionalToString(const optional<double>& value) {
    if (!value.has_value()) {
        return "NULL";
    }

    ostringstream stream;
    stream << fixed << setprecision(2) << value.value();
    return stream.str();
}


// -----------------------------------------------------------------------------
// 5. GROUPING INTO PARTITIONS
// -----------------------------------------------------------------------------

map<string, vector<Sale>> partitionByRegion(const vector<Sale>& sales) {
    /*
     * This map models:
     *
     *     PARTITION BY region
     *
     * Every region receives an independent collection of rows.
     */
    map<string, vector<Sale>> partitions;

    for (const auto& sale : sales) {
        partitions[sale.region].push_back(sale);
    }

    return partitions;
}


// -----------------------------------------------------------------------------
// 6. ORDERING
// -----------------------------------------------------------------------------

void sortPartitionChronologically(vector<Sale>& partition) {
    /*
     * A window's ORDER BY is part of the analytical definition.
     *
     * sale date alone may not be unique. The sale id is therefore used as a
     * deterministic tiebreaker.
     */
    sort(
        partition.begin(),
        partition.end(),
        [](const Sale& a, const Sale& b) {
            if (a.date != b.date) {
                return a.date < b.date;
            }

            return a.id < b.id;
        }
    );
}

void sortByRevenueDescending(vector<Sale>& partition) {
    /*
     * Revenue is the primary business ordering. Sale id provides deterministic
     * ordering when two sales have the same revenue.
     */
    sort(
        partition.begin(),
        partition.end(),
        [](const Sale& a, const Sale& b) {
            if (a.revenue != b.revenue) {
                return a.revenue > b.revenue;
            }

            return a.id < b.id;
        }
    );
}


// -----------------------------------------------------------------------------
// 7. REGIONAL TOTALS
// -----------------------------------------------------------------------------

unordered_map<string, double> calculateRegionTotals(
    const vector<Sale>& sales
) {
    unordered_map<string, double> totals;

    for (const auto& sale : sales) {
        totals[sale.region] += sale.revenue;
    }

    return totals;
}


// -----------------------------------------------------------------------------
// 8. ROW_NUMBER, RANK, DENSE_RANK
// -----------------------------------------------------------------------------

struct EmployeeRanking {
    Employee employee;
    int rowNumber = 0;
    int rank = 0;
    int denseRank = 0;
};

vector<EmployeeRanking> calculateEmployeeRankings(
    const vector<Employee>& employees
) {
    map<string, vector<Employee>> partitions;

    for (const auto& employee : employees) {
        partitions[employee.department].push_back(employee);
    }

    vector<EmployeeRanking> result;

    for (auto& [department, partition] : partitions) {
        sort(
            partition.begin(),
            partition.end(),
            [](const Employee& a, const Employee& b) {
                if (a.salary != b.salary) {
                    return a.salary > b.salary;
                }

                return a.id < b.id;
            }
        );

        double previousSalary = numeric_limits<double>::quiet_NaN();
        int currentDenseRank = 0;

        for (size_t index = 0; index < partition.size(); ++index) {
            const Employee& employee = partition[index];

            EmployeeRanking ranking;
            ranking.employee = employee;

            // ROW_NUMBER always produces a unique sequential position.
            ranking.rowNumber = static_cast<int>(index) + 1;

            // RANK skips numbers after ties.
            auto higherCount = count_if(
                partition.begin(),
                partition.end(),
                [&](const Employee& other) {
                    return other.salary > employee.salary;
                }
            );

            ranking.rank = static_cast<int>(higherCount) + 1;

            // DENSE_RANK increases only when the ordered value changes.
            if (index == 0 || employee.salary != previousSalary) {
                ++currentDenseRank;
            }

            ranking.denseRank = currentDenseRank;
            previousSalary = employee.salary;

            result.push_back(ranking);
        }
    }

    return result;
}

void printEmployeeRankings(
    const vector<EmployeeRanking>& rankings
) {
    printTitle("EMPLOYEE RANKING BY DEPARTMENT");

    cout << left
         << setw(12) << "Name"
         << setw(16) << "Department"
         << setw(12) << "Salary"
         << setw(10) << "ROW_NUM"
         << setw(10) << "RANK"
         << setw(12) << "DENSE_RANK"
         << "\n";

    cout << string(72, '-') << "\n";

    for (const auto& item : rankings) {
        cout << left
             << setw(12) << item.employee.name
             << setw(16) << item.employee.department
             << setw(12) << fixed << setprecision(0)
             << item.employee.salary
             << setw(10) << item.rowNumber
             << setw(10) << item.rank
             << setw(12) << item.denseRank
             << "\n";
    }
}


// -----------------------------------------------------------------------------
// 9. COMPLETE SALES WINDOW ANALYSIS
// -----------------------------------------------------------------------------

vector<SaleAnalytics> calculateSalesAnalytics(
    const vector<Sale>& sales
) {
    const auto totals = calculateRegionTotals(sales);

    auto partitions = partitionByRegion(sales);

    vector<SaleAnalytics> result;

    for (auto& [region, partition] : partitions) {
        sortPartitionChronologically(partition);

        double runningTotal = 0.0;

        for (size_t index = 0; index < partition.size(); ++index) {
            const Sale& sale = partition[index];

            SaleAnalytics analytics;
            analytics.sale = sale;

            // Equivalent to:
            //
            // SUM(revenue) OVER (PARTITION BY region)
            analytics.regionTotal = totals.at(region);

            // Equivalent to:
            //
            // SUM(revenue) OVER (
            //     PARTITION BY region
            //     ORDER BY date, id
            //     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            // )
            runningTotal += sale.revenue;
            analytics.runningRegionTotal = runningTotal;

            // Equivalent to LAG(revenue) OVER (...).
            if (index > 0) {
                analytics.previousRevenue =
                    partition[index - 1].revenue;

                analytics.revenueChange =
                    sale.revenue - partition[index - 1].revenue;
            }

            // Equivalent to LEAD(revenue) OVER (...).
            if (index + 1 < partition.size()) {
                analytics.nextRevenue =
                    partition[index + 1].revenue;
            }

            /*
             * Three-row moving average:
             *
             * ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
             *
             * Notice that ROWS means physical ordered rows, not calendar days.
             */
            const size_t start =
                index >= 2 ? index - 2 : 0;

            double movingTotal = 0.0;
            size_t movingCount = 0;

            for (size_t j = start; j <= index; ++j) {
                movingTotal += partition[j].revenue;
                ++movingCount;
            }

            analytics.movingAverage =
                movingTotal / static_cast<double>(movingCount);

            /*
             * Percentage of partition total:
             *
             * revenue / SUM(revenue) OVER (PARTITION BY region)
             */
            analytics.percentOfRegion =
                sale.revenue / analytics.regionTotal * 100.0;

            result.push_back(analytics);
        }
    }

    return result;
}


// -----------------------------------------------------------------------------
// 10. REVENUE RANKING
// -----------------------------------------------------------------------------

void assignRevenueRanks(vector<SaleAnalytics>& analytics) {
    map<string, vector<SaleAnalytics*>> partitions;

    for (auto& row : analytics) {
        partitions[row.sale.region].push_back(&row);
    }

    for (auto& [region, partition] : partitions) {
        sort(
            partition.begin(),
            partition.end(),
            [](const SaleAnalytics* a, const SaleAnalytics* b) {
                if (a->sale.revenue != b->sale.revenue) {
                    return a->sale.revenue > b->sale.revenue;
                }

                return a->sale.id < b->sale.id;
            }
        );

        int denseRank = 0;
        optional<double> previousRevenue;

        for (size_t index = 0; index < partition.size(); ++index) {
            SaleAnalytics* row = partition[index];

            // ROW_NUMBER-style position.
            row->rowNumber = static_cast<int>(index) + 1;

            /*
             * RANK:
             * position is one plus the number of rows with strictly greater
             * revenue.
             */
            int higherCount = 0;

            for (const SaleAnalytics* candidate : partition) {
                if (candidate->sale.revenue > row->sale.revenue) {
                    ++higherCount;
                }
            }

            row->rank = higherCount + 1;

            if (!previousRevenue.has_value() ||
                row->sale.revenue != previousRevenue.value()) {
                ++denseRank;
            }

            row->denseRank = denseRank;
            previousRevenue = row->sale.revenue;
        }
    }
}


// -----------------------------------------------------------------------------
// 11. TOP-N PER GROUP
// -----------------------------------------------------------------------------

vector<SaleAnalytics> topNPerRegion(
    const vector<SaleAnalytics>& analytics,
    size_t n
) {
    if (n == 0) {
        throw invalid_argument("Top-N value must be greater than zero.");
    }

    map<string, vector<SaleAnalytics>> partitions;

    for (const auto& row : analytics) {
        partitions[row.sale.region].push_back(row);
    }

    vector<SaleAnalytics> result;

    for (auto& [region, partition] : partitions) {
        sort(
            partition.begin(),
            partition.end(),
            [](const SaleAnalytics& a, const SaleAnalytics& b) {
                if (a.sale.revenue != b.sale.revenue) {
                    return a.sale.revenue > b.sale.revenue;
                }

                return a.sale.id < b.sale.id;
            }
        );

        const size_t limit = min(n, partition.size());

        for (size_t index = 0; index < limit; ++index) {
            result.push_back(partition[index]);
        }
    }

    return result;
}


// -----------------------------------------------------------------------------
// 12. REPORTING
// -----------------------------------------------------------------------------

void printSalesAnalytics(
    vector<SaleAnalytics> analytics
) {
    sort(
        analytics.begin(),
        analytics.end(),
        [](const SaleAnalytics& a, const SaleAnalytics& b) {
            if (a.sale.region != b.sale.region) {
                return a.sale.region < b.sale.region;
            }

            if (a.sale.date != b.sale.date) {
                return a.sale.date < b.sale.date;
            }

            return a.sale.id < b.sale.id;
        }
    );

    printTitle("REGIONAL SALES WINDOW ANALYTICS");

    cout << left
         << setw(5) << "ID"
         << setw(12) << "Date"
         << setw(10) << "Region"
         << setw(12) << "Revenue"
         << setw(14) << "RegionTotal"
         << setw(16) << "RunningTotal"
         << setw(14) << "Previous"
         << setw(14) << "Change"
         << setw(8) << "Rank"
         << setw(10) << "Dense"
         << setw(12) << "MovingAvg"
         << setw(10) << "%Region"
         << "\n";

    cout << string(137, '-') << "\n";

    for (const auto& row : analytics) {
        cout << left
             << setw(5) << row.sale.id
             << setw(12) << row.sale.date
             << setw(10) << row.sale.region
             << setw(12) << fixed << setprecision(2)
             << row.sale.revenue
             << setw(14) << row.regionTotal
             << setw(16) << row.runningRegionTotal
             << setw(14) << optionalToString(row.previousRevenue)
             << setw(14) << optionalToString(row.revenueChange)
             << setw(8) << row.rank
             << setw(10) << row.denseRank
             << setw(12) << row.movingAverage
             << setw(10) << row.percentOfRegion
             << "\n";
    }
}


// -----------------------------------------------------------------------------
// 13. TOP-N REPORT
// -----------------------------------------------------------------------------

void printTopN(vector<SaleAnalytics> rows, size_t n) {
    printTitle("TOP-N SALES PER REGION");

    cout << "Top " << n << " sales from each region\n\n";

    sort(
        rows.begin(),
        rows.end(),
        [](const SaleAnalytics& a, const SaleAnalytics& b) {
            if (a.sale.region != b.sale.region) {
                return a.sale.region < b.sale.region;
            }

            if (a.sale.revenue != b.sale.revenue) {
                return a.sale.revenue > b.sale.revenue;
            }

            return a.sale.id < b.sale.id;
        }
    );

    string currentRegion;

    size_t position = 0;

    for (const auto& row : rows) {
        if (row.sale.region != currentRegion) {
            currentRegion = row.sale.region;
            position = 0;
            cout << "\nRegion: " << currentRegion << "\n";
        }

        ++position;

        cout << "  "
             << position
             << ". Sale #"
             << row.sale.id
             << " | "
             << row.sale.product
             << " | revenue = "
             << fixed
             << setprecision(2)
             << row.sale.revenue
             << "\n";
    }
}


// -----------------------------------------------------------------------------
// 14. COMPLEXITY DISCUSSION
// -----------------------------------------------------------------------------

void printComplexityAnalysis() {
    printTitle("ALGORITHMIC AND PERFORMANCE CONSIDERATIONS");

    cout
        << "Partitioning with an ordered map is approximately O(n log p)\n"
        << "for p distinct partition keys.\n\n"

        << "Sorting each partition costs approximately O(n log n) in total\n"
        << "when the partitions collectively contain n rows.\n\n"

        << "Running totals can be computed in O(n) after ordering.\n\n"

        << "The deliberately straightforward RANK implementation shown here\n"
        << "scans each partition to count higher values. That can approach\n"
        << "O(n^2) within a partition. A production implementation can avoid\n"
        << "that repeated scan by assigning rank while traversing the already\n"
        << "sorted partition.\n\n"

        << "Database engines implement window functions using query planners,\n"
        << "sorting strategies, indexes, temporary structures, and execution\n"
        << "operators. Application code should not assume that manually\n"
        << "recreating a database window operation is faster.\n\n"

        << "For SQL workloads, examine EXPLAIN or EXPLAIN ANALYZE output and\n"
        << "measure the actual query under realistic data volumes.\n";
}


// -----------------------------------------------------------------------------
// 15. EDGE CASES
// -----------------------------------------------------------------------------

void demonstrateEdgeCases() {
    printTitle("EDGE CASES");

    vector<Sale> emptySales;

    if (emptySales.empty()) {
        cout << "Empty partition: no rows are produced.\n";
    }

    vector<Sale> oneSale = {
        {100, 1, "2026-02-01", "East", "Laptop", 500.0}
    };

    auto partitions = partitionByRegion(oneSale);

    cout
        << "Single-row partition: running total = "
        << partitions["East"][0].revenue
        << "\n";

    cout
        << "First row LAG value = NULL because no previous row exists.\n";

    cout
        << "Last row LEAD value = NULL because no next row exists.\n";

    cout
        << "Tied ORDER BY values require a deliberate decision about whether\n"
        << "ROW_NUMBER, RANK, or DENSE_RANK is appropriate.\n";

    cout
        << "NULL values should be explicitly handled when their placement\n"
        << "affects a business result.\n";
}


// -----------------------------------------------------------------------------
// 16. TESTS
// -----------------------------------------------------------------------------

void runTests(
    const vector<Employee>& employees,
    const vector<SaleAnalytics>& analytics
) {
    printTitle("TESTS");

    if (employees.size() != 12) {
        throw runtime_error("Expected 12 employees.");
    }

    if (analytics.size() != 16) {
        throw runtime_error("Expected 16 sales analytics rows.");
    }

    const auto engineering = calculateEmployeeRankings(
        vector<Employee>(
            employees.begin(),
            employees.begin() + 4
        )
    );

    if (engineering.size() != 4) {
        throw runtime_error("Engineering ranking test failed.");
    }

    /*
     * The two engineering employees with salary 110000 must share RANK = 1.
     * The next salary must have RANK = 3 and DENSE_RANK = 2.
     */
    bool foundExpectedTie = false;

    for (const auto& row : engineering) {
        if (row.employee.salary == 95000 &&
            row.rank == 3 &&
            row.denseRank == 2) {
            foundExpectedTie = true;
        }
    }

    if (!foundExpectedTie) {
        throw runtime_error("RANK/DENSE_RANK tie test failed.");
    }

    for (const auto& row : analytics) {
        if (row.regionTotal <= 0.0) {
            throw runtime_error("Region total must be positive.");
        }

        if (row.percentOfRegion < 0.0 ||
            row.percentOfRegion > 100.0) {
            throw runtime_error("Percentage must be between 0 and 100.");
        }
    }

    cout << "All tests passed.\n";
}


// -----------------------------------------------------------------------------
// 17. MAIN CASE STUDY
// -----------------------------------------------------------------------------

int main() {
    try {
        printTitle(
            "WINDOW FUNCTIONS I | OVER, PARTITION BY, ORDER BY"
        );

        const vector<Employee> employees = createEmployees();
        const vector<Sale> sales = createSales();

        validateData(employees, sales);

        /*
         * Stage 1:
         * Build the analytical dataset.
         */
        vector<SaleAnalytics> analytics =
            calculateSalesAnalytics(sales);

        /*
         * Stage 2:
         * Add ranking calculations.
         */
        assignRevenueRanks(analytics);

        /*
         * Stage 3:
         * Display the complete analytical result.
         */
        printSalesAnalytics(analytics);

        /*
         * Stage 4:
         * Show a common SQL pattern:
         *
         *     ROW_NUMBER() OVER (
         *         PARTITION BY region
         *         ORDER BY revenue DESC
         *     )
         *
         * followed by an outer filter for the desired N.
         */
        const size_t topN = 2;
        const vector<SaleAnalytics> topSales =
            topNPerRegion(analytics, topN);

        printTopN(topSales, topN);

        /*
         * Stage 5:
         * Show edge cases and algorithmic trade-offs.
         */
        demonstrateEdgeCases();
        printComplexityAnalysis();

        /*
         * Stage 6:
         * Run regression tests after all calculations.
         */
        runTests(employees, analytics);

        printTitle("CASE STUDY COMPLETED");

        cout
            << "The program demonstrated how SQL window-function concepts\n"
            << "can be implemented as explicit partition, ordering, and\n"
            << "row-relative operations in a strongly typed systems language.\n";

        return 0;
    }
    catch (const exception& error) {
        cerr << "ERROR: " << error.what() << "\n";
        return 1;
    }
}
