/*
 * SQL Joins I: INNER JOIN, LEFT JOIN, RIGHT JOIN
 *
 * C++17 case study:
 * A small order-management reporting engine.
 *
 * The program models customers and orders as separate relations and
 * implements SQL-style INNER, LEFT, and RIGHT JOIN operations over C++
 * containers.
 *
 * The purpose is to expose the underlying relational mechanics:
 * - matching keys
 * - preserved rows
 * - NULL-like unmatched values
 * - one-to-many relationships
 * - aggregation
 * - validation
 * - algorithmic complexity
 * - indexed equality joins
 * - modular application design
 *
 * Compile:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic sql_joins_1.cpp -o sql_joins_1
 *
 * Run:
 *   ./sql_joins_1
 */

#include <algorithm>
#include <cassert>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>


struct Customer {
    int customer_id;
    std::string customer_name;
    std::string city;
};


struct Order {
    int order_id;
    std::optional<int> customer_id;
    std::string product;
    double amount;
};


struct JoinedRow {
    const Customer* customer;
    const Order* order;
};


struct Department {
    int department_id;
    std::string department_name;
};


struct Employee {
    int employee_id;
    std::string employee_name;
    std::optional<int> department_id;
    double salary;
};


void printTitle(const std::string& title) {
    std::cout << "\n" << std::string(78, '=') << "\n";
    std::cout << title << "\n";
    std::cout << std::string(78, '=') << "\n";
}


void printCustomers(const std::vector<Customer>& customers) {
    std::cout << "\nCustomers\n";
    std::cout << std::left
              << std::setw(12) << "ID"
              << std::setw(22) << "Name"
              << std::setw(18) << "City"
              << "\n";

    std::cout << std::string(52, '-') << "\n";

    for (const auto& customer : customers) {
        std::cout << std::left
                  << std::setw(12) << customer.customer_id
                  << std::setw(22) << customer.customer_name
                  << std::setw(18) << customer.city
                  << "\n";
    }
}


void printOrders(const std::vector<Order>& orders) {
    std::cout << "\nOrders\n";
    std::cout << std::left
              << std::setw(12) << "Order ID"
              << std::setw(14) << "Customer ID"
              << std::setw(24) << "Product"
              << std::setw(12) << "Amount"
              << "\n";

    std::cout << std::string(62, '-') << "\n";

    for (const auto& order : orders) {
        std::cout << std::left
                  << std::setw(12) << order.order_id;

        if (order.customer_id.has_value()) {
            std::cout << std::setw(14) << *order.customer_id;
        } else {
            std::cout << std::setw(14) << "NULL";
        }

        std::cout << std::setw(24) << order.product
                  << std::fixed
                  << std::setprecision(2)
                  << std::setw(12) << order.amount
                  << "\n";
    }
}


void printJoinedRows(const std::vector<JoinedRow>& rows) {
    std::cout << "\nJoined result\n";
    std::cout << std::left
              << std::setw(22) << "Customer"
              << std::setw(12) << "Order ID"
              << std::setw(24) << "Product"
              << std::setw(12) << "Amount"
              << "\n";

    std::cout << std::string(70, '-') << "\n";

    for (const auto& row : rows) {
        if (row.customer != nullptr) {
            std::cout << std::left
                      << std::setw(22) << row.customer->customer_name;
        } else {
            std::cout << std::left
                      << std::setw(22) << "NULL";
        }

        if (row.order != nullptr) {
            std::cout << std::setw(12) << row.order->order_id
                      << std::setw(24) << row.order->product
                      << std::fixed
                      << std::setprecision(2)
                      << std::setw(12) << row.order->amount;
        } else {
            std::cout << std::setw(12) << "NULL"
                      << std::setw(24) << "NULL"
                      << std::setw(12) << "NULL";
        }

        std::cout << "\n";
    }
}


