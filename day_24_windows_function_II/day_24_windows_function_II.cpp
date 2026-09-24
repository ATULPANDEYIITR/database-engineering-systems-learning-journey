/*
 * Window Functions II: ROW_NUMBER, RANK, DENSE_RANK, NTILE
 *
 * C++17 industry-style case study:
 *
 * A regional sales analytics engine ranks sales representatives inside each
 * region. It demonstrates the mechanics behind four SQL ranking window
 * functions without requiring a database library:
 *
 *   ROW_NUMBER()
 *   RANK()
 *   DENSE_RANK()
 *   NTILE(n)
 *
 * The program models partitioning, ordering, ties, validation, top-N
 * reporting, segmentation, deduplication, testing, and complexity.
 */

#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;


// ============================================================================
// DOMAIN MODEL
// ============================================================================

struct SalesRecord {
    int saleId;
    string region;
    string salesperson;
    double revenue;
};

struct RankedSalesRecord {
    SalesRecord sale;
    int rowNumber = 0;
    int rank = 0;
    int denseRank = 0;
    int ntile = 0;
};


// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

string formatMoney(double value) {
    ostringstream stream;
    stream << fixed << setprecision(2) << value;
    return stream.str();
}


void printSales(const vector<SalesRecord>& records, const string& title) {
    cout << "\n" << title << "\n";
    cout << left
         << setw(8) << "ID"
         << setw(12) << "Region"
         << setw(16) << "Salesperson"
         << setw(14) << "Revenue"
         << "\n";

    cout << string(50, '-') << "\n";

    for (const auto& record : records) {
        cout << left
             << setw(8) << record.saleId
             << setw(12) << record.region
             << setw(16) << record.salesperson
             << setw(14) << formatMoney(record.revenue)
             << "\n";
    }
}


void printRankedSales(
    const vector<RankedSalesRecord>& records,
    const string& title
) {
    cout << "\n" << title << "\n";
    cout << left
         << setw(8) << "ID"
         << setw(12) << "Region"
         << setw(16) << "Name"
         << setw(14) << "Revenue"
         << setw(12) << "ROW_NUM"
         << setw(10) << "RANK"
         << setw(14) << "DENSE"
         << setw(10) << "NTILE"
         << "\n";

    cout << string(96, '-') << "\n";

    for (const auto& record : records) {
        cout << left
             << setw(8) << record.sale.saleId
             << setw(12) << record.sale.region
             << setw(16) << record.sale.salesperson
             << setw(14) << formatMoney(record.sale.revenue)
             << setw(12) << record.rowNumber
             << setw(10) << record.rank
             << setw(14) << record.denseRank
             << setw(10) << record.ntile
             << "\n";
    }
}


// ============================================================================
// WINDOW SPECIFICATION
// ============================================================================

class WindowSpecification {
public:
    /*
     * This case study uses:
     *
     * PARTITION BY region
     * ORDER BY revenue DESC, saleId ASC
     *
     * saleId is a deterministic secondary key for ROW_NUMBER.
     *
     * For RANK and DENSE_RANK we intentionally compare only revenue when
     * determining ties, because equal revenue should remain tied.
     */
    string partitionColumn = "region";
};


// ============================================================================
// PARTITIONING
// ============================================================================

map<string, vector<SalesRecord>>
partitionByRegion(const vector<SalesRecord>& records) {
    map<string, vector<SalesRecord>> partitions;

    for (const auto& record : records) {
        partitions[record.region].push_back(record);
    }

    return partitions;
}


// ============================================================================
// ORDERING
// ============================================================================

vector<SalesRecord>
sortByRevenueDescending(vector<SalesRecord> partition) {
    /*
     * Sorting is the major ordering step required by ranking functions.
     *
     * Complexity for a partition of size k is typically O(k log k).
     *
     * The saleId tie-breaker makes the physical order deterministic while
     * preserving the revenue-only definition of a ranking tie.
     */
    sort(
        partition.begin(),
        partition.end(),
        [](const SalesRecord& left, const SalesRecord& right) {
            if (left.revenue != right.revenue) {
                return left.revenue > right.revenue;
            }

            return left.saleId < right.saleId;
        }
    );

    return partition;
}


// ============================================================================
// ROW_NUMBER
// ============================================================================

