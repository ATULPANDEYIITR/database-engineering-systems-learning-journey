/*
 * Advanced Aggregation Case Study in C++17
 * ==========================================
 *
 * Scenario:
 *     An enterprise analytics service needs to produce sales reports across
 *     region, sales channel, and product category.
 *
 * Requirements:
 *     1. Detailed region/channel/category totals.
 *     2. Regional and channel subtotals.
 *     3. A complete multidimensional cube.
 *     4. Grand totals.
 *     5. Explicit grouping metadata.
 *     6. Filtering equivalent to HAVING.
 *     7. Validation and failure handling.
 *     8. Performance measurements.
 *
 * SQL systems can express these reports using:
 *
 *     GROUPING SETS
 *     ROLLUP
 *     CUBE
 *
 * This C++ program implements the same aggregation semantics in memory.
 * The purpose is to make the underlying mechanics explicit:
 *
 *     source rows
 *          |
 *          v
 *     grouping key
 *          |
 *          v
 *     aggregate state
 *          |
 *          v
 *     subtotal / grand-total rows
 *
 * Compile:
 *
 *     g++ -std=c++17 -O2 -Wall -Wextra -pedantic aggregation_case_study.cpp -o aggregation_case_study
 *
 * Run:
 *
 *     ./aggregation_case_study
 */

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <exception>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>


// ============================================================================
// 1. DOMAIN MODEL
// ============================================================================

struct Sale {
    int id{};
    std::string region;
    std::string country;
    std::string channel;
    std::string category;
    double revenue{};
    int quantity{};
};


// ============================================================================
// 2. AGGREGATE STATE
// ============================================================================

struct Aggregate {
    double revenue = 0.0;
    long long quantity = 0;
    long long orders = 0;

    void add(const Sale& sale) {
        revenue += sale.revenue;
        quantity += sale.quantity;
        ++orders;
    }
};


// ============================================================================
// 3. GROUPING RESULT
// ============================================================================

struct ReportRow {
    std::string region;
    std::string channel;
    std::string category;

    double revenue = 0.0;
    long long quantity = 0;
    long long orders = 0;

    /*
     * grouping flags have the same conceptual purpose as SQL GROUPING():
     *
     *     0 -> dimension participates in this grouping level
     *     1 -> dimension was aggregated away
     */
    int groupingRegion = 0;
    int groupingChannel = 0;
    int groupingCategory = 0;

    /*
     * This is a compact bit-mask representation analogous to GROUPING_ID().
     */
    int groupingId = 0;
};


// ============================================================================
// 4. GROUPING DIMENSIONS
// ============================================================================

enum class Dimension {
    Region,
    Channel,
    Category
};

using GroupingSet = std::vector<Dimension>;


// ============================================================================
// 5. DIMENSION ACCESS
// ============================================================================

std::string dimensionName(Dimension dimension) {
    switch (dimension) {
        case Dimension::Region:
            return "region";
        case Dimension::Channel:
            return "channel";
        case Dimension::Category:
            return "category";
    }

    throw std::logic_error("Unknown dimension.");
}


std::string valueOf(
    const Sale& sale,
    Dimension dimension
) {
    switch (dimension) {
        case Dimension::Region:
            return sale.region;
        case Dimension::Channel:
            return sale.channel;
        case Dimension::Category:
            return sale.category;
    }

    throw std::logic_error("Unknown dimension.");
}


// ============================================================================
// 6. VALIDATION
// ============================================================================

void validateSale(const Sale& sale) {
    if (sale.id <= 0) {
        throw std::invalid_argument("Sale ID must be positive.");
    }

    if (sale.region.empty()) {
        throw std::invalid_argument("Region cannot be empty.");
    }

    if (sale.country.empty()) {
        throw std::invalid_argument("Country cannot be empty.");
    }

    if (sale.channel.empty()) {
        throw std::invalid_argument("Channel cannot be empty.");
    }

    if (sale.category.empty()) {
        throw std::invalid_argument("Category cannot be empty.");
    }

    if (!std::isfinite(sale.revenue) || sale.revenue < 0.0) {
        throw std::invalid_argument(
            "Revenue must be finite and non-negative."
        );
    }

    if (sale.quantity < 0) {
        throw std::invalid_argument(
            "Quantity cannot be negative."
        );
    }
}


