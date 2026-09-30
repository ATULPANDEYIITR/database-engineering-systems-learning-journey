#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

/*
Advanced SQL Project
Repository-style analytical engine implemented as a C++17 case study.

Scenario:
A subscription-commerce platform needs a governance-quality analytical
reporting engine. The production data would normally live in SQL tables and
be queried using CTEs, joins, grouping, and window functions. This C++ case
study models the same analytical semantics in strongly typed data structures.

The design deliberately differs from the Python SQL execution example:
the focus here is on how an analytical query plan can be represented as a
typed pipeline with reusable stages, validation, ranking, cohort calculation,
and explicit complexity considerations.

The program demonstrates:
- normalized entities and relationships
- a fact-like order-item dataset
- joins represented through indexed lookup maps
- aggregation by month, category, and customer
- ranking and cumulative contribution
- cohort retention
- anomaly detection
- analytical pipeline validation
- explicit handling of cancelled/refunded orders
*/

struct Customer {
    int id;
    std::string name;
    std::string region;
    std::string segment;
    std::string signupDate;
};

struct Product {
    int id;
    std::string name;
    std::string category;
    double cost;
    double listPrice;
};

struct Order {
    int id;
    int customerId;
    std::string date;
    std::string status;
};

struct OrderItem {
    int orderId;
    int productId;
    int quantity;
    double unitPrice;
    double discount;
};

struct CustomerMetric {
    int customerId{};
    std::string customerName;
    std::string region;
    std::string segment;
    double revenue{};
    double margin{};
    int orders{};
    std::string lastOrder;
};

struct MonthlyMetric {
    std::string month;
    double revenue{};
};

struct RankedCustomer {
    CustomerMetric metric;
    int rank{};
    double revenueShare{};
};

struct ProductMetric {
    int productId{};
    std::string name;
    std::string category;
    double revenue{};
};

struct ParetoMetric {
    ProductMetric product;
    double revenueShare{};
    double cumulativeShare{};
};

struct CohortMetric {
    std::string cohortMonth;
    std::string activityMonth;
    int activeCustomers{};
    int cohortSize{};
    double retention{};
};

struct AnomalyMetric {
    int orderId{};
    std::string customerName;
    std::string date;
    double value{};
    double zScore{};
    bool anomaly{};
};

class AnalyticsEngine {
private:
    std::vector<Customer> customers;
    std::vector<Product> products;
    std::vector<Order> orders;
    std::vector<OrderItem> items;

    std::unordered_map<int, const Customer*> customerIndex;
    std::unordered_map<int, const Product*> productIndex;
    std::unordered_map<int, const Order*> orderIndex;

    static std::string monthOf(const std::string& isoDate) {
        if (isoDate.size() < 7) {
            throw std::invalid_argument("Invalid ISO date: " + isoDate);
        }
        return isoDate.substr(0, 7);
    }

    static double round2(double value) {
        return std::round(value * 100.0) / 100.0;
    }

    static bool isCompleted(const Order& order) {
        return order.status == "completed";
    }

    double itemRevenue(const OrderItem& item) const {
        return item.quantity * item.unitPrice * (1.0 - item.discount);
    }

    double itemMargin(const OrderItem& item) const {
        const auto productIt = productIndex.find(item.productId);

        if (productIt == productIndex.end()) {
            throw std::logic_error("Product index missing during margin calculation");
        }

        const Product& product = *productIt->second;

        return item.quantity *
               (item.unitPrice * (1.0 - item.discount) - product.cost);
    }

public:
    AnalyticsEngine() {
        seed();
        buildIndexes();
        validate();
    }

