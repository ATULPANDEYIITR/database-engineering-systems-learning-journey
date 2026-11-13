/*
 * Query Optimizer: Cost Estimation, Statistics and Plan Selection
 *
 * C++17
 *
 * Implements:
 * - Relational statistics catalog
 * - Most-common-value and histogram estimates
 * - Predicate selectivity
 * - Sequential and index scans
 * - Hash and nested-loop joins
 * - Dynamic-programming join enumeration
 * - Execution-plan costing
 * - Statistics validation
 * - Merge-free plan tree representation
 *
 * Compile:
 * g++ -std=c++17 -O2 -Wall -Wextra -pedantic query_optimizer.cpp -o query_optimizer
 *
 * Run:
 * ./query_optimizer
 */

#include <algorithm>
#include <cmath>
#include <ctime>
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
#include <utility>
#include <vector>

using namespace std;

// ============================================================
// 1. DOMAIN TYPES
// ============================================================

enum class PredicateOperator {
    Equal,
    LessThan,
    GreaterThan,
    Between
};

enum class JoinAlgorithm {
    Hash,
    NestedLoop
};

enum class ScanAlgorithm {
    Sequential,
    Index
};

class OptimizerException : public runtime_error {
public:
    explicit OptimizerException(const string& message)
        : runtime_error(message) {}
};

struct CostParameters {
    double sequentialPage = 1.0;
    double randomPage = 4.0;
    double tuple = 0.01;
    double operation = 0.0025;
    double hashBuild = 0.015;
    double nestedLoop = 0.005;
    double cacheDiscount = 0.75;
};

struct Histogram {
    vector<double> boundaries;

    void validate() const {
        if (boundaries.size() < 2) {
            throw OptimizerException(
                "Histogram needs at least two boundaries."
            );
        }

        for (size_t i = 0; i < boundaries.size(); ++i) {
            if (!isfinite(boundaries[i])) {
                throw OptimizerException(
                    "Non-finite histogram boundary."
                );
            }

            if (i > 0 && boundaries[i] <= boundaries[i - 1]) {
                throw OptimizerException(
                    "Histogram must be strictly increasing."
                );
            }
        }
    }

    double rangeSelectivity(double low, double high) const {
        validate();

        if (low > high) {
            throw OptimizerException("Invalid histogram range.");
        }

        const double minimum = boundaries.front();
        const double maximum = boundaries.back();

        if (high <= minimum || low >= maximum) {
            return 0.0;
        }

        const double overlap = max(
            0.0,
            min(high, maximum) - max(low, minimum)
        );

        return overlap / (maximum - minimum);
    }
};

struct ColumnStatistics {
    string name;
    size_t distinctValues = 1;
    double nullFraction = 0.0;
    map<string, double> mostCommonValues;
    optional<Histogram> histogram;

    void validate() const {
        if (name.empty() || distinctValues == 0) {
            throw OptimizerException(
                "Invalid column statistics."
            );
        }

        if (
            !isfinite(nullFraction) ||
            nullFraction < 0.0 ||
            nullFraction > 1.0
        ) {
            throw OptimizerException("Invalid null fraction.");
        }

        double total = 0.0;

        for (const auto& [value, frequency] : mostCommonValues) {
            (void)value;

            if (
                !isfinite(frequency) ||
                frequency < 0.0 ||
                frequency > 1.0
            ) {
                throw OptimizerException("Invalid MCV frequency.");
            }

            total += frequency;
        }

        if (total > 1.0 + 1e-9) {
            throw OptimizerException(
                "MCV frequencies exceed one."
            );
        }

        if (histogram.has_value()) {
            histogram->validate();
        }
    }
};

struct IndexStatistics {
    string column;
    size_t pages = 1;
    bool unique = false;
    bool indexOnly = false;
};

struct RelationStatistics {
    string name;
    double rows = 0.0;
    size_t pages = 0;

    map<string, ColumnStatistics> columns;
    map<string, IndexStatistics> indexes;

    time_t analyzedAt = time(nullptr);

