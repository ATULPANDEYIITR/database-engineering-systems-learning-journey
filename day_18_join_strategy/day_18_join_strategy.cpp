/*
Join Strategy: Join Keys, Cardinality, Duplicate Rows, and NULL Behavior

C++17 industry-style case study:
A transaction reconciliation and customer-order analytics engine.

The program demonstrates:
- join keys
- one-to-one, one-to-many, many-to-one and many-to-many cardinality
- duplicate-key multiplication
- SQL-like NULL semantics
- hash joins
- nested-loop joins
- composite keys
- left outer joins
- semi and anti joins
- validation of expected uniqueness
- row-count diagnostics
- overflow-aware size estimation
- complexity and memory considerations

Compile:
    g++ -std=c++17 -O2 -Wall -Wextra -pedantic join_strategy.cpp -o join_strategy
*/

#include <algorithm>
#include <cstddef>
#include <iomanip>
#include <iostream>
#include <limits>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

struct Customer {
    int customer_id;
    std::string country;
    std::string name;
    std::string segment;
};

struct Order {
    std::string order_id;
    int customer_id;
    double amount;
};

struct CustomerOrder {
    Customer customer;
    Order order;
};

struct Shipment {
    std::string country;
    int customer_id;
    std::string shipment_id;
};

struct CompositeCustomer {
    std::string country;
    int customer_id;
    std::string name;
};

struct OptionalOrder {
    std::string order_id;
    std::optional<int> customer_id;
    double amount;
};

struct OptionalCustomer {
    int customer_id;
    std::string name;
};

struct CustomerOptionalOrder {
    OptionalCustomer customer;
    std::optional<Order> order;
};

void print_title(const std::string& title) {
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << title << "\n";
    std::cout << std::string(80, '=') << "\n";
}

/*
SQL equality for ordinary join predicates.

In SQL:
    NULL = NULL
is UNKNOWN rather than TRUE.

std::optional<int> models a nullable integer. If either value is missing,
the equality predicate does not produce a join match.
*/
bool sql_equal(
    const std::optional<int>& left,
    const std::optional<int>& right
) {
    if (!left.has_value() || !right.has_value()) {
        return false;
    }

    return *left == *right;
}

/*
Null-safe equality deliberately gives NULL == NULL the value true.

This should only be used when the business rule explicitly wants missing
values to match each other.
*/
bool null_safe_equal(
    const std::optional<int>& left,
    const std::optional<int>& right
) {
    if (!left.has_value() && !right.has_value()) {
        return true;
    }

    if (!left.has_value() || !right.has_value()) {
        return false;
    }

    return *left == *right;
}

std::string optional_to_string(const std::optional<int>& value) {
    return value.has_value() ? std::to_string(*value) : "NULL";
}

void print_customer_orders(
    const std::vector<CustomerOrder>& rows,
    const std::string& title
) {
    std::cout << "\n" << title << "\n";
    std::cout
        << std::left
        << std::setw(10) << "Customer"
        << std::setw(12) << "Name"
        << std::setw(10) << "Country"
        << std::setw(12) << "Order"
        << std::setw(12) << "Amount"
        << "\n";

    for (const auto& row : rows) {
        std::cout
            << std::left
            << std::setw(10) << row.customer.customer_id
            << std::setw(12) << row.customer.name
            << std::setw(10) << row.customer.country
            << std::setw(12) << row.order.order_id
            << std::setw(12) << row.order.amount
            << "\n";
    }
}

/*
Naive nested-loop inner join.

For every customer, every order is inspected.

Complexity:
    O(N * M)

This is the clearest implementation for understanding the relational
definition of a join.
*/
std::vector<CustomerOrder> nested_loop_join(
    const std::vector<Customer>& customers,
    const std::vector<Order>& orders
) {
    std::vector<CustomerOrder> result;

    for (const auto& customer : customers) {
        for (const auto& order : orders) {
            if (customer.customer_id == order.customer_id) {
                result.push_back({customer, order});
            }
        }
    }

    return result;
}