vector<RankedSalesRecord>
calculateRowNumber(const vector<SalesRecord>& records) {
    vector<RankedSalesRecord> result;

    for (auto& [region, partition] : partitionByRegion(records)) {
        const auto ordered = sortByRevenueDescending(partition);

        for (size_t index = 0; index < ordered.size(); ++index) {
            RankedSalesRecord ranked;
            ranked.sale = ordered[index];
            ranked.rowNumber = static_cast<int>(index + 1);
            result.push_back(ranked);
        }
    }

    return result;
}


// ============================================================================
// RANK
// ============================================================================

vector<RankedSalesRecord>
calculateRank(const vector<SalesRecord>& records) {
    vector<RankedSalesRecord> result;

    for (auto& [region, partition] : partitionByRegion(records)) {
        const auto ordered = sortByRevenueDescending(partition);

        double previousRevenue = 0.0;
        int currentRank = 0;

        for (size_t index = 0; index < ordered.size(); ++index) {
            const auto& record = ordered[index];

            if (index == 0) {
                currentRank = 1;
            } else if (record.revenue != previousRevenue) {
                /*
                 * RANK uses the physical position when a new value appears.
                 * This creates gaps after ties.
                 */
                currentRank = static_cast<int>(index + 1);
            }

            RankedSalesRecord ranked;
            ranked.sale = record;
            ranked.rank = currentRank;

            result.push_back(ranked);
            previousRevenue = record.revenue;
        }
    }

    return result;
}


// ============================================================================
// DENSE_RANK
// ============================================================================

vector<RankedSalesRecord>
calculateDenseRank(const vector<SalesRecord>& records) {
    vector<RankedSalesRecord> result;

    for (auto& [region, partition] : partitionByRegion(records)) {
        const auto ordered = sortByRevenueDescending(partition);

        double previousRevenue = 0.0;
        int currentRank = 0;

        for (const auto& record : ordered) {
            if (currentRank == 0 || record.revenue != previousRevenue) {
                ++currentRank;
            }

            RankedSalesRecord ranked;
            ranked.sale = record;
            ranked.denseRank = currentRank;

            result.push_back(ranked);
            previousRevenue = record.revenue;
        }
    }

    return result;
}


// ============================================================================
// NTILE
// ============================================================================

vector<RankedSalesRecord>
calculateNTile(
    const vector<SalesRecord>& records,
    int bucketCount
) {
    if (bucketCount <= 0) {
        throw invalid_argument(
            "NTILE bucket count must be a positive integer."
        );
    }

    vector<RankedSalesRecord> result;

    for (auto& [region, partition] : partitionByRegion(records)) {
        const auto ordered = sortByRevenueDescending(partition);

        const int rowCount = static_cast<int>(ordered.size());

        if (rowCount == 0) {
            continue;
        }

        /*
         * Suppose there are q rows and n buckets:
         *
         * q = n * baseSize + remainder
         *
         * The first remainder buckets receive one additional row.
         */
        const int baseSize = rowCount / bucketCount;
        const int remainder = rowCount % bucketCount;

        for (int index = 0; index < rowCount; ++index) {
            int bucket = 0;

            if (index < (baseSize + 1) * remainder) {
                bucket = index / (baseSize + 1) + 1;
            } else if (baseSize == 0) {
                bucket = remainder;
            } else {
                bucket =
                    remainder +
                    (index - (baseSize + 1) * remainder) / baseSize +
                    1;
            }

            RankedSalesRecord ranked;
            ranked.sale = ordered[index];
            ranked.ntile = bucket;

            result.push_back(ranked);
        }
    }

    return result;
}


// ============================================================================
// COMBINED ANALYTICS ENGINE
// ============================================================================

class RegionalSalesAnalytics {
private:
    vector<SalesRecord> records;

public:
    explicit RegionalSalesAnalytics(vector<SalesRecord> input)
        : records(std::move(input)) {}