    void validate() const {
        if (name.empty() || rows < 0.0) {
            throw OptimizerException(
                "Invalid relation statistics."
            );
        }

        if (rows > 0.0 && pages == 0) {
            throw OptimizerException(
                "Nonempty relation requires pages."
            );
        }

        for (const auto& [name, column] : columns) {
            if (name != column.name) {
                throw OptimizerException(
                    "Column key mismatch."
                );
            }
            column.validate();
        }

        for (const auto& [name, index] : indexes) {
            if (
                name != index.column ||
                columns.find(name) == columns.end() ||
                index.pages == 0
            ) {
                throw OptimizerException(
                    "Invalid index statistics."
                );
            }
        }
    }
};

struct Predicate {
    string column;
    PredicateOperator operation;
    string value;
    optional<double> upper;
};

struct JoinCondition {
    string leftRelation;
    string leftColumn;
    string rightRelation;
    string rightColumn;
};

struct Plan {
    string operation;
    double cost = 0.0;
    double rows = 0.0;
    string details;
    vector<Plan> children;

    string explain(int depth = 0) const {
        ostringstream output;

        output << string(depth * 2, ' ')
               << operation
               << " (cost=" << fixed << setprecision(3)
               << cost
               << ", rows=" << rows << ")";

        if (!details.empty()) {
            output << "\n"
                   << string(depth * 2 + 2, ' ')
                   << details;
        }

        for (const auto& child : children) {
            output << "\n" << child.explain(depth + 1);
        }

        return output.str();
    }
};

// ============================================================
// 2. STATISTICS CATALOG
// ============================================================

class StatisticsCatalog {

private:
    unordered_map<string, RelationStatistics> relations;

public:

    void registerRelation(const RelationStatistics& statistics) {
        statistics.validate();

        if (relations.count(statistics.name)) {
            throw OptimizerException(
                "Duplicate relation: " + statistics.name
            );
        }

        relations.emplace(statistics.name, statistics);
    }

    const RelationStatistics& get(
        const string& relation
    ) const {
        auto iterator = relations.find(relation);

        if (iterator == relations.end()) {
            throw OptimizerException(
                "Missing relation statistics: " + relation
            );
        }

        return iterator->second;
    }

    bool isFresh(
        const string& relation,
        double maximumAgeSeconds = 86400.0
    ) const {
        const auto& statistics = get(relation);

        const double age = difftime(
            time(nullptr),
            statistics.analyzedAt
        );

        return age <= maximumAgeSeconds;
    }
};

// ============================================================
// 3. SELECTIVITY ESTIMATION
// ============================================================

class CardinalityEstimator {

private:
    const StatisticsCatalog& catalog;

    static double parseNumber(const string& value) {
        try {
            size_t position = 0;
            double result = stod(value, &position);

            if (
                position != value.size() ||
                !isfinite(result)
            ) {
                throw OptimizerException(
                    "Invalid numeric predicate."
                );
            }

            return result;
        } catch (const invalid_argument&) {
            throw OptimizerException(
                "Invalid numeric predicate."
            );
        } catch (const out_of_range&) {
            throw OptimizerException(
                "Numeric predicate out of range."
            );
        }
    }

public:

    explicit CardinalityEstimator(
        const StatisticsCatalog& catalog
    ) : catalog(catalog) {}