/*
Hash join.

The right relation is indexed by customer_id.

A vector is stored for each key rather than a single Order. This is essential:
a hash map containing only one row per key would incorrectly discard
duplicates and break 1:N and N:N joins.

Expected complexity:
    O(N + M)

Additional memory:
    O(M)
*/
std::vector<CustomerOrder> hash_join(
    const std::vector<Customer>& customers,
    const std::vector<Order>& orders
) {
    std::unordered_map<int, std::vector<const Order*>> index;

    for (const auto& order : orders) {
        index[order.customer_id].push_back(&order);
    }

    std::vector<CustomerOrder> result;

    for (const auto& customer : customers) {
        auto found = index.find(customer.customer_id);

        if (found == index.end()) {
            continue;
        }

        for (const Order* order : found->second) {
            result.push_back({customer, *order});
        }
    }

    return result;
}

std::vector<CustomerOptionalOrder> left_outer_join(
    const std::vector<OptionalCustomer>& customers,
    const std::vector<Order>& orders
) {
    std::unordered_map<int, std::vector<const Order*>> index;

    for (const auto& order : orders) {
        index[order.customer_id].push_back(&order);
    }

    std::vector<CustomerOptionalOrder> result;

    for (const auto& customer : customers) {
        auto found = index.find(customer.customer_id);

        if (found == index.end()) {
            result.push_back({customer, std::nullopt});
            continue;
        }

        for (const Order* order : found->second) {
            result.push_back({customer, *order});
        }
    }

    return result;
}

void print_left_join(
    const std::vector<CustomerOptionalOrder>& rows
) {
    std::cout
        << std::left
        << std::setw(10) << "Customer"
        << std::setw(15) << "Name"
        << std::setw(12) << "Order"
        << std::setw(12) << "Amount"
        << "\n";

    for (const auto& row : rows) {
        std::cout
            << std::left
            << std::setw(10) << row.customer.customer_id
            << std::setw(15) << row.customer.name;

        if (row.order.has_value()) {
            std::cout
                << std::setw(12) << row.order->order_id
                << std::setw(12) << row.order->amount;
        } else {
            std::cout
                << std::setw(12) << "NULL"
                << std::setw(12) << "NULL";
        }

        std::cout << "\n";
    }
}

struct CompositeKey {
    std::string country;
    int customer_id;

    bool operator==(const CompositeKey& other) const {
        return country == other.country &&
               customer_id == other.customer_id;
    }
};

struct CompositeKeyHash {
    std::size_t operator()(const CompositeKey& key) const {
        const std::size_t first =
            std::hash<std::string>{}(key.country);

        const std::size_t second =
            std::hash<int>{}(key.customer_id);

        /*
        A common hash-combination pattern. The exact hash quality depends on
        the standard-library implementation and workload.
        */
        return first ^
               (second + static_cast<std::size_t>(0x9e3779b9) +
                (first << 6) + (first >> 2));
    }
};

std::vector<std::pair<Shipment, CompositeCustomer>>
composite_hash_join(
    const std::vector<Shipment>& shipments,
    const std::vector<CompositeCustomer>& customers
) {
    std::unordered_map<
        CompositeKey,
        std::vector<const CompositeCustomer*>,
        CompositeKeyHash
    > index;

    for (const auto& customer : customers) {
        CompositeKey key{
            customer.country,
            customer.customer_id
        };

        index[key].push_back(&customer);
    }

    std::vector<std::pair<Shipment, CompositeCustomer>> result;

    for (const auto& shipment : shipments) {
        CompositeKey key{
            shipment.country,
            shipment.customer_id
        };

        auto found = index.find(key);

        if (found == index.end()) {
            continue;
        }

        for (const auto* customer : found->second) {
            result.emplace_back(shipment, *customer);
        }
    }

    return result;
}

/*
Semi join:
return customers for which at least one order exists.

Notice that customers are emitted once even if they have ten orders.
*/
std::vector<Customer> semi_join(
    const std::vector<Customer>& customers,
    const std::vector<Order>& orders
) {
    std::unordered_set<int> order_customer_ids;

    for (const auto& order : orders) {
        order_customer_ids.insert(order.customer_id);
    }

    std::vector<Customer> result;

    for (const auto& customer : customers) {
        if (order_customer_ids.contains(customer.customer_id)) {
            result.push_back(customer);
        }
    }

    return result;
}

/*
Anti join:
return customers for which no order exists.
*/
std::vector<Customer> anti_join(
    const std::vector<Customer>& customers,
    const std::vector<Order>& orders
) {
    std::unordered_set<int> order_customer_ids;

    for (const auto& order : orders) {
        order_customer_ids.insert(order.customer_id);
    }

    std::vector<Customer> result;

    for (const auto& customer : customers) {
        if (!order_customer_ids.contains(customer.customer_id)) {
            result.push_back(customer);
        }
    }

    return result;
}