void validateDataset(const std::vector<Sale>& sales) {
    std::set<int> ids;

    for (const Sale& sale : sales) {
        validateSale(sale);

        if (!ids.insert(sale.id).second) {
            throw std::invalid_argument(
                "Duplicate sale ID detected: " +
                std::to_string(sale.id)
            );
        }
    }
}


// ============================================================================
// 7. COMPOSITE GROUPING KEY
// ============================================================================

std::string makeGroupingKey(
    const Sale& sale,
    const GroupingSet& groupingSet
) {
    /*
     * A separator makes the composite key readable.
     *
     * In a production implementation, a typed struct with a custom hash
     * function can avoid serialization overhead.
     */
    std::ostringstream key;

    for (const Dimension dimension : groupingSet) {
        key << valueOf(sale, dimension) << '\x1F';
    }

    return key.str();
}


// ============================================================================
// 8. AGGREGATE ONE GROUPING SET
// ============================================================================

std::vector<ReportRow> aggregateGroupingSet(
    const std::vector<Sale>& sales,
    const GroupingSet& groupingSet
) {
    std::unordered_map<std::string, Aggregate> groups;

    for (const Sale& sale : sales) {
        const std::string key =
            makeGroupingKey(sale, groupingSet);

        groups[key].add(sale);
    }

    std::vector<ReportRow> results;

    for (const auto& [key, aggregate] : groups) {
        /*
         * The group key alone is not enough to reconstruct the dimension
         * values safely. We therefore derive the values by finding one
         * matching source row.
         *
         * For a production-scale implementation, storing the dimension
         * values alongside Aggregate in the map would avoid this lookup.
         */
        const Sale* representative = nullptr;

        for (const Sale& sale : sales) {
            if (makeGroupingKey(sale, groupingSet) == key) {
                representative = &sale;
                break;
            }
        }

        if (representative == nullptr) {
            throw std::logic_error(
                "Internal aggregation invariant violated."
            );
        }

        ReportRow row;

        row.region =
            std::find(
                groupingSet.begin(),
                groupingSet.end(),
                Dimension::Region
            ) != groupingSet.end()
                ? representative->region
                : "ALL";

        row.channel =
            std::find(
                groupingSet.begin(),
                groupingSet.end(),
                Dimension::Channel
            ) != groupingSet.end()
                ? representative->channel
                : "ALL";

        row.category =
            std::find(
                groupingSet.begin(),
                groupingSet.end(),
                Dimension::Category
            ) != groupingSet.end()
                ? representative->category
                : "ALL";

        row.revenue = aggregate.revenue;
        row.quantity = aggregate.quantity;
        row.orders = aggregate.orders;

        row.groupingRegion =
            std::find(
                groupingSet.begin(),
                groupingSet.end(),
                Dimension::Region
            ) == groupingSet.end();

        row.groupingChannel =
            std::find(
                groupingSet.begin(),
                groupingSet.end(),
                Dimension::Channel
            ) == groupingSet.end();

        row.groupingCategory =
            std::find(
                groupingSet.begin(),
                groupingSet.end(),
                Dimension::Category
            ) == groupingSet.end();

        /*
         * Binary construction of a GROUPING_ID-like value.
         *
         * Region is the highest-order bit.
         */
        row.groupingId =
            (row.groupingRegion << 2) |
            (row.groupingChannel << 1) |
            row.groupingCategory;

        results.push_back(std::move(row));
    }

    return results;
}


// ============================================================================
// 9. GROUPING SETS
// ============================================================================

std::vector<ReportRow> groupingSets(
    const std::vector<Sale>& sales,
    const std::vector<GroupingSet>& sets
) {
    std::vector<ReportRow> result;

    for (const GroupingSet& groupingSet : sets) {
        std::vector<ReportRow> partial =
            aggregateGroupingSet(sales, groupingSet);

        result.insert(
            result.end(),
            partial.begin(),
            partial.end()
        );
    }

    return result;
}


// ============================================================================
// 10. ROLLUP GENERATOR
// ============================================================================

std::vector<GroupingSet> rollup(
    const std::vector<Dimension>& dimensions
) {
    /*
     * ROLLUP(a,b,c):
     *
     *     (a,b,c)
     *     (a,b)
     *     (a)
     *     ()
     *
     * It follows a hierarchy from the most detailed level to the grand total.
     */
    std::vector<GroupingSet> result;

    for (std::size_t size = dimensions.size(); ; --size) {
        result.emplace_back(
            dimensions.begin(),
            dimensions.begin() + static_cast<std::ptrdiff_t>(size)
        );

        if (size == 0) {
            break;
        }
    }

    return result;
}