    double estimate(
        const string& relation,
        const Predicate& predicate
    ) const {

        const auto& statistics = catalog.get(relation);

        auto iterator = statistics.columns.find(
            predicate.column
        );

        if (iterator == statistics.columns.end()) {
            throw OptimizerException(
                "Unknown column: " + predicate.column
            );
        }

        const auto& column = iterator->second;

        switch (predicate.operation) {

            case PredicateOperator::Equal: {
                if (predicate.value == "NULL") {
                    return column.nullFraction;
                }

                auto mcv = column.mostCommonValues.find(
                    predicate.value
                );

                if (mcv != column.mostCommonValues.end()) {
                    return mcv->second;
                }

                return (
                    1.0 - column.nullFraction
                ) / static_cast<double>(column.distinctValues);
            }

            case PredicateOperator::LessThan:
            case PredicateOperator::GreaterThan:
            case PredicateOperator::Between: {

                if (!column.histogram.has_value()) {
                    return (
                        predicate.operation ==
                        PredicateOperator::Between
                    ) ? 0.25 : 0.33;
                }

                const auto& histogram = *column.histogram;

                const double low =
                    predicate.operation ==
                    PredicateOperator::GreaterThan
                    ? parseNumber(predicate.value)
                    : predicate.operation ==
                      PredicateOperator::Between
                        ? parseNumber(predicate.value)
                        : histogram.boundaries.front();

                const double high =
                    predicate.operation ==
                    PredicateOperator::LessThan
                    ? parseNumber(predicate.value)
                    : predicate.operation ==
                      PredicateOperator::Between
                        ? predicate.upper.value_or(
                            throw OptimizerException(
                                "Missing upper range boundary."
                            )
                        )
                        : histogram.boundaries.back();

                return histogram.rangeSelectivity(
                    low,
                    high
                );
            }
        }

        throw OptimizerException("Unsupported predicate.");
    }

    double estimateRows(
        const string& relation,
        const vector<Predicate>& predicates
    ) const {

        const auto& statistics = catalog.get(relation);

        double selectivity = 1.0;

        for (const auto& predicate : predicates) {
            selectivity *= estimate(relation, predicate);
        }

        return statistics.rows * selectivity;
    }
};

// ============================================================
// 4. SCAN COSTING
// ============================================================

class AccessPathEvaluator {

private:
    const StatisticsCatalog& catalog;
    const CardinalityEstimator& cardinality;
    CostParameters costs;

public:

    AccessPathEvaluator(
        const StatisticsCatalog& catalog,
        const CardinalityEstimator& cardinality,
        const CostParameters& costs
    ) : catalog(catalog),
        cardinality(cardinality),
        costs(costs) {}

    vector<Plan> candidates(
        const string& relation,
        const vector<Predicate>& predicates
    ) const {

        const auto& statistics = catalog.get(relation);

        const double rows = cardinality.estimateRows(
            relation,
            predicates
        );

        const double sequentialCost =
            statistics.pages * costs.sequentialPage
            + statistics.rows * costs.tuple
            + statistics.rows
            * predicates.size()
            * costs.operation;

        vector<Plan> plans;

        plans.push_back({
            "Sequential Scan",
            sequentialCost,
            rows,
            "relation=" + relation,
            {}
        });

        for (const auto& predicate : predicates) {

            if (
                predicate.operation != PredicateOperator::Equal
            ) {
                continue;
            }

            auto iterator = statistics.indexes.find(
                predicate.column
            );

            if (iterator == statistics.indexes.end()) {
                continue;
            }

            const auto& index = iterator->second;

            const double height = max(
                1.0,
                ceil(log2(index.pages + 1.0))
            );

            double heapPages = statistics.rows == 0.0
                ? 0.0
                : rows * statistics.pages / statistics.rows;

            if (index.indexOnly) {
                heapPages *= 0.1;
            }

            const double indexCost =
                height * costs.randomPage
                + heapPages * costs.randomPage
                * costs.cacheDiscount
                + rows * costs.tuple;

            plans.push_back({
                "Index Scan",
                indexCost,
                rows,
                "relation=" + relation
                + ", index=" + predicate.column,
                {}
            });
        }

        sort(
            plans.begin(),
            plans.end(),
            [](const Plan& a, const Plan& b) {
                return a.cost < b.cost;
            }
        );

        return plans;
    }
};

// ============================================================
// 5. JOIN COSTING
// ============================================================

class JoinEstimator {

private:
    const StatisticsCatalog& catalog;
    CostParameters costs;

public:

    JoinEstimator(
        const StatisticsCatalog& catalog,
        const CostParameters& costs
    ) : catalog(catalog), costs(costs) {}