std::vector<JoinedRow> innerJoin(
    const std::vector<Customer>& customers,
    const std::vector<Order>& orders
) {
    /*
     * Nested-loop INNER JOIN.
     *
     * Every customer is compared with every order. A row pair is emitted
     * only when both customer IDs exist and are equal.
     *
     * Complexity:
     *   O(customers * orders)
     *
     * This is easy to understand but is not the preferred approach for
     * large equality joins when an index can be used.
     */
    std::vector<JoinedRow> result;

    for (const auto& customer : customers) {
        for (const auto& order : orders) {
            if (
                order.customer_id.has_value() &&
                *order.customer_id == customer.customer_id
            ) {
                result.push_back({&customer, &order});
            }
        }
    }

    return result;
}


std::vector<JoinedRow> leftJoin(
    const std::vector<Customer>& customers,
    const std::vector<Order>& orders
) {
    /*
     * LEFT JOIN preserves every customer.
     *
     * If a customer has multiple orders, each matching order creates one
     * output row. If no order matches, the order pointer remains nullptr.
     */
    std::vector<JoinedRow> result;

    for (const auto& customer : customers) {
        bool foundMatch = false;

        for (const auto& order : orders) {
            if (
                order.customer_id.has_value() &&
                *order.customer_id == customer.customer_id
            ) {
                foundMatch = true;
                result.push_back({&customer, &order});
            }
        }

        if (!foundMatch) {
            result.push_back({&customer, nullptr});
        }
    }

    return result;
}


std::vector<JoinedRow> rightJoin(
    const std::vector<Customer>& customers,
    const std::vector<Order>& orders
) {
    /*
     * RIGHT JOIN preserves every order.
     *
     * It is implemented directly here to make the preservation rule clear.
     * An equivalent SQL query can usually be written as a reversed LEFT
     * JOIN:
     *
     *   orders LEFT JOIN customers
     *
     * with the corresponding key condition.
     */
    std::vector<JoinedRow> result;

    for (const auto& order : orders) {
        bool foundMatch = false;

        if (order.customer_id.has_value()) {
            for (const auto& customer : customers) {
                if (*order.customer_id == customer.customer_id) {
                    foundMatch = true;
                    result.push_back({&customer, &order});
                }
            }
        }

        if (!foundMatch) {
            result.push_back({nullptr, &order});
        }
    }

    return result;
}


std::vector<JoinedRow> leftJoinExpensiveOrders(
    const std::vector<Customer>& customers,
    const std::vector<Order>& orders,
    double minimumAmount
) {
    /*
     * This models:
     *
     * LEFT JOIN orders
     *   ON customer_id = customer_id
     *  AND amount >= minimumAmount
     *
     * The customer remains even when no order satisfies the additional
     * predicate.
     */
    std::vector<JoinedRow> result;

    for (const auto& customer : customers) {
        bool foundMatch = false;

        for (const auto& order : orders) {
            if (
                order.customer_id.has_value() &&
                *order.customer_id == customer.customer_id &&
                order.amount >= minimumAmount
            ) {
                foundMatch = true;
                result.push_back({&customer, &order});
            }
        }

        if (!foundMatch) {
            result.push_back({&customer, nullptr});
        }
    }

    return result;
}


std::vector<JoinedRow> indexedInnerJoin(
    const std::vector<Customer>& customers,
    const std::vector<Order>& orders
) {
    /*
     * Build a hash index from customer_id to orders.
     *
     * Average complexity:
     *   O(customers + orders + output)
     *
     * Additional memory:
     *   O(orders)
     *
     * std::unordered_multimap is appropriate because multiple orders may
     * belong to one customer.
     */
    std::unordered_multimap<int, const Order*> orderIndex;

    for (const auto& order : orders) {
        if (order.customer_id.has_value()) {
            orderIndex.emplace(*order.customer_id, &order);
        }
    }

    std::vector<JoinedRow> result;

    for (const auto& customer : customers) {
        auto range = orderIndex.equal_range(customer.customer_id);

        for (auto iterator = range.first; iterator != range.second; ++iterator) {
            result.push_back({&customer, iterator->second});
        }
    }

    return result;
}