    void seed() {
        customers = {
            {1, "Aarav Industries", "North", "enterprise", "2024-01-05"},
            {2, "Bharat Retail", "North", "business", "2024-01-15"},
            {3, "Cedar Labs", "West", "enterprise", "2024-02-03"},
            {4, "Delta Studio", "West", "business", "2024-02-19"},
            {5, "Epsilon Works", "South", "consumer", "2024-03-01"},
            {6, "Falcon Systems", "South", "enterprise", "2024-03-12"},
            {7, "Ganga Foods", "East", "business", "2024-04-08"},
            {8, "Horizon Media", "East", "consumer", "2024-04-21"},
            {9, "Indus Analytics", "North", "business", "2024-05-04"},
            {10, "Jade Health", "West", "enterprise", "2024-05-18"},
            {11, "Kaveri Design", "South", "consumer", "2024-06-10"},
            {12, "Lotus Commerce", "East", "business", "2024-06-25"}
        };

        products = {
            {1, "Data Platform", "Software", 180.0, 500.0},
            {2, "Security Suite", "Security", 120.0, 360.0},
            {3, "Analytics Pro", "Analytics", 90.0, 280.0},
            {4, "Cloud Storage", "Infrastructure", 40.0, 140.0},
            {5, "API Gateway", "Infrastructure", 65.0, 190.0},
            {6, "Support Plan", "Services", 35.0, 120.0}
        };

        orders = {
            {101, 1, "2024-01-20", "completed"},
            {102, 1, "2024-02-20", "completed"},
            {103, 1, "2024-04-10", "completed"},
            {104, 2, "2024-02-02", "completed"},
            {105, 2, "2024-03-14", "completed"},
            {106, 2, "2024-05-17", "completed"},
            {107, 3, "2024-02-20", "completed"},
            {108, 3, "2024-03-22", "completed"},
            {109, 3, "2024-06-05", "completed"},
            {110, 4, "2024-03-01", "completed"},
            {111, 4, "2024-03-18", "refunded"},
            {112, 4, "2024-05-02", "completed"},
            {113, 5, "2024-03-20", "completed"},
            {114, 5, "2024-04-21", "completed"},
            {115, 6, "2024-03-25", "completed"},
            {116, 6, "2024-04-30", "completed"},
            {117, 6, "2024-06-30", "completed"},
            {118, 7, "2024-04-15", "completed"},
            {119, 7, "2024-05-20", "completed"},
            {120, 8, "2024-05-01", "completed"},
            {121, 9, "2024-05-10", "completed"},
            {122, 9, "2024-06-15", "completed"},
            {123, 10, "2024-05-28", "completed"},
            {124, 10, "2024-06-25", "completed"},
            {125, 11, "2024-06-20", "completed"},
            {126, 12, "2024-06-29", "completed"},
            {127, 1, "2024-05-15", "cancelled"},
            {128, 2, "2024-06-18", "completed"},
            {129, 3, "2024-05-15", "completed"},
            {130, 6, "2024-05-15", "completed"}
        };

        items = {
            {101, 1, 2, 480, 0.04}, {101, 6, 2, 110, 0},
            {102, 3, 3, 260, 0.05},
            {103, 2, 2, 340, 0.02}, {103, 4, 5, 130, 0},
            {104, 3, 2, 270, 0},
            {105, 5, 3, 180, 0.05}, {105, 6, 1, 115, 0},
            {106, 1, 1, 490, 0},
            {107, 1, 4, 450, 0.10}, {107, 3, 2, 270, 0},
            {108, 2, 3, 350, 0.03},
            {109, 3, 5, 250, 0.08},
            {110, 4, 4, 135, 0},
            {111, 5, 2, 185, 0},
            {112, 6, 5, 110, 0.05},
            {113, 4, 2, 140, 0},
            {114, 3, 2, 275, 0},
            {115, 1, 2, 490, 0},
            {116, 2, 2, 350, 0}, {116, 6, 2, 115, 0},
            {117, 1, 1, 500, 0},
            {118, 5, 4, 180, 0.05},
            {119, 6, 3, 120, 0}, {119, 4, 3, 135, 0},
            {120, 3, 2, 280, 0},
            {121, 2, 3, 355, 0.02},
            {122, 5, 2, 190, 0},
            {123, 1, 3, 470, 0.04},
            {124, 2, 2, 360, 0},
            {125, 4, 5, 125, 0},
            {126, 6, 2, 115, 0},
            {127, 1, 1, 500, 0},
            {128, 3, 4, 260, 0.07},
            {129, 2, 1, 350, 0},
            {130, 1, 1, 500, 0}, {130, 5, 2, 185, 0}
        };
    }