    double estimateRows(
        double leftRows,
        double rightRows,
        const JoinCondition& join
    ) const {

        const auto& left = catalog.get(
            join.leftRelation
        );

        const auto& right = catalog.get(
            join.rightRelation
        );

        const auto leftColumn = left.columns.find(
            join.leftColumn
        );

        const auto rightColumn = right.columns.find(
            join.rightColumn
        );

        if (
            leftColumn == left.columns.end() ||
            rightColumn == right.columns.end()
        ) {
            throw OptimizerException(
                "Invalid join columns."
            );
        }

        const double denominator = max(
            static_cast<double>(
                leftColumn->second.distinctValues
            ),
            static_cast<double>(
                rightColumn->second.distinctValues
            )
        );

        return leftRows * rightRows /
            max(denominator, 1.0);
    }

    vector<Plan> candidates(
        const Plan& left,
        const Plan& right,
        const JoinCondition& join
    ) const {

        const double rows = estimateRows(
            left.rows,
            right.rows,
            join
        );

        const double buildRows = min(
            left.rows,
            right.rows
        );

        const double probeRows = max(
            left.rows,
            right.rows
        );

        const double hashCost =
            left.cost + right.cost
            + buildRows * costs.hashBuild
            + probeRows * costs.operation
            + (left.rows + right.rows) * costs.tuple;

        const double nestedCost =
            left.cost + right.cost
            + left.rows * right.rows * costs.nestedLoop
            + rows * costs.tuple;

        return {
            {
                "Hash Join",
                hashCost,
                rows,
                "build_rows=" + to_string(buildRows),
                {left, right}
            },
            {
                "Nested Loop",
                nestedCost,
                rows,
                "outer_rows=" + to_string(left.rows),
                {left, right}
            }
        };
    }
};

// ============================================================
// 6. QUERY MODEL
// ============================================================

struct Query {
    vector<string> relations;
    map<string, vector<Predicate>> predicates;
    vector<JoinCondition> joins;
};

// ============================================================
// 7. DYNAMIC-PROGRAMMING OPTIMIZER
// ============================================================

class QueryOptimizer {

private:
    const StatisticsCatalog& catalog;
    CostParameters costs;
    CardinalityEstimator cardinality;
    AccessPathEvaluator accessPaths;
    JoinEstimator joinEstimator;

    using Subset = uint64_t;

    static Subset bit(size_t position) {
        return 1ULL << position;
    }

    static int countBits(Subset value) {
        return __builtin_popcountll(value);
    }

public:

    QueryOptimizer(
        const StatisticsCatalog& catalog,
        const CostParameters& costs
    ) : catalog(catalog),
        costs(costs),
        cardinality(catalog),
        accessPaths(catalog, cardinality, costs),
        joinEstimator(catalog, costs) {}

    Plan optimize(const Query& query) const {

        const size_t n = query.relations.size();

        if (n == 0 || n > 12) {
            throw OptimizerException(
                "Optimizer supports 1 to 12 relations."
            );
        }

        set<string> uniqueRelations;

        for (const auto& relation : query.relations) {
            if (!uniqueRelations.insert(relation).second) {
                throw OptimizerException(
                    "Duplicate relation."
                );
            }

            catalog.get(relation);
        }

        const Subset fullMask = (1ULL << n) - 1;

        unordered_map<Subset, Plan> dp;

        // Base states: cheapest access path for each relation.
        for (size_t i = 0; i < n; ++i) {

            const auto& relation = query.relations[i];

            auto predicateIterator =
                query.predicates.find(relation);

            vector<Predicate> predicates;

            if (predicateIterator != query.predicates.end()) {
                predicates = predicateIterator->second;
            }

            auto alternatives = accessPaths.candidates(
                relation,
                predicates
            );

            dp[bit(i)] = alternatives.front();
        }

        // Enumerate connected left-deep join plans.
        for (int size = 2; size <= static_cast<int>(n); ++size) {

            for (Subset mask = 1; mask <= fullMask; ++mask) {

                if (countBits(mask) != size) {
                    continue;
                }

                optional<Plan> best;

                for (size_t relationIndex = 0;
                     relationIndex < n;
                     ++relationIndex) {

                    const Subset relationBit = bit(
                        relationIndex
                    );

                    if (!(mask & relationBit)) {
                        continue;
                    }

                    const Subset leftMask =
                        mask ^ relationBit;

                    auto leftIterator = dp.find(leftMask);

                    if (leftIterator == dp.end()) {
                        continue;
                    }

                    auto rightIterator = dp.find(relationBit);

                    if (rightIterator == dp.end()) {
                        continue;
                    }

                    const string& rightRelation =
                        query.relations[relationIndex];

                    for (const auto& join : query.joins) {

                        bool connects = false;

                        if (
                            join.leftRelation == rightRelation &&
                            leftMask != 0
                        ) {
                            for (size_t i = 0; i < n; ++i) {
                                if (
                                    (leftMask & bit(i)) &&
                                    query.relations[i] ==
                                    join.rightRelation
                                ) {
                                    connects = true;
                                }
                            }
                        }

                        if (
                            join.rightRelation == rightRelation &&
                            leftMask != 0
                        ) {
                            for (size_t i = 0; i < n; ++i) {
                                if (
                                    (leftMask & bit(i)) &&
                                    query.relations[i] ==
                                    join.leftRelation
                                ) {
                                    connects = true;
                                }
                            }
                        }

                        if (!connects) {
                            continue;
                        }

                        auto alternatives =
                            joinEstimator.candidates(
                                leftIterator->second,
                                rightIterator->second,
                                join
                            );

                        for (const auto& candidate : alternatives) {
                            if (
                                !best.has_value() ||
                                candidate.cost < best->cost
                            ) {
                                best = candidate;
                            }
                        }
                    }
                }

                if (best.has_value()) {
                    dp[mask] = *best;
                }
            }
        }

        auto result = dp.find(fullMask);

        if (result == dp.end()) {
            throw OptimizerException(
                "No connected execution plan exists."
            );
        }

        return result->second;
    }
};

