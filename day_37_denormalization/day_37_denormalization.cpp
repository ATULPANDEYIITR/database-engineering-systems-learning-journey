/*
 * Denormalization case study: repository-independent order analytics.
 *
 * The system begins with normalized entities and builds a denormalized
 * analytical projection. It demonstrates:
 *
 * - join cost versus read-model lookup
 * - materialized aggregates
 * - update propagation
 * - stale data detection
 * - reconciliation
 * - policy-driven denormalization decisions
 * - complexity and memory trade-offs
 *
 * Compile:
 *   g++ -std=c++17 -O2 denormalization.cpp -o denormalization
 */

#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using CustomerId = int;
using ProductId = int;
using OrderId = int;

struct Customer {
    CustomerId id;
    std::string name;
    std::string region;
};

struct Product {
    ProductId id;
    std::string name;
    std::string category;
    double unitPrice;
};

struct Order {
    OrderId id;
    CustomerId customerId;
    std::string orderDate;
    std::string status;
};

struct OrderLine {
    OrderId orderId;
    ProductId productId;
    int quantity;
};

struct OrderSummary {
    OrderId orderId;
    CustomerId customerId;
    std::string customerName;
    std::string region;
    std::string orderDate;
    std::string status;
    int itemCount;
    double totalAmount;
};

struct DecisionScenario {
    std::string name;
    double readFrequency;
    double writeFrequency;
    double joinCost;
    bool needsHistoricalSnapshot;
    bool strictImmediateConsistency;
};

class NormalizedStore {
public:
    std::unordered_map<CustomerId, Customer> customers;
    std::unordered_map<ProductId, Product> products;
    std::unordered_map<OrderId, Order> orders;
    std::vector<OrderLine> orderLines;

    OrderSummary buildSummary(OrderId orderId) const {
        const auto orderIt = orders.find(orderId);

        if (orderIt == orders.end()) {
            throw std::invalid_argument("Unknown order ID.");
        }

        const Order& order = orderIt->second;
        const auto customerIt = customers.find(order.customerId);

        if (customerIt == customers.end()) {
            throw std::logic_error("Order references a missing customer.");
        }

        OrderSummary summary{
            order.id,
            customerIt->second.id,
            customerIt->second.name,
            customerIt->second.region,
            order.orderDate,
            order.status,
            0,
            0.0
        };

        for (const auto& line : orderLines) {
            if (line.orderId != orderId) {
                continue;
            }

            if (line.quantity <= 0) {
                throw std::logic_error("Order quantity must be positive.");
            }

            const auto productIt = products.find(line.productId);

            if (productIt == products.end()) {
                throw std::logic_error("Order line references a missing product.");
            }

            summary.itemCount += line.quantity;
            summary.totalAmount += productIt->second.unitPrice * line.quantity;
        }

        summary.totalAmount = roundMoney(summary.totalAmount);
        return summary;
    }

    static double roundMoney(double value) {
        return std::round(value * 100.0) / 100.0;
    }
};

class ReadModel {
private:
    std::unordered_map<OrderId, OrderSummary> summaries_;
    std::size_t version_ = 0;

public:
    void rebuild(const NormalizedStore& source) {
        summaries_.clear();

        for (const auto& [orderId, order] : source.orders) {
            summaries_.emplace(orderId, source.buildSummary(orderId));
        }

        ++version_;
    }

    void refreshOrder(const NormalizedStore& source, OrderId orderId) {
        summaries_[orderId] = source.buildSummary(orderId);
        ++version_;
    }

    const OrderSummary& get(OrderId orderId) const {
        const auto it = summaries_.find(orderId);

        if (it == summaries_.end()) {
            throw std::out_of_range("Order does not exist in read model.");
        }

        return it->second;
    }

    std::size_t size() const {
        return summaries_.size();
    }

    std::size_t version() const {
        return version_;
    }
};