std::unordered_map<int, std::size_t> count_customer_keys(
    const std::vector<Customer>& customers
) {
    std::unordered_map<int, std::size_t> counts;

    for (const auto& customer : customers) {
        ++counts[customer.customer_id];
    }

    return counts;
}

std::unordered_map<int, std::size_t> count_order_keys(
    const std::vector<Order>& orders
) {
    std::unordered_map<int, std::size_t> counts;

    for (const auto& order : orders) {
        ++counts[order.customer_id];
    }

    return counts;
}

/*
A uniqueness assertion converts an assumed data-model rule into executable
validation. This is important when downstream calculations require a 1:1
relationship.
*/
void validate_unique_customer_key(
    const std::vector<Customer>& customers
) {
    const auto counts = count_customer_keys(customers);

    for (const auto& [customer_id, count] : counts) {
        if (count > 1) {
            throw std::runtime_error(
                "customer_id=" + std::to_string(customer_id) +
                " violates expected uniqueness"
            );
        }
    }
}

/*
Exact inner-join result-size calculation for an equality join.

For every matching key:
    contribution = left_count * right_count

The overflow check matters when this calculation is used as a diagnostic for
very large datasets.
*/
std::size_t expected_join_size(
    const std::vector<Customer>& customers,
    const std::vector<Order>& orders
) {
    const auto customer_counts = count_customer_keys(customers);
    const auto order_counts = count_order_keys(orders);

    std::size_t total = 0;

    for (const auto& [customer_id, customer_count] : customer_counts) {
        auto found = order_counts.find(customer_id);

        if (found == order_counts.end()) {
            continue;
        }

        const std::size_t order_count = found->second;

        if (
            customer_count >
            std::numeric_limits<std::size_t>::max() / order_count
        ) {
            throw std::overflow_error(
                "Expected join-size calculation overflowed"
            );
        }

        const std::size_t contribution =
            customer_count * order_count;

        if (
            total >
            std::numeric_limits<std::size_t>::max() - contribution
        ) {
            throw std::overflow_error(
                "Expected join-size calculation overflowed"
            );
        }

        total += contribution;
    }

    return total;
}

void print_customer_list(
    const std::vector<Customer>& customers,
    const std::string& title
) {
    std::cout << "\n" << title << "\n";

    for (const auto& customer : customers) {
        std::cout
            << "  "
            << customer.customer_id
            << " | "
            << customer.name
            << " | "
            << customer.segment
            << "\n";
    }
}

void demonstrate_basic_case() {
    print_title("1. Customer-order inner join");

    const std::vector<Customer> customers{
        {1, "IN", "Asha", "retail"},
        {2, "IN", "Ravi", "business"},
        {3, "US", "John", "retail"},
        {4, "IN", "Meera", "retail"}
    };

    const std::vector<Order> orders{
        {"O1", 1, 100.00},
        {"O2", 1, 200.00},
        {"O3", 2, 500.00},
        {"O4", 2, 700.00},
        {"O5", 99, 50.00}
    };

    const auto nested_result =
        nested_loop_join(customers, orders);

    const auto hash_result =
        hash_join(customers, orders);

    print_customer_orders(
        nested_result,
        "Nested-loop join"
    );

    print_customer_orders(
        hash_result,
        "Hash join"
    );

    if (nested_result.size() != hash_result.size()) {
        throw std::runtime_error(
            "Join implementations disagree on result cardinality"
        );
    }

    std::cout
        << "\nBoth implementations produce "
        << hash_result.size()
        << " matching rows.\n";
}

void demonstrate_cardinality() {
    print_title("2. Cardinality and duplicate multiplication");

    const std::vector<Customer> customers{
        {1, "IN", "Asha", "retail"},
        {2, "IN", "Ravi", "business"}
    };

    const std::vector<Order> orders{
        {"O1", 1, 100.00},
        {"O2", 1, 200.00},
        {"O3", 1, 300.00},
        {"O4", 2, 500.00}
    };

    std::cout
        << "Customer relation: unique customer_id -> 1 side\n"
        << "Order relation: multiple orders per customer -> N side\n"
        << "Observed relationship: 1:N\n";

    const auto result = hash_join(customers, orders);

    print_customer_orders(result, "1:N result");

    std::cout
        << "\nRows for customer 1: 1 customer x 3 orders = 3 rows.\n";
}