    void buildIndexes() {
        customerIndex.clear();
        productIndex.clear();
        orderIndex.clear();

        for (const auto& customer : customers) {
            customerIndex[customer.id] = &customer;
        }

        for (const auto& product : products) {
            productIndex[product.id] = &product;
        }

        for (const auto& order : orders) {
            orderIndex[order.id] = &order;
        }
    }

    void validate() const {
        std::set<int> customerIds;
        std::set<int> productIds;
        std::set<int> orderIds;

        for (const auto& customer : customers) {
            if (!customerIds.insert(customer.id).second) {
                throw std::runtime_error("Duplicate customer ID");
            }
        }

        for (const auto& product : products) {
            if (!productIds.insert(product.id).second) {
                throw std::runtime_error("Duplicate product ID");
            }

            if (product.cost < 0 || product.listPrice < product.cost) {
                throw std::runtime_error("Invalid product pricing");
            }
        }

        for (const auto& order : orders) {
            if (!orderIds.insert(order.id).second) {
                throw std::runtime_error("Duplicate order ID");
            }

            if (!customerIndex.contains(order.customerId)) {
                throw std::runtime_error("Order references missing customer");
            }

            if (order.status != "completed" &&
                order.status != "cancelled" &&
                order.status != "refunded") {
                throw std::runtime_error("Invalid order status");
            }
        }

        for (const auto& item : items) {
            if (!orderIndex.contains(item.orderId)) {
                throw std::runtime_error("Item references missing order");
            }

            if (!productIndex.contains(item.productId)) {
                throw std::runtime_error("Item references missing product");
            }

            if (item.quantity <= 0 ||
                item.discount < 0 ||
                item.discount > 1 ||
                item.unitPrice < 0) {
                throw std::runtime_error("Invalid order item");
            }
        }
    }

    std::vector<MonthlyMetric> monthlyRevenue() const {
        std::map<std::string, double> totals;

        for (const auto& item : items) {
            const Order& order = *orderIndex.at(item.orderId);

            if (!isCompleted(order)) {
                continue;
            }

            totals[monthOf(order.date)] += itemRevenue(item);
        }

        std::vector<MonthlyMetric> result;

        for (const auto& [month, revenue] : totals) {
            result.push_back({month, round2(revenue)});
        }

        return result;
    }

    std::vector<CustomerMetric> customerMetrics() const {
        std::unordered_map<int, CustomerMetric> metrics;

        for (const auto& item : items) {
            const Order& order = *orderIndex.at(item.orderId);

            if (!isCompleted(order)) {
                continue;
            }

            const Customer& customer = *customerIndex.at(order.customerId);

            auto [it, inserted] = metrics.emplace(
                customer.id,
                CustomerMetric{
                    customer.id,
                    customer.name,
                    customer.region,
                    customer.segment,
                    0.0,
                    0.0,
                    0,
                    ""
                }
            );

            CustomerMetric& metric = it->second;

            metric.revenue += itemRevenue(item);
            metric.margin += itemMargin(item);

            if (metric.lastOrder.empty() || order.date > metric.lastOrder) {
                metric.lastOrder = order.date;
            }
        }

        std::set<std::pair<int, int>> customerOrders;

        for (const auto& item : items) {
            const Order& order = *orderIndex.at(item.orderId);

            if (isCompleted(order)) {
                customerOrders.insert({order.customerId, order.id});
            }
        }

        for (const auto& [customerId, orderId] : customerOrders) {
            metrics.at(customerId).orders++;
        }

        std::vector<CustomerMetric> result;

        for (auto& [id, metric] : metrics) {
            metric.revenue = round2(metric.revenue);
            metric.margin = round2(metric.margin);
            result.push_back(metric);
        }

        std::sort(
            result.begin(),
            result.end(),
            [](const auto& a, const auto& b) {
                return a.revenue > b.revenue;
            }
        );

        return result;
    }