// ============================================================
// 8. SAMPLE DATABASE STATISTICS
// ============================================================

StatisticsCatalog buildCatalog() {

    StatisticsCatalog catalog;

    RelationStatistics customers;
    customers.name = "customers";
    customers.rows = 100000;
    customers.pages = 1000;

    customers.columns["customer_id"] = {
        "customer_id",
        100000,
        0.0,
        {},
        nullopt
    };

    customers.columns["region"] = {
        "region",
        10,
        0.0,
        {
            {"North", 0.35},
            {"South", 0.25},
            {"East", 0.20},
            {"West", 0.15}
        },
        nullopt
    };

    customers.indexes["customer_id"] = {
        "customer_id", 250, true, false
    };

    customers.indexes["region"] = {
        "region", 80, false, false
    };

    catalog.registerRelation(customers);

    RelationStatistics orders;
    orders.name = "orders";
    orders.rows = 1000000;
    orders.pages = 12000;

    orders.columns["order_id"] = {
        "order_id", 1000000, 0.0, {}, nullopt
    };

    orders.columns["customer_id"] = {
        "customer_id", 100000, 0.0, {}, nullopt
    };

    orders.columns["status"] = {
        "status",
        4,
        0.0,
        {
            {"COMPLETED", 0.65},
            {"PENDING", 0.20},
            {"CANCELLED", 0.10},
            {"FAILED", 0.05}
        },
        nullopt
    };

    orders.columns["amount"] = {
        "amount",
        50000,
        0.0,
        {},
        Histogram{
            {0, 100, 250, 500, 1000, 5000, 10000}
        }
    };

    orders.indexes["customer_id"] = {
        "customer_id", 2000, false, false
    };

    orders.indexes["status"] = {
        "status", 500, false, false
    };

    orders.indexes["order_id"] = {
        "order_id", 2500, true, false
    };

    catalog.registerRelation(orders);

    RelationStatistics payments;
    payments.name = "payments";
    payments.rows = 850000;
    payments.pages = 9000;

    payments.columns["payment_id"] = {
        "payment_id", 850000, 0.0, {}, nullopt
    };

    payments.columns["order_id"] = {
        "order_id", 800000, 0.0, {}, nullopt
    };

    payments.columns["payment_status"] = {
        "payment_status",
        3,
        0.0,
        {
            {"SUCCESS", 0.80},
            {"PENDING", 0.15},
            {"FAILED", 0.05}
        },
        nullopt
    };

    payments.indexes["order_id"] = {
        "order_id", 1800, false, false
    };

    payments.indexes["payment_id"] = {
        "payment_id", 2000, true, false
    };

    catalog.registerRelation(payments);

    return catalog;
}