// ============================================================================
// 11. CUBE GENERATOR
// ============================================================================

std::vector<GroupingSet> cube(
    const std::vector<Dimension>& dimensions
) {
    /*
     * CUBE produces every subset of dimensions.
     *
     * n dimensions -> 2^n grouping sets.
     *
     * Bitmask representation is natural here:
     *
     *     bit = 1 -> include dimension
     *     bit = 0 -> aggregate dimension away
     */
    if (dimensions.size() >= sizeof(std::size_t) * 8) {
        throw std::overflow_error(
            "Too many dimensions for this bitmask implementation."
        );
    }

    const std::size_t combinations =
        std::size_t{1} << dimensions.size();

    std::vector<GroupingSet> result;
    result.reserve(combinations);

    for (std::size_t mask = 0; mask < combinations; ++mask) {
        GroupingSet groupingSet;

        for (std::size_t index = 0;
             index < dimensions.size();
             ++index) {

            if ((mask & (std::size_t{1} << index)) != 0) {
                groupingSet.push_back(dimensions[index]);
            }
        }

        result.push_back(std::move(groupingSet));
    }

    /*
     * Detailed grouping levels are displayed first.
     */
    std::sort(
        result.begin(),
        result.end(),
        [](const GroupingSet& left, const GroupingSet& right) {
            return left.size() > right.size();
        }
    );

    return result;
}


// ============================================================================
// 12. SQL-LIKE HAVING FILTER
// ============================================================================

std::vector<ReportRow> havingMinimumRevenue(
    const std::vector<ReportRow>& rows,
    double minimumRevenue
) {
    if (!std::isfinite(minimumRevenue)) {
        throw std::invalid_argument(
            "HAVING threshold must be finite."
        );
    }

    std::vector<ReportRow> result;

    std::copy_if(
        rows.begin(),
        rows.end(),
        std::back_inserter(result),
        [minimumRevenue](const ReportRow& row) {
            return row.revenue >= minimumRevenue;
        }
    );

    return result;
}


// ============================================================================
// 13. SORTING REPORT ROWS
// ============================================================================

void sortReport(
    std::vector<ReportRow>& rows
) {
    std::sort(
        rows.begin(),
        rows.end(),
        [](const ReportRow& left, const ReportRow& right) {
            if (left.groupingId != right.groupingId) {
                return left.groupingId < right.groupingId;
            }

            if (left.region != right.region) {
                return left.region < right.region;
            }

            if (left.channel != right.channel) {
                return left.channel < right.channel;
            }

            return left.category < right.category;
        }
    );
}


// ============================================================================
// 14. REPORT DISPLAY
// ============================================================================

std::string fit(
    const std::string& value,
    std::size_t width
) {
    if (value.size() >= width) {
        return value.substr(0, width);
    }

    return value + std::string(width - value.size(), ' ');
}


void printReport(
    const std::string& title,
    std::vector<ReportRow> rows,
    std::size_t maximumRows = std::numeric_limits<std::size_t>::max()
) {
    sortReport(rows);

    std::cout << "\n"
              << std::string(110, '=')
              << "\n"
              << title
              << "\n"
              << std::string(110, '=')
              << "\n";

    std::cout
        << fit("Region", 14) << " | "
        << fit("Channel", 14) << " | "
        << fit("Category", 16) << " | "
        << fit("Revenue", 14) << " | "
        << fit("Qty", 8) << " | "
        << fit("Orders", 8) << " | "
        << fit("GID", 5)
        << "\n";

    std::cout << std::string(110, '-') << "\n";

    const std::size_t count =
        std::min(maximumRows, rows.size());

    for (std::size_t index = 0; index < count; ++index) {
        const ReportRow& row = rows[index];

        std::ostringstream revenue;

        revenue
            << std::fixed
            << std::setprecision(2)
            << row.revenue;

        std::cout
            << fit(row.region, 14) << " | "
            << fit(row.channel, 14) << " | "
            << fit(row.category, 16) << " | "
            << fit(revenue.str(), 14) << " | "
            << std::setw(8) << row.quantity << " | "
            << std::setw(8) << row.orders << " | "
            << std::setw(5) << row.groupingId
            << "\n";
    }

    if (rows.size() > maximumRows) {
        std::cout
            << "... "
            << rows.size() - maximumRows
            << " additional rows omitted from display.\n";
    }

    std::cout
        << "\nRows: "
        << rows.size()
        << "\n";
}