    std::vector<RankedCustomer> rankCustomers() const {
        auto metrics = customerMetrics();

        const double totalRevenue = std::accumulate(
            metrics.begin(),
            metrics.end(),
            0.0,
            [](double total, const CustomerMetric& metric) {
                return total + metric.revenue;
            }
        );

        std::vector<RankedCustomer> result;

        double previousRevenue = -1;
        int currentRank = 0;

        for (std::size_t i = 0; i < metrics.size(); ++i) {
            if (metrics[i].revenue != previousRevenue) {
                currentRank = static_cast<int>(i) + 1;
                previousRevenue = metrics[i].revenue;
            }

            const double share =
                totalRevenue == 0
                    ? 0
                    : 100.0 * metrics[i].revenue / totalRevenue;

            result.push_back({
                metrics[i],
                currentRank,
                round2(share)
            });
        }

        return result;
    }

    std::vector<ParetoMetric> productPareto() const {
        std::unordered_map<int, ProductMetric> metrics;

        for (const auto& item : items) {
            const Order& order = *orderIndex.at(item.orderId);

            if (!isCompleted(order)) {
                continue;
            }

            const Product& product = *productIndex.at(item.productId);

            auto [it, inserted] = metrics.emplace(
                product.id,
                ProductMetric{
                    product.id,
                    product.name,
                    product.category,
                    0.0
                }
            );

            it->second.revenue += itemRevenue(item);
        }

        std::vector<ProductMetric> productsByRevenue;

        for (auto& [id, metric] : metrics) {
            metric.revenue = round2(metric.revenue);
            productsByRevenue.push_back(metric);
        }

        std::sort(
            productsByRevenue.begin(),
            productsByRevenue.end(),
            [](const auto& a, const auto& b) {
                return a.revenue > b.revenue;
            }
        );

        const double total = std::accumulate(
            productsByRevenue.begin(),
            productsByRevenue.end(),
            0.0,
            [](double value, const ProductMetric& metric) {
                return value + metric.revenue;
            }
        );

        std::vector<ParetoMetric> result;
        double cumulative = 0;

        for (const auto& product : productsByRevenue) {
            cumulative += product.revenue;

            result.push_back({
                product,
                total == 0 ? 0 : round2(100.0 * product.revenue / total),
                total == 0 ? 0 : round2(100.0 * cumulative / total)
            });
        }

        return result;
    }

    std::vector<CohortMetric> cohortRetention() const {
        std::unordered_map<int, std::string> firstPurchase;
        std::unordered_map<int, std::set<std::string>> activity;

        for (const auto& order : orders) {
            if (!isCompleted(order)) {
                continue;
            }

            const std::string month = monthOf(order.date);

            auto it = firstPurchase.find(order.customerId);

            if (it == firstPurchase.end() || order.date < it->second) {
                firstPurchase[order.customerId] = order.date;
            }

            activity[order.customerId].insert(month);
        }

        std::map<std::string, std::vector<int>> cohorts;

        for (const auto& [customerId, firstDate] : firstPurchase) {
            cohorts[monthOf(firstDate)].push_back(customerId);
        }

        std::vector<CohortMetric> result;

        for (const auto& [cohortMonth, cohortCustomers] : cohorts) {
            std::map<std::string, int> activeCount;

            for (int customerId : cohortCustomers) {
                for (const auto& month : activity[customerId]) {
                    activeCount[month]++;
                }
            }

            for (const auto& [activityMonth, active] : activeCount) {
                const double retention =
                    cohortCustomers.empty()
                        ? 0
                        : 100.0 * active / cohortCustomers.size();

                result.push_back({
                    cohortMonth,
                    activityMonth,
                    active,
                    static_cast<int>(cohortCustomers.size()),
                    round2(retention)
                });
            }
        }

        std::sort(
            result.begin(),
            result.end(),
            [](const auto& a, const auto& b) {
                if (a.cohortMonth != b.cohortMonth) {
                    return a.cohortMonth < b.cohortMonth;
                }
                return a.activityMonth < b.activityMonth;
            }
        );

        return result;
    }