void demonstrate_many_to_many() {
    print_title("3. Many-to-many multiplication");

    const std::vector<Customer> left{
        {7, "IN", "Account event 1", "event"},
        {7, "IN", "Account event 2", "event"},
        {7, "IN", "Account event 3", "event"}
    };

    const std::vector<Order> right{
        {"T1", 7, 10.00},
        {"T2", 7, 20.00}
    };

    const std::size_t expected =
        expected_join_size(left, right);

    std::cout
        << "Three left rows and two right rows share the same key.\n"
        << "Expected output: 3 * 2 = "
        << expected
        << " rows.\n";

    /*
    This multiplication is mathematically correct for the join. It may still
    be logically wrong for a business calculation if the analyst expected
    one row per account.
    */
}

void demonstrate_left_outer_join() {
    print_title("4. Left outer join");

    const std::vector<OptionalCustomer> customers{
        {1, "Asha"},
        {2, "Ravi"},
        {3, "Meera"},
        {99, "No Orders"}
    };

    const std::vector<Order> orders{
        {"O1", 1, 100.00},
        {"O2", 2, 200.00}
    };

    const auto result =
        left_outer_join(customers, orders);

    print_left_join(result);

    std::cout
        << "\nCustomer 99 survives because a left outer join preserves "
        << "every left-side row.\n";
}

void demonstrate_null_behavior() {
    print_title("5. NULL behavior");

    const std::optional<int> missing_a = std::nullopt;
    const std::optional<int> missing_b = std::nullopt;
    const std::optional<int> customer_id = 10;

    std::cout
        << "sql_equal(NULL, NULL): "
        << std::boolalpha
        << sql_equal(missing_a, missing_b)
        << "\n";

    std::cout
        << "null_safe_equal(NULL, NULL): "
        << null_safe_equal(missing_a, missing_b)
        << "\n";

    std::cout
        << "sql_equal(NULL, 10): "
        << sql_equal(missing_a, customer_id)
        << "\n";

    std::cout
        << "\nOrdinary equality joins therefore exclude rows whose "
        << "join key is NULL.\n";
}

void demonstrate_composite_key() {
    print_title("6. Composite join key");

    const std::vector<Shipment> shipments{
        {"IN", 10, "S1"},
        {"US", 10, "S2"},
        {"IN", 20, "S3"}
    };

    const std::vector<CompositeCustomer> customers{
        {"IN", 10, "Asha"},
        {"US", 10, "John"},
        {"IN", 20, "Ravi"}
    };

    const auto result =
        composite_hash_join(shipments, customers);

    std::cout
        << "country + customer_id is used as the logical key.\n\n";

    for (const auto& [shipment, customer] : result) {
        std::cout
            << shipment.shipment_id
            << " -> "
            << customer.name
            << " ("
            << customer.country
            << ", "
            << customer.customer_id
            << ")\n";
    }
}

void demonstrate_semi_and_anti_join() {
    print_title("7. Semi join and anti join");

    const std::vector<Customer> customers{
        {1, "IN", "Asha", "retail"},
        {2, "IN", "Ravi", "business"},
        {3, "IN", "Meera", "retail"}
    };

    const std::vector<Order> orders{
        {"O1", 1, 100.00},
        {"O2", 1, 200.00},
        {"O3", 1, 300.00},
        {"O4", 2, 500.00}
    };

    print_customer_list(
        semi_join(customers, orders),
        "Customers with at least one order"
    );

    print_customer_list(
        anti_join(customers, orders),
        "Customers with no order"
    );

    std::cout
        << "\nCustomer 1 appears once in the semi join despite having "
        << "three orders.\n";
}

void demonstrate_validation() {
    print_title("8. Data-quality validation");

    const std::vector<Customer> invalid_customers{
        {1, "IN", "Asha", "retail"},
        {2, "IN", "Ravi", "business"},
        {2, "IN", "Duplicate Ravi", "business"}
    };

    try {
        validate_unique_customer_key(invalid_customers);
        std::cout << "Validation unexpectedly passed.\n";
    } catch (const std::exception& error) {
        std::cout
            << "Validation failed correctly: "
            << error.what()
            << "\n";
    }

    std::cout
        << "\nUniqueness validation is useful when a downstream calculation "
        << "assumes a 1:1 relationship.\n";
}