// ============================================================
// 9. VALIDATION TESTS
// ============================================================

void runTests(
    const StatisticsCatalog& catalog,
    const QueryOptimizer& optimizer
) {
    CardinalityEstimator estimator(catalog);

    const double north = estimator.estimate(
        "customers",
        {
            "region",
            PredicateOperator::Equal,
            "North",
            nullopt
        }
    );

    if (abs(north - 0.35) > 1e-9) {
        throw OptimizerException(
            "MCV estimation test failed."
        );
    }

    const double range = estimator.estimate(
        "orders",
        {
            "amount",
            PredicateOperator::Between,
            "1000",
            5000.0
        }
    );

    if (range < 0.0 || range > 1.0) {
        throw OptimizerException(
            "Histogram estimation test failed."
        );
    }

    try {
        Histogram invalid{{10, 5, 20}};
        invalid.validate();

        throw OptimizerException(
            "Invalid histogram was accepted."
        );
    } catch (const OptimizerException& error) {
        if (
            string(error.what()) ==
            "Invalid histogram was accepted."
        ) {
            throw;
        }
    }

    try {
        catalog.get("missing_relation");

        throw OptimizerException(
            "Unknown relation was accepted."
        );
    } catch (const OptimizerException& error) {
        if (
            string(error.what()) ==
            "Unknown relation was accepted."
        ) {
            throw;
        }
    }

    cout << "[TEST] Validation tests passed.\n";
}

// ============================================================
// 10. MAIN
// ============================================================

int main() {

    try {

        const auto catalog = buildCatalog();

        const CostParameters costs;

        const QueryOptimizer optimizer(
            catalog,
            costs
        );

        runTests(catalog, optimizer);

        Query query;

        query.relations = {
            "customers",
            "orders",
            "payments"
        };

        query.predicates["customers"] = {
            {
                "region",
                PredicateOperator::Equal,
                "North",
                nullopt
            }
        };

        query.predicates["orders"] = {
            {
                "status",
                PredicateOperator::Equal,
                "COMPLETED",
                nullopt
            },
            {
                "amount",
                PredicateOperator::Between,
                "100",
                1000.0
            }
        };

        query.predicates["payments"] = {
            {
                "payment_status",
                PredicateOperator::Equal,
                "SUCCESS",
                nullopt
            }
        };

        query.joins = {
            {
                "customers",
                "customer_id",
                "orders",
                "customer_id"
            },
            {
                "orders",
                "order_id",
                "payments",
                "order_id"
            }
        };

        cout << "\nQUERY OPTIMIZATION ENGINE\n";
        cout << "=========================\n";

        CardinalityEstimator estimator(catalog);

        AccessPathEvaluator accessPaths(
            catalog,
            estimator,
            costs
        );

        for (const auto& relation : query.relations) {

            const auto& statistics = catalog.get(relation);

            auto predicates = query.predicates[relation];

            const auto alternatives = accessPaths.candidates(
                relation,
                predicates
            );

            cout << "\nRelation: " << relation << "\n";
            cout << "Base rows: " << statistics.rows << "\n";
            cout << "Estimated rows: "
                 << alternatives.front().rows << "\n";

            for (const auto& alternative : alternatives) {
                cout << "  " << alternative.operation
                     << " cost=" << alternative.cost << "\n";
            }

            if (!catalog.isFresh(relation)) {
                cerr << "[WARNING] Stale statistics: "
                     << relation << "\n";
            }
        }

        const Plan selected = optimizer.optimize(query);

        cout << "\nSELECTED EXECUTION PLAN\n";
        cout << "=======================\n";

        cout << selected.explain() << "\n";

        cout << "\nEstimated total cost: "
             << selected.cost << "\n";

        cout << "Estimated output rows: "
             << selected.rows << "\n";

        cout << "\nOptimization completed successfully.\n";

    } catch (const exception& error) {

        cerr << "[OPTIMIZER ERROR] "
             << error.what() << "\n";

        return 1;
    }

    return 0;
}