struct CustomerReport {
    std::string customer_name;
    int order_count;
    double total_spend;
};


std::vector<CustomerReport> buildCustomerReport(
    const std::vector<Customer>& customers,
    const std::vector<Order>& orders
) {
    /*
     * Reporting requirement:
     * every customer must appear, including customers with zero orders.
     *
     * A LEFT JOIN is the correct conceptual operation.
     */
    const auto joined = leftJoin(customers, orders);

    std::map<int, CustomerReport> reports;

    for (const auto& row : joined) {
        if (row.customer == nullptr) {
            continue;
        }

        auto [iterator, inserted] = reports.emplace(
            row.customer->customer_id,
            CustomerReport{
                row.customer->customer_name,
                0,
                0.0
            }
        );

        CustomerReport& report = iterator->second;

        if (row.order != nullptr) {
            report.order_count += 1;
            report.total_spend += row.order->amount;
        }

        (void)inserted;
    }

    std::vector<CustomerReport> output;

    for (const auto& [customerId, report] : reports) {
        (void)customerId;
        output.push_back(report);
    }

    std::sort(
        output.begin(),
        output.end(),
        [](const CustomerReport& first, const CustomerReport& second) {
            return first.total_spend > second.total_spend;
        }
    );

    return output;
}


void printCustomerReport(const std::vector<CustomerReport>& reports) {
    std::cout << "\nCustomer report\n";

    std::cout << std::left
              << std::setw(22) << "Customer"
              << std::setw(15) << "Orders"
              << std::setw(15) << "Total Spend"
              << "\n";

    std::cout << std::string(52, '-') << "\n";

    for (const auto& report : reports) {
        std::cout << std::left
                  << std::setw(22) << report.customer_name
                  << std::setw(15) << report.order_count
                  << std::fixed
                  << std::setprecision(2)
                  << std::setw(15) << report.total_spend
                  << "\n";
    }
}


void validateForeignKeyRelationships(
    const std::vector<Customer>& customers,
    const std::vector<Order>& orders
) {
    printTitle("Relationship validation");

    std::unordered_map<int, bool> customerIds;

    for (const auto& customer : customers) {
        customerIds[customer.customer_id] = true;
    }

    bool hasInvalidReference = false;

    for (const auto& order : orders) {
        if (
            order.customer_id.has_value() &&
            !customerIds.contains(*order.customer_id)
        ) {
            hasInvalidReference = true;

            std::cout
                << "Order " << order.order_id
                << " refers to customer "
                << *order.customer_id
                << ", which does not exist.\n";
        }
    }

    if (!hasInvalidReference) {
        std::cout << "No invalid non-NULL customer references found.\n";
    }

    std::cout
        << "In a relational database, a foreign-key constraint can enforce "
           "this relationship at the database level.\n";
}


void demonstrateDepartments() {
    printTitle("Multi-table case study extension");

    const std::vector<Department> departments{
        {10, "Engineering"},
        {20, "Finance"},
        {30, "Human Resources"},
        {40, "Security"}
    };

    const std::vector<Employee> employees{
        {1, "Anita", 10, 95000.0},
        {2, "Ravi", 10, 110000.0},
        {3, "Meera", 20, 90000.0},
        {4, "Karan", std::nullopt, 70000.0},
        {5, "Nisha", 30, 85000.0}
    };

    std::cout
        << "Department -> employees\n";

    for (const auto& department : departments) {
        bool found = false;

        for (const auto& employee : employees) {
            if (
                employee.department_id.has_value() &&
                *employee.department_id == department.department_id
            ) {
                found = true;

                std::cout
                    << "  "
                    << department.department_name
                    << " -> "
                    << employee.employee_name
                    << " ($"
                    << std::fixed
                    << std::setprecision(2)
                    << employee.salary
                    << ")\n";
            }
        }

        if (!found) {
            std::cout
                << "  "
                << department.department_name
                << " -> NULL\n";
        }
    }

    std::cout
        << "\nSecurity has no employees, but a LEFT JOIN-style traversal "
           "preserves the department.\n";
}