// ============================================================================
// 15. REPORT ASSERTIONS
// ============================================================================

double totalRevenue(
    const std::vector<Sale>& sales
) {
    double total = 0.0;

    for (const Sale& sale : sales) {
        total += sale.revenue;
    }

    return total;
}


void verifyGrandTotal(
    const std::vector<Sale>& sales,
    const std::vector<ReportRow>& rows
) {
    /*
     * Grand total generated by GROUP BY () has all grouping flags set to 1.
     */
    const auto iterator =
        std::find_if(
            rows.begin(),
            rows.end(),
            [](const ReportRow& row) {
                return row.groupingRegion == 1 &&
                       row.groupingChannel == 1 &&
                       row.groupingCategory == 1;
            }
        );

    if (iterator == rows.end()) {
        throw std::runtime_error(
            "Grand total row was not generated."
        );
    }

    const double expected = totalRevenue(sales);

    if (std::abs(iterator->revenue - expected) > 1e-9) {
        throw std::runtime_error(
            "Grand total does not match independent calculation."
        );
    }
}


// ============================================================================
// 16. SQL GENERATION FOR THE CASE STUDY
// ============================================================================

std::string sqlIdentifier(
    const std::string& identifier
) {
    /*
     * SQL identifiers are not values.
     *
     * In real applications, use a database driver's identifier-quoting
     * mechanism when dynamic identifiers are unavoidable.
     */
    if (identifier.empty()) {
        throw std::invalid_argument(
            "SQL identifier cannot be empty."
        );
    }

    for (char character : identifier) {
        const bool valid =
            std::isalnum(
                static_cast<unsigned char>(character)
            ) ||
            character == '_';

        if (!valid) {
            throw std::invalid_argument(
                "Unsafe SQL identifier: " + identifier
            );
        }
    }

    if (std::isdigit(
        static_cast<unsigned char>(identifier.front())
    )) {
        throw std::invalid_argument(
            "SQL identifier cannot start with a digit."
        );
    }

    return identifier;
}


std::string dimensionsToSql(
    const std::vector<std::string>& dimensions
) {
    std::ostringstream output;

    for (std::size_t index = 0;
         index < dimensions.size();
         ++index) {

        if (index > 0) {
            output << ", ";
        }

        output << sqlIdentifier(dimensions[index]);
    }

    return output.str();
}


void printSqlCaseStudy() {
    const std::string dimensions =
        "region, channel, category";

    std::cout << "\n"
              << std::string(110, '=')
              << "\n"
              << "SQL EQUIVALENTS"
              << "\n"
              << std::string(110, '=')
              << "\n";

    std::cout
        << "\nGROUPING SETS:\n"
        << "SELECT region, channel, category, SUM(revenue)\n"
        << "FROM sales\n"
        << "GROUP BY GROUPING SETS (\n"
        << "    (region, channel, category),\n"
        << "    (region, channel),\n"
        << "    (region),\n"
        << "    ()\n"
        << ");\n";

    std::cout
        << "\nROLLUP:\n"
        << "SELECT " << dimensions << ", SUM(revenue)\n"
        << "FROM sales\n"
        << "GROUP BY ROLLUP("
        << dimensions
        << ");\n";

    std::cout
        << "\nCUBE:\n"
        << "SELECT " << dimensions << ", SUM(revenue)\n"
        << "FROM sales\n"
        << "GROUP BY CUBE("
        << dimensions
        << ");\n";
}


// ============================================================================
// 17. SERVICE CLASS
// ============================================================================

class AnalyticsService {
private:
    std::vector<Sale> sales_;

public:
    explicit AnalyticsService(std::vector<Sale> sales)
        : sales_(std::move(sales)) {
        validateDataset(sales_);
    }

    std::vector<ReportRow> regionalRollup() const {
        return groupingSets(
            sales_,
            rollup({
                Dimension::Region,
                Dimension::Channel,
                Dimension::Category
            })
        );
    }