    vector<RankedSalesRecord> analyze(int bucketCount) const {
        if (bucketCount <= 0) {
            throw invalid_argument("Bucket count must be positive.");
        }

        vector<RankedSalesRecord> result;

        /*
         * We calculate all four functions against the same logical window.
         * The matching is done by saleId because saleId is unique in this
         * case study.
         */
        const auto rowNumbers = calculateRowNumber(records);
        const auto ranks = calculateRank(records);
        const auto denseRanks = calculateDenseRank(records);
        const auto tiles = calculateNTile(records, bucketCount);

        unordered_map<int, RankedSalesRecord> byId;

        for (const auto& row : rowNumbers) {
            byId[row.sale.saleId] = row;
        }

        for (const auto& row : ranks) {
            byId[row.sale.saleId].rank = row.rank;
        }

        for (const auto& row : denseRanks) {
            byId[row.sale.saleId].denseRank = row.denseRank;
        }

        for (const auto& row : tiles) {
            byId[row.sale.saleId].ntile = row.ntile;
        }

        /*
         * Rebuild the result in a stable business order:
         * region first, then revenue descending, then sale ID.
         */
        for (auto& [id, row] : byId) {
            result.push_back(row);
        }

        sort(
            result.begin(),
            result.end(),
            [](const RankedSalesRecord& left,
               const RankedSalesRecord& right) {
                if (left.sale.region != right.sale.region) {
                    return left.sale.region < right.sale.region;
                }

                if (left.sale.revenue != right.sale.revenue) {
                    return left.sale.revenue > right.sale.revenue;
                }

                return left.sale.saleId < right.sale.saleId;
            }
        );

        return result;
    }

    vector<RankedSalesRecord> topNPerRegion(int n) const {
        if (n <= 0) {
            throw invalid_argument("N must be positive.");
        }

        const auto ranked = calculateRowNumber(records);

        vector<RankedSalesRecord> result;

        for (const auto& row : ranked) {
            if (row.rowNumber <= n) {
                result.push_back(row);
            }
        }

        return result;
    }

    vector<RankedSalesRecord> topNWithTies(int n) const {
        if (n <= 0) {
            throw invalid_argument("N must be positive.");
        }

        const auto ranked = calculateRank(records);

        vector<RankedSalesRecord> result;

        for (const auto& row : ranked) {
            if (row.rank <= n) {
                result.push_back(row);
            }
        }

        return result;
    }

    vector<RankedSalesRecord> secondHighestDistinctRevenue() const {
        const auto ranked = calculateDenseRank(records);

        vector<RankedSalesRecord> result;

        for (const auto& row : ranked) {
            if (row.denseRank == 2) {
                result.push_back(row);
            }
        }

        return result;
    }
};


// ============================================================================
// INPUT VALIDATION
// ============================================================================

void validateSalesData(const vector<SalesRecord>& records) {
    map<int, bool> seenIds;

    for (const auto& record : records) {
        if (record.saleId <= 0) {
            throw invalid_argument(
                "Every sale ID must be positive."
            );
        }

        if (record.region.empty()) {
            throw invalid_argument(
                "Every sales record must have a region."
            );
        }

        if (record.salesperson.empty()) {
            throw invalid_argument(
                "Every sales record must have a salesperson."
            );
        }

        if (record.revenue < 0.0) {
            throw invalid_argument(
                "Revenue cannot be negative."
            );
        }

        if (seenIds[record.saleId]) {
            throw invalid_argument(
                "Sale IDs must be unique."
            );
        }

        seenIds[record.saleId] = true;
    }
}


// ============================================================================
// TEST HELPERS
// ============================================================================

void assertEqual(
    const vector<int>& actual,
    const vector<int>& expected,
    const string& message
) {
    if (actual != expected) {
        ostringstream stream;
        stream << message << "\nExpected: ";

        for (int value : expected) {
            stream << value << ' ';
        }

        stream << "\nActual: ";

        for (int value : actual) {
            stream << value << ' ';
        }

        throw runtime_error(stream.str());
    }
}