void runSemanticAssertions(
    const std::vector<Customer>& customers,
    const std::vector<Order>& orders
) {
    printTitle("Executable semantic tests");

    const auto inner = innerJoin(customers, orders);
    const auto left = leftJoin(customers, orders);
    const auto right = rightJoin(customers, orders);
    const auto indexed = indexedInnerJoin(customers, orders);

    assert(inner.size() == 4);
    assert(left.size() == 6);
    assert(right.size() == 5);
    assert(indexed.size() == inner.size());

    const auto unmatchedCustomers = std::count_if(
        left.begin(),
        left.end(),
        [](const JoinedRow& row) {
            return row.order == nullptr;
        }
    );

    assert(unmatchedCustomers == 2);

    const auto unassignedOrders = std::count_if(
        orders.begin(),
        orders.end(),
        [](const Order& order) {
            return !order.customer_id.has_value();
        }
    );

    assert(unassignedOrders == 1);

    std::cout << "INNER JOIN row-count assertion: PASSED\n";
    std::cout << "LEFT JOIN row-count assertion: PASSED\n";
    std::cout << "RIGHT JOIN row-count assertion: PASSED\n";
    std::cout << "Hash-indexed INNER JOIN assertion: PASSED\n";
    std::cout << "Unmatched customer assertion: PASSED\n";
    std::cout << "NULL customer reference assertion: PASSED\n";
}


void demonstratePerformance() {
    printTitle("Performance case study");

    /*
     * The dataset is large enough to demonstrate the difference in
     * algorithmic structure without creating an excessive demonstration
     * runtime.
     */
    std::vector<Customer> customers;
    std::vector<Order> orders;

    constexpr int customerCount = 2000;
    constexpr int orderCount = 10000;

    customers.reserve(customerCount);
    orders.reserve(orderCount);

    for (int id = 1; id <= customerCount; ++id) {
        customers.push_back({
            id,
            "Customer " + std::to_string(id),
            id % 2 == 0 ? "Delhi" : "Lucknow"
        });
    }

    for (int id = 1; id <= orderCount; ++id) {
        const int customerId = (id % customerCount) + 1;

        orders.push_back({
            id,
            customerId,
            "Product " + std::to_string(id % 20),
            static_cast<double>((id % 100) * 100 + 100)
        });
    }

    const auto startNested = std::chrono::steady_clock::now();

    const auto nestedResult = innerJoin(customers, orders);

    const auto endNested = std::chrono::steady_clock::now();

    const auto startIndexed = std::chrono::steady_clock::now();

    const auto indexedResult = indexedInnerJoin(customers, orders);

    const auto endIndexed = std::chrono::steady_clock::now();

    const auto nestedMilliseconds =
        std::chrono::duration_cast<std::chrono::milliseconds>(
            endNested - startNested
        ).count();

    const auto indexedMilliseconds =
        std::chrono::duration_cast<std::chrono::milliseconds>(
            endIndexed - startIndexed
        ).count();

    std::cout
        << "Nested-loop output rows: "
        << nestedResult.size()
        << "\n";

    std::cout
        << "Indexed output rows: "
        << indexedResult.size()
        << "\n";

    std::cout
        << "Nested-loop elapsed milliseconds: "
        << nestedMilliseconds
        << "\n";

    std::cout
        << "Indexed elapsed milliseconds: "
        << indexedMilliseconds
        << "\n";

    assert(nestedResult.size() == indexedResult.size());

    std::cout
        << "\nThe nested-loop algorithm performs roughly "
           "customers * orders comparisons.\n";

    std::cout
        << "The indexed implementation builds a hash-based lookup and "
           "then probes it for each customer.\n";

    std::cout
        << "Actual database engines may select nested-loop, hash, merge, "
           "or other execution strategies based on statistics and indexes.\n";
}