    std::vector<ReportRow> completeCube() const {
        return groupingSets(
            sales_,
            cube({
                Dimension::Region,
                Dimension::Channel,
                Dimension::Category
            })
        );
    }

    std::vector<ReportRow> selectedGroupingSets() const {
        return groupingSets(
            sales_,
            {
                {Dimension::Region, Dimension::Category},
                {Dimension::Region},
                {Dimension::Category},
                {}
            }
        );
    }

    const std::vector<Sale>& sales() const {
        return sales_;
    }
};


// ============================================================================
// 18. PERFORMANCE TEST DATA
// ============================================================================

std::vector<Sale> makeSyntheticSales(
    std::size_t count
) {
    const std::vector<std::string> regions = {
        "North", "South", "East", "West"
    };

    const std::vector<std::string> channels = {
        "Online", "Retail", "Partner"
    };

    const std::vector<std::string> categories = {
        "Electronics", "Furniture", "Software", "Services"
    };

    std::vector<Sale> rows;
    rows.reserve(count);

    for (std::size_t index = 0; index < count; ++index) {
        Sale sale;

        sale.id = static_cast<int>(index + 1);
        sale.region = regions[index % regions.size()];
        sale.country = "India";
        sale.channel = channels[index % channels.size()];
        sale.category = categories[index % categories.size()];
        sale.revenue =
            100.0 +
            static_cast<double>((index * 37) % 5000);
        sale.quantity =
            static_cast<int>((index % 10) + 1);

        rows.push_back(std::move(sale));
    }

    return rows;
}


// ============================================================================
// 19. TIMING HELPER
// ============================================================================

template <typename Function>
auto measureMilliseconds(
    const std::string& label,
    Function&& function
) {
    const auto start =
        std::chrono::steady_clock::now();

    auto result =
        function();

    const auto finish =
        std::chrono::steady_clock::now();

    const auto elapsed =
        std::chrono::duration_cast<
            std::chrono::microseconds
        >(finish - start).count();

    std::cout
        << label
        << ": "
        << elapsed / 1000.0
        << " ms\n";

    return result;
}


// ============================================================================
// 20. EDGE CASES
// ============================================================================

void demonstrateEmptyDataset() {
    const std::vector<Sale> empty;

    const auto rollupRows =
        groupingSets(
            empty,
            rollup({
                Dimension::Region,
                Dimension::Channel
            })
        );

    std::cout
        << "\nEmpty dataset generated "
        << rollupRows.size()
        << " rows in this in-memory implementation.\n";

    /*
     * SQL's behavior for GROUP BY () over empty input should be verified
     * against the actual database. Aggregate functions have their own
     * empty-input semantics:
     *
     *     COUNT(*) -> normally 0
     *     SUM(...) -> normally NULL
     *     AVG(...) -> normally NULL
     *     MIN(...) -> normally NULL
     *     MAX(...) -> normally NULL
     */
}


void demonstrateInvalidInput() {
    try {
        Sale invalid;
        invalid.id = 1;
        invalid.region = "North";
        invalid.country = "India";
        invalid.channel = "Online";
        invalid.category = "Electronics";
        invalid.revenue = -500.0;
        invalid.quantity = 1;

        validateSale(invalid);
    }
    catch (const std::exception& exception) {
        std::cout
            << "\nExpected validation failure: "
            << exception.what()
            << "\n";
    }
}


// ============================================================================
// 21. MAIN CASE STUDY
// ============================================================================