void runRankingTests() {
    vector<SalesRecord> testData = {
        {1, "A", "P1", 100.0},
        {2, "A", "P2", 100.0},
        {3, "A", "P3", 90.0},
        {4, "A", "P4", 80.0}
    };

    const auto rowNumbers = calculateRowNumber(testData);
    vector<int> actualRowNumbers;

    for (const auto& row : rowNumbers) {
        actualRowNumbers.push_back(row.rowNumber);
    }

    assertEqual(
        actualRowNumbers,
        {1, 2, 3, 4},
        "ROW_NUMBER test failed."
    );

    const auto ranks = calculateRank(testData);
    vector<int> actualRanks;

    for (const auto& row : ranks) {
        actualRanks.push_back(row.rank);
    }

    assertEqual(
        actualRanks,
        {1, 1, 3, 4},
        "RANK test failed."
    );

    const auto denseRanks = calculateDenseRank(testData);
    vector<int> actualDenseRanks;

    for (const auto& row : denseRanks) {
        actualDenseRanks.push_back(row.denseRank);
    }

    assertEqual(
        actualDenseRanks,
        {1, 1, 2, 3},
        "DENSE_RANK test failed."
    );

    const auto tiles = calculateNTile(testData, 2);
    vector<int> actualTiles;

    for (const auto& row : tiles) {
        actualTiles.push_back(row.ntile);
    }

    assertEqual(
        actualTiles,
        {1, 1, 2, 2},
        "NTILE test failed."
    );

    cout << "\nAll C++ ranking tests passed.\n";
}


// ============================================================================
// EDGE CASE TESTS
// ============================================================================

void runEdgeCaseTests() {
    vector<SalesRecord> empty;

    const auto rowNumbers = calculateRowNumber(empty);

    if (!rowNumbers.empty()) {
        throw runtime_error(
            "Empty input should produce empty ROW_NUMBER output."
        );
    }

    vector<SalesRecord> oneRow = {
        {1, "A", "Only", 500.0}
    };

    const auto singleTile = calculateNTile(oneRow, 5);

    if (singleTile.size() != 1 || singleTile.front().ntile != 1) {
        throw runtime_error(
            "NTILE with more buckets than rows failed."
        );
    }

    bool rejected = false;

    try {
        calculateNTile(oneRow, 0);
    } catch (const invalid_argument&) {
        rejected = true;
    }

    if (!rejected) {
        throw runtime_error(
            "Invalid NTILE bucket count was not rejected."
        );
    }

    cout << "All edge-case tests passed.\n";
}


// ============================================================================
// SYNTHETIC DATA FOR PERFORMANCE TESTING
// ============================================================================

vector<SalesRecord> generateSyntheticData(size_t count) {
    const vector<string> regions = {
        "North",
        "South",
        "East",
        "West"
    };

    vector<SalesRecord> result;
    result.reserve(count);

    for (size_t index = 0; index < count; ++index) {
        const double revenue =
            50000.0 +
            static_cast<double>((index * 7919ULL) % 100000ULL);

        result.push_back(
            SalesRecord{
                static_cast<int>(index + 1),
                regions[index % regions.size()],
                "Employee_" + to_string(index + 1),
                revenue
            }
        );
    }

    return result;
}


// ============================================================================
// MAIN CASE STUDY
// ============================================================================