int main() {
    printTitle("SQL Joins I: INNER JOIN, LEFT JOIN, RIGHT JOIN");

    std::cout
        << "Case study: order-management reporting\n\n"
        << "The system stores customers and orders separately.\n"
        << "customer_id is the relationship key.\n"
        << "The reporting layer must answer both matching and preservation "
           "questions.\n";

    const std::vector<Customer> customers{
        {1, "Asha", "Lucknow"},
        {2, "Bharat", "Delhi"},
        {3, "Chitra", "Mumbai"},
        {4, "Dev", "Pune"},
        {5, "Esha", "Jaipur"}
    };

    const std::vector<Order> orders{
        {101, 1, "Laptop", 75000.0},
        {102, 1, "Mouse", 1500.0},
        {103, 2, "Monitor", 18000.0},
        {104, 3, "Keyboard", 3500.0},
        {105, std::nullopt, "Unassigned Device", 9000.0}
    };

    printCustomers(customers);
    printOrders(orders);

    printTitle("INNER JOIN");

    const auto inner = innerJoin(customers, orders);
    printJoinedRows(inner);

    std::cout
        << "\nOnly customer/order pairs satisfying the relationship key "
           "are returned.\n";

    printTitle("LEFT JOIN");

    const auto left = leftJoin(customers, orders);
    printJoinedRows(left);

    std::cout
        << "\nEvery customer is preserved. Unmatched orders are represented "
           "by nullptr, which plays the role of SQL NULL in this C++ model.\n";

    printTitle("RIGHT JOIN");

    const auto right = rightJoin(customers, orders);
    printJoinedRows(right);

    std::cout
        << "\nEvery order is preserved. The unassigned order has no matching "
           "customer.\n";

    printTitle("LEFT JOIN with an ON-style condition");

    const auto expensive = leftJoinExpensiveOrders(
        customers,
        orders,
        5000.0
    );

    printJoinedRows(expensive);

    std::cout
        << "\nCustomers remain preserved even when they have no order "
           "meeting the amount condition.\n";

    printTitle("Customer analytics report");

    const auto report = buildCustomerReport(customers, orders);
    printCustomerReport(report);

    validateForeignKeyRelationships(customers, orders);

    demonstrateDepartments();

    printTitle("Join semantics and NULL");

    std::cout
        << "INNER JOIN: preserve only matching pairs.\n"
        << "LEFT JOIN: preserve every left-side row.\n"
        << "RIGHT JOIN: preserve every right-side row.\n"
        << "NULL does not equal an ordinary key value.\n"
        << "One-to-many relationships multiply output rows.\n";

    runSemanticAssertions(customers, orders);

    demonstratePerformance();

    printTitle("Architecture and implementation trade-offs");

    std::cout
        << R"(
A production application should normally delegate SQL JOIN execution to a
relational database rather than implementing joins manually in application
code.

A database can:
- use indexes;
- maintain statistics;
- choose an execution plan;
- process data close to storage;
- enforce foreign-key constraints;
- optimize joins and filters;
- manage transactions and concurrency.

Manual C++ joins are useful for understanding relational mechanics, processing
already-loaded data, implementing specialized in-memory operations, and
studying algorithms.

Memory safety also matters. This case study stores pointers into vectors. The
pointers remain valid because the vectors are not modified after the join
operations begin. If a vector were reallocated, previously stored pointers
could become invalid. Production code must therefore consider object
lifetimes carefully.

For security, user-controlled values should not be concatenated into SQL
strings. Parameterized database APIs should be used when C++ communicates
with a real database.

The key design decision in a reporting system is not simply which JOIN syntax
to write. It is deciding which entities must be preserved, which relationship
defines a valid match, how NULL should be handled, and what cardinality the
result is expected to have.
)";

    printTitle("Completed");

    std::cout
        << "All C++ SQL JOIN case-study demonstrations completed successfully.\n";

    return 0;
}