int main() {
    try {
        const std::vector<Sale> sales = {
            {1, "North", "India", "Online", "Electronics", 1200.00, 3},
            {2, "North", "India", "Retail", "Electronics", 800.00, 2},
            {3, "North", "India", "Online", "Furniture", 1500.00, 1},
            {4, "North", "Nepal", "Online", "Electronics", 700.00, 2},
            {5, "South", "India", "Online", "Electronics", 1800.00, 4},
            {6, "South", "India", "Retail", "Furniture", 2200.00, 2},
            {7, "South", "India", "Online", "Furniture", 1100.00, 1},
            {8, "South", "Sri Lanka", "Retail", "Electronics", 900.00, 2},
            {9, "West", "India", "Online", "Electronics", 2500.00, 5},
            {10, "West", "India", "Retail", "Furniture", 1700.00, 2},
            {11, "West", "Pakistan", "Online", "Furniture", 1000.00, 1},
            {12, "East", "India", "Online", "Electronics", 1300.00, 3},
            {13, "East", "India", "Retail", "Furniture", 1600.00, 2},
            {14, "East", "Bangladesh", "Online", "Electronics", 600.00, 2}
        };

        AnalyticsService service(sales);

        std::cout
            << "ADVANCED AGGREGATION CASE STUDY\n"
            << "================================\n"
            << "Sales rows: "
            << service.sales().size()
            << "\n";

        // --------------------------------------------------------------------
        // GROUPING SETS
        // --------------------------------------------------------------------
        auto groupingSetReport =
            service.selectedGroupingSets();

        printReport(
            "SELECTED GROUPING SETS REPORT",
            groupingSetReport
        );

        // --------------------------------------------------------------------
        // ROLLUP
        // --------------------------------------------------------------------
        auto rollupReport =
            service.regionalRollup();

        printReport(
            "ROLLUP(region, channel, category)",
            rollupReport
        );

        verifyGrandTotal(
            service.sales(),
            rollupReport
        );

        // --------------------------------------------------------------------
        // HAVING
        // --------------------------------------------------------------------
        auto highRevenue =
            havingMinimumRevenue(
                rollupReport,
                3000.0
            );

        printReport(
            "ROLLUP + HAVING revenue >= 3000",
            highRevenue
        );

        // --------------------------------------------------------------------
        // CUBE
        // --------------------------------------------------------------------
        auto cubeReport =
            service.completeCube();

        printReport(
            "CUBE(region, channel, category) - FIRST 30 ROWS",
            cubeReport,
            30
        );

        std::cout
            << "\nCUBE grouping-set count for three dimensions: "
            << cube({
                Dimension::Region,
                Dimension::Channel,
                Dimension::Category
            }).size()
            << "\n";

        // --------------------------------------------------------------------
        // SQL EQUIVALENTS
        // --------------------------------------------------------------------
        printSqlCaseStudy();

        // --------------------------------------------------------------------
        // PERFORMANCE
        // --------------------------------------------------------------------
        const auto syntheticSales =
            makeSyntheticSales(10000);

        AnalyticsService performanceService(
            syntheticSales
        );

        std::cout
            << "\n"
            << std::string(110, '=')
            << "\n"
            << "PERFORMANCE DEMONSTRATION"
            << "\n"
            << std::string(110, '=')
            << "\n";

        auto timedRollup =
            measureMilliseconds(
                "10,000-row ROLLUP",
                [&performanceService]() {
                    return performanceService.regionalRollup();
                }
            );

        auto timedCube =
            measureMilliseconds(
                "10,000-row CUBE",
                [&performanceService]() {
                    return performanceService.completeCube();
                }
            );

        std::cout
            << "ROLLUP output rows: "
            << timedRollup.size()
            << "\n"
            << "CUBE output rows: "
            << timedCube.size()
            << "\n";

        /*
         * CUBE is not automatically "better" than ROLLUP.
         *
         * The choice depends on the reporting dimensions required.
         * CUBE creates more grouping combinations, which can increase
         * computation, memory consumption, and output size.
         */

        // --------------------------------------------------------------------
        // EDGE CASES
        // --------------------------------------------------------------------
        demonstrateEmptyDataset();
        demonstrateInvalidInput();

        // --------------------------------------------------------------------
        // ENGINEERING NOTES
        // --------------------------------------------------------------------
        std::cout
            << "\n"
            << std::string(110, '=')
            << "\n"
            << "ENGINEERING NOTES"
            << "\n"
            << std::string(110, '=')
            << "\n"
            << "GROUPING SETS: explicit reporting levels\n"
            << "ROLLUP: hierarchical reporting levels\n"
            << "CUBE: every combination of selected dimensions\n"
            << "GROUPING(): distinguishes subtotal dimensions\n"
            << "GROUPING_ID(): compact grouping-level metadata\n"
            << "HAVING: filters after aggregation\n"
            << "WHERE: filters source rows before aggregation\n"
            << "CUBE complexity: 2^n grouping sets for n dimensions\n";

        return 0;
    }
    catch (const std::exception& exception) {
        std::cerr
            << "Fatal error: "
            << exception.what()
            << "\n";

        return 1;
    }
}