int main() {
    try {
        cout << string(90, '=') << "\n";
        cout << "WINDOW FUNCTIONS II: SALES RANKING CASE STUDY\n";
        cout << string(90, '=') << "\n";

        vector<SalesRecord> sales = {
            {1, "North", "A", 90000.0},
            {2, "North", "B", 85000.0},
            {3, "North", "C", 85000.0},
            {4, "North", "D", 70000.0},

            {5, "South", "E", 95000.0},
            {6, "South", "F", 95000.0},
            {7, "South", "G", 80000.0},
            {8, "South", "H", 60000.0},

            {9, "East", "I", 120000.0},
            {10, "East", "J", 110000.0},
            {11, "East", "K", 110000.0},
            {12, "East", "L", 90000.0},

            {13, "West", "M", 100000.0},
            {14, "West", "N", 90000.0},
            {15, "West", "O", 90000.0},
            {16, "West", "P", 70000.0}
        };

        validateSalesData(sales);
        printSales(sales, "Source sales records");

        RegionalSalesAnalytics analytics(sales);

        // --------------------------------------------------------------------
        // Complete regional analysis
        // --------------------------------------------------------------------

        const auto completeAnalysis = analytics.analyze(4);

        printRankedSales(
            completeAnalysis,
            "Regional ranking with ROW_NUMBER, RANK, DENSE_RANK, NTILE(4)"
        );

        // --------------------------------------------------------------------
        // ROW_NUMBER use case
        // --------------------------------------------------------------------

        const auto topTwo = analytics.topNPerRegion(2);

        printRankedSales(
            topTwo,
            "Top 2 physical rows per region using ROW_NUMBER"
        );

        // --------------------------------------------------------------------
        // RANK use case
        // --------------------------------------------------------------------

        const auto topTwoWithTies = analytics.topNWithTies(2);

        printRankedSales(
            topTwoWithTies,
            "Top 2 ranking positions per region using RANK"
        );

        // --------------------------------------------------------------------
        // DENSE_RANK use case
        // --------------------------------------------------------------------

        const auto secondHighest =
            analytics.secondHighestDistinctRevenue();

        printRankedSales(
            secondHighest,
            "Second-highest distinct revenue per region using DENSE_RANK"
        );

        // --------------------------------------------------------------------
        // Explicit conceptual comparison
        // --------------------------------------------------------------------

        cout << R"(
CONCEPTUAL COMPARISON

For ordered values:

    100, 100, 90, 80

ROW_NUMBER:
    1, 2, 3, 4

RANK:
    1, 1, 3, 4

DENSE_RANK:
    1, 1, 2, 3

NTILE(2):
    1, 1, 2, 2

ROW_NUMBER gives every physical row a unique position.
RANK preserves competition-style gaps after ties.
DENSE_RANK preserves ties without gaps.
NTILE distributes rows into approximately equal-sized buckets.
)";

        // --------------------------------------------------------------------
        // Error handling demonstration
        // --------------------------------------------------------------------

        cout << "\nERROR HANDLING\n";

        try {
            analytics.analyze(0);
        } catch (const invalid_argument& error) {
            cout << "Rejected invalid bucket count: "
                 << error.what() << "\n";
        }

        // --------------------------------------------------------------------
        // Performance demonstration
        // --------------------------------------------------------------------

        cout << "\nPERFORMANCE DEMONSTRATION\n";

        const auto largeDataset = generateSyntheticData(50000);

        const auto start = chrono::high_resolution_clock::now();

        const auto rankedLargeDataset =
            calculateRowNumber(largeDataset);

        const auto finish = chrono::high_resolution_clock::now();

        const chrono::duration<double, milli> elapsed =
            finish - start;

        cout << "Rows processed: "
             << rankedLargeDataset.size()
             << "\n";

        cout << "ROW_NUMBER execution time in this C++ model: "
             << fixed << setprecision(3)
             << elapsed.count()
             << " ms\n";

        cout << R"(
The benchmark demonstrates the computational cost of partitioning and
sorting in this in-memory model. It is not a prediction of SQL database
performance.

A database optimizer may use indexes, parallel execution, external sorting,
partition pruning, statistics, memory management, and specialized execution
operators. The actual query plan must be evaluated on the target database
system and workload.
)";

        // --------------------------------------------------------------------
        // Testing
        // --------------------------------------------------------------------

        runRankingTests();
        runEdgeCaseTests();

        // --------------------------------------------------------------------
        // Complexity discussion
        // --------------------------------------------------------------------

        cout << R"(
COMPLEXITY MODEL

For a partition containing k rows:

    Partition construction       O(k)
    Sorting                      O(k log k)
    ROW_NUMBER after sorting     O(k)
    RANK after sorting           O(k)
    DENSE_RANK after sorting     O(k)
    NTILE after sorting          O(k)

Across all partitions containing n rows, sorting is commonly the dominant
operation, although the exact implementation depends on the execution
engine.

Memory usage can be O(n) in this educational implementation because
partitions and sorted copies are materialized explicitly.

DATABASE WINDOW FUNCTIONS

A corresponding SQL query for the modeled analysis would conceptually use:

    ROW_NUMBER() OVER (
        PARTITION BY region
        ORDER BY revenue DESC, sale_id ASC
    )

    RANK() OVER (
        PARTITION BY region
        ORDER BY revenue DESC
    )

    DENSE_RANK() OVER (
        PARTITION BY region
        ORDER BY revenue DESC
    )

    NTILE(4) OVER (
        PARTITION BY region
        ORDER BY revenue DESC, sale_id ASC
    )

The SQL engine performs these operations as part of its execution plan,
rather than requiring application code to manually construct the rankings.
)";

        cout << "\nCase study completed successfully.\n";
        return 0;
    }
    catch (const exception& error) {
        cerr << "Fatal error: " << error.what() << "\n";
        return 1;
    }
}