    std::vector<AnomalyMetric> orderAnomalies() const {
        std::vector<double> values;

        std::map<int, double> orderValues;

        for (const auto& item : items) {
            const Order& order = *orderIndex.at(item.orderId);

            if (!isCompleted(order)) {
                continue;
            }

            orderValues[order.id] += itemRevenue(item);
        }

        for (const auto& [orderId, value] : orderValues) {
            values.push_back(value);
        }

        if (values.empty()) {
            return {};
        }

        const double mean =
            std::accumulate(values.begin(), values.end(), 0.0)
            / values.size();

        double squaredDeviation = 0;

        for (double value : values) {
            squaredDeviation += (value - mean) * (value - mean);
        }

        const double stddev =
            std::sqrt(squaredDeviation / values.size());

        std::vector<AnomalyMetric> result;

        for (const auto& [orderId, value] : orderValues) {
            const Order& order = *orderIndex.at(orderId);
            const Customer& customer = *customerIndex.at(order.customerId);

            const double z =
                stddev == 0 ? 0 : (value - mean) / stddev;

            result.push_back({
                orderId,
                customer.name,
                order.date,
                round2(value),
                round2(z),
                z > 2.0
            });
        }

        std::sort(
            result.begin(),
            result.end(),
            [](const auto& a, const auto& b) {
                return a.value > b.value;
            }
        );

        return result;
    }

    void printMonthlyAnalysis() const {
        std::cout << "\n=== Monthly Revenue ===\n";
        std::cout
            << std::left
            << std::setw(10) << "Month"
            << std::setw(15) << "Revenue"
            << std::setw(15) << "Previous"
            << std::setw(15) << "Growth %"
            << std::setw(18) << "Rolling Avg"
            << "\n";

        auto rows = monthlyRevenue();

        for (std::size_t i = 0; i < rows.size(); ++i) {
            const double previous =
                i == 0 ? 0 : rows[i - 1].revenue;

            const double growth =
                i == 0 || previous == 0
                    ? 0
                    : 100.0 * (rows[i].revenue - previous) / previous;

            const std::size_t start = i >= 2 ? i - 2 : 0;

            double rollingTotal = 0;
            int count = 0;

            for (std::size_t j = start; j <= i; ++j) {
                rollingTotal += rows[j].revenue;
                ++count;
            }

            const double rollingAverage = rollingTotal / count;

            std::cout
                << std::left
                << std::setw(10) << rows[i].month
                << std::setw(15) << std::fixed << std::setprecision(2)
                << rows[i].revenue
                << std::setw(15) << previous
                << std::setw(15) << growth
                << std::setw(18) << rollingAverage
                << "\n";
        }
    }

    void printCustomerRanking() const {
        std::cout << "\n=== Customer Revenue Ranking ===\n";

        const auto rows = rankCustomers();

        std::cout
            << std::left
            << std::setw(7) << "Rank"
            << std::setw(22) << "Customer"
            << std::setw(13) << "Region"
            << std::setw(13) << "Orders"
            << std::setw(15) << "Revenue"
            << std::setw(13) << "Share %"
            << "\n";

        for (const auto& row : rows) {
            std::cout
                << std::left
                << std::setw(7) << row.rank
                << std::setw(22) << row.metric.customerName
                << std::setw(13) << row.metric.region
                << std::setw(13) << row.metric.orders
                << std::setw(15) << row.metric.revenue
                << std::setw(13) << row.revenueShare
                << "\n";
        }
    }