NormalizedStore createStore() {
    NormalizedStore store;

    store.customers.emplace(
        1, Customer{1, "Aarav Mehta", "North"}
    );
    store.customers.emplace(
        2, Customer{2, "Priya Nair", "South"}
    );
    store.customers.emplace(
        3, Customer{3, "Kabir Singh", "North"}
    );
    store.customers.emplace(
        4, Customer{4, "Meera Shah", "West"}
    );

    store.products.emplace(
        101, Product{101, "Mechanical Keyboard", "Peripherals", 89.99}
    );
    store.products.emplace(
        102, Product{102, "USB-C Dock", "Peripherals", 129.50}
    );
    store.products.emplace(
        103, Product{103, "27-inch Monitor", "Displays", 279.00}
    );
    store.products.emplace(
        104, Product{104, "Laptop Stand", "Accessories", 45.00}
    );
    store.products.emplace(
        105, Product{105, "Noise-Cancelling Headset", "Audio", 159.95}
    );

    store.orders.emplace(
        5001, Order{5001, 1, "2026-09-01", "SHIPPED"}
    );
    store.orders.emplace(
        5002, Order{5002, 2, "2026-09-02", "PROCESSING"}
    );
    store.orders.emplace(
        5003, Order{5003, 1, "2026-09-03", "DELIVERED"}
    );
    store.orders.emplace(
        5004, Order{5004, 3, "2026-09-04", "SHIPPED"}
    );
    store.orders.emplace(
        5005, Order{5005, 4, "2026-09-05", "CANCELLED"}
    );

    store.orderLines = {
        {5001, 101, 1},
        {5001, 103, 2},
        {5002, 102, 1},
        {5002, 104, 2},
        {5003, 105, 1},
        {5003, 101, 2},
        {5004, 103, 1},
        {5004, 104, 1},
        {5005, 102, 1}
    };

    return store;
}

bool reconcile(
    const NormalizedStore& source,
    const OrderSummary& stored
) {
    const OrderSummary current = source.buildSummary(stored.orderId);

    return stored.customerId == current.customerId &&
           stored.customerName == current.customerName &&
           stored.region == current.region &&
           stored.status == current.status &&
           stored.itemCount == current.itemCount &&
           std::abs(stored.totalAmount - current.totalAmount) < 0.001;
}

void printSummary(const OrderSummary& summary) {
    std::cout
        << "Order " << summary.orderId
        << " | customer=" << summary.customerName
        << " | region=" << summary.region
        << " | status=" << summary.status
        << " | units=" << summary.itemCount
        << " | total=" << std::fixed << std::setprecision(2)
        << summary.totalAmount
        << '\n';
}

void demonstrateStaleData(NormalizedStore& source, ReadModel& readModel) {
    std::cout << "\n=== STALE DATA ===\n";

    std::cout
        << "Before source update: "
        << readModel.get(5001).customerName
        << '\n';

    source.customers.at(1).name = "Aarav Mehta Kumar";

    std::cout
        << "Source: "
        << source.customers.at(1).name
        << '\n';

    std::cout
        << "Read model: "
        << readModel.get(5001).customerName
        << '\n';

    // Denormalization does not remove the need for synchronization.
    readModel.refreshOrder(source, 5001);

    std::cout
        << "After projection refresh: "
        << readModel.get(5001).customerName
        << '\n';
}

void demonstrateCorruptionDetection(
    const NormalizedStore& source,
    const ReadModel& readModel
) {
    std::cout << "\n=== RECONCILIATION ===\n";

    const OrderSummary& stored = readModel.get(5002);

    std::cout
        << "Order 5002 consistent: "
        << std::boolalpha
        << reconcile(source, stored)
        << '\n';

    OrderSummary corrupted = stored;
    corrupted.totalAmount += 50.0;

    std::cout
        << "Corrupted aggregate consistent: "
        << reconcile(source, corrupted)
        << '\n';
}

void demonstrateComplexity() {
    std::cout << "\n=== COMPLEXITY TRADE-OFF ===\n";
    std::cout
        << "A normalized report may require locating the order, customer, "
           "and all matching order lines, then aggregating products.\n";

    std::cout
        << "An indexed denormalized read model can often retrieve a "
           "precomputed summary in approximately O(1) average hash-map lookup.\n";

    std::cout
        << "The trade-off is shifted to writes: source changes can require "
           "projection updates, event processing, or periodic reconciliation.\n";
}