void demonstrate_strategy_tradeoffs() {
    print_title("9. Join strategy trade-offs");

    std::cout
        << "Nested-loop join:\n"
        << "  Complexity: O(N*M)\n"
        << "  Memory: low additional memory\n"
        << "  Strength: simple and useful for small/selective inputs\n\n"

        << "Hash join:\n"
        << "  Expected complexity: O(N+M)\n"
        << "  Memory: O(build-side rows)\n"
        << "  Strength: efficient equality joins on large unsorted inputs\n\n"

        << "Sort-merge join:\n"
        << "  Typical cost: sorting plus linear merge\n"
        << "  Strength: useful when data is already sorted or ordered processing "
        << "has additional value\n\n"

        << "Indexed nested-loop join:\n"
        << "  Cost depends on lookup complexity and number of outer rows\n"
        << "  Strength: highly selective lookups can avoid scanning the entire "
        << "inner relation\n";
}

void demonstrate_production_scenario() {
    print_title("10. Production-style sales analytics");

    const std::vector<Customer> customers{
        {101, "IN", "Asha", "retail"},
        {102, "IN", "Bharat", "business"},
        {103, "IN", "Chen", "retail"}
    };

    const std::vector<Order> orders{
        {"O101", 101, 100.00},
        {"O102", 101, 250.00},
        {"O103", 102, 800.00},
        {"O104", 102, 700.00}
    };

    const auto joined =
        hash_join(customers, orders);

    std::unordered_map<std::string, double> revenue_by_segment;

    for (const auto& row : joined) {
        revenue_by_segment[row.customer.segment] +=
            row.order.amount;
    }

    print_customer_orders(
        joined,
        "Orders enriched with customer attributes"
    );

    std::cout << "\nRevenue by segment:\n";

    for (const auto& [segment, revenue] : revenue_by_segment) {
        std::cout
            << "  "
            << segment
            << ": "
            << std::fixed
            << std::setprecision(2)
            << revenue
            << "\n";
    }

    std::cout
        << "\nThe customer table is unique by customer_id, so each order "
        << "receives exactly one customer record.\n";
}

void demonstrate_diagnostics() {
    print_title("11. Join diagnostics");

    const std::vector<Customer> customers{
        {1, "IN", "Asha", "retail"},
        {2, "IN", "Ravi", "business"},
        {3, "IN", "Meera", "retail"}
    };

    const std::vector<Order> orders{
        {"O1", 1, 100.00},
        {"O2", 1, 200.00},
        {"O3", 2, 300.00},
        {"O4", 2, 400.00}
    };

    const std::size_t expected =
        expected_join_size(customers, orders);

    const auto actual =
        hash_join(customers, orders).size();

    std::cout
        << "Left rows:    " << customers.size() << "\n"
        << "Right rows:   " << orders.size() << "\n"
        << "Expected join rows: " << expected << "\n"
        << "Actual join rows:   " << actual << "\n";

    if (expected != actual) {
        throw std::runtime_error(
            "Join cardinality diagnostic failed"
        );
    }

    std::cout
        << "Cardinality diagnostic passed.\n";
}

int main() {
    try {
        std::cout
            << "JOIN STRATEGY CASE STUDY\n"
            << "Join keys, cardinality, duplicate rows, and NULL behavior\n";

        demonstrate_basic_case();
        demonstrate_cardinality();
        demonstrate_many_to_many();
        demonstrate_left_outer_join();
        demonstrate_null_behavior();
        demonstrate_composite_key();
        demonstrate_semi_and_anti_join();
        demonstrate_validation();
        demonstrate_strategy_tradeoffs();
        demonstrate_production_scenario();
        demonstrate_diagnostics();

        print_title("Key engineering rules");

        std::cout
            << "1. Define the intended grain of every relation before joining.\n"
            << "2. Confirm that join keys represent the same business entity.\n"
            << "3. Check uniqueness assumptions before relying on 1:1 behavior.\n"
            << "4. Preserve duplicate matches rather than silently overwriting them.\n"
            << "5. Treat NULL semantics explicitly.\n"
            << "6. Estimate expected output cardinality before expensive joins.\n"
            << "7. Use hash, merge, or indexed strategies according to workload.\n"
            << "8. Watch memory consumption when building hash indexes.\n"
            << "9. Treat accidental Cartesian products as a serious data-quality risk.\n"
            << "10. Validate row counts before using joined data in financial or KPI calculations.\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr
            << "\nFatal error: "
            << error.what()
            << "\n";

        return 1;
    }
}