    void printParetoAnalysis() const {
        std::cout << "\n=== Product Pareto Analysis ===\n";

        const auto rows = productPareto();

        std::cout
            << std::left
            << std::setw(20) << "Product"
            << std::setw(18) << "Category"
            << std::setw(15) << "Revenue"
            << std::setw(15) << "Share %"
            << std::setw(18) << "Cumulative %"
            << "\n";

        for (const auto& row : rows) {
            std::cout
                << std::left
                << std::setw(20) << row.product.name
                << std::setw(18) << row.product.category
                << std::setw(15) << row.product.revenue
                << std::setw(15) << row.revenueShare
                << std::setw(18) << row.cumulativeShare
                << "\n";
        }
    }

    void printCohorts() const {
        std::cout << "\n=== Cohort Retention ===\n";

        const auto rows = cohortRetention();

        std::cout
            << std::left
            << std::setw(14) << "Cohort"
            << std::setw(14) << "Activity"
            << std::setw(12) << "Active"
            << std::setw(12) << "Cohort Size"
            << std::setw(14) << "Retention %"
            << "\n";

        for (const auto& row : rows) {
            std::cout
                << std::left
                << std::setw(14) << row.cohortMonth
                << std::setw(14) << row.activityMonth
                << std::setw(12) << row.activeCustomers
                << std::setw(12) << row.cohortSize
                << std::setw(14) << row.retention
                << "\n";
        }
    }

    void printAnomalies() const {
        std::cout << "\n=== Order Anomaly Detection ===\n";

        const auto rows = orderAnomalies();

        std::cout
            << std::left
            << std::setw(10) << "Order"
            << std::setw(22) << "Customer"
            << std::setw(14) << "Date"
            << std::setw(15) << "Value"
            << std::setw(12) << "Z-Score"
            << std::setw(18) << "Classification"
            << "\n";

        for (const auto& row : rows) {
            std::cout
                << std::left
                << std::setw(10) << row.orderId
                << std::setw(22) << row.customerName
                << std::setw(14) << row.date
                << std::setw(15) << row.value
                << std::setw(12) << row.zScore
                << std::setw(18)
                << (row.anomaly ? "potential anomaly" : "normal")
                << "\n";
        }
    }

    void printObservedCustomerValue() const {
        std::cout << "\n=== Observed Customer Value ===\n";

        auto rows = customerMetrics();

        std::cout
            << std::left
            << std::setw(22) << "Customer"
            << std::setw(15) << "Segment"
            << std::setw(12) << "Orders"
            << std::setw(15) << "Revenue"
            << std::setw(15) << "Margin"
            << "\n";

        for (const auto& row : rows) {
            std::cout
                << std::left
                << std::setw(22) << row.customerName
                << std::setw(15) << row.segment
                << std::setw(12) << row.orders
                << std::setw(15) << row.revenue
                << std::setw(15) << row.margin
                << "\n";
        }
    }
};

int main() {
    try {
        AnalyticsEngine engine;

        /*
        Each report is an independent analytical projection over the same
        normalized data. In a SQL implementation these correspond to separate
        SELECT statements, CTE pipelines, GROUP BY operations, and window
        expressions.
        */
        engine.printMonthlyAnalysis();
        engine.printCustomerRanking();
        engine.printParetoAnalysis();
        engine.printCohorts();
        engine.printAnomalies();
        engine.printObservedCustomerValue();

        std::cout
            << "\nAnalytical pipeline completed successfully.\n";
        return 0;
    }
    catch (const std::exception& error) {
        std::cerr
            << "Analytical pipeline failed: "
            << error.what()
            << '\n';

        return 1;
    }
}