std::string recommend(const DecisionScenario& scenario) {
    if (scenario.needsHistoricalSnapshot) {
        return "Denormalization is appropriate when the duplicated values define a deliberate historical snapshot.";
    }

    if (scenario.strictImmediateConsistency &&
        scenario.writeFrequency > scenario.readFrequency) {
        return "Prefer normalization because frequent writes and strict consistency make duplication expensive.";
    }

    if (scenario.readFrequency > scenario.writeFrequency * 5.0 &&
        scenario.joinCost >= 3.0) {
        return "Denormalization is a strong candidate after measuring the workload.";
    }

    return "Keep the normalized design until profiling demonstrates a material benefit.";
}

void demonstrateDecisionEngine() {
    std::cout << "\n=== DENORMALIZATION DECISIONS ===\n";

    const std::vector<DecisionScenario> scenarios{
        {
            "Operational dashboard",
            100.0,
            10.0,
            5.0,
            false,
            false
        },
        {
            "Customer master record",
            10.0,
            20.0,
            1.0,
            false,
            true
        },
        {
            "Historical invoice",
            50.0,
            2.0,
            4.0,
            true,
            true
        }
    };

    for (const auto& scenario : scenarios) {
        std::cout
            << scenario.name
            << ": "
            << recommend(scenario)
            << '\n';
    }
}

void benchmark(
    const NormalizedStore& source,
    const ReadModel& readModel
) {
    constexpr int iterations = 50000;

    auto start = std::chrono::steady_clock::now();

    volatile double normalizedTotal = 0.0;

    for (int i = 0; i < iterations; ++i) {
        for (const auto& [orderId, order] : source.orders) {
            normalizedTotal += source.buildSummary(orderId).totalAmount;
        }
    }

    auto normalizedEnd = std::chrono::steady_clock::now();

    volatile double denormalizedTotal = 0.0;

    for (int i = 0; i < iterations; ++i) {
        for (const auto& [orderId, order] : source.orders) {
            denormalizedTotal += readModel.get(orderId).totalAmount;
        }
    }

    auto denormalizedEnd = std::chrono::steady_clock::now();

    const auto normalizedMs =
        std::chrono::duration_cast<std::chrono::milliseconds>(
            normalizedEnd - start
        ).count();

    const auto denormalizedMs =
        std::chrono::duration_cast<std::chrono::milliseconds>(
            denormalizedEnd - normalizedEnd
        ).count();

    std::cout << "\n=== BENCHMARK ===\n";
    std::cout
        << "Normalized reconstruction: "
        << normalizedMs << " ms\n";

    std::cout
        << "Denormalized lookup: "
        << denormalizedMs << " ms\n";

    std::cout
        << "This benchmark isolates an in-memory implementation. "
           "It does not predict database performance because real database "
           "systems add indexes, query planning, caching, disk I/O, "
           "concurrency, and network latency.\n";

    if (normalizedTotal == -1.0 || denormalizedTotal == -1.0) {
        std::cerr << "Unreachable benchmark guard.\n";
    }
}

int main() {
    try {
        NormalizedStore source = createStore();
        ReadModel readModel;

        std::cout << "=== NORMALIZED SOURCE ===\n";
        printSummary(source.buildSummary(5001));

        std::cout << "\n=== MATERIALIZED READ MODEL ===\n";
        readModel.rebuild(source);

        for (const auto& [orderId, order] : source.orders) {
            printSummary(readModel.get(orderId));
        }

        demonstrateStaleData(source, readModel);
        demonstrateCorruptionDetection(source, readModel);
        demonstrateComplexity();
        demonstrateDecisionEngine();
        benchmark(source, readModel);

        std::cout
            << "\n=== ARCHITECTURAL BOUNDARY ===\n"
            << "The normalized store remains the authoritative source. "
               "The denormalized read model is derived data. "
               "That distinction makes ownership, refresh, and reconciliation "
               "rules explicit.\n";
    }
    catch (const std::exception& error) {
        std::cerr
            << "Application failure: "
            << error.what()
            << '\n';

        return 1;
    }

    return 0;
}
